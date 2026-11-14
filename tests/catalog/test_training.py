import datetime

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.models import ProfileCategory, ServiceKind, Training
from apps.catalog.visibility import nanny_eligible
from tests.factories import (
    NannyFactory,
    NannyServiceFactory,
    PrivateContextFactory,
    ServiceFactory,
    SpecialistFactory,
    TrainingFactory,
)


@pytest.fixture
def nanny(db, reference, kato_demo):
    return NannyFactory()


def test_training_is_translatable_and_ordered(nanny):
    TrainingFactory(profile=nanny, title="Первая помощь детям", hours=16, is_first_aid=True)
    TrainingFactory(profile=nanny, title="Основы РАС", hours=72)
    training = Training.objects.language("ru").get(translations__title="Основы РАС")
    training.create_translation("kk", title="АСБ негіздері")
    assert Training.objects.language("kk").get(pk=training.pk).title == "АСБ негіздері"
    assert [t.hours for t in nanny.trainings.all()] == [16, 72]


def test_training_hours_sums_trainings(nanny):
    assert nanny.training_hours == 0
    TrainingFactory(profile=nanny, hours=16, is_first_aid=True)
    TrainingFactory(profile=nanny, hours=72)
    assert nanny.training_hours == 88


def test_category_defaults_to_specialist(db):
    profile = SpecialistFactory()
    assert profile.category == ProfileCategory.SPECIALIST and not profile.is_nanny
    assert NannyFactory().is_nanny


def test_nanny_eligible_with_training_first_aid_and_record(nanny):
    TrainingFactory(profile=nanny, hours=16, is_first_aid=True)
    TrainingFactory(profile=nanny, hours=72)
    assert nanny_eligible(nanny)


def test_nanny_not_eligible_without_trainings(nanny):
    assert not nanny_eligible(nanny)


def test_nanny_not_eligible_without_first_aid(nanny):
    TrainingFactory(profile=nanny, hours=72)
    assert not nanny_eligible(nanny)


def test_nanny_not_eligible_without_criminal_record_certificate(db, reference):
    nanny = NannyFactory(criminal_record_issued_on=None)
    TrainingFactory(profile=nanny, hours=16, is_first_aid=True)
    assert not nanny_eligible(nanny)


def test_training_without_certificate_number_does_not_count(nanny):
    TrainingFactory(profile=nanny, hours=16, is_first_aid=True, certificate_number=" ")
    assert not nanny_eligible(nanny)


def test_specialist_profile_may_have_types(db, reference):
    SpecialistFactory(specialist_types=["logoped"]).full_clean()


def test_nanny_service_valid(nanny):
    NannyServiceFactory(context__specialist=nanny).full_clean()


@pytest.mark.parametrize(
    "changes,field",
    [
        ({"kind": "consultation"}, "kind"),
        ({"formats": ["in_person"]}, "formats"),
        ({"formats": ["home_visit", "online"]}, "formats"),
        ({"price_hour": None, "price_night": None, "price_month": None}, "price_hour"),
        ({"price_session": 5000}, "price_session"),
    ],
)
def test_nanny_service_invalid(nanny, kato_demo, changes, field):
    service = NannyServiceFactory(context__specialist=nanny)
    for name, value in changes.items():
        if name == "kind":
            value = ServiceKind.objects.get(slug=value)
        setattr(service, name, value)
    with pytest.raises(ValidationError) as exc:
        service.full_clean()
    assert field in exc.value.message_dict


def test_specialist_service_rejects_nanny_kind_and_prices(db, reference):
    service = ServiceFactory(context=PrivateContextFactory())
    service.full_clean()
    service.price_hour = 3000
    with pytest.raises(ValidationError) as exc:
        service.full_clean()
    assert "price_hour" in exc.value.message_dict
    service.price_hour = None
    service.kind = ServiceKind.objects.get(slug="childcare")
    with pytest.raises(ValidationError) as exc:
        service.full_clean()
    assert "kind" in exc.value.message_dict


def test_criminal_record_date_is_stored(db, reference):
    nanny = NannyFactory(criminal_record_issued_on=datetime.date(2026, 3, 1))
    nanny.refresh_from_db()
    assert nanny.criminal_record_issued_on == datetime.date(2026, 3, 1)
