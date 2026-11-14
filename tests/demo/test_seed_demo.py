import datetime
import json

import pytest
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.measure import D
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Method,
    ProfileCategory,
    Service,
    SpecialistProfile,
    SpecialistType,
    Training,
)
from apps.catalog.visibility import nanny_eligible
from apps.demo.generators import (
    DATA_DIR,
    LOGIN_PHONE_PREFIX,
    NANNY_LOGIN_PHONE_PREFIX,
    load_json,
)
from apps.geo.models import Address, KatoNode
from apps.search.models import SearchOffer
from apps.search.query import SearchParams, search

STOP_PHRASES = ["вылеч", "излеч", "гарантир", "самый эффективный", "самый лучший", "уникальн", "снимем диагноз", "100%"]


def test_seed_demo_creates_searchable_catalog(db):
    call_command("seed_demo", specialists=30, seed=1)
    assert SpecialistProfile.objects.filter(category=ProfileCategory.SPECIALIST).count() == 30
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
        Training.objects.count(),
    )
    before = counts()
    call_command("seed_demo", specialists=30, seed=1)
    assert counts() == before


def test_seed_demo_has_online_only_and_kk_bios(db):
    call_command("seed_demo", specialists=30, seed=1)
    specialists = SpecialistProfile.objects.filter(category=ProfileCategory.SPECIALIST)
    online_only = [p for p in specialists if p.formats == ["online"]]
    assert len(online_only) == 6  # i % 5 == 4
    assert all(not s.addresses.exists() for p in online_only for s in p.services())
    assert sum(p.has_translation("kk") for p in specialists) == 15  # even i
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
    call_command("seed_demo", specialists=10, nannies=4, seed=1)
    catalog_users = User.objects.filter(phone__startswith=LOGIN_PHONE_PREFIX) | User.objects.filter(
        phone__startswith=NANNY_LOGIN_PHONE_PREFIX
    )
    assert catalog_users.count() == 14
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


def test_seed_demo_nannies_are_a_separate_category(db):
    call_command("seed_demo", specialists=10, nannies=12, seed=1)
    nannies = SpecialistProfile.objects.filter(category=ProfileCategory.NANNY).prefetch_related("trainings", "specialist_types")
    assert nannies.count() == 12
    assert all(not n.specialist_types.all() and n.formats == ["home_visit"] for n in nannies)
    for n in nannies:
        (service,) = n.services()
        assert service.kind.slug == "childcare" and service.formats == ["home_visit"] and service.price_session is None
        assert service.home_visit_area.level == "district"
        service.full_clean()
        n.full_clean()


def test_seed_demo_hides_nannies_that_break_the_rule(db):
    call_command("seed_demo", specialists=0, nannies=24, seed=1)
    nannies = list(SpecialistProfile.objects.filter(category=ProfileCategory.NANNY).prefetch_related("trainings"))
    hidden = [n for n in nannies if not nanny_eligible(n)]
    assert len(hidden) == 3
    assert {bool(n.criminal_record_issued_on) for n in hidden} == {True, False}  # no record, and no first aid course
    shown = search(SearchParams(section="nannies"))
    assert shown.total == 21
    assert not {c.specialist.pk for c in shown.cards} & {n.pk for n in hidden}


def test_seed_demo_nanny_trainings_and_prices_in_ranges(db):
    call_command("seed_demo", specialists=0, nannies=24, seed=1)
    for t in Training.objects.all():
        assert (16 <= t.hours <= 40) if t.is_first_aid else (24 <= t.hours <= 120)
        assert t.certificate_number and t.issuer and t.safe_translation_getter("title", language_code="ru")
    for s in Service.objects.all():
        assert 2000 <= s.price_hour <= 4000
        assert s.price_night is None or 12000 <= s.price_night <= 25000
        assert s.price_month is None or 180000 <= s.price_month <= 300000
    eligible = [n for n in SpecialistProfile.objects.prefetch_related("trainings") if nanny_eligible(n)]
    assert all(1 <= len([t for t in n.trainings.all() if not t.is_first_aid]) <= 3 for n in eligible)
    assert any(n.has_translation("kk") and n.safe_translation_getter("availability", language_code="kk") for n in eligible)


def test_seed_demo_nannies_do_not_change_specialists(db):
    snapshot = lambda: list(
        SpecialistProfile.objects.filter(category=ProfileCategory.SPECIALIST).order_by("slug").values_list("slug", "display_name", "age_min")
    )
    call_command("seed_demo", specialists=12, nannies=0, seed=3)
    without = snapshot()
    call_command("seed_demo", specialists=12, nannies=6, seed=3)
    assert snapshot() == without


def test_nanny_data_uses_existing_condition_slugs_and_no_stop_phrases(db):
    call_command("seed_reference_data")
    data = load_json("nannies.json")
    assert set(data["conditions"]) <= set(DevelopmentalCondition.objects.values_list("slug", flat=True))
    text = (DATA_DIR / "nannies.json").read_text(encoding="utf-8").lower()
    assert not [p for p in STOP_PHRASES if p in text]


def test_seed_demo_criminal_records_are_in_the_past(db):
    call_command("seed_demo", specialists=0, nannies=24, seed=1)
    today = timezone.localdate()
    dates = [n.criminal_record_issued_on for n in SpecialistProfile.objects.filter(category=ProfileCategory.NANNY)]
    assert any(dates) and all(d <= today - datetime.timedelta(days=30) for d in dates if d)
