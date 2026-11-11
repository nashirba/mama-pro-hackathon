from django.db import models
from django.db.models.signals import post_save
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

from apps.core.text import normalize_kk


class SearchableReference(TranslatableModel):
    """Reference row with a slug, comma-separated synonyms and a normalized key for suggestions."""

    slug = models.SlugField(max_length=80, unique=True)
    synonyms = models.TextField(blank=True, help_text="через запятую")
    search_key = models.TextField(editable=False, default="")

    class Meta:
        abstract = True

    def __str__(self):
        return self.safe_translation_getter("name", any_language=True) or self.slug

    def refresh_search_key(self) -> None:
        """Recompute search_key from names in all languages and synonyms (no signals fired)."""
        parts = [*self.translations.values_list("name", flat=True), *self.synonyms.split(",")]
        key = normalize_kk(" ".join(p for p in parts if p.strip()))
        type(self)._default_manager.filter(pk=self.pk).update(search_key=key)
        self.search_key = key


class SpecialistType(SearchableReference):
    translations = TranslatedFields(
        name=models.CharField(max_length=200),
        name_plural=models.CharField(max_length=200),
        # The plural in the case it takes inside a landing title: «Логопеды» (RU), «логопедтер» (KZ).
        landing_name=models.CharField(max_length=200),
    )


class DevelopmentalCondition(SearchableReference):
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    is_no_diagnosis = models.BooleanField(default=False)

    translations = TranslatedFields(
        name=models.CharField(max_length=200),
        landing_name=models.CharField(max_length=200),
    )


class Method(SearchableReference):
    class EvidenceLevel(models.TextChoices):
        ESTABLISHED = "established", _("есть доказательная база")
        LIMITED = "limited", _("ограниченная доказательная база")
        NOT_ESTABLISHED_OR_HARMFUL = "not_established_or_harmful", _("нет доказательств эффективности")
        NOT_THERAPY = "not_therapy", _("педагогическая система, не терапия")

    evidence_level = models.CharField(max_length=30, choices=EvidenceLevel.choices)

    translations = TranslatedFields(name=models.CharField(max_length=200))


class ServiceKind(TranslatableModel):
    slug = models.SlugField(max_length=80, unique=True)

    translations = TranslatedFields(name=models.CharField(max_length=200))

    def __str__(self):
        return self.safe_translation_getter("name", any_language=True) or self.slug


class CommunicationLanguage(TranslatableModel):
    code = models.CharField(max_length=10, unique=True)

    translations = TranslatedFields(name=models.CharField(max_length=200))

    def __str__(self):
        return self.safe_translation_getter("name", any_language=True) or self.code


def _refresh_from_model(sender, instance, **kwargs):
    instance.refresh_search_key()


def _refresh_from_translation(sender, instance, **kwargs):
    instance.master.refresh_search_key()


for _model in (SpecialistType, DevelopmentalCondition, Method):
    post_save.connect(_refresh_from_model, sender=_model, dispatch_uid=f"search_key_{_model.__name__}")
    post_save.connect(
        _refresh_from_translation,
        sender=_model._parler_meta.root_model,
        dispatch_uid=f"search_key_tr_{_model.__name__}",
    )
