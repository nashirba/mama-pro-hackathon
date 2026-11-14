from apps.accounts.models import User
from apps.consents.models import Consent
from tests.factories import UserFactory


def _register_new(client, next_url=None):
    client.post("/ru/login/", {"phone": "+77011234567"})
    data = {"code": "0000", "user_agreement": "on", "pd_processing": "on"}
    if next_url:
        data["next"] = next_url
    return client.post("/ru/login/code/", data)


def test_new_user_goes_to_register_after_code(client, db):
    r = _register_new(client)
    assert r.headers["Location"] == "/ru/register/"
    user = User.objects.get(phone="+77011234567")
    assert not user.has_full_name and Consent.objects.filter(user=user).count() == 2


def test_register_keeps_safe_next(client, db):
    r = _register_new(client, "/ru/specialists/")
    assert r.headers["Location"] == "/ru/register/?next=%2Fru%2Fspecialists%2F"
    r = client.post(
        "/ru/register/", {"last_name": "Иванова", "first_name": "Айгуль", "next": "/ru/specialists/"}
    )
    assert r.headers["Location"] == "/ru/specialists/"


def test_register_drops_external_next(client, db):
    _register_new(client)
    r = client.post(
        "/ru/register/", {"last_name": "Иванова", "first_name": "Айгуль", "next": "https://evil.example/"}
    )
    assert r.headers["Location"] == "/ru/cabinet/"


def test_register_requires_both_names(client, db):
    _register_new(client)
    r = client.post("/ru/register/", {"last_name": "  ", "first_name": "Айгуль"})
    assert r.status_code == 200 and "Обязательное поле" in r.content.decode()
    assert not User.objects.get().has_full_name


def test_register_page_copy(client, db):
    _register_new(client)
    html = client.get("/ru/register/").content.decode()
    assert "Создать личный кабинет" in html and ">Фамилия<" in html and "Создать</button>" in html


def test_register_saves_names_stripped(client, db):
    _register_new(client)
    client.post("/ru/register/", {"last_name": " Иванова ", "first_name": "Айгуль"})
    user = User.objects.get()
    assert (user.last_name, user.first_name) == ("Иванова", "Айгуль")


def test_register_with_full_name_redirects_to_cabinet(client, db):
    client.force_login(UserFactory())
    assert client.get("/ru/register/").headers["Location"] == "/ru/cabinet/"


def test_register_anonymous_redirects_to_login(client, db):
    assert client.get("/ru/register/").headers["Location"].startswith("/ru/login/")
