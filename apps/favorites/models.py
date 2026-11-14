from django.conf import settings
from django.db import models
from django.utils import timezone


class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favorites")
    profile = models.ForeignKey(
        "catalog.SpecialistProfile",
        on_delete=models.CASCADE,
        related_name="favorited_by",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["user", "profile"], name="favorite_user_profile_unique")]

    def __str__(self) -> str:
        return f"{self.user} → {self.profile}"
