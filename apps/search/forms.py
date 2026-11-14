"""Choices for the filter form. The page is a plain GET form parsed leniently by `SearchParams`, so there is no Django Form to validate."""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _

from apps.catalog.models import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Format,
    Method,
    SpecialistType,
    VerificationLevel,
)
from apps.geo.models import KatoNode

AGE_GROUPS = [(0, 3), (3, 7), (7, 12), (12, 18)]
FILTERABLE_LEVELS = (VerificationLevel.EDUCATION, VerificationLevel.CREDENTIAL, VerificationLevel.SAFETY)


def _name(obj) -> str:
    return obj.safe_translation_getter("name", any_language=True) or ""


@dataclass
class FilterChoices:
    cities: list[KatoNode]  # regions and cities
    district_groups: list[tuple[KatoNode, list[KatoNode]]]  # (parent, its districts / rural okrugs)
    specialist_types: list[SpecialistType]
    conditions: list[tuple[DevelopmentalCondition, int]]  # (condition, depth), parents before children
    methods: list[Method]
    languages: list[CommunicationLanguage]
    formats: list[tuple[str, str]]
    verification_levels: list[tuple[str, str]]
    sorts: list[tuple[str, str]]
    pay_units: list[tuple[str, str]]


def _condition_rows(conditions: list[DevelopmentalCondition]) -> list[tuple[DevelopmentalCondition, int]]:
    children: dict[int | None, list[DevelopmentalCondition]] = {}
    for c in conditions:
        children.setdefault(c.parent_id, []).append(c)
    rows: list[tuple[DevelopmentalCondition, int]] = []

    def walk(parent_id, depth):
        for c in sorted(children.get(parent_id, []), key=_name):
            rows.append((c, depth))
            walk(c.pk, depth + 1)

    walk(None, 0)
    return rows


PAY_UNITS = [("hour", _("По часам")), ("night", _("Ночью")), ("month", _("Помесячно"))]


def _sorts(section: str) -> list[tuple[str, str]]:
    if section == "nannies":
        return [("relevance", _("По релевантности")), ("price", _("По цене за час")), ("experience", _("По опыту"))]
    return [("relevance", _("По релевантности")), ("price", _("По цене")), ("experience", _("По стажу"))]


def build_filter_choices(section: str = "specialists") -> FilterChoices:
    nodes = list(KatoNode.objects.prefetch_related("translations").select_related("parent"))
    cities = sorted((n for n in nodes if n.level in (KatoNode.Level.REGION, KatoNode.Level.CITY)), key=_name)
    groups: dict[int, list[KatoNode]] = {}
    for n in nodes:
        if n.level in (KatoNode.Level.DISTRICT, KatoNode.Level.RURAL) and n.parent_id:
            groups.setdefault(n.parent_id, []).append(n)
    by_id = {n.pk: n for n in nodes}
    district_groups = sorted(
        ((by_id[pid], sorted(items, key=_name)) for pid, items in groups.items()), key=lambda g: _name(g[0])
    )
    return FilterChoices(
        cities=cities,
        district_groups=district_groups,
        specialist_types=sorted(SpecialistType.objects.prefetch_related("translations"), key=_name),
        conditions=_condition_rows(list(DevelopmentalCondition.objects.prefetch_related("translations"))),
        methods=sorted(Method.objects.prefetch_related("translations"), key=_name),
        languages=sorted(CommunicationLanguage.objects.prefetch_related("translations"), key=_name),
        formats=list(Format.choices),
        verification_levels=[(level.value, level.label) for level in FILTERABLE_LEVELS],
        sorts=_sorts(section),
        pay_units=PAY_UNITS,
    )
