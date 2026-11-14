from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import prefetch_related_objects
from django.http import Http404, JsonResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.utils.translation import get_language, override, pgettext
from django.utils.translation import gettext as _

from apps.catalog.models import DevelopmentalCondition, SpecialistType
from apps.core.city import selected_city
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


NANNIES_SLUG = "nannies"  # `/<city>/nannies/` opens the nanny section of the city


def nannies_landing_title(city: KatoNode, lang: str) -> str:
    """Like `landing_title`: in the active language when the city has its own locative in it, otherwise entirely in RU."""
    if not _own_translation(city, "name_locative", lang):
        lang = "ru"
    locative = _own_translation(city, "name_locative", lang)
    with override(lang):
        if not locative:
            city_name = _own_translation(city, "name", lang) or city.safe_translation_getter("name", any_language=True)
            return pgettext("nannies landing title without locative", "Обученные няни: %(city)s") % {"city": city_name}
        return pgettext("nannies landing title", "Обученные няни %(locative)s") % {"locative": locative}


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


def _search_params(qd: QueryDict, section: str = "specialists") -> SearchParams:
    """The district, when given, overrides the city for the search."""
    search_qd = qd.copy()
    district_id = _int_or_none(qd.get("district_id"))
    if district_id is not None:
        search_qd["kato_id"] = str(district_id)
    return SearchParams.from_querydict(search_qd, section=section)


def _active_filter_count(params: SearchParams) -> int:
    """Selected filters for the badge of the "Filters" button: every checked value, and one per range or scalar."""
    lists = (
        params.specialist_type_ids,
        params.condition_ids,
        params.formats,
        params.language_codes,
        params.method_ids,
        params.pay_units,
    )
    flags = (
        params.kato_id is not None,
        params.child_age_min is not None or params.child_age_max is not None,
        params.price_min is not None or params.price_max is not None,
        params.price_month_min is not None or params.price_month_max is not None,
        params.price_hour_min is not None or params.price_hour_max is not None,
        params.free_only,
        params.experience_min is not None,
        params.near is not None,
    )
    return sum(len(values) for values in lists) + sum(flags)


def _active_chips(qd: QueryDict, params: SearchParams, choices, results_path: str) -> list[dict]:
    """Removable chips for the selected filters: a label and the URL of the same search without that one value."""

    def without(keys=(), **drop):
        clean = QueryDict(mutable=True)
        for key, values in qd.lists():
            kept = [v for v in values if v != "" and key not in keys]
            if key in drop:
                kept = [v for v in kept if v != drop[key]]
            if key != "page" and kept:
                clean.setlist(key, kept)
        return _url(results_path, clean.urlencode())

    chips: list[dict] = []

    def add(label, url):
        chips.append({"label": label, "url": url})

    def num(value):
        return floatformat(value, "0g")

    def rng(lo, hi, both, only_lo, only_hi):
        if lo is not None and hi is not None:
            return both % {"lo": num(lo), "hi": num(hi)}
        if lo is not None:
            return only_lo % {"lo": num(lo)}
        return only_hi % {"hi": num(hi)}

    if params.q:
        add(f"«{params.q}»", without(["q"]))
    nodes = {n.pk: n for n in choices.cities}
    for _parent, districts in choices.district_groups:
        nodes.update({n.pk: n for n in districts})
    district_id = _int_or_none(qd.get("district_id"))
    kato_id = _int_or_none(qd.get("kato_id"))
    if district_id in nodes:
        add(_name_of(nodes[district_id]), without(["district_id"]))
    if kato_id in nodes:
        add(_name_of(nodes[kato_id]), without(["kato_id", "district_id"]))
    by_key = (
        ("specialist_type_ids", params.specialist_type_ids, {o.pk: o for o in choices.specialist_types}),
        ("condition_ids", params.condition_ids, {c.pk: c for c, _depth in choices.conditions}),
        ("method_ids", params.method_ids, {m.pk: m for m in choices.methods}),
    )
    for key, selected, objs in by_key:
        for value in selected:
            if value in objs:
                add(_name_of(objs[value]), without(**{key: str(value)}))
    for key, selected, labels in (
        ("formats", params.formats, dict(choices.formats)),
        ("language_codes", params.language_codes, {lang.code: _name_of(lang) for lang in choices.languages}),
        ("pay_units", params.pay_units, dict(choices.pay_units)),
    ):
        for value in selected:
            if value in labels:
                add(str(labels[value]), without(**{key: value}))
    if params.child_age_min is not None or params.child_age_max is not None:
        add(
            rng(
                params.child_age_min,
                params.child_age_max,
                _("Возраст: %(lo)s–%(hi)s лет"),
                _("Возраст: от %(lo)s лет"),
                _("Возраст: до %(hi)s лет"),
            ),
            without(["child_age_min", "child_age_max"]),
        )
    if params.price_min is not None or params.price_max is not None:
        add(
            rng(
                params.price_min,
                params.price_max,
                _("Цена за занятие: %(lo)s–%(hi)s ₸"),
                _("Цена за занятие: от %(lo)s ₸"),
                _("Цена за занятие: до %(hi)s ₸"),
            ),
            without(["price_min", "price_max"]),
        )
    if params.price_month_min is not None or params.price_month_max is not None:
        add(
            rng(
                params.price_month_min,
                params.price_month_max,
                _("Цена в месяц: %(lo)s–%(hi)s ₸"),
                _("Цена в месяц: от %(lo)s ₸"),
                _("Цена в месяц: до %(hi)s ₸"),
            ),
            without(["price_month_min", "price_month_max"]),
        )
    if params.price_hour_min is not None or params.price_hour_max is not None:
        add(
            rng(
                params.price_hour_min,
                params.price_hour_max,
                _("Цена за час: %(lo)s–%(hi)s ₸"),
                _("Цена за час: от %(lo)s ₸"),
                _("Цена за час: до %(hi)s ₸"),
            ),
            without(["price_hour_min", "price_hour_max"]),
        )
    if params.free_only:
        add(_("Только бесплатные"), without(["free_only"]))
    if params.experience_min is not None:
        label = _("Опыт от, лет") if params.section == "nannies" else _("Стаж от, лет")
        add(f"{label}: {params.experience_min}", without(["experience_min"]))
    if params.near is not None:
        add(_("Рядом со мной"), without(["near"] + (["sort"] if qd.get("sort") == "distance" else [])))
    return chips


