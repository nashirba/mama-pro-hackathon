from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.catalog.models import SpecialistProfile

from .models import Favorite


def _safe_next(request) -> str:
    candidate = request.POST.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return ""


@require_POST
@login_required
def toggle(request, slug):
    profile = get_object_or_404(SpecialistProfile, slug=slug)
    favorite, created = Favorite.objects.get_or_create(
        user=request.user, profile=profile
    )
    if not created:
        favorite.delete()
    next_url = _safe_next(request)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "favorites/_button.html",
            {"profile": profile, "active": created, "next": next_url},
        )
    if next_url:
        return redirect(next_url)
    name = "catalog:nanny" if profile.is_nanny else "catalog:specialist"
    return redirect(reverse(name, args=[profile.slug]))
