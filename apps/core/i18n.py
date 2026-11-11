from django.utils.translation import get_language
from parler.utils import get_language_settings


def first_translated(obj, field: str) -> str:
    """First non-empty value of a parler field: the active language, then its fallbacks.

    Parler falls back only when the whole row of the active language is missing; a row with an
    empty field would otherwise hide the fallback text.
    """
    language = get_language()
    for code in [language, *get_language_settings(language).get("fallbacks", [])]:
        if obj.has_translation(code):
            value = obj.safe_translation_getter(field, language_code=code, default="")
            if value:
                return value
    return ""
