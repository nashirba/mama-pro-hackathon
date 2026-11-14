from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.db import IntegrityError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.catalog.models import DevelopmentalCondition
from apps.catalog.visibility import catalog_visible_profiles
from apps.geo.models import KatoNode

from .access import is_safe_url, member_required
from .forms import CommentForm, ComplaintForm, NicknameForm, PostEditForm, PostForm
from .models import Post, PostImage
from .names import needs_nickname
from .query import (
    FeedParams,
    comment_for_viewer,
    comment_tree,
    feed,
    feed_params,
    post_for_viewer,
    visible_posts,
)
from .services import (
    add_comment,
    file_complaint,
    mention_prefix,
    save_post,
    save_post_edit,
    soft_delete_comment,
    soft_delete_post,
    toggle_like,
)


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
        # The fragment URL is not a page to come back to: like buttons fall back to the post page.
        return render(request, "community/_feed_page.html", {**context, "fragment": True})

    specialist = catalog_visible_profiles().filter(pk=params.specialist_id).first() if params.specialist_id else None
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
    # A hidden post is visible to its author only, so its photo must not sit in a shared cache.
    response["Cache-Control"] = "private, no-store" if post.is_hidden else "public, max-age=86400"
    return response


def _own_post(request, pk: int) -> Post:
    return get_object_or_404(visible_posts(request.user), pk=pk, author=request.user)


def _form_context(form, *, post=None) -> dict:
    selected = None
    if post is None:
        raw = str(form["specialist"].value() or "")
        selected = (
            catalog_visible_profiles()
            .prefetch_related("specialist_types", "contexts__services__addresses__kato", "contexts__services__home_visit_area__parent")
            .filter(pk=raw)
            .first()
            if raw.isdigit()
            else None
        )
        if selected:
            _with_option_details([selected])
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
        form = PostForm(user=user, initial={"kind": request.GET.get("kind"), "specialist": request.GET.get("specialist")})
    return render(request, "community/post_form.html", _form_context(form))


@member_required
def edit(request, pk: int):
    post = _own_post(request, pk)
    if request.method == "POST":
        form = PostEditForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            save_post_edit(form.instance, form.upload, remove_image=form.cleaned_data["remove_image"])
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


def _post_url(post_id: int, comment_id: int | None = None) -> str:
    url = reverse("community:post", kwargs={"pk": post_id})
    return f"{url}#comment-{comment_id}" if comment_id else url


def _back(request, fallback: str) -> str:
    candidate = request.POST.get("next", "")
    return candidate if is_safe_url(request, candidate) else fallback


def _comments_fragment(request, post):
    """The comment tree plus an out-of-band refresh of the "N ответов" counter (recounted after the write)."""
    post = post_for_viewer(post.pk, request.user)
    context = {"post": post, "nodes": comment_tree(post, request.user), "with_reply_count": True}
    return render(request, "community/_comments.html", context)


def _comment_form_response(request, post, form, key: str):
    """Re-show a comment form that was not saved (error or sensitive-data warning) with the user's text kept.

    HTMX: only that form is swapped (retargeted), so other forms and the thread stay as they are.
    Without HTMX: the whole post page, with the reply box of that comment open.
    """
    context = {"post": post, "comment_form": form, "comment_form_key": key}
    if request.headers.get("HX-Request"):
        response = render(request, "community/_comment_form.html", {**context, "parent": "" if key == "new" else key})
        response["HX-Retarget"] = f"#comment-form-{key}"
        response["HX-Reswap"] = "outerHTML"
        return response
    context["nodes"] = comment_tree(post, request.user)
    return render(request, "community/post_detail.html", context)


@member_required
@require_POST
def comment(request, pk: int):
    post = post_for_viewer(pk, request.user)
    parent = None
    parent_id = request.POST.get("parent", "")
    if parent_id:
        if not parent_id.isdigit():
            raise Http404
        parent = comment_for_viewer(int(parent_id), request.user)
        if parent.post_id != post.pk:
            raise Http404
    form = CommentForm(request.POST, mention=mention_prefix(parent))
    if not form.is_valid():
        return _comment_form_response(request, post, form, str(parent.pk) if parent else "new")
    created = add_comment(post, request.user, form.cleaned_data["body"], parent)
    if request.headers.get("HX-Request"):
        return _comments_fragment(request, post)
    return redirect(_post_url(post.pk, created.pk))


