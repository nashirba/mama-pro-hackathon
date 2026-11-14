from datetime import date

from django.utils.translation import ngettext


def format_age(birth_date: date, today: date) -> str:
    """Full years and remaining full months, e.g. «4 года 8 мес.»."""
    total_months = (today.year - birth_date.year) * 12 + today.month - birth_date.month
    if today.day < birth_date.day:
        total_months -= 1
    # A 29 February birthday completes the month on 1 March in non-leap years.
    years, months = divmod(max(total_months, 0), 12)

    parts = []
    if years:
        parts.append(ngettext("%(n)d год", "%(n)d лет", years) % {"n": years})
    if months or not years:
        parts.append(ngettext("%(n)d мес.", "%(n)d мес.", months) % {"n": months})
    return " ".join(parts)
