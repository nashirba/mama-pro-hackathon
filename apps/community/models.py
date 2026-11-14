from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.db.models import Q, Value
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.text import normalize_kk

POST_BODY_MAX = 3000
RATING_MIN, RATING_MAX = 1, 5
COMMENT_BODY_MAX = 1000


def _ru(obj, field: str) -> str:
    return obj.safe_translation_getter(field, language_code="ru", any_language=True) or ""


def _all_names(obj) -> list[str]:
    return [n for n in obj.translations.values_list("name", flat=True) if n]


class Post(models.Model):
    class Kind(models.TextChoices):
        QUESTION = "question", _("Вопрос")
        STORY = "story", _("История")
        REVIEW = "review", _("Отзыв")

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="community_posts")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    body = models.TextField(validators=[MaxLengthValidator(POST_BODY_MAX)])
    condition = models.ForeignKey(
        "catalog.DevelopmentalCondition", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    city = models.ForeignKey(
        "geo.KatoNode", null=True, blank=True, on_delete=models.PROTECT, related_name="+", limit_choices_to={"level": "city"}
    )
    specialist = models.ForeignKey(
        "catalog.SpecialistProfile", null=True, blank=True, on_delete=models.PROTECT, related_name="community_reviews"
    )
    # A review's score. NULL only for reviews written before ratings existed; they are left out of the average.
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(RATING_MIN), MaxValueValidator(RATING_MAX)]
    )
    is_hidden = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    search_vector = SearchVectorField(null=True)
    search_norm = models.TextField(default="")

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"], name="community_post_vector_gin"),
            GinIndex(fields=["search_norm"], opclasses=["gin_trgm_ops"], name="community_post_norm_trgm"),
            models.Index(fields=["-created_at"], name="community_post_created"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["author", "specialist"],
                condition=Q(kind="review", is_deleted=False),
                name="community_review_unique_live",
            ),
            models.CheckConstraint(
                condition=Q(kind="review", specialist__isnull=False) | (~Q(kind="review") & Q(specialist__isnull=True)),
                name="community_review_has_specialist",
            ),
            models.CheckConstraint(
                condition=Q(rating__isnull=True) | Q(kind="review", rating__gte=RATING_MIN, rating__lte=RATING_MAX),
                name="community_rating_on_review_in_range",
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} #{self.pk}"

    def refresh_search(self) -> None:
        """Fill `search_norm` and `search_vector` (same recipe as the catalog's SearchOffer)."""
        ru_parts = [self.body]
        norm_parts = [self.body]
        if self.specialist_id:
            ru_parts.append(self.specialist.display_name)
            norm_parts.append(self.specialist.display_name)
        for obj in (self.condition if self.condition_id else None, self.city if self.city_id else None):
            if obj is not None:
                ru_parts.append(_ru(obj, "name"))
                norm_parts.extend(_all_names(obj))
        self.search_norm = normalize_kk(" ".join(p for p in norm_parts if p))
        self.search_vector = SearchVector(Value(" ".join(p for p in ru_parts if p)), config="russian") + SearchVector(
            Value(self.search_norm), config="simple"
        )

    def save(self, *args, **kwargs):
        self.refresh_search()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = {*update_fields, "search_norm", "search_vector"}
        super().save(*args, **kwargs)


class PostImage(models.Model):
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name="image")
    data = models.BinaryField()
    content_type = models.CharField(max_length=50)


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="community_comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    body = models.TextField(validators=[MaxLengthValidator(COMMENT_BODY_MAX)])
    is_hidden = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [models.Index(fields=["post", "created_at"], name="community_comment_post_created")]

    def __str__(self):
        return f"Comment #{self.pk}"


def _exactly_one_target() -> Q:
    return (Q(post__isnull=False) & Q(comment__isnull=True)) | (Q(post__isnull=True) & Q(comment__isnull=False))


class Like(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="community_likes")
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name="likes")
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE, related_name="likes")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "post"], name="community_like_unique_post"),
            models.UniqueConstraint(fields=["user", "comment"], name="community_like_unique_comment"),
            models.CheckConstraint(condition=_exactly_one_target(), name="community_like_one_target"),
        ]


class Complaint(models.Model):
    class Reason(models.TextChoices):
        AD = "ad", _("Реклама")
        CHILD_DATA = "child_data", _("Данные ребёнка")
        INSULT = "insult", _("Оскорбление")
        MEDICAL = "medical", _("Опасный медицинский совет")
        OTHER = "other", _("Другое")

    class Status(models.TextChoices):
        NEW = "new", _("Новая")
        RESOLVED = "resolved", _("Закрыта")

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="community_complaints")
    post = models.ForeignKey(Post, null=True, blank=True, on_delete=models.CASCADE, related_name="complaints")
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.CASCADE, related_name="complaints")
    reason = models.CharField(max_length=12, choices=Reason.choices)
    text = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=_exactly_one_target(), name="community_complaint_one_target"),
        ]

    @property
    def target(self):
        return self.post or self.comment
