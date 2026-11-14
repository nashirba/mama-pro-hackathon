"""Synthetic community feed for the demo: parents with nicknames, posts, comments, replies, likes, a few photos.

Everything random goes through the `random.Random` passed in. The seed owns only the posts of its own users
(synthetic parents and the seed specialists). Seeding is create-if-absent: a start of the service must never touch posts
that already exist, because real users comment, like and complain on them and shared links point at their ids. Only an
explicit reset deletes and recreates the seed data.
"""

from datetime import timedelta
from io import BytesIO
from random import Random

from django.db import transaction
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.catalog.models import (
    DevelopmentalCondition,
    ProfileCategory,
    SpecialistProfile,
)
from apps.catalog.visibility import (
    catalog_visible_profiles,
    catalog_visible_specialists,
)
from apps.community.models import Comment, Complaint, Like, Post
from apps.community.services import add_comment, save_post
from apps.demo.generators import LOGIN_PHONE_PREFIX, NANNY_LOGIN_PHONE_PREFIX, load_json
from apps.geo.models import KatoNode

PARENT_PHONE_PREFIX = "+7700002"  # +7700000 specialists, +7700001 nannies
IMAGE_EVERY = 4  # every 4th post (indices 1, 5, 9, ...) gets a photo: ~10 of ~40
# Scores of the specialist reviews in order; fixed, so the random sequence of the rest of the seed does not change.
REVIEW_RATINGS = [5, 4, 5, 5, 3, 4, 5, 2, 4, 5, 5, 4, 3, 5]


def _placeholder_jpeg(rng: Random) -> tuple[bytes, str]:
    color = tuple(rng.randint(120, 230) for _ in range(3))
    buffer = BytesIO()
    Image.new("RGB", (800, 600), color).save(buffer, "JPEG", quality=70)
    return buffer.getvalue(), "image/jpeg"


def _parents(nicknames: list[str]) -> list[User]:
    parents = []
    for i, nickname in enumerate(nicknames):
        phone = f"{PARENT_PHONE_PREFIX}{i:04d}"
        user = User.objects.filter(phone=phone).first() or User.objects.create_user(phone, preferred_language="ru")
        user.display_name = nickname
        user.last_name, user.first_name = "Демо", nickname
        user.save()
        parents.append(user)
    return parents


def has_seed_posts() -> bool:
    """Whether the seed was already created: some post by a synthetic parent exists.

    Deliberately not "any post exists" - real users' posts must not block seeding, and the seed must not
    be recreated over its own posts. Specialist accounts are not checked: they only add comments and reviews on top.
    """
    return Post.objects.filter(author__phone__startswith=PARENT_PHONE_PREFIX).exists()


def clear_community() -> None:
    """Delete the seed posts and the seed accounts' comments, with everything attached to them."""
    authors = User.objects.filter(phone__startswith=PARENT_PHONE_PREFIX) | User.objects.filter(
        phone__startswith=LOGIN_PHONE_PREFIX
    )
    posts = Post.objects.filter(author__in=authors)
    comments = Comment.objects.filter(author__in=authors)
    Complaint.objects.filter(post__in=posts).delete()
    Complaint.objects.filter(comment__in=comments).delete()
    Like.objects.filter(post__in=posts).delete()
    Like.objects.filter(comment__in=comments).delete()
    Comment.objects.filter(post__in=posts).delete()
    comments.delete()
    posts.delete()


def _review_target(rng: Random, author: User, visible: list[SpecialistProfile], used: set[tuple[int, int]]):
    options = [s for s in visible if (author.pk, s.pk) not in used]
    return rng.choice(options) if options else None


