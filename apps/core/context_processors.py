from django.conf import settings
from django.utils.functional import SimpleLazyObject

from apps.core.city import cities, selected_city


def site(request):
    return {
        "DEPLOY_PROFILE": settings.DEPLOY_PROFILE,
        "IS_DEMO": settings.DEPLOY_PROFILE == "demo",
        "BRAND_NAME": settings.BRAND_NAME,
    }


def city(request):
    # Lazy: renders that do not show the header (htmx partials, admin) run no city query.
    return {
        "CITIES": SimpleLazyObject(lambda: cities(request)),
        "SELECTED_CITY": SimpleLazyObject(lambda: selected_city(request)),
    }
