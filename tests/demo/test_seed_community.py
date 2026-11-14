import json

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.catalog.models import DevelopmentalCondition, SpecialistProfile
from apps.catalog.visibility import catalog_visible_specialists
from apps.community.models import Comment, Like, Post
from apps.community.services import add_comment, save_post, toggle_like
from apps.community.pii import looks_sensitive
from apps.demo.generators import DATA_DIR, load_json
from apps.geo.models import KatoNode
from tests.demo.test_seed_demo import STOP_PHRASES


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
    visible = set(catalog_visible_specialists().values_list("pk", flat=True))
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
