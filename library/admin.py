from django.contrib import admin

from .models import Book, BookRequest, Notification


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "owner", "holder", "in_pool", "created_at")
    list_filter = ("in_pool", "created_at")
    search_fields = ("title", "author", "isbn", "owner__username", "holder__username")
    raw_id_fields = ("owner", "holder")
    list_select_related = ("owner", "holder")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)


@admin.register(BookRequest)
class BookRequestAdmin(admin.ModelAdmin):
    list_display = ("book", "requester", "owner", "status", "created_at", "updated_at")
    list_filter = ("status", "created_at")
    search_fields = (
        "book__title", "book__author",
        "requester__username", "owner__username",
    )
    raw_id_fields = ("book", "requester", "owner")
    list_select_related = ("book", "requester", "owner")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "short_message", "is_read", "created_at")
    list_filter = ("is_read", "created_at")
    search_fields = ("user__username", "message")
    raw_id_fields = ("user", "book")
    list_select_related = ("user", "book")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    @admin.display(description="Mesaj")
    def short_message(self, obj):
        return obj.message[:60] + ("…" if len(obj.message) > 60 else "")