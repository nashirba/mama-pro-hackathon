from collections import Counter

from apps.search.builder import rebuild_all, rebuild_for_context
from apps.search.models import SearchOffer
from tests.factories import (
    AddressFactory,
    NannyFactory,
    NannyServiceFactory,
    PrivateContextFactory,
    ServiceFactory,
    TrainingFactory,
)


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


def _eligible_nanny_service(**service):
    nanny = NannyFactory()
    TrainingFactory(profile=nanny, hours=16, is_first_aid=True)
    TrainingFactory(profile=nanny, hours=72)
    return NannyServiceFactory(context__specialist=nanny, **service)


def test_nanny_offer_carries_category_prices_and_training_hours(db, reference, kato_demo):
    svc = _eligible_nanny_service(price_hour=3000, price_night=15000, price_month=200000)
    rebuild_for_context(svc.context_id)
    o = SearchOffer.objects.get(service=svc)
    assert (o.category, o.price_hour, o.price_night, o.price_month, o.training_hours) == ("nanny", 3000, 15000, 200000, 88)
    assert o.formats == ["home_visit"] and o.specialist_type_ids == []


def test_specialist_offer_has_specialist_category(db, kato_demo):
    svc = ServiceFactory(formats=["online"])
    rebuild_for_context(svc.context_id)
    o = SearchOffer.objects.get(service=svc)
    assert (o.category, o.price_hour, o.price_night, o.training_hours) == ("specialist", None, None, 0)


def test_ineligible_nanny_has_no_offers(db, reference, kato_demo):
    svc = NannyServiceFactory()
    TrainingFactory(profile=svc.context.specialist, hours=72)  # no first aid course
    assert rebuild_for_context(svc.context_id) == 0


def test_training_save_and_delete_rebuild_offers(db, reference, kato_demo, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        svc = NannyServiceFactory()
        nanny = svc.context.specialist
    assert not SearchOffer.objects.filter(service=svc).exists()
    with django_capture_on_commit_callbacks(execute=True):
        first_aid = TrainingFactory(profile=nanny, hours=16, is_first_aid=True)
    assert SearchOffer.objects.get(service=svc).training_hours == 16
    with django_capture_on_commit_callbacks(execute=True):
        first_aid.delete()
    assert not SearchOffer.objects.filter(service=svc).exists()


def test_criminal_record_change_rebuilds_offers(db, reference, kato_demo, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        svc = _eligible_nanny_service()
    assert SearchOffer.objects.filter(service=svc).exists()
    nanny = svc.context.specialist
    with django_capture_on_commit_callbacks(execute=True):
        nanny.criminal_record_issued_on = None
        nanny.save()
    assert not SearchOffer.objects.filter(service=svc).exists()
