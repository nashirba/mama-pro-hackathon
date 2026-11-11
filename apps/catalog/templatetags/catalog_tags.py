from django import template

from apps.catalog.links import ContactLinks
from apps.catalog.links import contact_links as _contact_links
from apps.catalog.models import Format, VerificationLevel
from apps.core.i18n import first_translated
from apps.geo import links as geo_links

register = template.Library()


@register.simple_tag
def contact_links(profile) -> ContactLinks:
    return _contact_links(profile)


@register.filter
def two_gis_url(address) -> str:
    return geo_links.two_gis_url(address)


@register.filter
def two_gis_route_url(address) -> str:
    return geo_links.two_gis_route_url(address)


@register.filter
def format_label(value: str) -> str:
    return Format(value).label


@register.filter
def verification_label(value: str) -> str:
    return VerificationLevel(value).label


@register.filter
def tr(obj, field: str) -> str:
    return first_translated(obj, field)
