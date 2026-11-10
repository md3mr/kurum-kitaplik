from django.contrib import admin

from .models import Book, BookRequest

admin.site.register(Book)
admin.site.register(BookRequest)