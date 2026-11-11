from apps.accounts.models import User

from .models import CURRENT_VERSION, Consent


def record_consents(user: User, kinds: list[str], ip: str) -> list[Consent]:
    return Consent.objects.bulk_create(
        [Consent(user=user, kind=kind, version=CURRENT_VERSION, ip=ip or None) for kind in kinds]
    )