def _name_of(obj) -> str:
    return obj.safe_translation_getter("name", any_language=True) or ""


def _render_results(
    request, qd: QueryDict, heading: str | None = None, extra: dict | None = None, section: str = "specialists"
):
    """`qd` is the filter state shown in the form; `section` is "specialists" or "nannies"."""
    is_nannies = section == "nannies"
    district_id = _int_or_none(qd.get("district_id"))
    params = _search_params(qd, section)
    result = search(params)
    choices = build_filter_choices(section)
    profiles = [c.specialist for c in result.cards]
    if is_nannies:
        prefetch_related_objects(profiles, "trainings", "conditions__translations", "languages__translations")
    else:
        prefetch_related_objects(profiles, "specialist_types__translations", "languages__translations")

    results_path = reverse("search:nannies" if is_nannies else "search:results")
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
    online_url = (
        None
        if is_nannies or "online" in formats or params.kato_id is None
        else _url(results_path, _query_string(qd, formats=[*formats, "online"]))
    )
    page_query = _query_string(qd)
    sep = "&" if page_query else ""

    context = {
        "section": section,
        "is_nannies": is_nannies,
        "default_heading": _("Обученные няни") if is_nannies else _("Каталог специалистов"),
        "results_path": results_path,
        "heading": heading,
        "params": params,
        "result": result,
        "choices": choices,
        "active_chips": _active_chips(qd, params, choices, results_path),
        "selected_kato": _int_or_none(qd.get("kato_id")),
        "selected_district": district_id,
        "near_value": params.to_querydict().get("near", ""),
        "age_groups": age_groups,
        "map_config": None if is_nannies else map_config(params.kato_id, page_query),  # a nanny comes to the family
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


def _redirect_to_selected_city(request):
    """A bare catalog URL (no filters, not HTMX) opens in the city chosen in the header."""
    if request.headers.get("HX-Request") or not set(request.GET) <= {"focus"}:
        return None
    city = selected_city(request)
    if city is None:
        return None
    query = QueryDict(mutable=True)
    query["kato_id"] = str(city.pk)
    if "focus" in request.GET:
        query["focus"] = request.GET["focus"]
    return redirect(_url(request.path, query.urlencode()))


def results(request):
    return _redirect_to_selected_city(request) or _render_results(request, request.GET)


def nannies(request):
    return _redirect_to_selected_city(request) or _render_results(request, request.GET, section="nannies")


def landing(request, city_slug, slug):
    city = get_object_or_404(KatoNode.objects.filter(level__in=[KatoNode.Level.CITY, KatoNode.Level.REGION]), slug=city_slug)
    qd = request.GET.copy()
    qd["kato_id"] = str(city.pk)
    if slug == NANNIES_SLUG:
        return _render_results(request, qd, heading=nannies_landing_title(city, get_language()), section="nannies")
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
