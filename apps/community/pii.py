"""Heuristic detection of child data (IIN, phone) in post text. Only warns, never blocks."""

import re

IIN_RE = re.compile(r"(?<!\d)\d{12}(?!\d)")
# Kazakh mobile: optional +7 / 8 / 7 prefix, then 7XX XXX XX XX with optional spaces, dashes and brackets.
# The digit run must start and end at the match, so a 12-digit IIN or a longer number never matches.
PHONE_RE = re.compile(r"(?<!\d)(?:(?:\+7|8|7)[\s\-()]*)?7\d{2}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)")


def looks_sensitive(text: str) -> list[str]:
    found = []
    if IIN_RE.search(text):
        found.append("iin")
    if PHONE_RE.search(text):
        found.append("phone")
    return found
