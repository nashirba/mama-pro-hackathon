from django.contrib import admin
from parler.admin import TranslatableAdmin, TranslatableTabularInline

from .models import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Method,
    PracticeContext,
    Service,
    ServiceKind,
    SpecialistProfile,
    SpecialistType,
    Training,
)


@admin.register(SpecialistType)
class SpecialistTypeAdmin(TranslatableAdmin):
    list_display = ("slug", "name", "name_plural", "landing_name")
    search_fields = ("slug", "translations__name", "synonyms")


@admin.register(DevelopmentalCondition)
class DevelopmentalConditionAdmin(TranslatableAdmin):
    list_display = ("slug", "name", "parent", "is_no_diagnosis")
    search_fields = ("slug", "translations__name", "synonyms")


@admin.register(Method)
class MethodAdmin(TranslatableAdmin):
    list_display = ("slug", "name", "evidence_level")
    list_filter = ("evidence_level",)
    search_fields = ("slug", "translations__name", "synonyms")


@admin.register(ServiceKind)
class ServiceKindAdmin(TranslatableAdmin):
    list_display = ("slug", "name")


@admin.register(CommunicationLanguage)
class CommunicationLanguageAdmin(TranslatableAdmin):
    list_display = ("code", "name")


class TrainingInline(TranslatableTabularInline):
    model = Training
    extra = 0
    fields = ("title", "issuer", "year", "hours", "certificate_number", "is_first_aid")


@admin.register(SpecialistProfile)
class SpecialistProfileAdmin(TranslatableAdmin):
    list_display = ("display_name", "slug", "category", "practice_start_year")
    list_filter = ("category",)
    search_fields = ("display_name", "slug")
    filter_horizontal = ("specialist_types", "conditions", "methods", "languages")
    inlines = [TrainingInline]


@admin.register(PracticeContext)
class PracticeContextAdmin(admin.ModelAdmin):  # not translatable, so a plain ModelAdmin
    list_display = ("specialist", "kind", "catalog_enabled")
    list_filter = ("kind", "catalog_enabled")


@admin.register(Service)
class ServiceAdmin(TranslatableAdmin):
    list_display = ("title", "context", "kind", "price_session", "price_hour", "is_free")
    list_filter = ("kind", "is_free")
    filter_horizontal = ("addresses", "conditions", "methods", "languages")
