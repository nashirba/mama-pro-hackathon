from datetime import date

import pytest
from django.utils import translation

from apps.cabinet.ages import format_age


@pytest.mark.parametrize(
    "born, today, expected",
    [
        (date(2021, 3, 12), date(2025, 11, 14), "4 года 8 мес."),
        (date(2024, 11, 14), date(2025, 11, 14), "1 год"),
        (date(2020, 11, 14), date(2025, 11, 14), "5 лет"),
        (date(2025, 3, 1), date(2025, 11, 14), "8 мес."),
        (date(2025, 11, 14), date(2025, 11, 14), "0 мес."),
        (date(2020, 2, 29), date(2021, 2, 28), "11 мес."),
        (date(2020, 2, 29), date(2021, 3, 1), "1 год"),
        (date(2004, 1, 1), date(2025, 6, 1), "21 год 5 мес."),
    ],
)
def test_format_age_ru(born, today, expected):
    with translation.override("ru"):
        assert format_age(born, today) == expected
