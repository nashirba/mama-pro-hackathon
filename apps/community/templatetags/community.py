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


@register.filter
def author_badge_visible(obj) -> bool:
    """For a post or comment: does its author's specialist profile have a public page (annotated when available)."""
    flag = getattr(obj, "author_specialist_visible", None)
    return flag if flag is not None else is_specialist_visible(obj.author.specialist_profile)


@register.filter
def review_specialist_visible(post) -> bool:
    flag = getattr(post, "review_specialist_visible", None)
    return flag if flag is not None else is_specialist_visible(post.specialist)
