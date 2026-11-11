import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.catalog.models import DevelopmentalCondition, Method
from apps.catalog.visibility import is_catalog_visible
from tests.factories import PrivateContextFactory, ServiceFactory, SpecialistFactory


def test_service_inherits_profile_attrs(db, reference):
    s = SpecialistFactory(age_min=0, age_max=18, conditions=["ras"], methods=["aba"], languages=["ru"], specialist_types=["logoped"])
    attrs = ServiceFactory(context=PrivateContextFactory(specialist=s)).effective_attrs()
    assert (attrs.age_min, attrs.age_max) == (0, 18)
    assert attrs.condition_ids == [DevelopmentalCondition.objects.get(slug="ras").id]
    assert attrs.language_codes == ["ru"] and attrs.method_ids == [Method.objects.get(slug="aba").id]


def test_service_narrows_attrs(db, reference):
    s = SpecialistFactory(age_min=0, age_max=18, conditions=["ras", "adhd"])
    svc = ServiceFactory(context=PrivateContextFactory(specialist=s), age_min=3, age_max=7, conditions=["ras"])
    attrs = svc.effective_attrs()
    assert (attrs.age_min, attrs.age_max) == (3, 7)
    assert attrs.condition_ids == [DevelopmentalCondition.objects.get(slug="ras").id]


def test_one_private_context_per_specialist(db):
    s = SpecialistFactory()
    PrivateContextFactory(specialist=s)
    with pytest.raises(IntegrityError), transaction.atomic():
        PrivateContextFactory(specialist=s)


def test_experience_years(db, freezer):
    freezer.move_to("2026-11-10")
    assert SpecialistFactory(practice_start_year=2016).experience_years == 10


def test_invisible_without_flag(db):
    assert is_catalog_visible(PrivateContextFactory(catalog_enabled=False)) is False
    assert is_catalog_visible(PrivateContextFactory(catalog_enabled=True)) is True


def test_home_visit_requires_area(db, kato_demo):
    svc = ServiceFactory.build(formats=["home_visit"], home_visit_area=None)
    with pytest.raises(ValidationError) as e:
        svc.full_clean(exclude=["context", "kind"])
    assert "home_visit_area" in e.value.message_dict
    svc.home_visit_area = kato_demo["almaty"]
    svc.full_clean(exclude=["context", "kind"])      # не бросает


def test_free_service_has_no_price(db):
    svc = ServiceFactory.build(is_free=True, price_session=0)
    with pytest.raises(ValidationError) as e:
        svc.full_clean(exclude=["context", "kind"])
    assert "price_session" in e.value.message_dict


def test_whatsapp_phone_normalized(db):
    s = SpecialistFactory.build(whatsapp_phone="8 701 123 45 67")
    s.clean()
    assert s.whatsapp_phone == "+77011234567"


def test_age_range_validated(db):
    s = SpecialistFactory.build(age_min=10, age_max=3)
    with pytest.raises(ValidationError):
        s.full_clean(exclude=["user", "photo"])
