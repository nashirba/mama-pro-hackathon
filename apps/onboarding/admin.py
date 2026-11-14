from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db.models import F
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from . import services
from .models import Application, ApplicationCourse, ApplicationDocument, BlockedPhone

APPROVE, NEEDS_CHANGES, REJECT = "approve", "needs_changes", "reject"


class DecisionForm(forms.ModelForm):
    """The moderator's decision on a submitted application. Everything else on the page is read-only."""

    decision = forms.ChoiceField(
        label=_("Решение"),
        required=False,
        choices=[
            ("", "—"),
            (APPROVE, _("Одобрить: все проверки пройдены, профиль появится в каталоге")),
            (NEEDS_CHANGES, _("Вернуть на доработку")),
            (REJECT, _("Отклонить: номер попадёт в чёрный список")),
        ],
    )

    class Meta:
        model = Application
        fields = ["moderator_comment"]
        labels = {"moderator_comment": _("Комментарий для заявителя")}

    def clean(self):
        cleaned = super().clean()
        decision = cleaned.get("decision")
        if decision and self.instance.status != Application.Status.SUBMITTED:
            raise ValidationError(_("Решение принимается только по анкете на проверке"))
        if decision in (NEEDS_CHANGES, REJECT) and not cleaned.get("moderator_comment", "").strip():
            self.add_error("moderator_comment", _("Напишите, что исправить или почему отказ"))
        return cleaned


class DocumentInline(admin.TabularInline):
    model = ApplicationDocument
    extra = 0
    can_delete = False
    fields = ("kind", "file_link", "uploaded_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    @admin.display(description=_("Файл"))
    def file_link(self, obj):
        if obj.pk is None:  # the empty template row of the inline
            return "-"
        return format_html('<a href="{}" target="_blank">{}</a>', reverse("onboarding:document_file", args=[obj.pk]), obj.filename)


class CourseInline(admin.TabularInline):
    model = ApplicationCourse
    extra = 0
    can_delete = False
    fields = ("title", "issuer", "year", "hours", "certificate_number", "is_first_aid")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = DecisionForm
    list_display = ("__str__", "phone", "category", "status", "submitted_at", "decided_at")
    list_filter = ("status", "category")
    search_fields = ("user__phone", "user__last_name", "user__first_name")
    ordering = (F("submitted_at").desc(nulls_last=True),)
    inlines = (DocumentInline, CourseInline)
    readonly_fields = (
        "user",
        "phone",
        "category",
        "status",
        "specialist_types",
        "education",
        "practice_start_year",
        "age_min",
        "age_max",
        "conditions",
        "methods",
        "languages",
        "bio",
        "approach",
        "availability",
        "formats",
        "area",
        "street",
        "building",
        "duration_min",
        "price_session",
        "price_hour",
        "price_month",
        "criminal_record_issued_on",
        "submitted_at",
        "decided_at",
        "decided_by",
        "profile",
    )
    fieldsets = (
        (_("Заявитель"), {"fields": ("user", "phone", "category", "status", "submitted_at")}),
        (
            _("Анкета"),
            {
                "fields": (
                    "specialist_types",
                    "education",
                    "practice_start_year",
                    ("age_min", "age_max"),
                    "conditions",
                    "methods",
                    "languages",
                    "bio",
                    "approach",
                    "availability",
                    "formats",
                    "area",
                    ("street", "building"),
                    ("duration_min", "price_session"),
                    ("price_hour", "price_month"),
                    "criminal_record_issued_on",
                )
            },
        ),
        (_("Решение"), {"fields": ("decision", "moderator_comment", "decided_at", "decided_by", "profile")}),
    )

    def has_add_permission(self, request):
        return False

    @admin.display(description=_("Телефон"), ordering="user__phone")
    def phone(self, obj):
        return obj.user.phone

    def save_model(self, request, obj, form, change):
        decision = form.cleaned_data.get("decision")
        if not decision:
            obj.save(update_fields=["moderator_comment"])
            return
        comment = form.cleaned_data.get("moderator_comment", "")
        try:
            if decision == APPROVE:
                obj.moderator_comment = comment
                services.approve(obj, request.user)
            elif decision == NEEDS_CHANGES:
                services.request_changes(obj, comment, request.user)
            else:
                services.reject(obj, comment, request.user)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))


@admin.register(BlockedPhone)
class BlockedPhoneAdmin(admin.ModelAdmin):
    list_display = ("phone", "application", "created_at")
    search_fields = ("phone",)
