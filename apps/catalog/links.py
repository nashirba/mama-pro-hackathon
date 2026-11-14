import re
from dataclasses import dataclass
from urllib.parse import quote

from django.conf import settings
from django.utils.translation import gettext


def wa_default_text() -> str:
    return gettext("Здравствуйте! Нашёл(ла) вас через «%(brand)s», хочу записаться на консультацию") % {
        "brand": settings.BRAND_NAME
    }


def wa_me_url(phone_e164: str, text: str) -> str:
    digits = re.sub(r"\D", "", phone_e164)
    return f"https://wa.me/{digits}?text={quote(text, safe='')}"


@dataclass(frozen=True)
class ContactLinks:
    whatsapp: str | None
    phone: str | None
    disabled_in_demo: bool = False

    @property
    def visible(self) -> bool:
        return bool(self.whatsapp or self.phone or self.disabled_in_demo)


def contact_links(profile) -> ContactLinks:
    """In demo every contact leads only to DEMO_CONTACT_PHONE (never to a seeded number); empty = disabled buttons."""
    if settings.DEPLOY_PROFILE == "demo":
        demo_phone = settings.DEMO_CONTACT_PHONE
        if not demo_phone:
            return ContactLinks(whatsapp=None, phone=None, disabled_in_demo=True)
        return ContactLinks(whatsapp=wa_me_url(demo_phone, wa_default_text()), phone=f"tel:{demo_phone}")
    return ContactLinks(
        whatsapp=wa_me_url(profile.whatsapp_phone, wa_default_text()) if profile.whatsapp_phone else None,
        phone=f"tel:{profile.public_phone}" if profile.public_phone else None,
    )
