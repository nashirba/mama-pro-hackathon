from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Comment, Complaint, Post
from .names import author_name


class _HideShowMixin:
    @admin.action(description=_("Скрыть"))
    def hide(self, request, queryset):
        queryset.update(is_hidden=True)

    @admin.action(description=_("Показать"))
    def unhide(self, request, queryset):
        queryset.update(is_hidden=False)


@admin.register(Post)
class PostAdmin(_HideShowMixin, admin.ModelAdmin):
    list_display = ("id", "kind", "rating", "author_label", "short_body", "is_hidden", "is_deleted", "created_at")
    list_filter = ("is_hidden", "is_deleted", "kind")
    search_fields = ("body",)
    raw_id_fields = ("author", "specialist", "condition", "city")
    readonly_fields = ("search_vector", "search_norm")
    actions = ("hide", "unhide")

    @admin.display(description=_("Автор"))
    def author_label(self, obj):
        return author_name(obj.author) or obj.author_id

    @admin.display(description=_("Текст"))
    def short_body(self, obj):
        return obj.body[:80]


@admin.register(Comment)
class CommentAdmin(_HideShowMixin, admin.ModelAdmin):
    list_display = ("id", "post", "author_label", "short_body", "is_hidden", "is_deleted", "created_at")
    list_filter = ("is_hidden", "is_deleted", "post__kind")
    search_fields = ("body",)
    raw_id_fields = ("post", "author", "parent")
    actions = ("hide", "unhide")

    @admin.display(description=_("Автор"))
    def author_label(self, obj):
        return author_name(obj.author) or obj.author_id

    @admin.display(description=_("Текст"))
    def short_body(self, obj):
        return obj.body[:80]


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "reason", "status", "target_link", "created_at")
    list_filter = ("status", "reason")
    raw_id_fields = ("user", "post", "comment")
    actions = ("hide_and_resolve", "resolve")

    @admin.display(description=_("Объект"))
    def target_link(self, obj):
        target = obj.target
        url = reverse(f"admin:community_{target._meta.model_name}_change", args=[target.pk])
        return format_html('<a href="{}">{}</a>', url, target)

    @admin.action(description=_("Скрыть контент и закрыть жалобу"))
    def hide_and_resolve(self, request, queryset):
        for complaint in queryset.select_related("post", "comment"):
            target = complaint.target
            target.is_hidden = True
            target.save(update_fields=["is_hidden"])
        queryset.update(status=Complaint.Status.RESOLVED)

    @admin.action(description=_("Закрыть жалобу"))
    def resolve(self, request, queryset):
        queryset.update(status=Complaint.Status.RESOLVED)
