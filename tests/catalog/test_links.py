from apps.catalog.links import wa_default_text, wa_me_url


def test_wa_me_url():
    assert (
        wa_me_url("+77011234567", "Здравствуйте!")
        == "https://wa.me/77011234567?text=%D0%97%D0%B4%D1%80%D0%B0%D0%B2%D1%81%D1%82%D0%B2%D1%83%D0%B9%D1%82%D0%B5%21"
    )


def test_wa_default_text_is_gettext_string():
    assert wa_default_text() == "Здравствуйте! Нашёл(ла) вас через «Особенный путь с Mama Pro», хочу записаться на консультацию"


def test_wa_default_text_for_nanny():
    assert wa_default_text(nanny=True) == "Здравствуйте! Нашёл(ла) вас через «Особенный путь с Mama Pro», хочу обсудить работу няней"
