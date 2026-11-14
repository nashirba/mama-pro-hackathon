"""Pure generators of synthetic specialists and nannies for the demo. No database access: `seed_demo` writes the specs to the DB.

Everything random goes through the `random.Random` passed in, so one seed always yields the same catalog.
Shares that must not be left to luck (online-only, KZ translation) are derived from the specialist index.
"""

import datetime
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from random import Random

DATA_DIR = Path(__file__).resolve().parent / "data"

LOGIN_PHONE_PREFIX = "+7700000"  # synthetic login numbers, never shown anywhere
VERIFICATION_ORDER = ["identity", "education", "credential", "safety"]

# The brief says 3 km; the 50 m margin covers the difference between the spherical and the ellipsoidal distance.
MAX_ADDRESS_RADIUS_M = 2950
_METERS_PER_DEGREE = 111_195.0  # sphere, the same model PostGIS uses for ST_DistanceSphere

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z", "и": "i", "й": "i",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch", "ы": "y", "э": "e", "ю": "yu", "я": "ya", "ь": "", "ъ": "",
    "ә": "a", "ғ": "g", "қ": "k", "ң": "n", "ө": "o", "ұ": "u", "ү": "u", "һ": "h", "і": "i",
}


@dataclass(frozen=True)
class ServiceSpec:
    kind: str
    title: dict[str, str]
    description: dict[str, str]
    duration_min: int
    formats: list[str]
    price_session: int | None
    price_month: int | None
    is_free: bool


@dataclass(frozen=True)
class SpecialistSpec:
    index: int
    login_phone: str
    preferred_language: str
    display_name: str
    slug: str
    practice_start_year: int
    age_min: int
    age_max: int
    specialist_types: list[str]
    conditions: list[str]
    methods: list[str]
    languages: list[str]
    verification_levels: list[str]
    online_only: bool
    bio: dict[str, str]  # ru always; kk only when the specialist has a KZ translation
    approach: dict[str, str]
    services: list[ServiceSpec] = field(default_factory=list)

    @property
    def formats(self) -> list[str]:
        used = {f for s in self.services for f in s.formats}
        return [f for f in ("in_person", "home_visit", "online") if f in used]

    @property
    def has_kk(self) -> bool:
        return "kk" in self.bio


@dataclass(frozen=True)
class AddressSpec:
    street: str
    building: str
    lon: float
    lat: float


def load_json(name: str) -> dict:
    with (DATA_DIR / name).open(encoding="utf-8") as f:
        return json.load(f)


def is_online_only(index: int) -> bool:
    return index % 5 == 4  # 20%


def has_kk_translation(index: int) -> bool:
    return index % 2 == 0  # half


def transliterate(text: str) -> str:
    return "".join(_TRANSLIT.get(ch, ch) for ch in text.lower())


def _slug_part(text: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in transliterate(text)).strip("-")


def _round_price(rng: Random, low: int, high: int) -> int:
    return round(rng.randint(low, high) / 500) * 500


def _services(rng: Random, archetype: dict, bios: dict, online_only: bool, has_kk: bool) -> list[ServiceSpec]:
    description = archetype["service_description"]
    pool = list(archetype["services"])
    if not online_only:
        pool.append(bios["home_visit"])
    chosen = rng.sample(range(len(pool)), min(rng.randint(1, 4), len(pool)))
    if not online_only and all(pool[i]["kind"] == "home_visit" for i in chosen):
        chosen[0] = 0  # an in-person specialist always has at least one in-person service (and so an address)
    result = []
    for i in sorted(chosen):
        item = pool[i]
        kind = item["kind"]
        if online_only:
            formats = ["online"]
        elif kind == "home_visit":
            formats = ["home_visit"]
        else:
            formats = ["in_person", "online"] if rng.random() < 0.3 else ["in_person"]
        price = _round_price(rng, *item["price"])
        price_session, price_month, is_free = price, None, False
        if kind == "course":
            price_session, price_month = None, price
        elif kind == "session" and rng.random() < 0.4:
            price_month = price * 8
        if kind == "consultation" and rng.random() < 0.06:
            price_session, price_month, is_free = None, None, True  # a free service keeps both prices as NULL
        elif rng.random() < 0.08:
            price_session, price_month = None, None  # "on request"
        result.append(
            ServiceSpec(
                kind=kind,
                title=_langs(item["title"], has_kk),
                description=_langs(description, has_kk),
                duration_min=item["minutes"],
                formats=formats,
                price_session=price_session,
                price_month=price_month,
                is_free=is_free,
            )
        )
    return result


