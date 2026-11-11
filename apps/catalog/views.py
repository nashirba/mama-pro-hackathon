from django.http import Http404
from django.shortcuts import get_object_or_404, render

from apps.search.geojson import specialist_feature_collection

from .models import Service, SpecialistProfile
from .visibility import is_catalog_visible


def specialist_detail(request, slug):
    profile = get_object_or_404(
        SpecialistProfile.objects.prefetch_related(
            "translations",
            "specialist_types__translations",
            "conditions__translations",
            "methods__translations",
            "languages__translations",
            "contexts",
        ),
        slug=slug,
    )
    contexts = [c for c in profile.contexts.all() if is_catalog_visible(c)]
    if not contexts:
        raise Http404
    services = list(
        Service.objects.filter(context__in=contexts)
        .select_related("kind", "home_visit_area")
        .prefetch_related(
            "translations", "kind__translations", "addresses__kato__translations", "home_visit_area__translations"
        )
        .order_by("pk")
    )
    addresses = {}
    for service in services:
        for address in service.addresses.all():
            addresses.setdefault(address.pk, address)
    return render(
        request,
        "catalog/specialist_detail.html",
        {
            "profile": profile,
            "services": services,
            "addresses": list(addresses.values()),
            "geojson": specialist_feature_collection(profile),
        },
    )
