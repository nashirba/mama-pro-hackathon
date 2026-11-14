from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import Format
from apps.catalog.models.profile import validate_age_range
from apps.geo.models import KatoNode

from .models import Application, ApplicationCourse, ApplicationDocument

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024
# The type comes from the file's first bytes, not from what the browser claims.
SIGNATURES = {b"%PDF": "application/pdf", b"\xff\xd8\xff": "image/jpeg", b"\x89PNG": "image/png"}


def sniff_type(head: bytes) -> str | None:
    return next((kind for magic, kind in SIGNATURES.items() if head.startswith(magic)), None)

COMMON_FIELDS = ["practice_start_year", "age_min", "age_max", "conditions", "languages", "area", "bio", "approach"]
SPECIALIST_FIELDS = [
    "specialist_types",
    "education",
    *COMMON_FIELDS,
    "methods",
    "formats",
    "street",
    "building",
    "duration_min",
    "price_session",
]
NANNY_FIELDS = [*COMMON_FIELDS, "availability", "price_hour", "price_month", "criminal_record_issued_on"]

LABELS = {
    "specialist_types": _("Специализация"),
    "education": _("Образование"),
    "practice_start_year": _("Год начала работы"),
    "age_min": _("Возраст детей: от, лет"),
    "age_max": _("Возраст детей: до, лет"),
    "conditions": _("С какими особенностями развития работаете"),
    "languages": _("Языки общения"),
    "area": _("Город или район"),
    "bio": _("О себе"),
    "approach": _("Подход к работе"),
    "methods": _("Методы"),
    "formats": _("Формат работы"),
    "street": _("Улица"),
    "building": _("Дом"),
    "duration_min": _("Длительность занятия, мин"),
    "price_session": _("Цена за занятие, ₸"),
    "availability": _("График работы"),
    "price_hour": _("Цена за час, ₸"),
    "price_month": _("Цена за месяц, ₸"),
    "criminal_record_issued_on": _("Дата выдачи справки о несудимости"),
}

HELP = {
    "education": _("Вуз, специальность, год окончания. Переподготовка и курсы - тоже здесь"),
    "street": _("Для очного приёма"),
}


def _area_choices():
    """Cities and their districts; a district is shown with its city."""
    nodes = KatoNode.objects.filter(level__in=[KatoNode.Level.CITY, KatoNode.Level.DISTRICT]).select_related("parent")
    return nodes.filter(Q(level=KatoNode.Level.CITY) | Q(parent__level=KatoNode.Level.CITY))


class AreaChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.parent}, {obj}" if obj.level == KatoNode.Level.DISTRICT else str(obj)


class ApplicationForm(forms.ModelForm):
    """Every field is optional: the form saves a draft. `services.missing_for_submit` checks completeness."""

    area = AreaChoiceField(queryset=KatoNode.objects.none(), required=False, label=LABELS["area"])
    formats = forms.MultipleChoiceField(
        choices=Format.choices, required=False, widget=forms.CheckboxSelectMultiple, label=LABELS["formats"]
    )

    class Meta:
        model = Application
        fields = SPECIALIST_FIELDS + ["availability", "price_hour", "price_month", "criminal_record_issued_on"]
        labels = LABELS
        help_texts = HELP
        widgets = {
            "specialist_types": forms.CheckboxSelectMultiple,
            "conditions": forms.CheckboxSelectMultiple,
            "methods": forms.CheckboxSelectMultiple,
            "languages": forms.CheckboxSelectMultiple,
            "education": forms.Textarea(attrs={"rows": 3}),
            "bio": forms.Textarea(attrs={"rows": 5}),
            "approach": forms.Textarea(attrs={"rows": 3}),
            "availability": forms.Textarea(attrs={"rows": 3}),
            "criminal_record_issued_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        keep = NANNY_FIELDS if self.instance.is_nanny else SPECIALIST_FIELDS
        for name in list(self.fields):
            if name not in keep:
                del self.fields[name]
        self.fields["area"].queryset = _area_choices()
        self.fields["area"].empty_label = _("Выберите")
        self.fields["practice_start_year"].widget.attrs.update(min=1960, max=timezone.localdate().year)

    def clean_practice_start_year(self):
        value = self.cleaned_data["practice_start_year"]
        if value is not None and not 1960 <= value <= timezone.localdate().year:
            raise forms.ValidationError(_("Укажите год от 1960 до текущего"))
        return value

    def clean_criminal_record_issued_on(self):
        value = self.cleaned_data.get("criminal_record_issued_on")
        if value is not None and value > timezone.localdate():
            raise forms.ValidationError(_("Дата не может быть в будущем"))
        return value

    def clean(self):
        cleaned = super().clean()
        try:
            validate_age_range(cleaned.get("age_min"), cleaned.get("age_max"))
        except forms.ValidationError as exc:
            self.add_error(None, exc)
        return cleaned


class DocumentForm(forms.Form):
    kind = forms.ChoiceField(label=_("Тип документа"), choices=ApplicationDocument.Kind.choices)
    file = forms.FileField(label=_("Файл (PDF, JPG или PNG, до 5 МБ)"))

    def clean_file(self):
        upload = self.cleaned_data["file"]
        if upload.size > MAX_DOCUMENT_BYTES:
            raise forms.ValidationError(_("Файл больше 5 МБ"))
        upload.seek(0)
        self.detected_type = sniff_type(upload.read(8))
        upload.seek(0)
        if self.detected_type is None:
            raise forms.ValidationError(_("Загрузите PDF, JPG или PNG"))
        return upload

    def save(self, application: Application) -> ApplicationDocument:
        upload = self.cleaned_data["file"]
        return ApplicationDocument.objects.create(
            application=application,
            kind=self.cleaned_data["kind"],
            filename=upload.name[:200],
            content_type=self.detected_type,
            data=upload.read(),
        )


class CourseForm(forms.ModelForm):
    class Meta:
        model = ApplicationCourse
        fields = ["title", "issuer", "year", "hours", "certificate_number", "is_first_aid"]
        labels = {
            "title": _("Название курса"),
            "issuer": _("Кто проводил"),
            "year": _("Год"),
            "hours": _("Часов"),
            "certificate_number": _("Номер сертификата"),
            "is_first_aid": _("Первая помощь детям"),
        }

    def clean_year(self):
        value = self.cleaned_data["year"]
        if not 1960 <= value <= timezone.localdate().year:
            raise forms.ValidationError(_("Укажите год от 1960 до текущего"))
        return value
