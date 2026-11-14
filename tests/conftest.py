import datetime
from dataclasses import dataclass

import pytest
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management import call_command
from django.utils import timezone, translation

from apps.catalog.models import SpecialistProfile
from apps.geo.models import Address, KatoNode
from apps.search.builder import rebuild_all
from tests.factories import (
    AddressFactory,
    NannyFactory,
    NannyServiceFactory,
    PrivateContextFactory,
    ServiceFactory,
    SpecialistFactory,
    TrainingFactory,
)


@pytest.fixture(autouse=True)
def _default_language():
    """A request to /kk/... leaves `kk` active in the thread; fixtures must not inherit it."""
    translation.activate(settings.LANGUAGE_CODE)
    yield
    translation.activate(settings.LANGUAGE_CODE)


@pytest.fixture
def kato_demo(db) -> dict[str, KatoNode]:
    call_command("load_kato_demo")
    return {n.slug: n for n in KatoNode.objects.all()}


@pytest.fixture
def address_almaty(kato_demo) -> Address:
    return Address.objects.create(kato=kato_demo["almaty"], street="Абая", building="1", point=Point(76.945465, 43.238293, srid=4326))


@pytest.fixture
def address_in_almaly_district(kato_demo) -> Address:
    return Address.objects.create(kato=kato_demo["almalinskiy"], street="Райымбека", building="2", point=Point(76.9140, 43.2530, srid=4326))


@pytest.fixture
def address_rural(kato_demo) -> Address:
    return Address.objects.create(kato=kato_demo["rural-demo"], street="Центральная", building="3", point=Point(70.0, 49.0, srid=4326))


@pytest.fixture
def reference(db) -> None:
    call_command("seed_reference_data")


@dataclass
class CatalogFixture:
    specialists: dict[str, SpecialistProfile]
    kato: dict[str, KatoNode]
    addresses: dict[str, Address]


TEST_PHONE = "+77011234567"

# slug, RU name, types, (age_min, age_max), conditions, methods, languages, experience, verification, kk, profile formats
ROSTER = [
    ("ivanova-logoped", "Иванова Анна", ["logoped"], (3, 12), ["zrr", "alalia"], ["speech-therapy"], ["ru"], 12,
     ["identity", "education", "credential"], True, ["in_person"]),
    ("serikov-aba", "Сериков Данияр", ["aba-therapist", "behavior-analyst"], (2, 10), ["ras"], ["aba", "esdm"], ["kk", "ru"], 6,
     ["identity", "education", "credential", "safety"], True, ["in_person", "online"]),
    ("kim-neuro", "Ким Елена", ["child-psychologist", "neuropsychologist"], (5, 17), ["adhd", "anxiety-behavior"],
     ["cbt", "neuro-correction", "tomatis"], ["ru"], 3, ["identity"], False, ["in_person"]),
    ("nurlan-online", "Ахметов Нурлан", ["logoped"], (4, 16), ["stuttering", "zrr"], ["speech-therapy"], ["kk", "ru"], 20,
     ["identity", "education", "credential", "safety"], True, ["online"]),
    ("bekova-karaganda", "Бекова Айгерим", ["defectologist"], (3, 10), ["zrr"], ["teacch"], ["kk"], 8,
     ["identity", "education", "credential"], True, ["in_person"]),
    ("omarova-home", "Омарова Гульнара", ["special-educator"], (3, 18), ["down-syndrome", "intellectual-disability"],
     ["parent-training"], ["ru"], 9, ["identity", "education"], False, ["home_visit"]),
    ("sergeev-free", "Сергеев Павел", ["school-psychologist"], (6, 18), ["learning-difficulties"], [], ["ru"], 2,
     ["identity", "education", "safety"], False, ["in_person"]),
    ("hidden-logoped", "Скрытов Игорь", ["logoped"], (3, 12), ["zrr"], ["speech-therapy"], ["ru"], 5,
     ["identity"], False, ["in_person"]),
]

ADDRESSES = [
    # key, kato slug, street, building, (lon, lat)
    ("almaly", "almalinskiy", "Абая", "10", (76.9100, 43.2510)),
    ("medeu", "medeuskiy", "Тестовая", "1", (76.9650, 43.2380)),
    ("esil", "esilskiy", "Тестовая", "2", (71.4300, 51.1280)),
    ("karaganda", "karaganda", "Бухар-Жырау", "50", (73.1020, 49.8060)),
    ("saryarka", "saryarkinskiy", "Тестовая", "3", (71.4160, 51.1800)),
]

