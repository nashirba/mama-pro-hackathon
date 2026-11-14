from django import template

from .. import names

register = template.Library()


@register.filter
def author_name(user) -> str:
    return names.author_name(user)


@register.filter
def is_specialist(user) -> bool:
    return names.is_specialist(user)


@register.filter
def author_badge_visible(obj) -> bool:
    """For a post or comment: does its author's specialist profile have a public page (annotated by `apps.community.query`)."""
    return obj.author_specialist_visible


@register.filter
def review_specialist_visible(post) -> bool:
    return post.review_specialist_visible
