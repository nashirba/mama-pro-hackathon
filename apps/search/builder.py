"""Builds SearchOffer rows. A context's rows are always replaced as a whole, so a rebuild never leaves duplicates."""

from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.db.models import Value

from apps.catalog.models import (
    DevelopmentalCondition,
    Format,
    Method,
    PracticeContext,
    Service,
    SpecialistType,
)
from apps.catalog.visibility import is_catalog_visible, nanny_eligible
from apps.geo.models import KatoNode

from .models import SearchOffer
from .normalize import normalize_kk


def _ru(obj, field: str) -> str:
    return obj.safe_translation_getter(field, language_code="ru", any_language=True) or ""


def _synonyms(objs) -> list[str]:
    return [o.synonyms for o in objs if o.synonyms.strip()]


class _KatoCache:
    """Ids (node + ancestors) and names in all languages (node + ancestors) per KatoNode, loaded once per rebuild."""

    def __init__(self):
        self._cache: dict[int, tuple[list[int], list[str]]] = {}

    def get(self, node: KatoNode) -> tuple[list[int], list[str]]:
        if node.pk not in self._cache:
            ids = [node.pk, *node.ancestor_ids()]
            names = list(
                KatoNode.objects.filter(pk__in=ids).values_list("translations__name", flat=True)
            )
            self._cache[node.pk] = (ids, [n for n in names if n])
        return self._cache[node.pk]


def _vector(a: list[str], b: list[str], c: list[str], norm: str):
    def part(texts, weight=None):
        return SearchVector(Value(" ".join(t for t in texts if t)), weight=weight, config="russian")

    return part(a, "A") + part(b, "B") + part(c, "C") + SearchVector(Value(norm), config="simple")


def _service_offers(service: Service, kato: _KatoCache) -> list[SearchOffer]:
    context = service.context
    specialist = context.specialist
    attrs = service.effective_attrs()
    types = list(SpecialistType.objects.filter(pk__in=attrs.specialist_type_ids).prefetch_related("translations"))
    conditions = list(DevelopmentalCondition.objects.filter(pk__in=attrs.condition_ids).prefetch_related("translations"))
    methods = list(Method.objects.filter(pk__in=attrs.method_ids).prefetch_related("translations"))
    titles = list(service.translations.values_list("title", flat=True))

    vector_a = [specialist.display_name, *(_ru(t, "name") for t in types)]
    vector_b = [*(_ru(c, "name") for c in conditions), *(_ru(m, "name") for m in methods), *_synonyms([*types, *conditions, *methods])]
    vector_c = [_ru(service, "title"), _ru(specialist, "bio")]
    base_norm = [specialist.display_name, *(o.search_key for o in [*types, *conditions, *methods]), *titles]

    common = {
        "specialist": specialist,
        "category": specialist.category,
        "context": context,
        "service": service,
        "price_session": service.price_session,
        "price_month": service.price_month,
        "price_hour": service.price_hour,
        "price_night": service.price_night,
        "is_free": service.is_free,
        "age_min": attrs.age_min,
        "age_max": attrs.age_max,
        "condition_ids": attrs.condition_ids,
        "method_ids": attrs.method_ids,
        "specialist_type_ids": attrs.specialist_type_ids,
        "language_codes": attrs.language_codes,
        "experience_years": specialist.experience_years,
        "training_hours": specialist.training_hours,
        "verification_levels": list(specialist.demo_verification_levels),
    }

    def row(*, node=None, address=None, fmt: str) -> SearchOffer:
        ids, names = kato.get(node) if node else ([], [])
        norm = normalize_kk(" ".join([*base_norm, *names, address.street if address else ""]))
        return SearchOffer(
            **common,
            address=address,
            point=address.point if address else None,
            kato_ids=ids,
            is_online=fmt == Format.ONLINE,
            formats=[fmt],
            search_norm=norm,
            search_vector=_vector(vector_a, vector_b, vector_c, norm),
        )

    rows = []
    formats = service.formats or []
    if Format.IN_PERSON in formats:
        rows += [row(node=a.kato, address=a, fmt=Format.IN_PERSON) for a in service.addresses.select_related("kato").order_by("pk")]
    if Format.HOME_VISIT in formats and service.home_visit_area_id is not None:
        rows.append(row(node=service.home_visit_area, fmt=Format.HOME_VISIT))
    if Format.ONLINE in formats:
        rows.append(row(fmt=Format.ONLINE))
    return rows


def rebuild_for_context(context_id: int) -> int:
    """Replace all SearchOffer rows of a practice context; returns the number of rows written."""
    with transaction.atomic():
        SearchOffer.objects.filter(context_id=context_id).delete()
        context = (
            PracticeContext.objects.select_related("specialist")
            .prefetch_related("specialist__trainings")
            .filter(pk=context_id)
            .first()
        )
        if context is None or not is_catalog_visible(context):
            return 0
        if context.specialist.is_nanny and not nanny_eligible(context.specialist):
            return 0
        kato = _KatoCache()
        rows = []
        for service in context.services.order_by("pk"):
            service.context = context  # the specialist with the prefetched trainings
            rows += _service_offers(service, kato)
        return len(SearchOffer.objects.bulk_create(rows))


def rebuild_all() -> int:
    return sum(rebuild_for_context(pk) for pk in PracticeContext.objects.order_by("pk").values_list("pk", flat=True))
