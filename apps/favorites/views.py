from urllib.parse import urlsplit

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.db.models import prefetch_related_objects
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.catalog.models import SpecialistProfile
from apps.search.query import cards_for_profiles

from .models import Favorite


def _safe_next(request) -> str:
    candidate = request.POST.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return ""


def _profile_url(profile: SpecialistProfile) -> str:
    name = "catalog:nanny" if profile.is_nanny else "catalog:specialist"
    return reverse(name, args=[profile.slug])


def _login_for_htmx(request, profile: SpecialistProfile) -> HttpResponse:
    """An expired session: send the whole page to login instead of swapping the login page into the card."""
    current = request.headers.get("HX-Current-URL", "")
    if current and url_has_allowed_host_and_scheme(current, allowed_hosts={request.get_host()}):
        parts = urlsplit(current)
        back = parts.path + (f"?{parts.query}" if parts.query else "")
    else:
        back = _profile_url(profile)
    response = HttpResponse(status=204)
    response["HX-Redirect"] = redirect_to_login(back).url
    return response


@require_POST
def toggle(request, slug):
    profile = get_object_or_404(SpecialistProfile, slug=slug)
    if not request.user.is_authenticated:
        if request.headers.get("HX-Request"):
            return _login_for_htmx(request, profile)
        return redirect_to_login(request.get_full_path())
    favorite = Favorite.objects.filter(user=request.user, profile=profile).first()
    if favorite:
        favorite.delete()
        created = False
    else:
        # Adding is allowed only for catalog-visible profiles: search_offers exists only for them.
        if not profile.search_offers.exists():
            raise Http404
        Favorite.objects.get_or_create(user=request.user, profile=profile)
        created = True
    next_url = _safe_next(request)
    if request.headers.get("HX-Request"):
        return render(
            request,
            "favorites/_button.html",
            {"profile": profile, "active": created, "next": next_url},
        )
    if next_url:
        return redirect(next_url)
    return redirect(_profile_url(profile))


@login_required
def favorite_list(request):
    favorites = request.user.favorites.select_related("profile").prefetch_related("profile__translations")
    profiles = [f.profile for f in favorites]
    specialists = [p for p in profiles if not p.is_nanny]
    nannies = [p for p in profiles if p.is_nanny]
    prefetch_related_objects(specialists, "specialist_types__translations", "languages__translations")
    prefetch_related_objects(nannies, "trainings", "conditions__translations", "languages__translations")
    return render(
        request,
        "favorites/list.html",
        {"specialist_cards": cards_for_profiles(specialists), "nanny_cards": cards_for_profiles(nannies)},
    )
