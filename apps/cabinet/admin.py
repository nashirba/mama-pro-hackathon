from django.contrib import admin

from apps.accounts.admin import UserAdmin
from apps.accounts.models import User

from .models import Child


class ChildInline(admin.TabularInline):
    model = Child
    extra = 0


admin.site.unregister(User)


@admin.register(User)
class UserWithChildrenAdmin(UserAdmin):
    inlines = [ChildInline]
