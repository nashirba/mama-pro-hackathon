from django.http import HttpRequest

from apps.core.i18n import first_translated
from apps.geo.models import KatoNode

COOKIE = "city"
COOKIE_MAX_AGE = 365 * 24 * 60 * 60


def cities(request: HttpRequest) -> list[KatoNode]:
    """Cities sorted by the name in the active language; one query per request."""
    if not hasattr(request, "_cities"):
        request._cities = sorted(
            KatoNode.objects.filter(level=KatoNode.Level.CITY).prefetch_related("translations"),
            key=lambda node: first_translated(node, "name"),
        )
    return request._cities


def selected_city(request: HttpRequest) -> KatoNode | None:
    """The city from the cookie; a bad value or a node that is not a city counts as no city."""
    try:
        city_id = int(request.COOKIES.get(COOKIE, ""))
    except ValueError:
        return None
    return next((c for c in cities(request) if c.pk == city_id), None)
