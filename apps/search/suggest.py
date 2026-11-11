from dataclasses import dataclass
from typing import Literal

from django.urls import reverse
from django.utils.translation import override

from apps.catalog.models import DevelopmentalCondition, Method, SpecialistType
from apps.core.i18n import first_translated
from apps.core.text import normalize_kk

MIN_QUERY_LENGTH = 2

# kind, model, results filter parameter; the order is the order in the list
SOURCES = (
    ("type", SpecialistType, "specialist_type_ids"),
    ("condition", DevelopmentalCondition, "condition_ids"),
    ("method", Method, "method_ids"),
)


@dataclass(frozen=True)
class Suggestion:
    kind: Literal["type", "condition", "method"]
    slug: str
    label: str
    url: str


def suggest(q: str, lang: str, limit: int = 8, kato_id: int | None = None) -> list[Suggestion]:
    """Reference rows whose `search_key` (names in all languages and synonyms) contains the query.

    The label is in `lang` with the per-field fallback to RU; the links open the results page with the row as a filter
    (and the chosen city, when `kato_id` is given).
    """
    key = normalize_kk(q)
    if len(key) < MIN_QUERY_LENGTH:
        return []
    suggestions: list[Suggestion] = []
    with override(lang):
        results_url = reverse("search:results")
        city = f"&kato_id={kato_id}" if kato_id is not None else ""
        for kind, model, param in SOURCES:
            remaining = limit - len(suggestions)
            if remaining <= 0:
                break
            rows = model.objects.filter(search_key__contains=key).prefetch_related("translations").order_by("slug")[:remaining]
            suggestions.extend(
                Suggestion(kind, row.slug, first_translated(row, "name") or row.slug, f"{results_url}?{param}={row.pk}{city}")
                for row in rows
            )
    return suggestions
