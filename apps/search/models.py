from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from apps.catalog.models import (
    PracticeContext,
    ProfileCategory,
    Service,
    SpecialistProfile,
)
from apps.geo.models import Address


class SearchOffer(models.Model):
    """Denormalized catalog row: one per service format (one per address for in-person). Rebuilt by `apps.search.builder`."""

    specialist = models.ForeignKey(SpecialistProfile, on_delete=models.CASCADE, related_name="search_offers")
    category = models.CharField(max_length=20, default=ProfileCategory.SPECIALIST, db_index=True)  # the section
    context = models.ForeignKey(PracticeContext, on_delete=models.CASCADE, related_name="search_offers")
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="search_offers")
    address = models.ForeignKey(Address, null=True, blank=True, on_delete=models.CASCADE, related_name="search_offers")
    point = gis_models.PointField(srid=4326, null=True, blank=True)
    kato_ids = ArrayField(models.IntegerField(), default=list)
    is_online = models.BooleanField(default=False)
    formats = ArrayField(models.CharField(max_length=20), default=list)  # exactly one element: the format of this row

    price_session = models.PositiveIntegerField(null=True, blank=True)
    price_month = models.PositiveIntegerField(null=True, blank=True)
    price_hour = models.PositiveIntegerField(null=True, blank=True)  # a nanny only
    price_night = models.PositiveIntegerField(null=True, blank=True)  # a nanny only
    is_free = models.BooleanField(default=False)
    age_min = models.PositiveSmallIntegerField()
    age_max = models.PositiveSmallIntegerField()

    condition_ids = ArrayField(models.IntegerField(), default=list)
    method_ids = ArrayField(models.IntegerField(), default=list)
    specialist_type_ids = ArrayField(models.IntegerField(), default=list)
    language_codes = ArrayField(models.CharField(max_length=10), default=list)
    experience_years = models.PositiveSmallIntegerField(default=0)
    training_hours = models.PositiveIntegerField(default=0)  # a nanny only: the sum over her courses
    verification_levels = ArrayField(models.CharField(max_length=20), default=list)  # plan 4 fills these from real badges

    search_vector = SearchVectorField(null=True)
    search_norm = models.TextField(default="")

    class Meta:
        indexes = [
            GinIndex(fields=["search_vector"], name="searchoffer_vector_gin"),
            GinIndex(fields=["search_norm"], opclasses=["gin_trgm_ops"], name="searchoffer_norm_trgm"),
            GinIndex(fields=["kato_ids"], name="searchoffer_kato_gin"),
            GinIndex(fields=["condition_ids"], name="searchoffer_cond_gin"),
            GinIndex(fields=["method_ids"], name="searchoffer_method_gin"),
            GinIndex(fields=["specialist_type_ids"], name="searchoffer_type_gin"),
            GinIndex(fields=["language_codes"], name="searchoffer_lang_gin"),
        ]

    def __str__(self):
        return f"{self.specialist_id}/{self.service_id}/{self.formats}"
