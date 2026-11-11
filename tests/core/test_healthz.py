def test_healthz_ok(client, db):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "db": "ok"}


def test_user_model_uses_phone(db, django_user_model):
    u = django_user_model.objects.create_user(phone="+77011234567")
    assert django_user_model.USERNAME_FIELD == "phone"
    assert u.preferred_language == "ru"


def test_session_auth_hash_changes_with_epoch(db, django_user_model):
    u = django_user_model.objects.create_user(phone="+77011234567")
    before = u.get_session_auth_hash()
    u.session_epoch += 1
    assert u.get_session_auth_hash() != before
