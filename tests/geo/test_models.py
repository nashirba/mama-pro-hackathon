import pytest
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.geo.models import KatoNode


def test_descendants_include_districts(db, kato_demo):
    ids = kato_demo["almaty"].descendant_ids()
    assert set(ids) == {kato_demo[s].id for s in ("almaty", "almalinskiy", "medeuskiy", "bostandykskiy")}


def test_ancestor_ids_nearest_first(db, kato_demo):
    assert kato_demo["almalinskiy"].ancestor_ids() == [kato_demo["almaty"].id]
    assert kato_demo["aktobe-almatinskiy"].ancestor_ids() == [kato_demo["aktobe"].id, kato_demo["aktyubinskaya-oblast"].id]


def test_city_of_nodes(db, kato_demo):
    assert kato_demo["almalinskiy"].city() == kato_demo["almaty"]
    assert kato_demo["almaty"].city() == kato_demo["almaty"]
    assert kato_demo["rural-demo"].city() is None


def test_kk_name_and_locative(db, kato_demo):
    n = KatoNode.objects.language("kk").get(slug="karaganda")
    assert n.name == "Қарағанды" and n.name_locative == "Қарағандыдағы"
    assert KatoNode.objects.language("ru").get(slug="astana").name_locative == "в Астане"


def test_slug_unique(db, kato_demo):
    with pytest.raises(IntegrityError), transaction.atomic():
        KatoNode.objects.create(code="999", level="city", slug="almaty")


def test_load_kato_demo_idempotent(db):
    call_command("load_kato_demo")
    n = KatoNode.objects.count()
    call_command("load_kato_demo")
    assert KatoNode.objects.count() == n == 18
