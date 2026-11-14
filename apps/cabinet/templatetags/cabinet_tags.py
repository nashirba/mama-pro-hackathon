from django import template
from django.utils import timezone

from apps.cabinet.ages import format_age

register = template.Library()


@register.filter
def age(value):
    if value is None:
        return ""
    return format_age(value, timezone.localdate())
