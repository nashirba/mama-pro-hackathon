from apps.catalog.admin import SpecialistProfileForm
from apps.catalog.models import SpecialistType
from tests.factories import NannyFactory


def test_admin_form_rejects_specialist_types_for_nanny(db, reference):
    nanny = NannyFactory()
    specialist_type = SpecialistType.objects.first()
    form = SpecialistProfileForm(data={"category": "nanny", "specialist_types": [specialist_type.pk]}, instance=nanny)
    assert not form.is_valid()
    assert "specialist_types" in form.errors


def test_admin_form_accepts_nanny_without_specialist_types(db, reference):
    form = SpecialistProfileForm(data={"category": "nanny"}, instance=NannyFactory())
    form.is_valid()
    assert "specialist_types" not in form.errors


def test_admin_form_allows_specialist_types_for_specialist(db, reference):
    specialist_type = SpecialistType.objects.first()
    form = SpecialistProfileForm(data={"category": "specialist", "specialist_types": [specialist_type.pk]})
    form.is_valid()
    assert "specialist_types" not in form.errors