def _own_comment(request, pk: int):
    found = comment_for_viewer(pk, request.user)
    if found.author_id != request.user.pk:
        raise Http404
    return found


@member_required
def comment_edit(request, pk: int):
    target = _own_comment(request, pk)
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            target.body = form.cleaned_data["body"]
            target.save(update_fields=["body"])
            return redirect(_post_url(target.post_id, target.pk))
    else:
        form = CommentForm(initial={"body": target.body})
    return render(request, "community/comment_form.html", {"form": form, "comment": target})


@member_required
@require_POST
def comment_delete(request, pk: int):
    target = _own_comment(request, pk)
    soft_delete_comment(target)
    return redirect(_post_url(target.post_id))


def _target(request, target: str, pk: int):
    """(post, comment) the viewer may act on; exactly one is set."""
    if target == "post":
        return post_for_viewer(pk, request.user), None
    if target == "comment":
        return None, comment_for_viewer(pk, request.user)
    raise Http404


@member_required(nickname=False)
@require_POST
def like(request, target: str, pk: int):
    post, found = _target(request, target, pk)
    liked, count = toggle_like(request.user, post=post, comment=found)
    fallback = _post_url(post.pk) if post else _post_url(found.post_id, found.pk)
    if request.headers.get("HX-Request"):
        context = {"target": target, "pk": pk, "liked": liked, "count": count, "next": _back(request, fallback)}
        return render(request, "community/_like_button.html", context)
    return redirect(_back(request, fallback))


@member_required(nickname=False)
def complain(request, target: str, pk: int):
    post, found = _target(request, target, pk)
    post_id = post.pk if post else found.post_id
    if request.method == "POST":
        form = ComplaintForm(request.POST)
        if form.is_valid():
            file_complaint(request.user, post=post, comment=found, **form.cleaned_data)
            messages.success(request, _("Жалоба отправлена"))
            return redirect(_post_url(post_id))
    else:
        form = ComplaintForm()
    return render(request, "community/complaint_form.html", {"form": form, "post_id": post_id, "target": found or post})


def _kato_place(kato) -> str:
    name = kato.safe_translation_getter("name", any_language=True) or ""
    city = kato.city()
    if city is not None and city.pk != kato.pk:
        return f"{city.safe_translation_getter('name', any_language=True)}, {name}"
    return name


def _option_place(profile) -> str:
    """"City, district" of the first practice address (a nanny: of the first home-visit area), so a mother can tell namesakes apart."""
    for context in profile.contexts.all():
        for service in context.services.all():
            for address in service.addresses.all():
                return _kato_place(address.kato)
    for context in profile.contexts.all():
        for service in context.services.all():
            if service.home_visit_area is not None:
                return _kato_place(service.home_visit_area)
    return ""


def _with_option_details(profiles: list) -> list:
    for profile in profiles:
        profile.option_role = (
            _("Няня") if profile.is_nanny else ", ".join(t.name for t in profile.specialist_types.all())
        )
        profile.option_place = _option_place(profile)
    return profiles


def specialist_options(request):
    q = (request.GET.get("q") or "").strip()
    visible = catalog_visible_profiles().prefetch_related(
        "specialist_types", "contexts__services__addresses__kato", "contexts__services__home_visit_area__parent"
    )
    specialists = list(visible.filter(display_name__icontains=q).order_by("display_name")[:10]) if q else []
    raw = request.GET.get("specialist", "")
    selected = visible.filter(pk=raw).first() if raw.isdigit() else None
    if selected and selected not in specialists:
        specialists.insert(0, selected)
    _with_option_details(specialists)
    context = {"specialists": specialists, "selected_id": selected.pk if selected else None, "q": q}
    return render(request, "community/_specialist_options.html", context)
