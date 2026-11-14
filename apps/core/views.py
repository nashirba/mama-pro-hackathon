from django.conf import settings
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.i18n import set_language as django_set_language

from apps.catalog.models import ProfileCategory, SpecialistType
from apps.core.i18n import first_translated
from apps.geo.models import KatoNode
from apps.search.models import SearchOffer


def healthz(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "db": "ok"})


POPULAR_TYPES_LIMIT = 8


def robots_txt(request) -> HttpResponse:
    # The demo is not indexed.
    return HttpResponse("User-agent: *\nDisallow: /\n", content_type="text/plain")


def _popular_types() -> list[SpecialistType]:
    """Types by the number of distinct specialists in the search index (the same rows the results show), zero counts dropped."""
    specialists: dict[int, set[int]] = {}
    offers = SearchOffer.objects.filter(category=ProfileCategory.SPECIALIST)
    for specialist_id, type_ids in offers.values_list("specialist_id", "specialist_type_ids"):
        for type_id in type_ids:
            specialists.setdefault(type_id, set()).add(specialist_id)
    types = SpecialistType.objects.filter(pk__in=specialists).prefetch_related("translations")
    for t in types:
        t.specialists_count = len(specialists[t.pk])
    return sorted(types, key=lambda t: (-t.specialists_count, t.slug))[:POPULAR_TYPES_LIMIT]


def _nannies_count() -> int:
    """Nannies in the search index, so only the ones the nanny section shows."""
    return SearchOffer.objects.filter(category=ProfileCategory.NANNY).values("specialist_id").distinct().count()


def home(request):
    popular_types = _popular_types()
    cities = sorted(
        KatoNode.objects.filter(level=KatoNode.Level.CITY).prefetch_related("translations"),
        key=lambda node: first_translated(node, "name"),
    )
    return render(
        request, "core/home.html", {"popular_types": popular_types, "cities": cities, "nannies_count": _nannies_count()}
    )


def set_language(request) -> HttpResponse:
    response = django_set_language(request)
    user = request.user
    lang = request.POST.get("language")
    if user.is_authenticated and lang in dict(settings.LANGUAGES) and lang != user.preferred_language:
        user.preferred_language = lang
        user.save(update_fields=["preferred_language"])
    return response
