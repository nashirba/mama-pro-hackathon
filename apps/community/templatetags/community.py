from django import template

from apps.catalog.visibility import is_specialist_visible

from .. import names

register = template.Library()


@register.filter
def author_name(user) -> str:
    return names.author_name(user)


@register.filter
def is_specialist(user) -> bool:
    return names.is_specialist(user)


@register.filter
def specialist_visible(profile) -> bool:
    return is_specialist_visible(profile)
