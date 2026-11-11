from django import template
from django.template.defaultfilters import floatformat
from django.utils.html import json_script
from django.utils.translation import gettext

from apps.catalog.models import Format

register = template.Library()


@register.filter
def km(distance_m: float) -> str:
    return floatformat(distance_m / 1000, 1)


@register.filter
def card_formats(card) -> list[str]:
    """Formats of the offers matching the search, in the canonical order."""
    present = {fmt for offer in card.matching_offers for fmt in offer.formats}
    return [value for value, _label in Format.choices if value in present]


@register.simple_tag
def map_labels_script():
    """Popup texts for `kamqorMap`; `from` holds the price placeholder `__PRICE__`."""
    return json_script(
        {
            "free": gettext("бесплатно"),
            "from": gettext("от %(price)s ₸") % {"price": "__PRICE__"},
            "onRequest": gettext("цена по запросу"),
            "details": gettext("Подробнее"),
            "twoGis": gettext("Открыть в 2ГИС"),
        },
        "map-labels",
    )
