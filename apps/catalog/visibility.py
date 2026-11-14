from django.db.models import Exists, OuterRef, Q, QuerySet

from .models import PracticeContext, ProfileCategory, SpecialistProfile, Training


def is_catalog_visible(context: PracticeContext) -> bool:
    """The single place that decides whether a practice context is shown in the catalog."""
    return context.catalog_enabled


def nanny_eligible(profile: SpecialistProfile) -> bool:
    """The single place of the nanny rule: a course with a certificate, a pediatric first aid course among them,
    and a criminal record certificate. Uses the prefetched `trainings` when there are any."""
    certified = [t for t in profile.trainings.all() if t.certificate_number.strip()]
    return bool(certified) and any(t.is_first_aid for t in certified) and profile.criminal_record_issued_on is not None


# Community links and the review picker cover the specialist category only: nannies have their own page and rule.
def catalog_visible_specialists() -> QuerySet[SpecialistProfile]:
    """Specialist profiles with at least one catalog-visible context (same rule as `is_catalog_visible`)."""
    return SpecialistProfile.objects.filter(category=ProfileCategory.SPECIALIST, contexts__catalog_enabled=True).distinct()


def is_specialist_visible(profile: SpecialistProfile) -> bool:
    return profile.category == ProfileCategory.SPECIALIST and profile.contexts.filter(catalog_enabled=True).exists()


def specialist_visible_exists(profile_ref: str) -> Exists:
    """`is_specialist_visible` as a subquery; `profile_ref` is the outer field holding the profile id."""
    return Exists(
        PracticeContext.objects.filter(
            specialist_id=OuterRef(profile_ref), specialist__category=ProfileCategory.SPECIALIST, catalog_enabled=True
        )
    )


def _profile_visible_q() -> Q:
    """`is_catalog_visible` for any category, plus `nanny_eligible` for a nanny, as a filter on SpecialistProfile."""
    certified = Training.objects.filter(profile=OuterRef("pk")).exclude(certificate_number__regex=r"^\s*$")
    nanny_ok = (
        Q(category=ProfileCategory.NANNY, criminal_record_issued_on__isnull=False)
        & Exists(certified)
        & Exists(certified.filter(is_first_aid=True))
    )
    shown = Exists(PracticeContext.objects.filter(specialist=OuterRef("pk"), catalog_enabled=True))
    return shown & (Q(category=ProfileCategory.SPECIALIST) | nanny_ok)


def catalog_visible_profiles() -> QuerySet[SpecialistProfile]:
    """Specialists and nannies that have a public page: the ones parents can review."""
    return SpecialistProfile.objects.filter(_profile_visible_q())


def profile_visible_exists(profile_ref: str) -> Exists:
    """`catalog_visible_profiles` as a subquery; `profile_ref` is the outer field holding the profile id."""
    return Exists(catalog_visible_profiles().filter(pk=OuterRef(profile_ref)))
