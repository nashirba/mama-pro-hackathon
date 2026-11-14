from django import template
from django.utils.timesince import timesince
from django.utils.translation import npgettext_lazy

from .. import names

register = template.Library()

# Django ships no kk catalog for its own timesince units, so they fall back to RU: own strings fix that.
TIME_STRINGS = {
    "year": npgettext_lazy("timesince", "%(num)d year", "%(num)d years", "num"),
    "month": npgettext_lazy("timesince", "%(num)d month", "%(num)d months", "num"),
    "week": npgettext_lazy("timesince", "%(num)d week", "%(num)d weeks", "num"),
    "day": npgettext_lazy("timesince", "%(num)d day", "%(num)d days", "num"),
    "hour": npgettext_lazy("timesince", "%(num)d hour", "%(num)d hours", "num"),
    "minute": npgettext_lazy("timesince", "%(num)d minute", "%(num)d minutes", "num"),
}


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


@register.filter
def short_timesince(value) -> str:
    """Only the largest unit ('11 часов', '1 день'), so a post header stays short."""
    return timesince(value, depth=1, time_strings=TIME_STRINGS)
