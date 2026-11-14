from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Format,
    Method,
    ProfileCategory,
    SpecialistProfile,
    SpecialistType,
)
from apps.catalog.models.profile import MAX_CHILD_AGE
from apps.geo.models import KatoNode


class Application(models.Model):
    """A specialist's or a nanny's questionnaire. The catalog profile is created from it only on approval."""

    class Status(models.TextChoices):
        DRAFT = "draft", _("Черновик")
        SUBMITTED = "submitted", _("На проверке")
        NEEDS_CHANGES = "needs_changes", _("Нужна доработка")
        APPROVED = "approved", _("Одобрена")
        REJECTED = "rejected", _("Отклонена")

    EDITABLE = (Status.DRAFT, Status.NEEDS_CHANGES)

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="application")
    category = models.CharField(max_length=20, choices=ProfileCategory.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    practice_start_year = models.PositiveSmallIntegerField(null=True, blank=True)
    age_min = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(MAX_CHILD_AGE)])
    age_max = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(MAX_CHILD_AGE)])
    specialist_types = models.ManyToManyField(SpecialistType, blank=True, related_name="+")
    conditions = models.ManyToManyField(DevelopmentalCondition, blank=True, related_name="+")
    methods = models.ManyToManyField(Method, blank=True, related_name="+")
    languages = models.ManyToManyField(CommunicationLanguage, blank=True, related_name="+")
    education = models.TextField(blank=True)  # a specialist: university, speciality, year
    bio = models.TextField(blank=True)
    approach = models.TextField(blank=True)
    availability = models.TextField(blank=True)  # a nanny's schedule

    formats = ArrayField(models.CharField(max_length=20, choices=Format.choices), default=list, blank=True)
    area = models.ForeignKey(KatoNode, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    street = models.CharField(max_length=200, blank=True)
    building = models.CharField(max_length=50, blank=True)
    duration_min = models.PositiveSmallIntegerField(null=True, blank=True)
    price_session = models.PositiveIntegerField(null=True, blank=True)  # tenge, a specialist
    price_hour = models.PositiveIntegerField(null=True, blank=True)  # tenge, a nanny
    price_month = models.PositiveIntegerField(null=True, blank=True)  # tenge, a nanny
    criminal_record_issued_on = models.DateField(null=True, blank=True)

    moderator_comment = models.TextField(blank=True)  # shown to the applicant on «needs changes» and «rejected»
    created_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    profile = models.OneToOneField(
        SpecialistProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name="application"
    )

    class Meta:
        verbose_name = _("Заявка специалиста или няни")
        verbose_name_plural = _("Заявки специалистов и нянь")

    def __str__(self):
        return f"{self.user.last_name} {self.user.first_name} ({self.get_category_display()})"

    @property
    def is_nanny(self) -> bool:
        return self.category == ProfileCategory.NANNY

    @property
    def is_editable(self) -> bool:
        return self.status in self.EDITABLE


class ApplicationDocument(models.Model):
    """A scan of a diploma or certificate. Stored in the database and served only to its owner and to staff."""

    class Kind(models.TextChoices):
        DIPLOMA = "diploma", _("Диплом")
        CERTIFICATE = "certificate", _("Сертификат или удостоверение")
        COURSE = "course", _("Сертификат курса")
        CRIMINAL_RECORD = "criminal_record", _("Справка о несудимости")
        OTHER = "other", _("Другое")

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    filename = models.CharField(max_length=200)
    content_type = models.CharField(max_length=50)
    data = models.BinaryField()
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.filename


class ApplicationCourse(models.Model):
    """A nanny's course; becomes a `Training` of her profile on approval."""

    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name="courses")
    title = models.CharField(max_length=200)
    issuer = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField()
    hours = models.PositiveSmallIntegerField()
    certificate_number = models.CharField(max_length=50)
    is_first_aid = models.BooleanField(default=False)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.title


class BlockedPhone(models.Model):
    """A number whose application was rejected: no new specialist or nanny application from it.
    A separate table, so changing the phone in the cabinet does not free the number."""

    phone = models.CharField(max_length=16, unique=True)
    application = models.ForeignKey(Application, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _("Заблокированный номер")
        verbose_name_plural = _("Заблокированные номера")

    def __str__(self):
        return self.phone
