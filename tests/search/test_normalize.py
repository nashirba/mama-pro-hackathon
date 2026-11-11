from apps.search.normalize import normalize_kk


def test_normalize_kk():
    assert normalize_kk("Қарағанды") == "караганды"
    assert normalize_kk("Өскемен ҮЙ") == "оскемен уй"
