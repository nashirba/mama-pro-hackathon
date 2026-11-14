from dataclasses import dataclass
from typing import Literal

from django.db.models import Case, IntegerField, When
from django.urls import reverse
from django.utils.translation import gettext, override

from apps.catalog.models import DevelopmentalCondition, Method, SpecialistType
from apps.core.i18n import first_translated
from apps.core.text import normalize_kk

MIN_QUERY_LENGTH = 2
PER_KIND_LIMIT = 5  # so conditions and methods still fit into the limit

# kind, model, results filter parameter; the order is the order in the list
SOURCES = (
    ("type", SpecialistType, "specialist_type_ids"),
    ("condition", DevelopmentalCondition, "condition_ids"),
    ("method", Method, "method_ids"),
)
# Normalized stems that lead to the nanny section («няня», «няню», «бала күтуші»); a nanny is a profile category,
# not a reference row. The query matches when it contains a stem or is a beginning of one (3+ letters).
NANNY_KEYS = tuple(normalize_kk(k) for k in ("нян", "күтуші", "nanny"))


@dataclass(frozen=True)
class Suggestion:
    kind: Literal["nannies", "type", "condition", "method"]
    slug: str
    label: str
    url: str


def _matches_nannies(key: str) -> bool:
    return any((len(key) >= 3 and k.startswith(key)) or k in key for k in NANNY_KEYS)


def suggest(q: str, lang: str, limit: int = 8, kato_id: int | None = None) -> list[Suggestion]:
    """Reference rows whose `search_key` (names in all languages and synonyms) contains the query.

    The label is in `lang` with the per-field fallback to RU; the links open the results page with the row as a filter
    (and the chosen city, when `kato_id` is given). A query for a nanny puts the nanny section first.
    """
    key = normalize_kk(q)
    if len(key) < MIN_QUERY_LENGTH:
        return []
    suggestions: list[Suggestion] = []
    with override(lang):
        if _matches_nannies(key):
            city = f"?kato_id={kato_id}" if kato_id is not None else ""
            suggestions.append(Suggestion("nannies", "nannies", gettext("Обученные няни"), f"{reverse('search:nannies')}{city}"))
        results_url = reverse("search:results")
        city = f"&kato_id={kato_id}" if kato_id is not None else ""
        for kind, model, param in SOURCES:
            remaining = limit - len(suggestions)
            if remaining <= 0:
                break
            prefix = Case(When(search_key__startswith=key, then=0), default=1, output_field=IntegerField())
            rows = (
                model.objects.filter(search_key__contains=key)
                .annotate(prefix=prefix)
                .prefetch_related("translations")
                .order_by("prefix", "slug")[: min(remaining, PER_KIND_LIMIT)]
            )
            suggestions.extend(
                Suggestion(kind, row.slug, first_translated(row, "name") or row.slug, f"{results_url}?{param}={row.pk}{city}")
                for row in rows
            )
    return suggestions
