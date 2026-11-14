import json

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.catalog.models import DevelopmentalCondition, SpecialistProfile
from apps.catalog.visibility import catalog_visible_profiles
from apps.community.models import Comment, Like, Post
from apps.community.pii import looks_sensitive
from apps.community.services import add_comment, file_complaint, save_post, toggle_like
from apps.demo.community_seed import PARENT_PHONE_PREFIX
from apps.demo.generators import DATA_DIR, load_json
from apps.geo.models import KatoNode
from tests.demo.test_seed_demo import STOP_PHRASES
from tests.factories import PrivateContextFactory, SpecialistFactory, UserFactory


@pytest.fixture
def seeded(db):
    call_command("seed_demo", specialists=10, seed=1)


def test_seed_creates_posts_of_all_kinds_in_all_cities(seeded):
    assert Post.objects.count() >= 35
    assert set(Post.objects.values_list("kind", flat=True)) == {"question", "story", "review"}
    cities = set(KatoNode.objects.filter(level="city").values_list("id", flat=True))
    assert set(Post.objects.values_list("city_id", flat=True)) == cities
    assert Like.objects.exists() and Comment.objects.filter(parent__isnull=False).exists()
    assert not any(looks_sensitive(p.body) for p in Post.objects.all())


def test_seed_community_idempotent(db):
    call_command("seed_demo", specialists=10, seed=1)
    before = (Post.objects.count(), Comment.objects.count(), Like.objects.count())
    call_command("seed_demo", specialists=10, seed=1)
    assert (Post.objects.count(), Comment.objects.count(), Like.objects.count()) == before


def test_seed_reviews_only_visible_specialists_and_unique(seeded):
    reviews = Post.objects.filter(kind="review")
    assert reviews.exists()
    visible = set(catalog_visible_profiles().values_list("pk", flat=True))
    pairs = list(reviews.values_list("author_id", "specialist_id"))
    assert {s for _, s in pairs} <= visible
    assert len(pairs) == len(set(pairs))


def test_seed_some_posts_have_images_and_specialist_comments(seeded):
    assert 5 <= Post.objects.filter(image__isnull=False).count() <= 15
    image = Post.objects.filter(image__isnull=False).first().image
    assert image.content_type == "image/jpeg" and bytes(image.data)[:2] == b"\xff\xd8"
    assert Comment.objects.filter(author__specialist_profile__isnull=False).exists()


def test_community_json_uses_existing_slugs_and_no_stop_phrases(db):
    call_command("seed_demo", specialists=1, seed=1)
    data = load_json("community_ru.json")
    conditions = set(DevelopmentalCondition.objects.values_list("slug", flat=True))
    cities = set(KatoNode.objects.filter(level="city").values_list("slug", flat=True))
    assert len(data["nicknames"]) == 10 and len(set(data["nicknames"])) == 10
    texts = []
    for post in data["posts"]:
        assert post["kind"] in {"question", "story", "review"}
        assert post["condition"] in conditions and post["city"] in cities
        texts.append(post["body"])
        for comment in post["comments"]:
            assert comment.get("by", "parent") in {"parent", "specialist"}
            texts += [comment["body"], *comment["replies"]]
    assert all(not looks_sensitive(t) for t in texts)
    text = (DATA_DIR / "community_ru.json").read_text(encoding="utf-8").lower()
    assert not [p for p in STOP_PHRASES if p in text]
    assert json.loads(text)


def test_specialist_comments_come_only_from_marked_json_entries(seeded):
    data = load_json("community_ru.json")
    marked = sum(c.get("by") == "specialist" for p in data["posts"] for c in p["comments"])
    assert marked >= 3
    assert Comment.objects.filter(author__specialist_profile__isnull=False, parent__isnull=True).count() == marked


def test_specialist_comments_have_at_most_one_reply_so_no_specialist_replies():
    """`_seed_comments` alternates repliers (post author, then the commenter); the second reply would be the specialist's."""
    data = load_json("community_ru.json")
    offenders = [
        c["body"] for p in data["posts"] for c in p["comments"] if c.get("by") == "specialist" and len(c["replies"]) > 1
    ]
    assert not offenders


def test_no_seed_reply_is_authored_by_a_specialist(seeded):
    replies = Comment.objects.filter(parent__isnull=False, author__specialist_profile__isnull=False)
    assert not replies.exists()


def test_seed_does_not_touch_real_users_data(db):
    call_command("seed_demo", specialists=10, seed=1)
    user = User.objects.create_user("+77015556677", preferred_language="ru")
    user.display_name = "Реальная_мама"
    user.save()
    specialist = SpecialistProfile.objects.order_by("pk").first()
    post = save_post(Post(author=user, kind="story", body="Моя настоящая история."))
    review = save_post(Post(author=user, kind="review", body="Мой настоящий отзыв.", specialist=specialist))
    comment = add_comment(post, user, "Мой комментарий.")
    toggle_like(user, post=post)
    ids = lambda: (
        set(Post.objects.filter(author=user).values_list("pk", flat=True)),
        set(Comment.objects.filter(author=user).values_list("pk", flat=True)),
        set(Like.objects.filter(user=user).values_list("pk", flat=True)),
    )
    before = ids()
    call_command("seed_demo", specialists=10, seed=1)
    call_command("seed_demo", specialists=10, seed=1)
    assert ids() == before
    assert before[0] == {post.pk, review.pk} and before[1] == {comment.pk} and len(before[2]) == 1
    user.refresh_from_db()
    assert user.display_name == "Реальная_мама"


