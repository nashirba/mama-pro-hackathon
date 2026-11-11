from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from parler.models import TranslatableModel, TranslatedFields

DESCENDANTS_SQL = """
WITH RECURSIVE tree AS (
    SELECT id FROM geo_katonode WHERE id = %s
    UNION ALL
    SELECT n.id FROM geo_katonode n JOIN tree t ON n.parent_id = t.id
)
SELECT id FROM tree
"""


class KatoNode(TranslatableModel):
    class Level(models.TextChoices):
        REGION = "region", _("Область")
        CITY = "city", _("Город")
        DISTRICT = "district", _("Район")
        RURAL = "rural", _("Сельский округ")

    code = models.CharField(max_length=20, unique=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    level = models.CharField(max_length=10, choices=Level.choices)
    slug = models.SlugField(max_length=80, unique=True)
    two_gis_city_slug = models.CharField(max_length=50, blank=True)
    center = gis_models.PointField(srid=4326, null=True, blank=True)

    translations = TranslatedFields(
        name=models.CharField(max_length=200),
        name_locative=models.CharField(max_length=200, blank=True),
    )

    def __str__(self):
        return self.safe_translation_getter("name", default=self.slug)

    def descendant_ids(self) -> list[int]:
        """Id of this node and of all nodes below it."""
        return [n.id for n in KatoNode.objects.raw(DESCENDANTS_SQL, [self.pk])]

    def ancestor_ids(self) -> list[int]:
        """Ids of ancestors, nearest first."""
        ids = []
        node = self.parent
        while node is not None:
            ids.append(node.id)
            node = node.parent
        return ids

    def city(self) -> "KatoNode | None":
        node = self
        while node is not None:
            if node.level == self.Level.CITY:
                return node
            node = node.parent
        return None


TWO_GIS_PREFIX = "https://2gis.kz/"


def validate_two_gis_firm_url(value: str) -> None:
    if not value.startswith(TWO_GIS_PREFIX):
        raise ValidationError(_("Ссылка должна начинаться с %(prefix)s"), params={"prefix": TWO_GIS_PREFIX})


class Address(models.Model):
    kato = models.ForeignKey(KatoNode, on_delete=models.PROTECT, related_name="addresses")
    street = models.CharField(max_length=200)
    building = models.CharField(max_length=50)
    point = gis_models.PointField(srid=4326)
    two_gis_firm_url = models.URLField(blank=True, validators=[validate_two_gis_firm_url])

    def __str__(self):
        return f"{self.street}, {self.building}"

    def city_slug(self) -> str:
        city = self.kato.city()
        return city.two_gis_city_slug if city else ""
