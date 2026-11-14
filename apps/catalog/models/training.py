from django.db import models
from parler.models import TranslatableModel, TranslatedFields

from .profile import SpecialistProfile


class Training(TranslatableModel):
    """An external course a nanny completed, confirmed by a certificate. Mama Pro does not run the courses."""

    profile = models.ForeignKey(SpecialistProfile, on_delete=models.CASCADE, related_name="trainings")
    issuer = models.CharField(max_length=200)  # the organization that ran the course and issued the certificate
    year = models.PositiveSmallIntegerField()
    hours = models.PositiveSmallIntegerField()
    certificate_number = models.CharField(max_length=50)
    is_first_aid = models.BooleanField(default=False)  # a pediatric first aid course

    translations = TranslatedFields(title=models.CharField(max_length=200))

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.safe_translation_getter("title", any_language=True) or f"Training {self.pk}"