def _seed_post_and_comment() -> tuple[Post, Comment]:
    post = Post.objects.filter(author__phone__startswith=PARENT_PHONE_PREFIX, comments__parent__isnull=True).first()
    return post, post.comments.filter(parent__isnull=True).first()


def test_real_comment_on_seed_post_survives_reseed(db):
    call_command("seed_demo", specialists=10, seed=1)
    user = User.objects.create_user("+77015556677", preferred_language="ru")
    user.display_name = "Реальная_мама"
    user.save()
    post, seed_comment = _seed_post_and_comment()
    comment = add_comment(post, user, "Живой комментарий.")
    reply = add_comment(post, user, "Живой ответ.", parent=seed_comment)
    post_like = toggle_like(user, post=post) and Like.objects.get(user=user, post=post)
    comment_like = toggle_like(user, comment=seed_comment) and Like.objects.get(user=user, comment=seed_comment)
    complaint = file_complaint(user, post=post, reason="other", text="жалоба")
    seed_ids = set(Post.objects.filter(author__phone__startswith=PARENT_PHONE_PREFIX).values_list("pk", flat=True))

    call_command("seed_demo", specialists=10, seed=1)

    assert set(Post.objects.filter(author__phone__startswith=PARENT_PHONE_PREFIX).values_list("pk", flat=True)) == seed_ids
    for obj in (comment, reply, post_like, comment_like, complaint, seed_comment):
        assert type(obj).objects.filter(pk=obj.pk).exists()


def test_reset_community_recreates_seed_and_keeps_real_posts(db):
    call_command("seed_demo", specialists=10, seed=1)
    user = User.objects.create_user("+77015556677", preferred_language="ru")
    user.display_name = "Реальная_мама"
    user.save()
    own = save_post(Post(author=user, kind="story", body="Моя настоящая история."))
    old_ids = set(Post.objects.exclude(pk=own.pk).values_list("pk", flat=True))
    old_comment_ids = set(Comment.objects.values_list("pk", flat=True))
    old_like_ids = set(Like.objects.values_list("pk", flat=True))
    count, comment_count, like_count = len(old_ids), len(old_comment_ids), len(old_like_ids)
    assert comment_count and like_count

    call_command("seed_demo", specialists=10, seed=1, reset_community=True)

    new_ids = set(Post.objects.exclude(pk=own.pk).values_list("pk", flat=True))
    assert len(new_ids) == count and not new_ids & old_ids
    assert Post.objects.filter(pk=own.pk).exists()
    new_comments = set(Comment.objects.values_list("pk", flat=True))
    new_likes = set(Like.objects.values_list("pk", flat=True))
    assert new_comments and not new_comments & old_comment_ids
    assert new_likes and not new_likes & old_like_ids
    # same seed, same content: comments and replies are recreated in full
    assert len(new_comments) == comment_count
    assert Comment.objects.filter(parent__isnull=False).exists()
    assert not Comment.objects.filter(post__in=old_ids).exists() and not Like.objects.filter(post__in=old_ids).exists()


def test_seed_skips_visible_non_seed_specialists(db):
    outsider = SpecialistFactory(user=UserFactory(phone="+77019998877"))
    PrivateContextFactory(specialist=outsider, catalog_enabled=True)
    call_command("seed_demo", specialists=10, seed=1)
    assert not Post.objects.filter(specialist=outsider).exists()
    assert not Comment.objects.filter(author=outsider.user).exists()


def test_seed_parents_have_full_name(seeded):
    parent = User.objects.filter(phone__startswith=PARENT_PHONE_PREFIX).first()
    assert parent.has_full_name


def test_seed_reviews_have_ratings_and_nannies_are_reviewed(seeded):
    reviews = Post.objects.filter(kind="review")
    assert not reviews.filter(rating__isnull=True).exists()
    assert set(reviews.values_list("rating", flat=True)) <= {1, 2, 3, 4, 5}
    assert reviews.filter(specialist__category="nanny").count() == len(load_json("community_ru.json")["nanny_reviews"])


def test_reseed_backfills_missing_ratings(db):
    call_command("seed_demo", specialists=10, seed=1)
    Post.objects.filter(kind="review", specialist__category="specialist").update(rating=None)
    call_command("seed_demo", specialists=10, seed=1)
    assert not Post.objects.filter(kind="review", rating__isnull=True).exists()
