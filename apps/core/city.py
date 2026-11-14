from django.http import HttpRequest

from apps.core.i18n import first_translated
from apps.geo.models import KatoNode

COOKIE = "city"


def cities() -> list[KatoNode]:
    """Cities sorted by the name in the active language."""
    return sorted(
        KatoNode.objects.filter(level=KatoNode.Level.CITY).prefetch_related(
            "translations"
        ),
        key=lambda node: first_translated(node, "name"),
    )


def selected_city(request: HttpRequest) -> KatoNode | None:
    """The city from the cookie; a bad value or a node that is not a city counts as no city."""
    if not hasattr(request, "_selected_city"):
        request._selected_city = _from_cookie(request)
    return request._selected_city


def _from_cookie(request: HttpRequest) -> KatoNode | None:
    try:
        city_id = int(request.COOKIES.get(COOKIE, ""))
    except ValueError:
        return None
    return (
        KatoNode.objects.filter(pk=city_id, level=KatoNode.Level.CITY)
        .prefetch_related("translations")
        .first()
    )
