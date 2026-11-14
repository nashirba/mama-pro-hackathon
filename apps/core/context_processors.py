from django.conf import settings

from apps.core.city import cities, selected_city


def site(request):
    return {
        "DEPLOY_PROFILE": settings.DEPLOY_PROFILE,
        "IS_DEMO": settings.DEPLOY_PROFILE == "demo",
        "BRAND_NAME": settings.BRAND_NAME,
    }


def city(request):
    return {"CITIES": cities(), "SELECTED_CITY": selected_city(request)}
