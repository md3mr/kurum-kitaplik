from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    email = models.EmailField(unique=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        # Boş e-postayı '' yerine NULL kaydet; birden fazla NULL serbest,
        # '' ise benzersizlik kuralını ihlal eder.
        if not self.email:
            self.email = None
        super().save(*args, **kwargs)