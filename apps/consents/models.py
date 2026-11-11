from django.conf import settings
from django.db import models
from django.utils import timezone

CURRENT_VERSION = "v1"


class Consent(models.Model):
    USER_AGREEMENT = "user_agreement"
    PD_PROCESSING = "pd_processing"
    KIND_CHOICES = [
        (USER_AGREEMENT, "User agreement"),
        (PD_PROCESSING, "Personal data processing"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consents")
    kind = models.CharField(max_length=32, choices=KIND_CHOICES)
    version = models.CharField(max_length=16, default=CURRENT_VERSION)
    given_at = models.DateTimeField(default=timezone.now)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "kind"])]
