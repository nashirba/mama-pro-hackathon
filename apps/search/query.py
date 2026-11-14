import math
from dataclasses import dataclass, field, fields

from django.conf import settings
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    TrigramWordSimilarity,
)
from django.db.models import (
    Case,
    F,
    FloatField,
    IntegerField,
    Max,
    Min,
    Q,
    QuerySet,
    Value,
    When,
)
from django.http import QueryDict

from apps.catalog.models import (
    DevelopmentalCondition,
    Format,
    ProfileCategory,
    SpecialistProfile,
)
from apps.catalog.pricing import lowest

from .models import SearchOffer
from .normalize import normalize_kk

SORTS = ("relevance", "price", "distance", "experience")
SECTIONS = ("specialists", "nannies")
SECTION_CATEGORY = {"specialists": ProfileCategory.SPECIALIST, "nannies": ProfileCategory.NANNY}
# a nanny's pay unit -> the price column that must be set
PAY_UNIT_COLUMNS = {"hour": "price_hour", "night": "price_night", "month": "price_month"}

INT_FIELDS = (
    "kato_id", "child_age_min", "child_age_max", "price_min", "price_max", "price_month_min", "price_month_max", "experience_min",
    "price_hour_min", "price_hour_max",
)
# filters that exist in one section only; the other section ignores them, so a stale link cannot empty its results
SPECIALIST_ONLY_FIELDS = (
    "specialist_type_ids", "method_ids", "formats", "price_min", "price_max", "free_only", "near",
)
NANNY_ONLY_FIELDS = ("pay_units", "price_hour_min", "price_hour_max")
INT_LIST_FIELDS = ("specialist_type_ids", "condition_ids", "method_ids")
STR_LIST_FIELDS = ("formats", "language_codes", "pay_units")


def _int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_near(value: str | None) -> tuple[float, float] | None:
    try:
        lon, lat = (float(part) for part in value.split(","))
    except (AttributeError, ValueError):
        return None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):  # also rejects NaN
        return None
    return lon, lat


@dataclass
class SearchParams:
    q: str = ""
    kato_id: int | None = None
    specialist_type_ids: list[int] = field(default_factory=list)
    child_age_min: int | None = None
    child_age_max: int | None = None
    condition_ids: list[int] = field(default_factory=list)
    price_min: int | None = None
    price_max: int | None = None
    price_month_min: int | None = None
    price_month_max: int | None = None
    free_only: bool = False
    formats: list[str] = field(default_factory=list)
    language_codes: list[str] = field(default_factory=list)
    experience_min: int | None = None
    method_ids: list[int] = field(default_factory=list)
    sort: str = "relevance"
    near: tuple[float, float] | None = None  # (lon, lat)
    page: int = 1
    pay_units: list[str] = field(default_factory=list)  # nannies: "hour", "night", "month"
    price_hour_min: int | None = None
    price_hour_max: int | None = None
    section: str = "specialists"  # set by the view from the URL, never read from the query string

    @classmethod
    def from_querydict(cls, qd: QueryDict, section: str = "specialists") -> "SearchParams":
        """Lenient parsing: whatever cannot be parsed falls back to the default."""
        kwargs: dict = {"q": qd.get("q", "").strip(), "section": section if section in SECTIONS else "specialists"}
        for name in INT_FIELDS:
            kwargs[name] = _int(qd.get(name))
        for name in INT_LIST_FIELDS:
            kwargs[name] = [i for i in map(_int, qd.getlist(name)) if i is not None]
        for name in STR_LIST_FIELDS:
            kwargs[name] = [v for v in qd.getlist(name) if v]
        kwargs["free_only"] = qd.get("free_only", "").lower() in {"1", "true", "on", "yes"}
        kwargs["near"] = _parse_near(qd.get("near"))
        defaults = cls()
        for name in SPECIALIST_ONLY_FIELDS if kwargs["section"] == "nannies" else NANNY_ONLY_FIELDS:
            kwargs[name] = getattr(defaults, name)
        sort = qd.get("sort", "relevance")
        if sort not in SORTS or (sort == "distance" and kwargs["near"] is None):
            sort = "relevance"
        kwargs["sort"] = sort
        kwargs["page"] = max(_int(qd.get("page")) or 1, 1)
        return cls(**kwargs)

    def to_querydict(self) -> QueryDict:
        """Inverse of from_querydict; default values are omitted."""
        qd = QueryDict(mutable=True)
        defaults = SearchParams()
        for f in fields(self):
            value = getattr(self, f.name)
            if value == getattr(defaults, f.name) or f.name == "section":
                continue
            if f.name in INT_LIST_FIELDS or f.name in STR_LIST_FIELDS:
                qd.setlist(f.name, [str(v) for v in value])
            elif f.name == "near":
                qd[f.name] = f"{value[0]},{value[1]}"
            elif f.name == "free_only":
                qd[f.name] = "1"
            else:
                qd[f.name] = str(value)
        return qd


