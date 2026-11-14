import re

from apps.accounts.models import Role, User
from apps.onboarding.models import Application, BlockedPhone

PHONE = "+77011234567"


def _new_user(client):
    client.post("/ru/login/", {"phone": PHONE})
    client.post("/ru/login/code/", {"code": "0000", "user_agreement": "on", "pd_processing": "on"})


def _register(client, role):
    return client.post("/ru/register/", {"last_name": "Иванова", "first_name": "Айгуль", "role": role})


def test_register_page_asks_who_you_are(client, db):
    _new_user(client)
    html = client.get("/ru/register/").content.decode()
    assert "Кем вы являетесь?" in html
    for value in ("parent", "specialist", "nanny"):
        assert f'value="{value}"' in html
    assert not re.search(r'name="role"[^>]* checked', html)


def test_role_is_required(client, db):
    _new_user(client)
    r = client.post("/ru/register/", {"last_name": "Иванова", "first_name": "Айгуль"})
    assert r.status_code == 200
    assert not User.objects.get(phone=PHONE).has_full_name


def test_parent_goes_to_cabinet(client, db):
    _new_user(client)
    assert _register(client, "parent").headers["Location"] == "/ru/cabinet/"
    assert User.objects.get(phone=PHONE).role == Role.PARENT
    assert not Application.objects.exists()


def test_specialist_goes_to_questionnaire(client, db):
    _new_user(client)
    assert _register(client, "specialist").headers["Location"] == "/ru/cabinet/application/"
    app = Application.objects.get(user__phone=PHONE)
    assert app.category == "specialist" and app.status == "draft"


def test_nanny_gets_nanny_application(client, db):
    _new_user(client)
    _register(client, "nanny")
    assert Application.objects.get(user__phone=PHONE).category == "nanny"


def test_blocked_phone_cannot_apply_but_can_be_parent(client, db):
    BlockedPhone.objects.create(phone=PHONE)
    _new_user(client)
    r = _register(client, "specialist")
    assert r.status_code == 200
    assert "С этого номера нельзя подать анкету специалиста или няни" in r.content.decode()
    assert _register(client, "parent").headers["Location"] == "/ru/cabinet/"
