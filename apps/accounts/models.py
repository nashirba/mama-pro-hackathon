from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    LANGUAGE_CHOICES = [("ru", "Русский"), ("kk", "Қазақша")]

    phone = models.CharField(max_length=16, unique=True)
    email = models.EmailField(blank=True)
    # Community nickname; empty is stored as NULL so several users without one do not break `unique`.
    display_name = models.CharField(max_length=40, null=True, blank=True, unique=True)
    preferred_language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="ru")
    # "Log out everywhere" increments it; it is part of the session auth hash.
    session_epoch = models.PositiveIntegerField(default=0)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    def __str__(self):
        return self.phone

    def save(self, *args, **kwargs):
        self.display_name = (self.display_name or "").strip() or None
        super().save(*args, **kwargs)

    def get_session_auth_hash(self) -> str:
        key_salt = "apps.accounts.models.User.get_session_auth_hash"
        return salted_hmac(
            key_salt,
            f"{self.password}:{self.session_epoch}",
            algorithm="sha256",
        ).hexdigest()


class OtpChallenge(models.Model):
    phone = models.CharField(max_length=16)
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["phone", "-created_at"])]
