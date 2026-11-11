import re

_KK_TO_BASE = str.maketrans(
    {"ә": "а", "ғ": "г", "қ": "к", "ң": "н", "ө": "о", "ұ": "у", "ү": "у", "һ": "х", "і": "и", "ё": "е"}
)
_NON_WORD = re.compile(r"[^\w]+")


def normalize_kk(text: str) -> str:
    """Lowercase, fold Kazakh-specific letters to their base Cyrillic letters, drop punctuation."""
    return _NON_WORD.sub(" ", text.casefold().translate(_KK_TO_BASE)).strip()
