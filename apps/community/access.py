"""The single gate for every community write action: sign-in, then (optionally) a nickname."""

from functools import wraps
from urllib.parse import urlencode, urlparse

from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .names import needs_nickname


def is_safe_url(request, candidate: str) -> bool:
    return bool(candidate) and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    )


def _hx_current_path(request) -> str:
    parsed = urlparse(request.headers.get("HX-Current-URL", ""))
    if not parsed.path:
        return ""
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


def return_url(request, kwargs: dict) -> str:
    """Where to come back to after sign-in or nickname: the page the user was on, never the write endpoint."""
    if request.method == "GET":
        return request.get_full_path()
    for candidate in (_hx_current_path(request), request.POST.get("next", "")):
        if is_safe_url(request, candidate):
            return candidate
    if "pk" in kwargs:
        return reverse("community:post", kwargs={"pk": kwargs["pk"]})
    return reverse("community:feed")


def _redirect_to(request, url_name: str, next_url: str):
    url = f"{reverse(url_name)}?{urlencode({'next': next_url})}"
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=204)
        response["HX-Redirect"] = url
        return response
    return redirect(url)


def member_required(view=None, *, nickname: bool = True):
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return _redirect_to(request, "accounts:login", return_url(request, kwargs))
            if nickname and needs_nickname(request.user):
                return _redirect_to(request, "community:nickname", return_url(request, kwargs))
            return func(request, *args, **kwargs)

        return wrapper

    return decorator(view) if view is not None else decorator
