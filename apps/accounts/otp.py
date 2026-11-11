import hmac
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import OtpChallenge
from .sms import get_sms_sender


class OtpLocked(Exception):
    """Too many wrong attempts for the active challenge."""


def issue_code(phone: str) -> None:
    # Demo: the code is always settings.DEMO_OTP_CODE.
    code = settings.DEMO_OTP_CODE
    OtpChallenge.objects.create(
        phone=phone,
        expires_at=timezone.now() + timedelta(minutes=settings.OTP_TTL_MIN),
    )
    get_sms_sender().send(phone, _("Код входа в kamqor: %(code)s") % {"code": code})


def verify_code(phone: str, code: str) -> bool:
    with transaction.atomic():
        challenge = (
            OtpChallenge.objects.select_for_update()
            .filter(phone=phone, consumed_at__isnull=True, expires_at__gt=timezone.now())
            .order_by("-created_at", "-id")
            .first()
        )
        if challenge is None:
            return False
        if challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
            raise OtpLocked(phone)
        if hmac.compare_digest(code.encode(), settings.DEMO_OTP_CODE.encode()):
            challenge.consumed_at = timezone.now()
            challenge.save(update_fields=["consumed_at"])
            return True
        challenge.attempts += 1
        challenge.save(update_fields=["attempts"])
        return False
