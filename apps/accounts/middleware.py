from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

EXEMPT_VIEWS = {
    "accounts:register",
    "accounts:logout",
    "accounts:logout_all",
    "set_language",
    "healthz",
    "robots_txt",
}


class RequireFullNameMiddleware:
    """Send a logged-in user without a last and first name to the registration step."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if (
            not user.is_authenticated
            or user.is_staff
            or user.is_superuser
            or user.has_full_name
        ):
            return None
        match = request.resolver_match
        if match is not None and match.view_name in EXEMPT_VIEWS:
            return None
        url = reverse("accounts:register")
        if request.method == "GET":
            url += "?" + urlencode({"next": request.get_full_path()})
        return redirect(url)
