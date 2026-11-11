import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat, PhoneNumberType


class InvalidPhone(ValueError):
    """The value is not a Kazakhstan mobile number."""


def normalize_kz_mobile(raw: str) -> str:
    """Return the number in E.164 (+77XXXXXXXXX) or raise InvalidPhone."""
    try:
        number = phonenumbers.parse(raw, "KZ")
    except NumberParseException as exc:
        raise InvalidPhone(raw) from exc
    if not phonenumbers.is_valid_number(number):
        raise InvalidPhone(raw)
    if phonenumbers.number_type(number) != PhoneNumberType.MOBILE:
        raise InvalidPhone(raw)
    e164 = phonenumbers.format_number(number, PhoneNumberFormat.E164)
    if not e164.startswith("+77"):
        raise InvalidPhone(raw)
    return e164