@dataclass
class SpecialistCard:
    specialist: SpecialistProfile
    matching_offers: list[SearchOffer]
    price_from: int | None  # per session for a specialist, per hour for a nanny
    nearest_district_name: str | None
    nearest_city_name: str | None
    has_online: bool
    distance_m: float | None
    # a nanny's lowest price of each pay unit among the matching offers
    price_hour: int | None = None
    price_night: int | None = None
    price_month: int | None = None
    home_visit_area_name: str | None = None  # "city, district" of the first home visit offer


@dataclass
class SearchResult:
    cards: list[SpecialistCard]
    total: int
    page: int
    pages: int


def expand_conditions(ids: list[int]) -> list[int]:
    """The selected conditions and all their descendants."""
    result = set(ids)
    frontier = set(ids)
    while frontier:
        frontier = set(DevelopmentalCondition.objects.filter(parent_id__in=frontier).values_list("pk", flat=True)) - result
        result |= frontier
    return sorted(result)


def _effective_price(section: str):
    """The price the section sorts by: per session for specialists, per hour for nannies."""
    if section == "nannies":
        return F("price_hour")
    return Case(When(is_free=True, then=Value(0)), default=F("price_session"), output_field=IntegerField())


def search_offers_queryset(params: SearchParams) -> QuerySet[SearchOffer]:
    """Offers of the section matching all filters, annotated with eff_price, text_rank (only with q) and dist (only with near)."""
    qs = SearchOffer.objects.filter(category=SECTION_CATEGORY[params.section]).annotate(
        eff_price=_effective_price(params.section)
    )

    if params.kato_id is not None:
        where = Q(kato_ids__contains=[params.kato_id])
        if Format.ONLINE in params.formats:
            where |= Q(is_online=True)
        qs = qs.filter(where)

    # a lone bound is open-ended; with both bounds the age ranges must intersect (inclusive)
    if params.child_age_min is not None:
        qs = qs.filter(age_max__gte=params.child_age_min)
    if params.child_age_max is not None:
        qs = qs.filter(age_min__lte=params.child_age_max)

    for param, column in (
        (params.price_min, "price_session__gte"),
        (params.price_max, "price_session__lte"),
        (params.price_month_min, "price_month__gte"),
        (params.price_month_max, "price_month__lte"),
        (params.price_hour_min, "price_hour__gte"),
        (params.price_hour_max, "price_hour__lte"),
        (params.experience_min, "experience_years__gte"),
    ):
        if param is not None:
            qs = qs.filter(**{column: param})
    if params.free_only:
        qs = qs.filter(is_free=True)

    for values, column in (
        (params.specialist_type_ids, "specialist_type_ids__overlap"),
        (expand_conditions(params.condition_ids) if params.condition_ids else [], "condition_ids__overlap"),
        (params.method_ids, "method_ids__overlap"),
        (params.language_codes, "language_codes__overlap"),
        (params.formats, "formats__overlap"),
    ):
        if values:
            qs = qs.filter(**{column: values})

    pay_columns = [PAY_UNIT_COLUMNS[u] for u in params.pay_units if u in PAY_UNIT_COLUMNS]
    if pay_columns:  # any of the chosen pay units, like the other checkbox groups
        where = Q()
        for column in pay_columns:
            where |= Q(**{f"{column}__isnull": False})
        qs = qs.filter(where)

    normalized_q = normalize_kk(params.q)
    if normalized_q:
        query = SearchQuery(params.q, config="russian", search_type="websearch") | SearchQuery(normalized_q, config="simple")
        trgm = TrigramWordSimilarity(normalized_q, "search_norm")
        qs = qs.annotate(trgm=trgm).filter(Q(search_vector=query) | Q(trgm__gte=settings.SEARCH_TRIGRAM_MIN))
        qs = qs.annotate(text_rank=SearchRank(F("search_vector"), query) + F("trgm"))

    if params.near is not None:
        qs = qs.annotate(dist=Distance("point", Point(*params.near, srid=4326), output_field=FloatField()))
    return qs