def _langs(texts: dict[str, str], has_kk: bool) -> dict[str, str]:
    """RU always; KZ with the KZ text only for specialists that have a KZ translation."""
    return {"ru": texts["ru"], **({"kk": texts["kk"]} if has_kk else {})}


def build_specialist(rng: Random, index: int, names: dict, bios: dict, current_year: int) -> SpecialistSpec:
    online_only = is_online_only(index)
    has_kk = has_kk_translation(index)
    archetypes = bios["archetypes"]
    archetype = archetypes[index % len(archetypes)]  # 13 archetypes: coprime with 2 and 5, so every mix of shares occurs

    kazakh_name = rng.random() < 0.5
    group = names["kk" if kazakh_name else "ru"]
    female = rng.random() < 0.7
    first = rng.choice(group["female" if female else "male"])
    last = rng.choice(group["surnames"])[1 if female else 0]

    languages = ["kk", "ru"] if kazakh_name else ["ru"]
    if kazakh_name and rng.random() < 0.15:
        languages.append("en")
    if not kazakh_name and rng.random() < 0.2:
        languages.insert(0, "kk")

    age_lo, age_hi = archetype["age"]
    age_min = age_lo + rng.randint(0, 1)
    age_max = max(age_min, age_hi - rng.randint(0, 1))

    conditions = rng.sample(archetype["conditions"], rng.randint(1, len(archetype["conditions"])))
    methods = rng.sample(archetype["methods"], rng.randint(1, len(archetype["methods"])))
    levels = set(rng.sample(VERIFICATION_ORDER, rng.choice([0, 1, 1, 2, 2, 3, 4])))

    bio_tail = rng.choice(bios["bio_tail"])
    approach_tail = rng.choice(bios["approach_tail"])
    bio = {lang: f"{archetype['bio'][lang]} {bio_tail[lang]}" for lang in ("ru", "kk")}
    approach = {lang: f"{archetype['approach'][lang]} {approach_tail[lang]}" for lang in ("ru", "kk")}
    if not has_kk:
        bio, approach = {"ru": bio["ru"]}, {"ru": approach["ru"]}

    return SpecialistSpec(
        index=index,
        login_phone=f"{LOGIN_PHONE_PREFIX}{index:04d}",
        preferred_language="kk" if kazakh_name else "ru",
        display_name=f"{last} {first}",
        slug=f"{_slug_part(first)}-{_slug_part(last)}-{index + 1}",
        practice_start_year=current_year - rng.randint(1, 25),
        age_min=age_min,
        age_max=age_max,
        specialist_types=list(archetype["types"]),
        conditions=conditions,
        methods=methods,
        languages=languages,
        verification_levels=[level for level in VERIFICATION_ORDER if level in levels],
        online_only=online_only,
        bio=bio,
        approach=approach,
        services=_services(rng, archetype, bios, online_only, has_kk),
    )


def random_point_near(rng: Random, lon: float, lat: float, max_radius_m: float = MAX_ADDRESS_RADIUS_M) -> tuple[float, float]:
    """A uniformly distributed point within `max_radius_m` of (lon, lat): r = R * sqrt(u), random angle."""
    distance = max_radius_m * math.sqrt(rng.random())
    angle = rng.uniform(0, 2 * math.pi)
    d_lat = distance * math.sin(angle) / _METERS_PER_DEGREE
    d_lon = distance * math.cos(angle) / (_METERS_PER_DEGREE * math.cos(math.radians(lat)))
    return lon + d_lon, lat + d_lat


def build_addresses(rng: Random, streets: list[str], center: tuple[float, float]) -> list[AddressSpec]:
    """1-2 addresses near the district center."""
    result = []
    for _ in range(rng.randint(1, 2)):
        lon, lat = random_point_near(rng, *center)
        result.append(AddressSpec(street=rng.choice(streets), building=str(rng.randint(1, 150)), lon=lon, lat=lat))
    return result


# --- nannies -----------------------------------------------------------------------------------------------------

NANNY_LOGIN_PHONE_PREFIX = "+7700001"  # a block of its own, so nanny logins never meet specialist logins


@dataclass(frozen=True)
class TrainingSpec:
    title: dict[str, str]
    issuer: str
    year: int
    hours: int
    certificate_number: str
    is_first_aid: bool


