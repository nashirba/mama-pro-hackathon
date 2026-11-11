import json
from pathlib import Path

from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.geo.models import KatoNode

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "kato_demo.json"


class Command(BaseCommand):
    help = "Idempotent upsert of the demo KATO tree from apps/geo/data/kato_demo.json"

    @transaction.atomic
    def handle(self, *args, **options):
        with DATA_FILE.open(encoding="utf-8") as f:
            items = json.load(f)
        by_slug: dict[str, KatoNode] = {}
        for item in items:  # the file lists parents before children
            parent = None
            if item.get("parent"):
                try:
                    parent = by_slug[item["parent"]]
                except KeyError:
                    raise CommandError(f"Parent {item['parent']!r} of {item['slug']!r} must come earlier in the file")
            node = KatoNode.objects.filter(code=item["code"]).first() or KatoNode(code=item["code"])
            node.parent = parent
            node.level = item["level"]
            node.slug = item["slug"]
            node.two_gis_city_slug = item.get("two_gis_city_slug", "")
            center = item.get("center")
            node.center = Point(center[0], center[1], srid=4326) if center else None
            for lang, name in item["name"].items():
                node.set_current_language(lang)
                node.name = name
                node.name_locative = item.get("name_locative", {}).get(lang, "")
            node.save()
            by_slug[node.slug] = node
        self.stdout.write(f"KATO demo nodes loaded: {len(by_slug)}")
