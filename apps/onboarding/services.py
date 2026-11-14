"""The application lifecycle: draft → submitted → (needs changes → submitted)* → approved or rejected."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone, translation
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from apps.accounts.models import Role, User
from apps.catalog.models import (
    CHILDCARE_KIND,
    Format,
    PracticeContext,
    ProfileCategory,
    Service,
    ServiceKind,
    SpecialistProfile,
    Training,
    VerificationLevel,
)
from apps.demo.generators import transliterate
from apps.geo.models import Address

from .models import Application, ApplicationDocument, BlockedPhone

SPECIALIST_SERVICE_KIND = "session"
NANNY_SERVICE_DURATION_MIN = 60
# Approval means every check passed: identity, education, qualification and the criminal record certificate.
ALL_LEVELS = [level.value for level in VerificationLevel]


def is_phone_blocked(phone: str) -> bool:
    return BlockedPhone.objects.filter(phone=phone).exists()


def start_application(user: User) -> Application:
    """Called once the user has chosen the specialist or nanny role."""
    category = ProfileCategory.NANNY if user.role == Role.NANNY else ProfileCategory.SPECIALIST
    application, _created = Application.objects.get_or_create(user=user, defaults={"category": category})
    return application


def missing_for_submit(app: Application) -> list[str]:
    """What still has to be filled before the application can go to review. Empty = ready."""
    missing = []

    def need(condition, message):
        if not condition:
            missing.append(message)

    need(app.practice_start_year, _("Год начала работы"))
    need(app.age_min is not None and app.age_max is not None, _("Возраст детей"))
    need(app.languages.exists(), _("Языки общения"))
    need(app.area_id, _("Город или район"))
    need(app.bio.strip(), _("О себе"))
    documents = set(app.documents.values_list("kind", flat=True))
    if app.is_nanny:
        need(app.price_hour or app.price_month, _("Цена за час или за месяц"))
        need(app.criminal_record_issued_on, _("Дата выдачи справки о несудимости"))
        need(ApplicationDocument.Kind.CRIMINAL_RECORD in documents, _("Скан справки о несудимости"))
        courses = [c for c in app.courses.all() if c.certificate_number.strip()]
        need(courses, _("Курс с номером сертификата"))
        need(any(c.is_first_aid for c in courses), _("Курс первой помощи детям"))
    else:
        need(app.specialist_types.exists(), _("Специализация"))
        need(app.education.strip(), _("Образование"))
        need(app.formats, _("Формат работы"))
        need(app.price_session, _("Цена за занятие"))
        need(app.duration_min, _("Длительность занятия"))
        if Format.IN_PERSON in app.formats:
            need(app.street.strip() and app.building.strip(), _("Адрес приёма"))
        need(ApplicationDocument.Kind.DIPLOMA in documents, _("Скан диплома"))
    return missing


def submit(app: Application) -> None:
    if not app.is_editable:
        raise ValidationError(_("Анкету сейчас нельзя отправить"))
    missing = missing_for_submit(app)
    if missing:
        raise ValidationError(missing)
    app.status = Application.Status.SUBMITTED
    app.submitted_at = timezone.now()
    app.save(update_fields=["status", "submitted_at"])


def request_changes(app: Application, comment: str, moderator: User) -> None:
    _decide(app, Application.Status.NEEDS_CHANGES, comment, moderator)


def reject(app: Application, comment: str, moderator: User) -> None:
    with transaction.atomic():
        _decide(app, Application.Status.REJECTED, comment, moderator)
        BlockedPhone.objects.get_or_create(phone=app.user.phone, defaults={"application": app})


@transaction.atomic
def approve(app: Application, moderator: User) -> SpecialistProfile:
    """Create the catalog profile, its private practice context and one service; the search index follows by signals."""
    if app.status != Application.Status.SUBMITTED:
        raise ValidationError(_("Одобрить можно только анкету на проверке"))
    profile = _create_profile(app)
    context = PracticeContext.objects.create(specialist=profile, kind=PracticeContext.Kind.PRIVATE, catalog_enabled=True)
    _create_service(app, context)
    app.profile = profile
    _decide(app, Application.Status.APPROVED, app.moderator_comment, moderator)
    return profile


def _decide(app: Application, status: str, comment: str, moderator: User) -> None:
    if app.status != Application.Status.SUBMITTED:
        raise ValidationError(_("Решение принимается только по анкете на проверке"))
    app.status = status
    app.moderator_comment = comment
    app.decided_at = timezone.now()
    app.decided_by = moderator
    app.save()


def _unique_slug(user: User) -> str:
    base = slugify(transliterate(f"{user.first_name} {user.last_name}")) or "specialist"
    slug, n = base, 1
    while SpecialistProfile.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    return slug


def _create_profile(app: Application) -> SpecialistProfile:
    user = app.user
    profile = SpecialistProfile(
        user=user,
        slug=_unique_slug(user),
        category=app.category,
        display_name=f"{user.last_name} {user.first_name}",
        practice_start_year=app.practice_start_year,
        age_min=app.age_min,
        age_max=app.age_max,
        formats=[Format.HOME_VISIT] if app.is_nanny else list(app.formats),
        whatsapp_phone=user.phone,
        public_phone=user.phone,
        demo_verification_levels=list(ALL_LEVELS),
        criminal_record_issued_on=app.criminal_record_issued_on if app.is_nanny else None,
    )
    profile.set_current_language("ru")
    profile.bio = app.bio
    profile.approach = app.approach
    profile.availability = app.availability
    profile.save()
    if not app.is_nanny:
        profile.specialist_types.set(app.specialist_types.all())
        profile.methods.set(app.methods.all())
    profile.conditions.set(app.conditions.all())
    profile.languages.set(app.languages.all())
    for course in app.courses.all():
        training = Training(
            profile=profile,
            issuer=course.issuer,
            year=course.year,
            hours=course.hours,
            certificate_number=course.certificate_number,
            is_first_aid=course.is_first_aid,
        )
        training.set_current_language("ru")
        training.title = course.title
        training.save()
    return profile


def _create_service(app: Application, context: PracticeContext) -> Service:
    if app.is_nanny:
        service = Service(
            context=context,
            kind=ServiceKind.objects.get(slug=CHILDCARE_KIND),
            duration_min=NANNY_SERVICE_DURATION_MIN,
            formats=[Format.HOME_VISIT],
            price_hour=app.price_hour,
            price_month=app.price_month,
            home_visit_area=app.area,
        )
        title = gettext_noop("Услуги няни")
    else:
        service = Service(
            context=context,
            kind=ServiceKind.objects.get(slug=SPECIALIST_SERVICE_KIND),
            duration_min=app.duration_min,
            formats=list(app.formats),
            price_session=app.price_session,
            home_visit_area=app.area if Format.HOME_VISIT in app.formats else None,
        )
        title = gettext_noop("Индивидуальное занятие")
    for lang in ("ru", "kk"):
        with translation.override(lang):
            service.set_current_language(lang)
            service.title = _(title)
    service.save()
    if not app.is_nanny and Format.IN_PERSON in app.formats:
        service.addresses.add(_address(app))
    return service


def _address(app: Application) -> Address:
    """The point is the centre of the district or city: no geocoder in the demo; a moderator can move it in admin."""
    node = app.area
    while node is not None and node.center is None:
        node = node.parent
    if node is None:
        raise ValidationError(_("У выбранного района нет координат центра"))
    return Address.objects.create(kato=app.area, street=app.street, building=app.building, point=node.center)
