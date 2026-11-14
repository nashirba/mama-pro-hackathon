"""The single place that decides which community content a viewer sees (posts, comments) and how it is searched."""

from dataclasses import dataclass, field

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramWordSimilarity
from django.db.models import BooleanField, Count, Exists, F, IntegerField, OuterRef, Q, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce
from django.http import Http404, QueryDict
from django.shortcuts import get_object_or_404

from apps.catalog.models import SpecialistProfile
from apps.catalog.visibility import specialist_visible_exists
from apps.core.text import normalize_kk
from apps.search.query import expand_conditions

from .models import Comment, Like, Post, PostImage


@dataclass(frozen=True)
class FeedParams:
    kind: str | None = None
    condition_id: int | None = None
    city_id: int | None = None
    specialist_id: int | None = None
    q: str = ""
    page: int = 1


def _positive_int(raw: str | None) -> int | None:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def feed_params(qd: QueryDict) -> FeedParams:
    """Parse the feed query string; garbage values fall back to defaults instead of raising."""
    kind = qd.get("kind")
    return FeedParams(
        kind=kind if kind in Post.Kind.values else None,
        condition_id=_positive_int(qd.get("condition")),
        city_id=_positive_int(qd.get("city")),
        specialist_id=_positive_int(qd.get("specialist")),
        q=(qd.get("q") or "").strip(),
        page=_positive_int(qd.get("page")) or 1,
    )


def _is_member(viewer) -> bool:
    return bool(getattr(viewer, "is_authenticated", False))


def _visible_q(viewer) -> Q:
    """Not deleted, and not hidden unless the viewer wrote it."""
    visible = Q(is_hidden=False)
    if _is_member(viewer):
        visible |= Q(author=viewer)
    return Q(is_deleted=False) & visible


def visible_posts(viewer) -> QuerySet[Post]:
    return Post.objects.filter(_visible_q(viewer))


def _comment_visible(comment: Comment, viewer) -> bool:
    if comment.is_deleted:
        return False
    return not comment.is_hidden or (_is_member(viewer) and comment.author_id == viewer.pk)


def comment_for_viewer(pk: int, viewer) -> Comment:
    """A comment the viewer may act on; 404 if it, or its post, is not visible to them."""
    comment = get_object_or_404(Comment.objects.filter(_visible_q(viewer)).select_related("post"), pk=pk)
    if not visible_posts(viewer).filter(pk=comment.post_id).exists():
        raise Http404
    return comment


def _count(model, **lookup) -> Subquery:
    group = next(iter(lookup))
    rows = model.objects.filter(**lookup).order_by().values(group).annotate(n=Count("pk")).values("n")
    return Coalesce(Subquery(rows, output_field=IntegerField()), Value(0))


def _viewer_liked(viewer, **lookup) -> Exists | Value:
    if not _is_member(viewer):
        return Value(False, output_field=BooleanField())
    return Exists(Like.objects.filter(user=viewer, **lookup))


def with_counts(qs: QuerySet[Post], viewer) -> QuerySet[Post]:
    """The only place that annotates `like_count`, `reply_count`, `has_image` and `viewer_liked`."""
    visible_comments = Comment.objects.filter(_visible_q(viewer), post=OuterRef("pk"))
    reply_rows = visible_comments.order_by().values("post").annotate(n=Count("pk")).values("n")
    return qs.annotate(
        like_count=_count(Like, post=OuterRef("pk")),
        reply_count=Coalesce(Subquery(reply_rows, output_field=IntegerField()), Value(0)),
        has_image=Exists(PostImage.objects.filter(post=OuterRef("pk"))),
        viewer_liked=_viewer_liked(viewer, post=OuterRef("pk")),
    )


def _cards(qs: QuerySet[Post], viewer) -> QuerySet[Post]:
    return (
        with_counts(qs, viewer)
        .annotate(
            author_specialist_visible=specialist_visible_exists("author__specialist_profile__pk"),
            review_specialist_visible=specialist_visible_exists("specialist_id"),
        )
        .select_related("author__specialist_profile", "condition", "city", "specialist")
        .prefetch_related("condition__translations", "city__translations")
    )


def feed(params: FeedParams, viewer) -> QuerySet[Post]:
    qs = visible_posts(viewer)
    if params.kind:
        qs = qs.filter(kind=params.kind)
    if params.condition_id is not None:
        qs = qs.filter(condition_id__in=expand_conditions([params.condition_id]))
    if params.city_id is not None:
        qs = qs.filter(city_id=params.city_id)
    if params.specialist_id is not None:
        qs = qs.filter(specialist_id=params.specialist_id)

    normalized_q = normalize_kk(params.q)
    if normalized_q:
        query = SearchQuery(params.q, config="russian", search_type="websearch") | SearchQuery(normalized_q, config="simple")
        trgm = TrigramWordSimilarity(normalized_q, "search_norm")
        qs = qs.annotate(trgm=trgm).filter(Q(search_vector=query) | Q(trgm__gte=settings.SEARCH_TRIGRAM_MIN))
        qs = qs.annotate(text_rank=SearchRank(F("search_vector"), query) + F("trgm"))
        order = ["-text_rank", "-created_at", "-pk"]
    else:
        order = ["-created_at", "-pk"]
    return _cards(qs, viewer).order_by(*order)


def post_for_viewer(pk: int, viewer) -> Post:
    return get_object_or_404(_cards(visible_posts(viewer), viewer), pk=pk)


@dataclass
class CommentNode:
    """A top-level comment with its replies; `comment is None` is the "comment deleted" placeholder."""

    comment: Comment | None
    replies: list[Comment] = field(default_factory=list)


def comment_tree(post: Post, viewer) -> list[CommentNode]:
    comments = list(
        post.comments.select_related("author__specialist_profile")
        .annotate(
            like_count=_count(Like, comment=OuterRef("pk")),
            viewer_liked=_viewer_liked(viewer, comment=OuterRef("pk")),
            author_specialist_visible=specialist_visible_exists("author__specialist_profile__pk"),
        )
        .order_by("created_at", "pk")
    )
    replies: dict[int, list[Comment]] = {}
    for c in comments:
        if c.parent_id is not None and _comment_visible(c, viewer):
            replies.setdefault(c.parent_id, []).append(c)
    nodes = []
    for c in comments:
        if c.parent_id is not None:
            continue
        own_replies = replies.get(c.pk, [])
        if _comment_visible(c, viewer):
            nodes.append(CommentNode(c, own_replies))
        elif own_replies:
            nodes.append(CommentNode(None, own_replies))
    return nodes


def latest_reviews(specialist: SpecialistProfile, viewer, limit: int = 3) -> list[Post]:
    qs = visible_posts(viewer).filter(kind=Post.Kind.REVIEW, specialist=specialist)
    return list(_cards(qs, viewer).order_by("-created_at", "-pk")[:limit])


def latest_posts(viewer, limit: int = 3) -> list[Post]:
    return list(_cards(visible_posts(viewer), viewer).order_by("-created_at", "-pk")[:limit])
