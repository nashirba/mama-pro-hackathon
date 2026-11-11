from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from parler.admin import TranslatableAdmin

from .models import Address, KatoNode


@admin.register(KatoNode)
class KatoNodeAdmin(TranslatableAdmin):
    list_display = ("slug", "code", "level", "parent")
    list_filter = ("level",)
    search_fields = ("slug", "code", "translations__name")


@admin.register(Address)
class AddressAdmin(GISModelAdmin):
    list_display = ("street", "building", "kato")
    raw_id_fields = ("kato",)
