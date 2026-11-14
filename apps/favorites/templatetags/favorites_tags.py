from django import template

from apps.favorites.models import Favorite

register = template.Library()


@register.inclusion_tag("favorites/_button.html", takes_context=True)
def favorite_button(context, profile):
    request = context["request"]
    if not hasattr(request, "_favorite_ids"):
        request._favorite_ids = (
            set(
                Favorite.objects.filter(user=request.user).values_list(
                    "profile_id", flat=True
                )
            )
            if request.user.is_authenticated
            else set()
        )
    return {
        "profile": profile,
        "active": profile.pk in request._favorite_ids,
        "next": request.get_full_path(),
        "request": request,
        "csrf_token": context.get("csrf_token"),
    }
