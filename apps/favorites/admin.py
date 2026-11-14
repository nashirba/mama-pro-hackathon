from django.contrib import admin

from .models import Favorite


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "profile", "created_at")
    list_select_related = ("user", "profile")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # Delete stays allowed: Django checks it on cascades, so denying it would block deleting a user or a profile.
