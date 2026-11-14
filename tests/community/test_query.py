from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import Http404, QueryDict
from django.utils import timezone

from apps.catalog.models import DevelopmentalCondition
from apps.community import query
from apps.community.models import Like, Post, PostImage
from apps.community.query import CommentNode, FeedParams
from tests.factories import CommentFactory, NicknamedUserFactory, PostFactory, SpecialistFactory

pytestmark = pytest.mark.django_db

GUEST = AnonymousUser()


def ids(qs):
    return {p.pk for p in qs}


def test_feed_hides_deleted_and_foreign_hidden():
    author, other = NicknamedUserFactory(), NicknamedUserFactory()
    shown = PostFactory()
    hidden = PostFactory(author=author, is_hidden=True)
    deleted = PostFactory(author=author, is_deleted=True)
    params = FeedParams()
    assert ids(query.feed(params, GUEST)) == {shown.pk}
    assert ids(query.feed(params, other)) == {shown.pk}
    assert ids(query.feed(params, author)) == {shown.pk, hidden.pk}
    assert deleted.pk not in ids(query.feed(params, author))


def test_feed_filters_kind_condition_city_specialist(kato_demo, reference):
    ras = DevelopmentalCondition.objects.get(slug="ras")
    zrr = DevelopmentalCondition.objects.get(slug="zrr")
    city = kato_demo["karaganda"]
    spec = SpecialistFactory()
    story = PostFactory(kind=Post.Kind.STORY, condition=ras, city=city)
    review = PostFactory(kind=Post.Kind.REVIEW, specialist=spec, condition=zrr)
    question = PostFactory()
    assert ids(query.feed(FeedParams(kind="story"), GUEST)) == {story.pk}
    assert ids(query.feed(FeedParams(condition_id=ras.pk), GUEST)) == {story.pk}
    assert ids(query.feed(FeedParams(city_id=city.pk), GUEST)) == {story.pk}
    assert ids(query.feed(FeedParams(specialist_id=spec.pk), GUEST)) == {review.pk}
    assert ids(query.feed(FeedParams(), GUEST)) == {story.pk, review.pk, question.pk}
    both = FeedParams(kind="story", condition_id=ras.pk, city_id=city.pk)
    assert ids(query.feed(both, GUEST)) == {story.pk}
    assert ids(query.feed(FeedParams(kind="review", condition_id=ras.pk), GUEST)) == set()


def test_condition_filter_includes_children(reference):
    parent = DevelopmentalCondition.objects.get(slug="emotional-volitional")
    child = DevelopmentalCondition.objects.get(slug="ras")
    assert child.parent_id == parent.pk
    post = PostFactory(condition=child)
    assert ids(query.feed(FeedParams(condition_id=parent.pk), GUEST)) == {post.pk}


def test_search_word_typo_and_kk(kato_demo):
    autism = PostFactory(body="Мы столкнулись с аутизмом у сына")
    city_post = PostFactory(body="Ищем врача", city=kato_demo["karaganda"])
    PostFactory(body="Совсем другая тема про плавание")

    def found(q):
        return ids(query.feed(FeedParams(q=q), GUEST))

    assert autism.pk in found("аутизм")
    assert autism.pk in found("аутзм")
    assert found("Қарағанды") == {city_post.pk}
    assert found("Караганды") == {city_post.pk}


def test_search_orders_by_relevance_then_recency():
    old = PostFactory(body="аутизм", created_at=timezone.now() - timedelta(days=2))
    new = PostFactory(body="аутизм", created_at=timezone.now())
    assert [p.pk for p in query.feed(FeedParams(q="аутизм"), GUEST)] == [new.pk, old.pk]


def test_feed_orders_newest_first_and_defers_image_data():
    old = PostFactory(created_at=timezone.now() - timedelta(days=1))
    new = PostFactory()
    PostImage.objects.create(post=old, data=b"x" * 10, content_type="image/png")
    posts = list(query.feed(FeedParams(), GUEST))
    assert [p.pk for p in posts] == [new.pk, old.pk]
    assert [p.has_image for p in posts] == [False, True]


def test_feed_params_ignore_garbage():
    assert query.feed_params(QueryDict("kind=xxx&condition=abc&page=-3")) == FeedParams(page=1)
    qd = QueryDict("kind=review&condition=3&city=4&specialist=5&q=%20abc%20&page=2")
    assert query.feed_params(qd) == FeedParams(
        kind="review", condition_id=3, city_id=4, specialist_id=5, q="abc", page=2
    )
    assert query.feed_params(QueryDict("page=zzz")).page == 1


