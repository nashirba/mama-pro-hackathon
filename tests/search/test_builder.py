from collections import Counter

from apps.search.builder import rebuild_all, rebuild_for_context
from apps.search.models import SearchOffer
from tests.factories import AddressFactory, PrivateContextFactory, ServiceFactory


def test_offer_per_address_plus_online(db, kato_demo):
    a1, a2 = AddressFactory(kato=kato_demo["almalinskiy"]), AddressFactory(kato=kato_demo["medeuskiy"])
    svc = ServiceFactory(formats=["in_person", "online"], addresses=[a1, a2])
    rebuild_for_context(svc.context_id)
    offers = SearchOffer.objects.filter(service=svc)
    assert offers.count() == 3 and sorted(o.is_online for o in offers) == [False, False, True]
    online = offers.get(is_online=True)
    assert online.kato_ids == [] and online.address is None and online.point is None and online.formats == ["online"]


def test_home_visit_row_uses_area_and_no_point(db, kato_demo):
    svc = ServiceFactory(formats=["home_visit"], home_visit_area=kato_demo["almalinskiy"])
    rebuild_for_context(svc.context_id)
    o = SearchOffer.objects.get(service=svc)
    assert set(o.kato_ids) == {kato_demo["almalinskiy"].id, kato_demo["almaty"].id}
    assert o.point is None and o.address is None and o.formats == ["home_visit"]


def test_invisible_context_has_no_offers(db):
    svc = ServiceFactory(formats=["online"], context=PrivateContextFactory(catalog_enabled=False))
    assert rebuild_for_context(svc.context_id) == 0 and not SearchOffer.objects.filter(service=svc).exists()
    visible = ServiceFactory(formats=["online"], context=PrivateContextFactory(catalog_enabled=True))
    assert rebuild_for_context(visible.context_id) == 1 and SearchOffer.objects.filter(service=visible).count() == 1


def test_kato_ids_include_ancestors(db, kato_demo):
    svc = ServiceFactory(formats=["in_person"], addresses=[AddressFactory(kato=kato_demo["almalinskiy"])])
    rebuild_for_context(svc.context_id)
    assert set(SearchOffer.objects.get(service=svc).kato_ids) == {kato_demo["almalinskiy"].id, kato_demo["almaty"].id}


def test_rebuild_on_service_save(db, kato_demo, django_capture_on_commit_callbacks):
    svc = ServiceFactory(formats=["in_person"], price_session=8000, addresses=[AddressFactory(kato=kato_demo["almaty"])])
    rebuild_for_context(svc.context_id)
    with django_capture_on_commit_callbacks(execute=True):
        svc.price_session = 9000; svc.save()
    assert SearchOffer.objects.get(service=svc).price_session == 9000


def test_rebuild_is_idempotent(db, catalog_fixture):
    assert rebuild_all() == 9 and rebuild_all() == 9 and SearchOffer.objects.count() == 9


def test_roster_row_counts(db, catalog_fixture):
    counts = Counter(SearchOffer.objects.values_list("specialist__slug", flat=True))
    assert counts == {"ivanova-logoped": 1, "serikov-aba": 3, "kim-neuro": 1, "nurlan-online": 1, "bekova-karaganda": 1, "omarova-home": 1, "sergeev-free": 1}


def test_search_norm_has_kk_kato_name_without_special_letters(db, catalog_fixture):
    o = SearchOffer.objects.get(specialist__slug="bekova-karaganda")
    assert "караганды" in o.search_norm and "караганда" in o.search_norm
