import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import Role
from apps.catalog.models import CommunicationLanguage, SpecialistType
from apps.onboarding.models import Application, ApplicationCourse, ApplicationDocument
from apps.onboarding.services import start_application
from tests.factories import UserFactory

PDF = b"%PDF-1.4 demo"


def pdf(name="diploma.pdf"):
    return SimpleUploadedFile(name, PDF, content_type="application/pdf")


@pytest.fixture
def specialist_user(db):
    return UserFactory(phone="+77011112233", last_name="Серикова", first_name="Алия", role=Role.SPECIALIST)


@pytest.fixture
def nanny_user(db):
    return UserFactory(phone="+77011112244", last_name="Касымова", first_name="Дана", role=Role.NANNY)


@pytest.fixture
def staff(db):
    return UserFactory(phone="+77019990000", is_staff=True, is_superuser=True)


@pytest.fixture
def ready_specialist(specialist_user, reference, kato_demo) -> Application:
    """A specialist's application with everything filled, still a draft."""
    app = start_application(specialist_user)
    app.practice_start_year, app.age_min, app.age_max = 2015, 3, 10
    app.education, app.bio = "КазНПУ, логопедия, 2014", "Работаю с детьми с ЗРР"
    app.formats = ["in_person", "online"]
    app.area = kato_demo["almalinskiy"]
    app.street, app.building = "Абая", "15"
    app.duration_min, app.price_session = 45, 9000
    app.save()
    app.specialist_types.set(SpecialistType.objects.filter(slug="logoped"))
    app.languages.set(CommunicationLanguage.objects.filter(code="ru"))
    ApplicationDocument.objects.create(
        application=app, kind="diploma", filename="d.pdf", content_type="application/pdf", data=PDF
    )
    return app


@pytest.fixture
def ready_nanny(nanny_user, reference, kato_demo) -> Application:
    app = start_application(nanny_user)
    app.practice_start_year, app.age_min, app.age_max = 2018, 1, 7
    app.bio, app.availability = "Няня с опытом", "Будни"
    app.area = kato_demo["medeuskiy"]
    app.price_hour = 2500
    app.criminal_record_issued_on = "2026-10-01"
    app.save()
    app.languages.set(CommunicationLanguage.objects.filter(code="ru"))
    ApplicationDocument.objects.create(
        application=app, kind="criminal_record", filename="c.pdf", content_type="application/pdf", data=PDF
    )
    ApplicationCourse.objects.create(
        application=app, title="Первая помощь детям", issuer="Красный Полумесяц", year=2025, hours=16,
        certificate_number="FA-1", is_first_aid=True,
    )
    return app
