def test_root_redirects_ru_by_default(client):
    assert client.get("/").headers["Location"] == "/ru/"


def test_root_redirects_kk_by_accept_language(client):
    r = client.get("/", HTTP_ACCEPT_LANGUAGE="kk")
    assert r.headers["Location"] == "/kk/"


def test_html_lang_attribute(client, db):
    assert '<html lang="kk"' in client.get("/kk/").content.decode()


def test_demo_banner_only_in_demo(client, db, settings):
    settings.DEPLOY_PROFILE = "demo"
    assert "Демо-версия" in client.get("/ru/").content.decode()
    settings.DEPLOY_PROFILE = "test"
    assert "Демо-версия" not in client.get("/ru/").content.decode()


def test_setlang_saves_preferred_language_for_authenticated_user(client, db, django_user_model):
    user = django_user_model.objects.create_user(phone="+77011234567")
    client.force_login(user)
    r = client.post("/i18n/setlang/", {"language": "kk", "next": "/ru/"})
    assert r.status_code == 302 and r.headers["Location"] == "/kk/"
    user.refresh_from_db()
    assert user.preferred_language == "kk"


def test_setlang_anonymous_sets_cookie_only(client, db):
    r = client.post("/i18n/setlang/", {"language": "kk", "next": "/ru/"})
    assert r.cookies["django_language"].value == "kk"


def test_demo_banner_says_profiles_and_badges_are_fictional(client, db, settings):
    settings.DEPLOY_PROFILE = "demo"
    assert "Анкеты специалистов и отметки о проверке вымышлены." in client.get("/ru/").content.decode()
    assert "Мамандардың анкеталары мен тексеру белгілері ойдан шығарылған." in client.get("/kk/").content.decode()
    settings.DEPLOY_PROFILE = "test"
    assert "вымышлены" not in client.get("/ru/").content.decode()


def test_language_switcher_refreshes_next_from_current_location(client, db):
    assert "location.pathname + location.search" in client.get("/ru/").content.decode()
