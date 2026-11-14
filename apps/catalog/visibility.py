from .models import PracticeContext, SpecialistProfile


def is_catalog_visible(context: PracticeContext) -> bool:
    """The single place that decides whether a practice context is shown in the catalog."""
    return context.catalog_enabled


def nanny_eligible(profile: SpecialistProfile) -> bool:
    """The single place of the nanny rule: a course with a certificate, a pediatric first aid course among them,
    and a criminal record certificate. Uses the prefetched `trainings` when there are any."""
    certified = [t for t in profile.trainings.all() if t.certificate_number.strip()]
    return bool(certified) and any(t.is_first_aid for t in certified) and profile.criminal_record_issued_on is not None
