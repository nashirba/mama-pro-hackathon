from collections.abc import Iterable

from django.conf import settings
from django.urls import reverse

from apps.catalog.models import SpecialistProfile
from apps.geo.links import two_gis_url
from apps.geo.models import KatoNode

from .models import SearchOffer

KAZAKHSTAN_CENTER = [66.9, 48.0]
KAZAKHSTAN_ZOOM = 4
ZOOM_BY_LEVEL = {
    KatoNode.Level.REGION: 7,
    KatoNode.Level.CITY: 11,
    KatoNode.Level.DISTRICT: 12,
    KatoNode.Level.RURAL: 12,
}

# `address__kato__parent__parent` covers the walk of `Address.city_slug()` (district -> city -> region)
OFFER_RELATED = ("specialist", "address__kato__parent__parent")


def map_offers(offers):
    """Offers that have a point, ordered so that the offers of one marker are adjacent."""
    return (
        offers.filter(address__isnull=False, point__isnull=False)
        .select_related(*OFFER_RELATED)
        .order_by("specialist_id", "address_id", "pk")
    )


def _offer_price(offer: SearchOffer) -> int | None:
    return 0 if offer.is_free else offer.price_session


def _feature(offers: list[SearchOffer]) -> dict:
    first = offers[0]
    prices = [p for p in map(_offer_price, offers) if p is not None]
    price_from = min(prices) if prices else None
    specialist = first.specialist
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [first.point.x, first.point.y]},
        "properties": {
            "specialist_slug": specialist.slug,
            "name": specialist.display_name,
            "price_from": price_from,
            "is_free": price_from == 0,
            "url": reverse("catalog:specialist", args=[specialist.slug]),
            "two_gis_url": two_gis_url(first.address),
        },
    }


def feature_collection(offers: Iterable[SearchOffer], limit: int) -> dict:
    """One feature per (specialist, address); offers without a point (online, home visit) are skipped."""
    groups: dict[tuple[int, int], list[SearchOffer]] = {}
    for offer in offers:
        if offer.point is None or offer.address is None:
            continue
        key = (offer.specialist_id, offer.address_id)
        if key not in groups and len(groups) >= limit:
            continue
        groups.setdefault(key, []).append(offer)
    return {"type": "FeatureCollection", "features": [_feature(group) for group in groups.values()]}


def specialist_feature_collection(specialist: SpecialistProfile) -> dict:
    """The markers of one specialist's addresses (the offers exist only for catalog-visible contexts)."""
    return feature_collection(map_offers(specialist.search_offers.all()), settings.GEOJSON_MAX_FEATURES)


def default_view(kato_id: int | None) -> dict:
    """Center and zoom for the selected node, or for the nearest ancestor that has a center; Kazakhstan otherwise."""
    node = KatoNode.objects.select_related("parent__parent").filter(pk=kato_id).first() if kato_id is not None else None
    while node is not None:
        if node.center is not None:
            return {"center": [node.center.x, node.center.y], "zoom": ZOOM_BY_LEVEL[node.level]}
        node = node.parent
    return {"center": KAZAKHSTAN_CENTER, "zoom": KAZAKHSTAN_ZOOM}


def map_config(kato_id: int | None, query: str) -> dict:
    """Passed to the page through `json_script`, so no number is localized."""
    geojson_url = reverse("search:map_geojson")
    return {**default_view(kato_id), "geojsonUrl": f"{geojson_url}?{query}" if query else geojson_url}
