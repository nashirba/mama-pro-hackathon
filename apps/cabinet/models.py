from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Child(models.Model):
    class Sex(models.TextChoices):
        MALE = "male", _("Мальчик")
        FEMALE = "female", _("Девочка")

    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="children"
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    sex = models.CharField(max_length=6, blank=True, choices=Sex.choices)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = [F("birth_date").asc(nulls_last=True), "id"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip()
