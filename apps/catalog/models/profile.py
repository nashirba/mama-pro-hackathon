from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

from apps.accounts.phone import InvalidPhone, normalize_kz_mobile

from .reference import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Method,
    SpecialistType,
)


class Format(models.TextChoices):
    IN_PERSON = "in_person", _("Очно")
    HOME_VISIT = "home_visit", _("Выезд на дом")
    ONLINE = "online", _("Онлайн")


class ProfileCategory(models.TextChoices):
    """Stored, not derived from the types: a nanny is never a specialist (catalog, reference data, home page counts)."""

    SPECIALIST = "specialist", _("Специалист")
    NANNY = "nanny", _("Няня")


class VerificationLevel(models.TextChoices):
    IDENTITY = "identity", _("Личность подтверждена")
    EDUCATION = "education", _("Образование подтверждено")
    CREDENTIAL = "credential", _("Квалификация подтверждена")
    SAFETY = "safety", _("Проверка на безопасность пройдена")


MAX_CHILD_AGE = 18
PHONE_ERROR = _("Введите казахстанский мобильный номер, например +7 701 123 45 67")


def validate_age_range(age_min, age_max) -> None:
    if age_min is not None and age_max is not None and age_min > age_max:
        raise ValidationError({"age_max": _("Максимальный возраст не может быть меньше минимального")})


class SpecialistProfile(TranslatableModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="specialist_profile")
    slug = models.SlugField(max_length=80, unique=True)
    category = models.CharField(
        max_length=20, choices=ProfileCategory.choices, default=ProfileCategory.SPECIALIST, db_index=True
    )
    display_name = models.CharField(max_length=200)  # the name is not translated
    photo = models.ImageField(upload_to="specialists/", blank=True)
    practice_start_year = models.PositiveSmallIntegerField()
    age_min = models.PositiveSmallIntegerField(validators=[MaxValueValidator(MAX_CHILD_AGE)])
    age_max = models.PositiveSmallIntegerField(validators=[MaxValueValidator(MAX_CHILD_AGE)])

    specialist_types = models.ManyToManyField(SpecialistType, blank=True, related_name="specialists")
    conditions = models.ManyToManyField(DevelopmentalCondition, blank=True, related_name="specialists")
    methods = models.ManyToManyField(Method, blank=True, related_name="specialists")
    languages = models.ManyToManyField(CommunicationLanguage, blank=True, related_name="specialists")

    formats = ArrayField(models.CharField(max_length=20, choices=Format.choices), default=list)
    whatsapp_phone = models.CharField(max_length=16, blank=True)
    public_phone = models.CharField(max_length=16, blank=True)
    # Filled by seed_demo only; plan 4 replaces it with real badges.
    demo_verification_levels = ArrayField(
        models.CharField(max_length=20, choices=VerificationLevel.choices), default=list, blank=True
    )
    # A nanny only; plan 4 adds the scan and its moderation.
    criminal_record_issued_on = models.DateField(null=True, blank=True)

    translations = TranslatedFields(
        bio=models.TextField(blank=True),
        approach=models.TextField(blank=True),
        availability=models.TextField(blank=True),  # a nanny's schedule, free text
    )

    def __str__(self):
        return self.display_name

    @property
    def experience_years(self) -> int:
        return timezone.localdate().year - self.practice_start_year

    @property
    def is_nanny(self) -> bool:
        return self.category == ProfileCategory.NANNY

    @property
    def training_hours(self) -> int:
        """Uses the prefetched `trainings` when there are any."""
        return sum(t.hours for t in self.trainings.all())

    def services(self):
        from .service import Service

        return Service.objects.filter(context__specialist=self)

    def clean(self):
        super().clean()
        errors = {}
        for field in ("whatsapp_phone", "public_phone"):
            value = getattr(self, field)
            if not value:
                continue
            try:
                setattr(self, field, normalize_kz_mobile(value))
            except InvalidPhone:
                errors[field] = PHONE_ERROR
        try:
            validate_age_range(self.age_min, self.age_max)
        except ValidationError as exc:
            errors.update(exc.message_dict)
        if self.is_nanny and self.pk and self.specialist_types.exists():
            errors["specialist_types"] = _("У няни нет типов специалиста")
        if errors:
            raise ValidationError(errors)


class PracticeContext(models.Model):
    class Kind(models.TextChoices):
        PRIVATE = "private", _("Частная практика")
        ORGANIZATION = "organization", _("Организация")

    specialist = models.ForeignKey(SpecialistProfile, on_delete=models.CASCADE, related_name="contexts")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.PRIVATE)
    organization_id = models.PositiveIntegerField(null=True, blank=True)  # becomes an FK in plan 5
    catalog_enabled = models.BooleanField(default=False)  # temporary flag: plan 4 checks badges, plan 9 subscription

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["specialist"],
                condition=models.Q(kind="private"),
                name="one_private_context_per_specialist",
            )
        ]

    def __str__(self):
        return f"{self.specialist} ({self.kind})"
