from django.db.models import Exists, OuterRef, QuerySet

from .models import PracticeContext, SpecialistProfile


def is_catalog_visible(context: PracticeContext) -> bool:
    """The single place that decides whether a practice context is shown in the catalog."""
    return context.catalog_enabled


def catalog_visible_specialists() -> QuerySet[SpecialistProfile]:
    """Profiles with at least one catalog-visible context (same rule as `is_catalog_visible`)."""
    return SpecialistProfile.objects.filter(contexts__catalog_enabled=True).distinct()


def is_specialist_visible(profile: SpecialistProfile) -> bool:
    return profile.contexts.filter(catalog_enabled=True).exists()


def specialist_visible_exists(profile_ref: str) -> Exists:
    """`is_specialist_visible` as a subquery; `profile_ref` is the outer field holding the profile id."""
    return Exists(PracticeContext.objects.filter(specialist_id=OuterRef(profile_ref), catalog_enabled=True))