@transaction.atomic
def seed_community(rng: Random, *, reset: bool = False) -> tuple[int, bool]:
    """Create the demo community unless it exists; returns (number of seed posts, whether they were created now).

    With `reset` the seed data is deleted first and recreated (posts get new ids, others' replies and likes on them go).
    """
    if reset:
        clear_community()
    elif has_seed_posts():
        # Seeds created before ratings existed get scores and the nanny reviews; nothing else is touched.
        data = load_json("community_ru.json")
        _backfill_ratings()
        _seed_nanny_reviews(data["nanny_reviews"], _parents(data["nicknames"]))
        return Post.objects.filter(author__phone__startswith=PARENT_PHONE_PREFIX).count(), False
    data = load_json("community_ru.json")
    parents = _parents(data["nicknames"])
    specialists = list(
        catalog_visible_specialists()
        .filter(user__phone__startswith=LOGIN_PHONE_PREFIX)
        .select_related("user")
        .order_by("pk")
    )
    conditions = {c.slug: c for c in DevelopmentalCondition.objects.all()}
    cities = {n.slug: n for n in KatoNode.objects.filter(level=KatoNode.Level.CITY)}
    now = timezone.now()
    used_reviews: set[tuple[int, int]] = set()
    created = 0

    for index, item in enumerate(data["posts"]):
        author = parents[index % len(parents)]
        specialist = None
        if item["kind"] == "review":
            specialist = _review_target(rng, author, specialists, used_reviews)
            if specialist is None:
                continue  # no visible specialist to review (an empty catalog)
            used_reviews.add((author.pk, specialist.pk))
        post = Post(
            author=author,
            kind=item["kind"],
            body=item["body"],
            condition=conditions[item["condition"]],
            city=cities[item["city"]],
            specialist=specialist,
            rating=REVIEW_RATINGS[len(used_reviews) % len(REVIEW_RATINGS)] if specialist else None,
            created_at=now - timedelta(hours=rng.randint(2, 24 * 30)),
        )
        upload = _placeholder_jpeg(rng) if index % IMAGE_EVERY == 1 else None
        save_post(post, upload)
        created += 1
        _seed_comments(rng, post, item["comments"], index, parents, specialists)
        _seed_likes(rng, post, parents)
    created += _seed_nanny_reviews(data["nanny_reviews"], parents)
    return created, True


def _backfill_ratings() -> None:
    reviews = Post.objects.filter(
        author__phone__startswith=PARENT_PHONE_PREFIX, kind=Post.Kind.REVIEW, rating__isnull=True
    ).order_by("pk")
    for i, post in enumerate(reviews, start=1):
        post.rating = REVIEW_RATINGS[i % len(REVIEW_RATINGS)]
        post.save(update_fields=["rating"])


def _seed_nanny_reviews(items: list[dict], parents: list[User]) -> int:
    """One review per seed nanny in turn, by a different parent each; skipped once any seed nanny review exists."""
    nannies = list(
        catalog_visible_profiles()
        .filter(category=ProfileCategory.NANNY, user__phone__startswith=NANNY_LOGIN_PHONE_PREFIX)
        .order_by("pk")
    )
    if not nannies or Post.objects.filter(
        author__in=parents, kind=Post.Kind.REVIEW, specialist__category=ProfileCategory.NANNY
    ).exists():
        return 0
    conditions = {c.slug: c for c in DevelopmentalCondition.objects.all()}
    cities = {n.slug: n for n in KatoNode.objects.filter(level=KatoNode.Level.CITY)}
    now = timezone.now()
    for i, item in enumerate(items):
        post = Post(
            author=parents[(i * 3) % len(parents)],
            kind=Post.Kind.REVIEW,
            body=item["body"],
            condition=conditions[item["condition"]],
            city=cities[item["city"]],
            specialist=nannies[i % len(nannies)],
            rating=item["rating"],
            created_at=now - timedelta(days=i + 1),
        )
        save_post(post)
    return len(items)


def _seed_comments(rng, post: Post, comments: list[dict], index: int, parents: list[User], specialists) -> None:
    others = [p for p in parents if p.pk != post.author_id]
    for j, item in enumerate(comments):
        # Only comments written in a professional voice ("by": "specialist") belong to specialist accounts.
        if item.get("by") == "specialist":
            if not specialists:
                continue
            commenter = specialists[(index + j) % len(specialists)].user
        else:
            commenter = rng.choice(others)
        comment = add_comment(post, commenter, item["body"])
        for k, reply in enumerate(item["replies"]):
            # Replies alternate: the post author answers first, then the commenter again.
            replier = post.author if k % 2 == 0 else commenter
            add_comment(post, replier, reply, parent=comment)
        for liker in rng.sample(parents, rng.randint(0, 3)):
            if liker.pk != commenter.pk:
                Like.objects.get_or_create(user=liker, comment=comment)


def _seed_likes(rng, post: Post, parents: list[User]) -> None:
    for liker in rng.sample(parents, rng.randint(0, 8)):
        if liker.pk != post.author_id:
            Like.objects.get_or_create(user=liker, post=post)