# specialist, title, kind, minutes, formats, address key / "area:<kato slug>" / None, price_session, price_month, is_free
SERVICES = [
    ("ivanova-logoped", "Консультация логопеда", "consultation", 45, ["in_person"], "almaly", 8000, 60000, False),
    ("serikov-aba", "АВА-сессия", "session", 60, ["in_person", "online"], "medeu", 12000, None, False),
    ("serikov-aba", "Консультация для родителей", "consultation", 45, ["online"], None, 6000, None, False),
    ("kim-neuro", "Приём психолога", "consultation", 50, ["in_person"], "esil", 9000, None, False),
    ("nurlan-online", "Онлайн-занятие с логопедом", "session", 45, ["online"], None, None, None, False),
    ("bekova-karaganda", "Занятие дефектолога", "session", 45, ["in_person"], "karaganda", 7000, None, False),
    ("omarova-home", "Выезд специалиста на дом", "home_visit", 60, ["home_visit"], "area:almaty", 10000, None, False),
    ("sergeev-free", "Бесплатная консультация психолога", "consultation", 30, ["in_person"], "saryarka", None, None, True),
    ("hidden-logoped", "Консультация", "consultation", 45, ["in_person"], "almaly", 5000, None, False),
]


@pytest.fixture
def catalog_fixture(db, kato_demo, reference) -> CatalogFixture:
    """Fixed roster of 8 specialists, 9 services and 5 addresses; Tasks 7-10 rely on it."""
    year = timezone.localdate().year
    addresses = {
        key: AddressFactory(kato=kato_demo[kato], street=street, building=building, point=Point(*lonlat, srid=4326))
        for key, kato, street, building, lonlat in ADDRESSES
    }
    specialists = {}
    for slug, name, types, (age_min, age_max), conditions, methods, languages, years, levels, has_kk, formats in ROSTER:
        phone = "" if slug == "sergeev-free" else TEST_PHONE
        profile = SpecialistFactory(
            slug=slug, display_name=name, bio=f"Био: {name}", approach=f"Подход: {name}",
            practice_start_year=year - years, age_min=age_min, age_max=age_max, formats=formats,
            whatsapp_phone=phone, public_phone=phone, demo_verification_levels=levels,
            specialist_types=types, conditions=conditions, methods=methods, languages=languages,
        )
        if has_kk:
            profile.create_translation("kk", bio=f"Өмірбаян: {name}", approach=f"Подход: {name}")
        PrivateContextFactory(specialist=profile, catalog_enabled=slug != "hidden-logoped")
        specialists[slug] = profile
    for slug, title, kind, minutes, formats, place, price_session, price_month, is_free in SERVICES:
        area = kato_demo[place.removeprefix("area:")] if place and place.startswith("area:") else None
        ServiceFactory(
            context=specialists[slug].contexts.get(), kind__slug=kind, title=title, duration_min=minutes, formats=formats,
            price_session=price_session, price_month=price_month, is_free=is_free, home_visit_area=area,
            addresses=[addresses[place]] if place and not area else [],
        )
    rebuild_all()
    return CatalogFixture(specialists=specialists, kato=kato_demo, addresses=addresses)


# slug, name, area (KATO slug), prices (hour, night, month), conditions, languages, experience, trainings, has record
# trainings: (title, hours, is_first_aid); the last three nannies break one condition of the rule each
NANNIES = [
    ("aigul-nanny", "Сапарова Айгуль", "almalinskiy", (3000, 15000, None), ["ras", "zrr", "adhd", "down-syndrome"], ["kk", "ru"], 6,
     [("Первая помощь детям", 16, True), ("Основы РАС для нянь", 72, False), ("Поведение ребёнка", 24, False)], True),
    ("marina-nanny", "Ковалёва Марина", "astana", (2500, None, 200000), ["down-syndrome"], ["ru"], 3,
     [("Первая помощь детям", 24, True), ("Альтернативная коммуникация", 40, False)], True),
    ("no-record-nanny", "Без Справки", "almaty", (2000, None, None), ["ras"], ["ru"], 2, [("Первая помощь детям", 16, True)], False),
    ("no-first-aid-nanny", "Без Первой Помощи", "almaty", (2000, None, None), ["ras"], ["ru"], 2, [("Основы РАС", 72, False)], True),
    ("no-training-nanny", "Без Курсов", "almaty", (2000, None, None), ["ras"], ["ru"], 2, [], True),
]


@pytest.fixture
def nannies(catalog_fixture) -> dict[str, SpecialistProfile]:
    """Two nannies shown in the section and three hidden by the rule, next to the specialists of `catalog_fixture`."""
    year = timezone.localdate().year
    result = {}
    for slug, name, area, (hour, night, month), conditions, languages, years, trainings, has_record in NANNIES:
        profile = NannyFactory(
            slug=slug, display_name=name, bio=f"О себе: {name}", approach=f"Как работаю: {name}",
            availability=f"График: {name}", practice_start_year=year - years, age_min=2, age_max=12,
            whatsapp_phone=TEST_PHONE, public_phone=TEST_PHONE, conditions=conditions, languages=languages,
            criminal_record_issued_on=datetime.date(year, 2, 1) if has_record else None,
        )
        for title, hours, first_aid in trainings:
            TrainingFactory(profile=profile, title=title, hours=hours, is_first_aid=first_aid, issuer="Центр «Забота»")
        NannyServiceFactory(
            context=PrivateContextFactory(specialist=profile), home_visit_area=catalog_fixture.kato[area],
            price_hour=hour, price_night=night, price_month=month,
        )
        result[slug] = profile
    rebuild_all()
    return result
