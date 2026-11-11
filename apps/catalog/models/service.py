from dataclasses import dataclass

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

from apps.geo.models import Address, KatoNode

from .profile import MAX_CHILD_AGE, Format, PracticeContext, validate_age_range
from .reference import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Method,
    ServiceKind,
)


@dataclass(frozen=True)
class ServiceAttrs:
    age_min: int
    age_max: int
    condition_ids: list[int]
    method_ids: list[int]
    language_codes: list[str]
    specialist_type_ids: list[int]


class Service(TranslatableModel):
    context = models.ForeignKey(PracticeContext, on_delete=models.CASCADE, related_name="services")
    kind = models.ForeignKey(ServiceKind, on_delete=models.PROTECT, related_name="services")
    duration_min = models.PositiveSmallIntegerField()
    formats = ArrayField(models.CharField(max_length=20, choices=Format.choices), default=list)
    price_session = models.PositiveIntegerField(null=True, blank=True)  # tenge
    price_month = models.PositiveIntegerField(null=True, blank=True)  # tenge
    is_free = models.BooleanField(default=False)  # a free service keeps both prices as NULL, not 0
    addresses = models.ManyToManyField(Address, blank=True, related_name="services")
    home_visit_area = models.ForeignKey(KatoNode, null=True, blank=True, on_delete=models.PROTECT, related_name="+")

    # Search attributes: empty = inherited from the profile, set = narrowed for this service.
    age_min = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(MAX_CHILD_AGE)])
    age_max = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MaxValueValidator(MAX_CHILD_AGE)])
    conditions = models.ManyToManyField(DevelopmentalCondition, blank=True, related_name="services")
    methods = models.ManyToManyField(Method, blank=True, related_name="services")
    languages = models.ManyToManyField(CommunicationLanguage, blank=True, related_name="services")

    translations = TranslatedFields(
        title=models.CharField(max_length=200),
        description=models.TextField(blank=True),
    )

    def __str__(self):
        return self.safe_translation_getter("title", any_language=True) or f"Service {self.pk}"

    def clean(self):
        super().clean()
        errors = {}
        if Format.HOME_VISIT in (self.formats or []) and self.home_visit_area_id is None:
            errors["home_visit_area"] = _("Укажите область выезда")
        if self.is_free:
            for field in ("price_session", "price_month"):
                if getattr(self, field) is not None:
                    errors[field] = _("У бесплатной услуги не должно быть цены")
        try:
            validate_age_range(self.age_min, self.age_max)
        except ValidationError as exc:
            errors.update(exc.message_dict)
        if errors:
            raise ValidationError(errors)

    def effective_attrs(self) -> ServiceAttrs:
        profile = self.context.specialist
        conditions = self.conditions.all() or profile.conditions.all()
        methods = self.methods.all() or profile.methods.all()
        languages = self.languages.all() or profile.languages.all()
        return ServiceAttrs(
            age_min=profile.age_min if self.age_min is None else self.age_min,
            age_max=profile.age_max if self.age_max is None else self.age_max,
            condition_ids=sorted(c.id for c in conditions),
            method_ids=sorted(m.id for m in methods),
            language_codes=sorted(lang.code for lang in languages),
            specialist_type_ids=sorted(t.id for t in profile.specialist_types.all()),
        )
