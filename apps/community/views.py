from urllib.parse import urlencode

from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from apps.catalog.models import DevelopmentalCondition, SpecialistProfile
from apps.geo.models import KatoNode

from .access import is_safe_url, member_required
from .forms import NicknameForm
from .models import Post
from .names import needs_nickname
from .query import FeedParams, comment_tree, feed, feed_params, post_for_viewer


def _feed_qs(params: FeedParams, **override) -> str:
    """Query string of the feed state (never `page`); `override` replaces single values, None drops them."""
    values = {
        "kind": params.kind,
        "condition": params.condition_id,
        "city": params.city_id,
        "specialist": params.specialist_id,
        "q": params.q,
        **override,
    }
    return urlencode({k: v for k, v in values.items() if v not in (None, "")})


def _with_qs(qs: str) -> str:
    base = reverse("community:feed")
    return f"{base}?{qs}" if qs else base


def _kind_tabs(params: FeedParams) -> list[dict]:
    tabs = [(None, _("Все"))] + [
        (Post.Kind.QUESTION, _("Вопросы")),
        (Post.Kind.STORY, _("Истории")),
        (Post.Kind.REVIEW, _("Отзывы")),
    ]
    return [
        {"label": label, "url": _with_qs(_feed_qs(params, kind=kind)), "active": params.kind == kind}
        for kind, label in tabs
    ]


def feed_view(request):
    params = feed_params(request.GET)
    size = settings.COMMUNITY_PAGE_SIZE
    start = (params.page - 1) * size
    rows = list(feed(params, request.user)[start : start + size + 1])
    posts, has_more = rows[:size], len(rows) > size
    next_url = _with_qs(f"{_feed_qs(params)}&page={params.page + 1}".lstrip("&")) if has_more else ""
    context = {"posts": posts, "next_url": next_url, "params": params}
    if request.headers.get("HX-Request"):
        return render(request, "community/_feed_page.html", context)

    specialist = SpecialistProfile.objects.filter(pk=params.specialist_id).first() if params.specialist_id else None
    conditions = sorted(DevelopmentalCondition.objects.prefetch_related("translations"), key=lambda c: c.name)
    cities = sorted(KatoNode.objects.filter(level=KatoNode.Level.CITY).prefetch_related("translations"), key=lambda c: c.name)
    context.update(
        kind_tabs=_kind_tabs(params),
        conditions=conditions,
        cities=cities,
        specialist=specialist,
        clear_specialist_url=_with_qs(_feed_qs(params, specialist=None)),
    )
    return render(request, "community/feed.html", context)


def post_detail(request, pk: int):
    post = post_for_viewer(pk, request.user)
    return render(request, "community/post_detail.html", {"post": post, "nodes": comment_tree(post, request.user)})


@member_required(nickname=False)
def nickname(request):
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not is_safe_url(request, next_url):
        next_url = reverse("community:feed")
    if not needs_nickname(request.user):
        return redirect(next_url)
    if request.method == "POST":
        form = NicknameForm(request.POST, user=request.user)
        if form.is_valid() and form.save():
            return redirect(next_url)
    else:
        form = NicknameForm(user=request.user)
    return render(request, "community/nickname_form.html", {"form": form, "next": next_url})


def rules(request):
    return render(request, "community/rules.html")


def image(request, pk: int):
    raise Http404
