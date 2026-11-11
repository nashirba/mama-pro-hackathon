import json

import pytest
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import F

from apps.accounts.models import User
from apps.catalog.models import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Method,
    Service,
    SpecialistProfile,
    SpecialistType,
)
from apps.demo.generators import DATA_DIR, load_json
from apps.geo.models import Address, KatoNode
from apps.search.models import SearchOffer
from apps.search.query import SearchParams, search

STOP_PHRASES = ["вылеч", "излеч", "гарантир", "самый эффективный", "самый лучший", "уникальн", "снимем диагноз", "100%"]


def test_seed_demo_creates_searchable_catalog(db):
    call_command("seed_demo", specialists=30, seed=1)
    assert SpecialistProfile.objects.count() == 30
    for slug in ["almaty", "astana", "shymkent"]:  # 24 in-person specialists cover all 10 districts deterministically
        node = KatoNode.objects.get(slug=slug)
        assert search(SearchParams(kato_id=node.id)).total > 0


def test_seed_demo_idempotent(db):
    call_command("seed_demo", specialists=30, seed=1)
    counts = lambda: (
        User.objects.count(),
        SpecialistProfile.objects.count(),
        Service.objects.count(),
        Address.objects.count(),
        SearchOffer.objects.count(),
    )
    before = counts()
    call_command("seed_demo", specialists=30, seed=1)
    assert counts() == before


def test_seed_demo_has_online_only_and_kk_bios(db):
    call_command("seed_demo", specialists=30, seed=1)
    online_only = [p for p in SpecialistProfile.objects.all() if p.formats == ["online"]]
    assert len(online_only) == 6  # i % 5 == 4
    assert all(not s.addresses.exists() for p in online_only for s in p.services())
    assert sum(p.has_translation("kk") for p in SpecialistProfile.objects.all()) == 15  # even i
    for p in SpecialistProfile.objects.all():
        if p.has_translation("kk"):
            assert p.safe_translation_getter("bio", language_code="kk") and p.safe_translation_getter("approach", language_code="kk")


def test_seed_demo_covers_every_demo_district(db):
    call_command("seed_demo", specialists=30, seed=1)
    districts = set(KatoNode.objects.filter(level="district").values_list("id", flat=True))
    assert set(Address.objects.values_list("kato_id", flat=True)) == districts


def test_seed_demo_addresses_within_3km_of_district_center(db):
    call_command("seed_demo", specialists=30, seed=1)
    far = Address.objects.exclude(kato__center__isnull=True).annotate(d=Distance("point", F("kato__center"))).filter(d__gt=D(m=3000))
    assert Address.objects.exists() and not far.exists()


def test_seed_demo_uses_demo_contact_phone(db, settings):
    settings.DEMO_CONTACT_PHONE = "+77012223344"
    call_command("seed_demo", specialists=10, seed=1)
    assert set(SpecialistProfile.objects.values_list("whatsapp_phone", "public_phone")) == {("+77012223344", "+77012223344")}


def test_seed_demo_empty_contact_phone_leaves_buttons_disabled(db, settings):
    settings.DEMO_CONTACT_PHONE = ""
    call_command("seed_demo", specialists=10, seed=1)
    assert set(SpecialistProfile.objects.values_list("whatsapp_phone", flat=True)) == {""}


def test_seed_demo_rejects_invalid_contact_phone(db, settings):
    settings.DEMO_CONTACT_PHONE = "12345"
    with pytest.raises(CommandError):
        call_command("seed_demo", specialists=10, seed=1)


def test_seed_demo_users_are_not_staff(db):
    call_command("seed_demo", specialists=10, seed=1)
    assert User.objects.count() == 10
    assert not User.objects.filter(is_staff=True).exists() and not User.objects.filter(is_superuser=True).exists()
    assert not any(u.has_usable_password() for u in User.objects.all())


def test_demo_data_uses_existing_reference_slugs_and_no_stop_phrases(db):
    call_command("seed_reference_data")
    bios = load_json("bios.json")
    known = {
        "types": set(SpecialistType.objects.values_list("slug", flat=True)),
        "conditions": set(DevelopmentalCondition.objects.values_list("slug", flat=True)),
        "methods": set(Method.objects.values_list("slug", flat=True)),
    }
    for a in bios["archetypes"]:
        assert set(a["types"]) <= known["types"] and set(a["conditions"]) <= known["conditions"] and set(a["methods"]) <= known["methods"]
    assert set(CommunicationLanguage.objects.values_list("code", flat=True)) >= {"kk", "ru", "en"}
    text = (DATA_DIR / "bios.json").read_text(encoding="utf-8").lower()
    assert not [p for p in STOP_PHRASES if p in text]
    assert json.loads(text)  # the file stays valid JSON
