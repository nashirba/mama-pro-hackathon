from datetime import date

import pytest

from apps.cabinet.models import Child
from tests.factories import ChildFactory, UserFactory


def test_add_child_with_first_name_only(client, db):
    user = UserFactory()
    client.force_login(user)
    r = client.post(
        "/ru/cabinet/children/add/",
        {"first_name": "Арман", "last_name": "", "birth_date": "", "sex": ""},
    )
    assert r.headers["Location"] == "/ru/cabinet/"
    child = user.children.get()
    assert child.first_name == "Арман" and child.birth_date is None and child.sex == ""


def test_add_child_requires_first_name(client, db):
    client.force_login(UserFactory())
    r = client.post(
        "/ru/cabinet/children/add/", {"first_name": "", "last_name": "Иванов"}
    )
    assert r.status_code == 200 and not Child.objects.exists()


@pytest.mark.freeze_time("2025-11-14")
def test_cabinet_card_shows_filled_fields_and_age(client, db):
    user = UserFactory()
    ChildFactory(
        parent=user,
        first_name="Арман",
        last_name="Иванов",
        birth_date=date(2021, 3, 12),
        sex="male",
    )
    ChildFactory(parent=user, first_name="Дана")
    client.force_login(user)
    html = client.get("/ru/cabinet/").content.decode()
    assert "Иванов Арман" in html and "4 года 8 мес." in html and "Мальчик" in html
    assert "Дана" in html


def test_edit_child(client, db):
    child = ChildFactory()
    client.force_login(child.parent)
    client.post(
        f"/ru/cabinet/children/{child.pk}/edit/",
        {
            "first_name": "Арман",
            "last_name": "Иванов",
            "birth_date": "2021-03-12",
            "sex": "male",
        },
    )
    child.refresh_from_db()
    assert (child.last_name, child.sex) == ("Иванов", "male")


def test_delete_child(client, db):
    child = ChildFactory()
    client.force_login(child.parent)
    r = client.post(f"/ru/cabinet/children/{child.pk}/delete/")
    assert r.headers["Location"] == "/ru/cabinet/"
    assert not Child.objects.exists()


def test_delete_requires_post(client, db):
    child = ChildFactory()
    client.force_login(child.parent)
    assert client.get(f"/ru/cabinet/children/{child.pk}/delete/").status_code == 405


@pytest.mark.parametrize(
    "method, suffix", [("get", "edit/"), ("post", "edit/"), ("post", "delete/")]
)
def test_other_parents_child_is_404(client, db, method, suffix):
    child = ChildFactory()
    client.force_login(UserFactory())
    r = getattr(client, method)(
        f"/ru/cabinet/children/{child.pk}/{suffix}", {"first_name": "Чужой"}
    )
    assert r.status_code == 404
    child.refresh_from_db()
    assert child.first_name == "Арман"


@pytest.mark.freeze_time("2026-11-14")
def test_child_birth_date_in_future_rejected(client, db):
    client.force_login(UserFactory())
    r = client.post(
        "/ru/cabinet/children/add/",
        {"first_name": "Арман", "birth_date": "2026-11-15"},
    )
    assert "Дата рождения не может быть в будущем" in r.content.decode()


def test_demo_banner_on_child_form(client, db, settings):
    client.force_login(UserFactory())
    settings.DEPLOY_PROFILE = "demo"
    html = client.get("/ru/cabinet/children/add/").content.decode()
    assert "не вводите реальные данные ребёнка" in html
    settings.DEPLOY_PROFILE = "test"
    html = client.get("/ru/cabinet/children/add/").content.decode()
    assert "не вводите реальные данные ребёнка" not in html
