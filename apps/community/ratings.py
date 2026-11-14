"""The single place that computes a profile's rating: the average score and the number of reviews everyone can see."""

from dataclasses import dataclass

from django.db.models import Avg, Count

from .models import Post


@dataclass(frozen=True)
class Rating:
    average: float | None  # None when there are no rated reviews
    count: int


NO_RATING = Rating(None, 0)


def rated_reviews():
    """Reviews that count: live, not hidden by a moderator, with a score. The same set for every viewer."""
    return Post.objects.filter(kind=Post.Kind.REVIEW, is_deleted=False, is_hidden=False, rating__isnull=False)


def ratings_for(profile_ids) -> dict[int, Rating]:
    rows = (
        rated_reviews()
        .filter(specialist_id__in=list(profile_ids))
        .order_by()
        .values("specialist_id")
        .annotate(average=Avg("rating"), count=Count("pk"))
    )
    return {r["specialist_id"]: Rating(round(float(r["average"]), 1), r["count"]) for r in rows}


def rating_for(profile_id: int) -> Rating:
    return ratings_for([profile_id]).get(profile_id, NO_RATING)
