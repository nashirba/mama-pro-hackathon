from django.conf import settings
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST
from django.views.i18n import set_language as django_set_language

from apps.catalog.models import ProfileCategory, SpecialistType
from apps.community.query import latest_posts
from apps.core.city import COOKIE, cities
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
    return render(
        request,
        "core/home.html",
        {
            "popular_types": popular_types,
            "cities": cities(),
            "nannies_count": _nannies_count(),
            "recent_posts": latest_posts(request.user),
        },
    )


CITY_COOKIE_MAX_AGE = 365 * 24 * 60 * 60


@require_POST
def set_city(request) -> HttpResponse:
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = ""
    response = redirect(next_url or "core:home")
    kato_id = request.POST.get("kato_id", "")
    if kato_id.isdecimal() and any(str(c.pk) == kato_id for c in cities()):
        response.set_cookie(COOKIE, kato_id, max_age=CITY_COOKIE_MAX_AGE, samesite="Lax", path="/")
    else:
        response.delete_cookie(COOKIE, path="/", samesite="Lax")
    return response


def set_language(request) -> HttpResponse:
    response = django_set_language(request)
    user = request.user
    lang = request.POST.get("language")
    if user.is_authenticated and lang in dict(settings.LANGUAGES) and lang != user.preferred_language:
        user.preferred_language = lang
        user.save(update_fields=["preferred_language"])
    return response


# Mama Pro foundation pages; the content lives there, this page links to it.
MAMAPRO_ANNOUNCEMENTS_URL = "https://project2418305.tilda.ws/page40285738.html#!/tab/651857742-2"
MAMAPRO_COURSES_URL = "https://mamapro.kz/#rec199050404"
MAMAPRO_DONATE_URL = "https://kaspi.kz/pay/mamapro"
MAMAPRO_BRANCHES = [  # (city, Instagram); the foundation publishes no street addresses
    (gettext_lazy("Астана"), "https://instagram.com/mamapro_org"),
    (gettext_lazy("Алматы"), "https://instagram.com/mamapro_almaty"),
    (gettext_lazy("Усть-Каменогорск"), "https://instagram.com/mamapro_oskemen"),
    (gettext_lazy("Шымкент"), "https://instagram.com/mamapro_shymkent"),
    (gettext_lazy("Костанай"), "https://instagram.com/mamapro_kst"),
]


def mamapro(request):
    return render(
        request,
        "core/mamapro.html",
        {
            "announcements_url": MAMAPRO_ANNOUNCEMENTS_URL,
            "courses_url": MAMAPRO_COURSES_URL,
            "donate_url": MAMAPRO_DONATE_URL,
            "branches": MAMAPRO_BRANCHES,
        },
    )
