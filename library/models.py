from django.conf import settings
from django.db import models
from django.db.models import Q


class Book(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="books")
    holder = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                               on_delete=models.SET_NULL, related_name="borrowed_books")
    title = models.CharField(max_length=300)
    author = models.CharField(max_length=300)
    publisher = models.CharField(max_length=200, blank=True)
    isbn = models.CharField(max_length=13, blank=True, db_index=True)
    cover_url = models.URLField(blank=True)
    in_pool = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} — {self.author}"


class BookRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Onay bekliyor"
        APPROVED = "approved", "Onaylandı"
        RECEIVED = "received", "Teslim alındı"
        RETURNED = "returned", "İade edildi"
        REJECTED = "rejected", "Reddedildi"
        CANCELLED = "cancelled", "İptal edildi"

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="requests")
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                  related_name="sent_requests")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name="received_requests")
    status = models.CharField(max_length=10, choices=Status.choices,
                              default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["book", "requester"],
                condition=Q(status__in=["pending", "approved", "received"]),
                name="unique_active_request_per_user_book"
            )
        ]

    def __str__(self):
        return f"{self.requester} → {self.book} ({self.get_status_display()})"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    # Kitap silinse bile bildirim kalsın; kapak gösterilemezse placeholder
    book = models.ForeignKey(Book, null=True, blank=True, on_delete=models.SET_NULL,
                             related_name="notifications")
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.message[:20]}"