from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import prefetch_related_objects
from django.http import Http404, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.utils.translation import get_language, override, pgettext

from apps.catalog.models import DevelopmentalCondition, SpecialistType
from apps.geo.models import KatoNode

from .forms import AGE_GROUPS, build_filter_choices
from .geojson import feature_collection, map_config, map_offers
from .query import SearchParams, search, search_offers_queryset
from .suggest import suggest as suggest_items


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _own_translation(obj, field: str, lang: str) -> str:
    """The value in `lang` only: no fallback to another language."""
    if not obj.has_translation(lang):
        return ""
    return obj.safe_translation_getter(field, language_code=lang, default="") or ""


def landing_title(city: KatoNode, node, lang: str) -> str:
    """Built in the active language when both the node and the city have their own text in it, otherwise entirely in RU.

    Reference values are stored in the case they take inside the title, so nothing is lowercased here;
    the word order is a gettext message of the chosen language.
    """
    if not (_own_translation(node, "landing_name", lang) and _own_translation(city, "name_locative", lang)):
        lang = "ru"
    name = _own_translation(node, "landing_name", lang) or node.safe_translation_getter("landing_name", any_language=True)
    locative = _own_translation(city, "name_locative", lang)
    with override(lang):
        if not locative:
            city_name = _own_translation(city, "name", lang) or city.safe_translation_getter("name", any_language=True)
            return pgettext("landing title without locative", "%(name)s: %(city)s") % {"name": name, "city": city_name}
        return pgettext("landing title", "%(name)s %(locative)s") % {"name": name, "locative": locative}


def _query_string(qd: QueryDict, **overrides) -> str:
    """Query string without `page` and without empty values."""
    clean = QueryDict(mutable=True)
    for key, values in qd.lists():
        kept = [v for v in values if v != ""]
        if key != "page" and kept:
            clean.setlist(key, kept)
    for key, value in overrides.items():
        clean.setlist(key, value if isinstance(value, list) else [value])
    return clean.urlencode()


def _url(path: str, query: str) -> str:
    return f"{path}?{query}" if query else path


def _search_params(qd: QueryDict) -> SearchParams:
    """The district, when given, overrides the city for the search."""
    search_qd = qd.copy()
    district_id = _int_or_none(qd.get("district_id"))
    if district_id is not None:
        search_qd["kato_id"] = str(district_id)
    return SearchParams.from_querydict(search_qd)


def _active_filter_count(params: SearchParams) -> int:
    """Selected filters for the badge of the "Filters" button: every checked value, and one per range or scalar."""
    lists = (
        params.specialist_type_ids,
        params.condition_ids,
        params.formats,
        params.language_codes,
        params.verification_levels,
        params.method_ids,
    )
    flags = (
        params.kato_id is not None,
        params.child_age_min is not None or params.child_age_max is not None,
        params.price_min is not None or params.price_max is not None,
        params.price_month_min is not None or params.price_month_max is not None,
        params.free_only,
        params.experience_min is not None,
        params.near is not None,
    )
    return sum(len(values) for values in lists) + sum(flags)


def _render_results(request, qd: QueryDict, heading: str | None = None, extra: dict | None = None):
    """`qd` is the filter state shown in the form."""
    district_id = _int_or_none(qd.get("district_id"))
    params = _search_params(qd)
    result = search(params)
    prefetch_related_objects(
        [c.specialist for c in result.cards], "specialist_types__translations", "languages__translations"
    )

    results_path = reverse("search:results")
    age_groups = [
        {
            "min": lo,
            "max": hi,
            "url": _url(results_path, _query_string(qd, child_age_min=str(lo), child_age_max=str(hi))),
            "current": params.child_age_min == lo and params.child_age_max == hi,
        }
        for lo, hi in AGE_GROUPS
    ]
    formats = qd.getlist("formats")
    online_url = None if "online" in formats else _url(results_path, _query_string(qd, formats=[*formats, "online"]))
    page_query = _query_string(qd)
    sep = "&" if page_query else ""

    context = {
        "heading": heading,
        "params": params,
        "result": result,
        "choices": build_filter_choices(),
        "selected_kato": _int_or_none(qd.get("kato_id")),
        "selected_district": district_id,
        "near_value": params.to_querydict().get("near", ""),
        "age_groups": age_groups,
        "map_config": map_config(params.kato_id, page_query),
        "active_filter_count": _active_filter_count(params),
        "reset_url": results_path,
        "online_url": online_url,
        "prev_url": f"{request.path}?{page_query}{sep}page={result.page - 1}" if result.page > 1 else None,
        "next_url": f"{request.path}?{page_query}{sep}page={result.page + 1}" if result.page < result.pages else None,
        **(extra or {}),
    }
    # htmx refetches a page on a history cache miss with HX-Request too and swaps the response into <body>
    partial = bool(request.headers.get("HX-Request")) and not request.headers.get("HX-History-Restore-Request")
    context["partial"] = partial
    response = render(request, "search/_results_partial.html" if partial else "search/results.html", context)
    patch_vary_headers(response, ["HX-Request"])
    return response


def map_geojson(request):
    """The markers of the same filters as the results page; the limit counts markers, not offers."""
    offers = map_offers(search_offers_queryset(_search_params(request.GET)))
    return JsonResponse(feature_collection(offers.iterator(), settings.GEOJSON_MAX_FEATURES))


def results(request):
    return _render_results(request, request.GET)


def landing(request, city_slug, slug):
    city = get_object_or_404(KatoNode.objects.filter(level__in=[KatoNode.Level.CITY, KatoNode.Level.REGION]), slug=city_slug)
    qd = request.GET.copy()
    qd["kato_id"] = str(city.pk)
    try:
        node = SpecialistType.objects.get(slug=slug)
        qd.setlist("specialist_type_ids", [str(node.pk)])
    except ObjectDoesNotExist:
        try:
            node = DevelopmentalCondition.objects.get(slug=slug)
        except ObjectDoesNotExist:
            raise Http404 from None
        qd.setlist("condition_ids", [str(node.pk)])
    return _render_results(request, qd, heading=landing_title(city, node, get_language()))


def suggest(request):
    """The `<ul>` under the search box. Always a fragment: it has no full-page variant, so no HX-Request check."""
    suggestions = suggest_items(request.GET.get("q", ""), get_language(), kato_id=_int_or_none(request.GET.get("kato_id")))
    return render(request, "search/_suggest.html", {"suggestions": suggestions})
