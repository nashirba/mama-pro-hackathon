from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.search.geojson import specialist_feature_collection

from .models import ProfileCategory, Service, SpecialistProfile
from .visibility import is_catalog_visible, nanny_eligible

PROFILE_PREFETCH = (
    "translations",
    "conditions__translations",
    "languages__translations",
    "contexts",
)


def _load_profile(slug: str, category: str, prefetch: tuple[str, ...]) -> tuple[SpecialistProfile, list[Service]]:
    """The profile of the category with its catalog-visible services; 404 when it is hidden or of the other category."""
    profile = get_object_or_404(
        SpecialistProfile.objects.filter(category=category).prefetch_related(*PROFILE_PREFETCH, *prefetch), slug=slug
    )
    contexts = [c for c in profile.contexts.all() if is_catalog_visible(c)]
    if not contexts:
        raise Http404
    services = list(
        Service.objects.filter(context__in=contexts)
        .select_related("kind", "home_visit_area__parent")
        .prefetch_related(
            "translations",
            "kind__translations",
            "addresses__kato__translations",
            "home_visit_area__translations",
            "home_visit_area__parent__translations",
        )
        .order_by("pk")
    )
    return profile, services


def specialist_detail(request, slug):
    profile, services = _load_profile(
        slug, ProfileCategory.SPECIALIST, ("specialist_types__translations", "methods__translations")
    )
    addresses = {}
    for service in services:
        for address in service.addresses.all():
            addresses.setdefault(address.pk, address)
    prices = [0 if s.is_free else s.price_session for s in services if s.is_free or s.price_session is not None]
    return render(
        request,
        "catalog/specialist_detail.html",
        {
            "price_from": min(prices) if prices else None,
            "profile": profile,
            "services": services,
            "addresses": list(addresses.values()),
            "geojson": specialist_feature_collection(profile),
        },
    )


def _lowest(services: list[Service], field: str) -> int | None:
    values = [getattr(s, field) for s in services if getattr(s, field) is not None]
    return min(values) if values else None


def nanny_detail(request, slug):
    profile, services = _load_profile(slug, ProfileCategory.NANNY, ("trainings__translations",))
    if not nanny_eligible(profile):
        raise Http404
    areas = {}
    for service in services:
        if service.home_visit_area is not None:
            areas.setdefault(service.home_visit_area.pk, service.home_visit_area)
    return render(
        request,
        "catalog/nanny_detail.html",
        {
            "profile": profile,
            "services": services,
            "trainings": list(profile.trainings.all()),
            "areas": list(areas.values()),
            "price_hour": _lowest(services, "price_hour"),
            "price_night": _lowest(services, "price_night"),
            "price_month": _lowest(services, "price_month"),
        },
    )
