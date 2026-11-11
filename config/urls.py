from django.contrib import admin
from django.urls import include, path

from accounts import views as accounts_views
from library import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/signup/", accounts_views.signup, name="signup"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", views.home, name="home"),
    path("books/<int:pk>/request/", views.book_request, name="book_request"),
    path("my-books/", views.my_books, name="my_books"),
    path("my-books/add/", views.book_add, name="book_add"),
    path("my-books/isbn-lookup/", views.isbn_lookup, name="isbn_lookup"),
    path("my-books/<int:pk>/toggle/", views.book_toggle_pool, name="book_toggle_pool"),
    path("requests/", views.requests_list, name="requests"),
    path("requests/<int:pk>/<slug:action>/", views.request_action, name="request_action"),
    path("notifications/", views.notifications_list, name="notifications"),
]