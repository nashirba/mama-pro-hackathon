import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import (
    CommunicationLanguage,
    DevelopmentalCondition,
    Method,
    ServiceKind,
    SpecialistType,
)

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "reference_v1.json"


def upsert(model, key: str, item: dict, plain: tuple[str, ...], translated: tuple[str, ...]):
    """Upsert by `key`. A language row is written when any translated field has text in that language;
    in such a row every translated field is filled, with the RU value where there is no text for the language."""
    obj = model.objects.filter(**{key: item[key]}).first() or model(**{key: item[key]})
    for field in plain:
        if field in item:
            setattr(obj, field, item[field])
    obj.save()
    languages = {lang for field in translated for lang in item[field]}
    for lang in sorted(languages, key=lambda code: code != "ru"):  # ru first
        obj.set_current_language(lang)
        for field in translated:
            setattr(obj, field, item[field].get(lang) or item[field]["ru"])
        obj.save()
    return obj


class Command(BaseCommand):
    help = "Idempotent upsert of reference data from apps/catalog/data/reference_v1.json"

    @transaction.atomic
    def handle(self, *args, **options):
        with DATA_FILE.open(encoding="utf-8") as f:
            data = json.load(f)

        for item in data["specialist_types"]:
            upsert(SpecialistType, "slug", item, ("synonyms",), ("name", "name_plural", "landing_name"))

        conditions = {}
        for item in data["conditions"]:
            conditions[item["slug"]] = upsert(
                DevelopmentalCondition, "slug", item, ("synonyms", "is_no_diagnosis"), ("name", "landing_name")
            )
        for item in data["conditions"]:  # parents in a second pass: the file does not have to be ordered
            parent = conditions[item["parent"]] if item["parent"] else None
            DevelopmentalCondition.objects.filter(slug=item["slug"]).update(parent=parent)

        for item in data["methods"]:
            upsert(Method, "slug", item, ("synonyms", "evidence_level"), ("name",))
        for item in data["service_kinds"]:
            upsert(ServiceKind, "slug", item, (), ("name",))
        for item in data["communication_languages"]:
            upsert(CommunicationLanguage, "code", item, (), ("name",))

        self.stdout.write(
            f"Reference data loaded: {len(data['specialist_types'])} specialist types, {len(data['conditions'])} conditions, "
            f"{len(data['methods'])} methods, {len(data['service_kinds'])} service kinds, "
            f"{len(data['communication_languages'])} languages"
        )