@dataclass(frozen=True)
class NannySpec:
    index: int
    login_phone: str
    preferred_language: str
    display_name: str
    slug: str
    practice_start_year: int
    age_min: int
    age_max: int
    conditions: list[str]
    languages: list[str]
    criminal_record_issued_on: datetime.date | None
    trainings: list[TrainingSpec]
    bio: dict[str, str]  # ru always; kk only when the nanny has a KZ translation
    approach: dict[str, str]
    availability: dict[str, str]
    service_title: dict[str, str]
    service_description: dict[str, str]
    price_hour: int
    price_night: int | None
    price_month: int | None


def nanny_without_record(index: int) -> bool:
    return index % 12 == 3


def nanny_without_first_aid(index: int) -> bool:
    return index % 24 == 9


def _certificate(rng: Random, prefix: str, year: int) -> str:
    return f"{prefix}-{year}-{rng.randint(1000, 9999)}"


def _trainings(rng: Random, data: dict, current_year: int, first_aid: bool) -> list[TrainingSpec]:
    """A pediatric first aid course (16-40 hours) and 1-3 other courses (24-120 hours)."""
    result = []
    if first_aid:
        course = rng.choice(data["first_aid_courses"])
        year = current_year - rng.randint(0, 3)
        result.append(
            TrainingSpec(
                title=course["title"],
                issuer=course["issuer"],
                year=year,
                hours=rng.randrange(course["hours"][0], course["hours"][1] + 1, 4),
                certificate_number=_certificate(rng, course["prefix"], year),
                is_first_aid=True,
            )
        )
    for course in rng.sample(data["courses"], rng.randint(1, 3)):
        year = current_year - rng.randint(0, 5)
        result.append(
            TrainingSpec(
                title=course["title"],
                issuer=course["issuer"],
                year=year,
                hours=rng.randrange(24, 121, 8),
                certificate_number=_certificate(rng, course["prefix"], year),
                is_first_aid=False,
            )
        )
    return result


def build_nanny(rng: Random, index: int, names: dict, data: dict, current_year: int) -> NannySpec:
    """A nanny of the demo. Indexes picked by `nanny_without_record` / `nanny_without_first_aid` break the visibility
    rule on purpose: they exist in the database but the nanny section does not show them."""
    has_kk = has_kk_translation(index)
    kazakh_name = rng.random() < 0.5
    group = names["kk" if kazakh_name else "ru"]
    first = rng.choice(group["female"])
    last = rng.choice(group["surnames"])[1]
    languages = ["kk", "ru"] if kazakh_name else ["ru"]
    if not kazakh_name and rng.random() < 0.2:
        languages.insert(0, "kk")
    age_min, age_max = rng.choice(data["age_ranges"])
    conditions = rng.sample(data["conditions"], rng.randint(1, 4))
    record = None
    if not nanny_without_record(index):
        record = datetime.date(current_year - rng.randint(0, 1), rng.randint(1, 12), rng.randint(1, 28))
    low, high = data["prices"]["hour"]
    price_hour = _round_price(rng, low, high)
    price_night = _round_price(rng, *data["prices"]["night"]) if rng.random() < 0.6 else None
    price_month = round(rng.randint(*data["prices"]["month"]) / 10_000) * 10_000 if rng.random() < 0.5 else None

    def texts(key: str) -> dict[str, str]:
        return _langs(rng.choice(data[key]), has_kk)

    return NannySpec(
        index=index,
        login_phone=f"{NANNY_LOGIN_PHONE_PREFIX}{index:04d}",
        preferred_language="kk" if kazakh_name else "ru",
        display_name=f"{last} {first}",
        slug=f"{_slug_part(first)}-{_slug_part(last)}-n{index + 1}",
        practice_start_year=current_year - rng.randint(1, 15),
        age_min=age_min,
        age_max=age_max,
        conditions=conditions,
        languages=languages,
        criminal_record_issued_on=record,
        trainings=_trainings(rng, data, current_year, first_aid=not nanny_without_first_aid(index)),
        bio=texts("bio"),
        approach=texts("approach"),
        availability=texts("availability"),
        service_title=_langs(data["service"]["title"], has_kk),
        service_description=_langs(data["service"]["description"], has_kk),
        price_hour=price_hour,
        price_night=price_night,
        price_month=price_month,
    )
