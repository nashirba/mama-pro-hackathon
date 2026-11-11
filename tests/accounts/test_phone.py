import pytest

from apps.accounts.phone import InvalidPhone, normalize_kz_mobile


@pytest.mark.parametrize("raw", ["8 701 123 45 67", "+7 (701) 123-45-67", "87011234567", "7011234567", "+77011234567"])
def test_normalize_variants(raw):
    assert normalize_kz_mobile(raw) == "+77011234567"


@pytest.mark.parametrize("raw", ["+7 727 250 00 00", "+79161234567", "12345", ""])
def test_rejects_non_kz_mobile(raw):
    with pytest.raises(InvalidPhone):
        normalize_kz_mobile(raw)
