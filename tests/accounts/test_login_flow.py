import re

import pytest
from django.test import Client

from apps.accounts.models import User
from apps.consents.models import Consent


def test_code_form_shows_demo_code_only_in_demo(client, db, settings):
    settings.DEPLOY_PROFILE = "demo"
    client.post("/ru/login/", {"phone": "+77011234567"})
    assert 'data-demo-code="0000"' in client.get("/ru/login/code/").content.decode()
    settings.DEPLOY_PROFILE = "test"
    assert "data-demo-code" not in client.get("/ru/login/code/").content.decode()


def test_new_user_must_accept_consents(client, db):
    client.post("/ru/login/", {"phone": "+77011234567"})
    r = client.post("/ru/login/code/", {"code": "0000"})
    assert r.status_code == 200
    assert not User.objects.filter(phone="+77011234567").exists()
    assert Consent.objects.count() == 0


def test_missing_consents_do_not_burn_an_otp_attempt(client, db):
    client.post("/ru/login/", {"phone": "+77011234567"})
    for _ in range(6):
        assert client.post("/ru/login/code/", {"code": "1111"}).status_code == 200
    r = client.post("/ru/login/code/", {"code": "0000", "user_agreement": "on", "pd_processing": "on"})
    assert r.status_code == 302


def test_registration_form_shows_agreement_summary(client, db):
    client.post("/kk/login/", {"phone": "+77011234567"})
    html = client.get("/kk/login/code/").content.decode()
    assert re.search(r'data-consent-summary="user_agreement">\s*\S', html)
    assert re.search(r'data-consent-summary="pd_processing">\s*\S', html)
    assert 'name="user_agreement"' in html and 'name="pd_processing"' in html


def test_returning_user_form_has_no_consent_fields(client, db):
    User.objects.create_user(phone="+77011234567")
    client.post("/ru/login/", {"phone": "+77011234567"})
    html = client.get("/ru/login/code/").content.decode()
    assert 'name="user_agreement"' not in html


def test_new_user_registered_with_consents(client, db):
    client.post("/kk/login/", {"phone": "8 701 123 45 67"})
    r = client.post(
        "/kk/login/code/",
        {"code": "0000", "user_agreement": "on", "pd_processing": "on"},
        REMOTE_ADDR="10.0.0.5",
    )
    assert r.status_code == 302
    assert r.headers["Location"] == "/kk/register/"
    assert r.cookies["django_language"].value == "kk"
    user = User.objects.get(phone="+77011234567")
    assert user.preferred_language == "kk"
    consents = Consent.objects.filter(user=user)
    assert {c.kind for c in consents} == {"user_agreement", "pd_processing"}
    assert all(c.version == "v1" and c.ip == "10.0.0.5" for c in consents)


def test_returning_user_logs_in_without_new_consents(client, db):
    User.objects.create_user(phone="+77011234567")
    client.post("/ru/login/", {"phone": "+77011234567"})
    r = client.post("/ru/login/code/", {"code": "0000"})
    assert r.status_code == 302 and Consent.objects.count() == 0


def test_wrong_code_shows_error(client, db):
    User.objects.create_user(phone="+77011234567")
    client.post("/ru/login/", {"phone": "+77011234567"})
    r = client.post("/ru/login/code/", {"code": "1111"})
    assert r.status_code == 200 and "_auth_user_id" not in client.session


def test_locked_code_shows_error_not_500(client, db):
    User.objects.create_user(phone="+77011234567")
    client.post("/ru/login/", {"phone": "+77011234567"})
    for _ in range(5):
        client.post("/ru/login/code/", {"code": "1111"})
    r = client.post("/ru/login/code/", {"code": "0000"})
    assert r.status_code == 200 and "_auth_user_id" not in client.session


def test_code_page_without_phone_redirects_to_login(client, db):
    r = client.get("/ru/login/code/")
    assert r.status_code == 302 and r.headers["Location"] == "/ru/login/"


def test_bad_phone_shows_form_error_not_500(client, db):
    r = client.post("/ru/login/", {"phone": "+7 727 250 00 00"})
    assert r.status_code == 200 and "мобильный номер" in r.content.decode()


def test_login_activates_preferred_language(client, db):
    User.objects.create_user(phone="+77011234567", preferred_language="kk")
    client.post("/ru/login/", {"phone": "+77011234567"})
    r = client.post("/ru/login/code/", {"code": "0000", "next": "/ru/"})
    assert r.headers["Location"] == "/kk/"
    assert r.cookies["django_language"].value == "kk"


def test_safe_next_is_followed(client, db):
    User.objects.create_user(phone="+77011234567")
    client.post("/ru/login/", {"phone": "+77011234567"})
    r = client.post("/ru/login/code/", {"code": "0000", "next": "/ru/specialists/"})
    assert r.headers["Location"] == "/ru/specialists/"


def test_open_redirect_blocked(client, db):
    User.objects.create_user(phone="+77011234567")
    client.post("/ru/login/", {"phone": "+77011234567"})
    r = client.post("/ru/login/code/", {"code": "0000", "next": "https://evil.example/"})
    assert r.headers["Location"] == "/ru/"


def test_logout_ends_session(client, db):
    client.force_login(User.objects.create_user(phone="+77011234567"))
    assert client.post("/ru/logout/").status_code == 302
    assert "_auth_user_id" not in client.session


def test_logout_all_invalidates_other_sessions(db):
    user = User.objects.create_user(phone="+77011234567")
    a, b = Client(), Client()
    a.force_login(user)
    b.force_login(user)
    assert b.get("/ru/").wsgi_request.user.is_authenticated
    a.post("/ru/logout/all/")
    assert b.get("/ru/").wsgi_request.user.is_authenticated is False


@pytest.mark.parametrize("flags", [{"is_staff": True}, {"is_staff": True, "is_superuser": True}, {"is_active": False}])
def test_staff_cannot_login_with_otp(client, db, flags):
    User.objects.create_user(phone="+77011234567", **flags)
    client.post("/ru/login/", {"phone": "+77011234567"})
    r = client.post("/ru/login/code/", {"code": "0000"})
    assert r.status_code == 200
    assert "Неверный или просроченный код" in r.content.decode()
    assert "_auth_user_id" not in client.session


def test_demo_consent_does_not_claim_storage_in_kazakhstan(client, db, settings):
    settings.DEPLOY_PROFILE = "demo"
    assert "SMS не отправляются" in client.get("/ru/login/").content.decode()
    client.post("/ru/login/", {"phone": "+77011234567"})
    html = client.get("/ru/login/code/").content.decode()
    assert "на территории Республики Казахстан" not in html and "за пределами Республики Казахстан" in html
    settings.DEPLOY_PROFILE = "test"
    assert "на территории Республики Казахстан" in client.get("/ru/login/code/").content.decode()
    assert "Мы отправим код подтверждения" in client.get("/ru/login/").content.decode()


def test_pd_consent_lists_names_and_children(client, db):
    client.post("/ru/login/", {"phone": "+77011234567"})
    html = client.get("/ru/login/code/").content.decode()
    assert "фамилия, имя и дата рождения" in html and "пол детей" in html