def _order_by(params: SearchParams) -> list:
    tie = "specialist_id"
    if params.sort == "price":
        return [F("min_price").asc(nulls_last=True), tie]
    if params.sort == "experience":
        return [F("experience").desc(), tie]
    if params.sort == "distance" and params.near is not None:
        return [F("min_dist").asc(nulls_last=True), tie]
    if params.q and normalize_kk(params.q):
        return [F("best_rank").desc(), tie]
    return [tie]


def _offer_price(offer: SearchOffer) -> int | None:
    if offer.category == ProfileCategory.NANNY:
        return offer.price_hour
    return 0 if offer.is_free else offer.price_session


def _area_name(offers: list[SearchOffer]) -> str | None:
    area = next((o.service.home_visit_area for o in offers if Format.HOME_VISIT in o.formats and o.service.home_visit_area_id), None)
    if area is None:
        return None
    name = area.safe_translation_getter("name", any_language=True)
    city = area.city()
    if city is not None and city.pk != area.pk:
        return f"{city.safe_translation_getter('name', any_language=True)}, {name}"
    return name


def _build_card(specialist: SpecialistProfile, offers: list[SearchOffer], distance_m: float | None, near) -> SpecialistCard:
    prices = [p for p in map(_offer_price, offers) if p is not None]
    with_address = [o for o in offers if o.address is not None]
    nearest = None
    if with_address:
        nearest = min(with_address, key=lambda o: o.dist) if near and all(o.dist is not None for o in with_address) else with_address[0]
    city_name = None
    if nearest:
        city = nearest.address.kato.city()
        if city is not None and city.pk != nearest.address.kato.pk:
            city_name = city.safe_translation_getter("name", any_language=True)
    return SpecialistCard(
        specialist=specialist,
        matching_offers=offers,
        price_from=min(prices) if prices else None,
        nearest_district_name=nearest.address.kato.safe_translation_getter("name", any_language=True) if nearest else None,
        nearest_city_name=city_name,
        has_online=any(o.is_online for o in offers),
        distance_m=distance_m,
        price_hour=lowest(offers, "price_hour"),
        price_night=lowest(offers, "price_night"),
        price_month=lowest(offers, "price_month"),
        home_visit_area_name=_area_name(offers),
    )


def search(params: SearchParams) -> SearchResult:
    offers = search_offers_queryset(params)
    aggregates = {
        "min_price": Min("eff_price"),
        "experience": Max("experience_years"),
    }
    if params.q and normalize_kk(params.q):
        aggregates["best_rank"] = Max("text_rank")
    if params.near is not None:
        aggregates["min_dist"] = Min("dist")
    grouped = offers.values("specialist_id").annotate(**aggregates).order_by(*_order_by(params))

    total = grouped.count()
    page_size = settings.SEARCH_PAGE_SIZE
    pages = max(math.ceil(total / page_size), 1)
    page = min(params.page, pages)
    rows = list(grouped[(page - 1) * page_size : page * page_size])

    ids = [r["specialist_id"] for r in rows]
    by_specialist: dict[int, list[SearchOffer]] = {i: [] for i in ids}
    page_offers = (
        offers.filter(specialist_id__in=ids)
        .select_related("specialist", "address__kato__parent__parent", "service__home_visit_area__parent")
        .prefetch_related(
            "specialist__translations",
            "address__kato__translations",
            "address__kato__parent__translations",
            "address__kato__parent__parent__translations",
            "service__translations",
            "service__home_visit_area__translations",
            "service__home_visit_area__parent__translations",
        )
        .order_by("pk")
    )
    for offer in page_offers:
        by_specialist[offer.specialist_id].append(offer)

    cards = []
    for r in rows:
        page_specialist_offers = by_specialist[r["specialist_id"]]
        if not page_specialist_offers:  # the offers were rebuilt between the two queries
            continue
        cards.append(
            _build_card(page_specialist_offers[0].specialist, page_specialist_offers, r.get("min_dist"), params.near)
        )
    return SearchResult(cards=cards, total=total, page=page, pages=pages)
