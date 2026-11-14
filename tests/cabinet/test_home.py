from datetime import date

import pytest

from tests.factories import UserFactory


def test_cabinet_requires_login(client, db):
    assert client.get("/ru/cabinet/").headers["Location"].startswith("/ru/login/?next=")


def test_cabinet_shows_parent_data(client, db):
    user = UserFactory(phone="+77011234567")
    client.force_login(user)
    html = client.get("/ru/cabinet/").content.decode()
    assert "Иванова" in html and "Айгуль" in html and "+77011234567" in html
    assert "не указана" in html and "Вы ещё не добавили ребёнка" in html


def test_header_link_for_logged_in_only(client, db):
    assert "Личный кабинет" not in client.get("/ru/").content.decode()
    client.force_login(UserFactory())
    assert 'href="/ru/cabinet/"' in client.get("/ru/").content.decode()


def test_profile_edit_saves_birth_date(client, db):
    user = UserFactory()
    client.force_login(user)
    r = client.post(
        "/ru/cabinet/edit/",
        {"last_name": "Петрова", "first_name": "Алия", "birth_date": "1990-05-17"},
    )
    assert r.headers["Location"] == "/ru/cabinet/"
    user.refresh_from_db()
    assert (user.last_name, user.birth_date) == ("Петрова", date(1990, 5, 17))


@pytest.mark.freeze_time("2026-11-14")
def test_profile_birth_date_in_future_rejected(client, db):
    client.force_login(UserFactory())
    r = client.post(
        "/ru/cabinet/edit/",
        {"last_name": "Петрова", "first_name": "Алия", "birth_date": "2026-11-15"},
    )
    assert "Дата рождения не может быть в будущем" in r.content.decode()


def test_profile_edit_requires_names(client, db):
    client.force_login(UserFactory())
    r = client.post("/ru/cabinet/edit/", {"last_name": "", "first_name": "Алия"})
    assert r.status_code == 200
