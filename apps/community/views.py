from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.catalog.models import DevelopmentalCondition, SpecialistProfile
from apps.catalog.visibility import catalog_visible_specialists
from apps.geo.models import KatoNode

from .access import is_safe_url, member_required
from .forms import NicknameForm, PostEditForm, PostForm
from .models import Post, PostImage
from .names import needs_nickname
from .query import FeedParams, comment_tree, feed, feed_params, post_for_viewer, visible_posts
from .services import save_post, soft_delete_post


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
    post = post_for_viewer(pk, request.user)
    photo = get_object_or_404(PostImage, post_id=post.pk)
    response = HttpResponse(bytes(photo.data), content_type=photo.content_type)
    response["Cache-Control"] = "public, max-age=86400"
    return response


def _own_post(request, pk: int) -> Post:
    return get_object_or_404(visible_posts(request.user), pk=pk, author=request.user)


def _form_context(form, *, post=None) -> dict:
    selected = None
    if post is None:
        raw = str(form["specialist"].value() or "")
        selected = catalog_visible_specialists().filter(pk=raw).first() if raw.isdigit() else None
    return {
        "form": form,
        "post": post,
        "selected_specialist": selected,
        "initial_specialists": [selected] if selected else [],
    }


def _already_reviewed(request, existing: Post):
    messages.info(request, _("Вы уже писали отзыв об этом специалисте - его можно изменить"))
    return redirect("community:edit", pk=existing.pk)


@member_required
def new(request):
    user = request.user
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, user=user)
        if form.is_valid():
            post = form.instance
            post.author = user
            if post.kind == Post.Kind.REVIEW:
                existing = visible_posts(user).filter(author=user, kind=Post.Kind.REVIEW, specialist=post.specialist).first()
                if existing:
                    return _already_reviewed(request, existing)
            try:
                save_post(post, form.upload)
            except IntegrityError:
                existing = Post.objects.filter(
                    author=user, kind=Post.Kind.REVIEW, specialist=post.specialist, is_deleted=False
                ).first()
                if existing is None:
                    raise
                return _already_reviewed(request, existing)
            return redirect("community:post", pk=post.pk)
    else:
        kind = request.GET.get("kind")
        form = PostForm(user=user, initial={"kind": kind} if kind else None)
    return render(request, "community/post_form.html", _form_context(form))


@member_required
def edit(request, pk: int):
    post = _own_post(request, pk)
    if request.method == "POST":
        form = PostEditForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            save_post(form.instance, form.upload, remove_image=form.cleaned_data["remove_image"])
            return redirect("community:post", pk=post.pk)
    else:
        form = PostEditForm(instance=post)
    context = _form_context(form, post=post)
    context["has_image"] = PostImage.objects.filter(post=post).exists()
    return render(request, "community/post_form.html", context)


@member_required
@require_POST
def delete(request, pk: int):
    soft_delete_post(_own_post(request, pk))
    return redirect("community:feed")


def specialist_options(request):
    q = (request.GET.get("q") or "").strip()
    visible = catalog_visible_specialists()
    specialists = list(visible.filter(display_name__icontains=q).order_by("display_name")[:10]) if q else []
    raw = request.GET.get("specialist", "")
    selected = visible.filter(pk=raw).first() if raw.isdigit() else None
    if selected and selected not in specialists:
        specialists.insert(0, selected)
    context = {"specialists": specialists, "selected_id": selected.pk if selected else None, "q": q}
    return render(request, "community/_specialist_options.html", context)
