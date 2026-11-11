from django.conf import settings


def site(request):
    return {
        "DEPLOY_PROFILE": settings.DEPLOY_PROFILE,
        "IS_DEMO": settings.DEPLOY_PROFILE == "demo",
    }
