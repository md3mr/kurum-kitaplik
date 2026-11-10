from django.contrib import admin

from .models import Book, BookRequest


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "owner", "holder", "in_pool", "created_at")
    list_filter = ("in_pool", "owner")
    search_fields = ("title", "author", "isbn")


@admin.register(BookRequest)
class BookRequestAdmin(admin.ModelAdmin):
    list_display = ("book", "requester", "owner", "status", "created_at")
    list_filter = ("status",)