def test_counts_are_independent_and_visible_only():
    post = PostFactory()
    for _ in range(3):
        Like.objects.create(user=NicknamedUserFactory(), post=post)
    top = CommentFactory(post=post)
    CommentFactory(post=post, parent=top)
    CommentFactory(post=post, is_hidden=True)
    CommentFactory(post=post, is_deleted=True)
    got = query.post_for_viewer(post.pk, GUEST)
    assert got.like_count == 3
    assert got.reply_count == 2
    assert query.feed(FeedParams(), GUEST).get(pk=post.pk).reply_count == 2


def test_viewer_liked():
    liker, other = NicknamedUserFactory(), NicknamedUserFactory()
    post = PostFactory()
    comment = CommentFactory(post=post)
    Like.objects.create(user=liker, post=post)
    Like.objects.create(user=liker, comment=comment)
    assert query.post_for_viewer(post.pk, liker).viewer_liked is True
    assert query.post_for_viewer(post.pk, other).viewer_liked is False
    assert query.post_for_viewer(post.pk, GUEST).viewer_liked is False
    assert query.latest_posts(liker)[0].viewer_liked is True
    assert query.latest_posts(other)[0].viewer_liked is False
    assert query.latest_posts(GUEST)[0].viewer_liked is False
    for viewer, expected in ((liker, True), (other, False), (GUEST, False)):
        node = query.comment_tree(post, viewer)[0]
        assert node.comment.viewer_liked is expected
        assert node.comment.like_count == 1


def test_comment_for_viewer_404():
    author = NicknamedUserFactory()
    ok = CommentFactory()
    assert query.comment_for_viewer(ok.pk, GUEST) == ok
    deleted = CommentFactory(is_deleted=True)
    hidden = CommentFactory(author=author, is_hidden=True)
    on_hidden_post = CommentFactory(post=PostFactory(is_hidden=True))
    for c in (deleted, hidden, on_hidden_post):
        with pytest.raises(Http404):
            query.comment_for_viewer(c.pk, GUEST)
    assert query.comment_for_viewer(hidden.pk, author) == hidden
    with pytest.raises(Http404):
        query.comment_for_viewer(deleted.pk, author)
    with pytest.raises(Http404):
        query.comment_for_viewer(hidden.pk, NicknamedUserFactory())
    assert query.comment_for_viewer(on_hidden_post.pk, on_hidden_post.post.author) == on_hidden_post


def test_comment_tree_placeholder_and_order():
    post = PostFactory()
    now = timezone.now()
    first = CommentFactory(post=post, created_at=now - timedelta(minutes=3))
    gone_with_reply = CommentFactory(post=post, is_deleted=True, created_at=now - timedelta(minutes=2))
    reply = CommentFactory(post=post, parent=gone_with_reply, created_at=now - timedelta(minutes=1))
    CommentFactory(post=post, is_deleted=True, created_at=now)
    reply_author = NicknamedUserFactory()
    hidden_reply = CommentFactory(post=post, parent=first, author=reply_author, is_hidden=True)
    tree = query.comment_tree(post, GUEST)
    assert [n.comment.pk if n.comment else None for n in tree] == [first.pk, None]
    assert tree[0].replies == []
    assert tree[1] == CommentNode(None, [reply])
    own = query.comment_tree(post, reply_author)
    assert [r.pk for r in own[0].replies] == [hidden_reply.pk]


def test_post_for_viewer_404():
    author = NicknamedUserFactory()
    deleted = PostFactory(is_deleted=True)
    hidden = PostFactory(author=author, is_hidden=True)
    with pytest.raises(Http404):
        query.post_for_viewer(deleted.pk, deleted.author)
    with pytest.raises(Http404):
        query.post_for_viewer(hidden.pk, GUEST)
    with pytest.raises(Http404):
        query.post_for_viewer(hidden.pk, NicknamedUserFactory())
    assert query.post_for_viewer(hidden.pk, author).pk == hidden.pk


def test_latest_reviews_only_visible():
    spec = SpecialistFactory()
    now = timezone.now()
    posts = [
        PostFactory(kind=Post.Kind.REVIEW, specialist=spec, created_at=now - timedelta(hours=i)) for i in range(4)
    ]
    posts[1].is_hidden = True
    posts[1].save()
    PostFactory(kind=Post.Kind.REVIEW, specialist=SpecialistFactory())
    got = query.latest_reviews(spec, GUEST)
    assert [p.pk for p in got] == [posts[0].pk, posts[2].pk, posts[3].pk]


def test_latest_posts_limit_and_order():
    posts = [PostFactory(created_at=timezone.now() - timedelta(hours=i)) for i in range(5)]
    assert [p.pk for p in query.latest_posts(GUEST)] == [p.pk for p in posts[:3]]
