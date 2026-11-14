from tests.factories import UserFactory


def _start(client, new="8 702 765 43 21"):
    return client.post("/ru/cabinet/phone/", {"phone": new})


def test_phone_change_success(client, db):
    user = UserFactory(phone="+77011234567")
    client.force_login(user)
    assert _start(client).headers["Location"] == "/ru/cabinet/phone/code/"
    r = client.post("/ru/cabinet/phone/code/", {"code": "0000"})
    assert r.headers["Location"] == "/ru/cabinet/"
    user.refresh_from_db()
    assert user.phone == "+77027654321"
    assert "Номер телефона изменён" in client.get("/ru/cabinet/").content.decode()


def test_login_with_new_phone_after_change(client, db):
    user = UserFactory(phone="+77011234567")
    client.force_login(user)
    _start(client)
    client.post("/ru/cabinet/phone/code/", {"code": "0000"})
    client.post("/ru/logout/")
    client.post("/ru/login/", {"phone": "+77027654321"})
    r = client.post("/ru/login/code/", {"code": "0000"})
    assert r.status_code == 302 and client.session["_auth_user_id"] == str(user.pk)


def test_wrong_code_keeps_old_phone(client, db):
    user = UserFactory(phone="+77011234567")
    client.force_login(user)
    _start(client)
    r = client.post("/ru/cabinet/phone/code/", {"code": "1111"})
    assert "Неверный или просроченный код" in r.content.decode()
    user.refresh_from_db()
    assert user.phone == "+77011234567"


def test_locked_after_five_wrong_codes(client, db):
    user = UserFactory(phone="+77011234567")
    client.force_login(user)
    _start(client)
    for _ in range(5):
        client.post("/ru/cabinet/phone/code/", {"code": "1111"})
    r = client.post("/ru/cabinet/phone/code/", {"code": "0000"})
    assert "Слишком много неверных попыток" in r.content.decode()
    user.refresh_from_db()
    assert user.phone == "+77011234567"


def test_same_phone_in_other_format_rejected(client, db):
    client.force_login(UserFactory(phone="+77011234567"))
    assert "Это ваш текущий номер" in _start(client, "8 701 123 45 67").content.decode()


def test_taken_phone_rejected(client, db):
    UserFactory(phone="+77027654321")
    client.force_login(UserFactory(phone="+77011234567"))
    assert "Этот номер уже используется" in _start(client).content.decode()


def test_phone_taken_during_verification(client, db):
    user = UserFactory(phone="+77011234567")
    client.force_login(user)
    _start(client)
    UserFactory(phone="+77027654321")
    r = client.post("/ru/cabinet/phone/code/", {"code": "0000"})
    assert r.status_code == 200 and "Этот номер уже используется" in r.content.decode()
    assert "cabinet_new_phone" not in client.session
    user.refresh_from_db()
    assert user.phone == "+77011234567"


def test_code_step_without_session_redirects(client, db):
    client.force_login(UserFactory())
    assert (
        client.get("/ru/cabinet/phone/code/").headers["Location"]
        == "/ru/cabinet/phone/"
    )


def test_invalid_phone_shows_error(client, db):
    client.force_login(UserFactory())
    assert "мобильный номер" in _start(client, "+7 727 250 00 00").content.decode()


def test_phone_change_requires_login(client, db):
    assert client.get("/ru/cabinet/phone/").headers["Location"].startswith("/ru/login/")
