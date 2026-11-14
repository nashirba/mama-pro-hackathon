from django.db.models import Value

from apps.catalog.models import SpecialistProfile
from apps.catalog.visibility import (
    catalog_visible_specialists,
    is_specialist_visible,
    specialist_visible_exists,
)
from tests.factories import NannyFactory, PrivateContextFactory


def test_catalog_visible_specialists(catalog_fixture):
    sp = catalog_fixture.specialists
    visible = set(catalog_visible_specialists())
    assert sp["hidden-logoped"] not in visible
    assert sp["ivanova-logoped"] in visible
    assert len(visible) == 7
    for profile in sp.values():
        assert is_specialist_visible(profile) == (profile in visible)


def test_nannies_are_not_community_specialists(db):
    nanny = NannyFactory()
    PrivateContextFactory(specialist=nanny, catalog_enabled=True)
    assert nanny not in set(catalog_visible_specialists())
    assert not is_specialist_visible(nanny)
    annotated = SpecialistProfile.objects.annotate(ref=Value(nanny.pk)).annotate(v=specialist_visible_exists("ref")).get(pk=nanny.pk)
    assert annotated.v is False
