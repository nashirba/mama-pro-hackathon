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

CHILDCARE_KIND = "childcare"  # the only service kind of a nanny
NANNY_PRICES = ("price_hour", "price_night", "price_month")


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
    price_hour = models.PositiveIntegerField(null=True, blank=True)  # tenge, a nanny only
    price_night = models.PositiveIntegerField(null=True, blank=True)  # tenge, a nanny only
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
            for field in ("price_session", *NANNY_PRICES):
                if getattr(self, field) is not None:
                    errors[field] = _("У бесплатной услуги не должно быть цены")
        try:
            validate_age_range(self.age_min, self.age_max)
        except ValidationError as exc:
            errors.update(exc.message_dict)
        if self.context_id is not None and self.kind_id is not None:
            errors.update(self._category_errors())
        if errors:
            raise ValidationError(errors)

    def _category_errors(self) -> dict:
        """A nanny offers only childcare at the family's home, priced per hour, night or month; a specialist never does."""
        errors = {}
        is_childcare = self.kind.slug == CHILDCARE_KIND
        if self.context.specialist.is_nanny:
            if not is_childcare:
                errors["kind"] = _("У няни только услуги няни")
            if list(self.formats or []) != [Format.HOME_VISIT]:
                errors["formats"] = _("Няня работает только с выездом на дом")
            if all(getattr(self, field) is None for field in NANNY_PRICES):
                errors["price_hour"] = _("Укажите цену за час, за ночь или за месяц")
            if self.price_session is not None:
                errors["price_session"] = _("У няни нет цены за занятие")
        else:
            if is_childcare:
                errors["kind"] = _("Услуги няни есть только у няни")
            for field in ("price_hour", "price_night"):
                if getattr(self, field) is not None:
                    errors[field] = _("Цена за час и за ночь есть только у няни")
        return errors

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
