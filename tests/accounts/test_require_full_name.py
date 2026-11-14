import pytest

from tests.factories import UserFactory


def test_nameless_user_redirected_from_any_page(client, db):
    client.force_login(UserFactory(first_name="", last_name=""))
    r = client.get("/ru/specialists/", {"q": "лого"})
    # next is the full path with its query already percent-encoded, so it is encoded once more as a value
    assert (
        r.headers["Location"]
        == "/ru/register/?next=%2Fru%2Fspecialists%2F%3Fq%3D%25D0%25BB%25D0%25BE%25D0%25B3%25D0%25BE"
    )


def test_nameless_user_post_redirected_without_next(client, db):
    client.force_login(UserFactory(first_name="", last_name=""))
    assert client.post("/ru/community/new/").headers["Location"] == "/ru/register/"


@pytest.mark.parametrize(
    "method, url",
    [
        ("get", "/ru/register/"),
        ("post", "/ru/logout/"),
        ("post", "/ru/logout/all/"),
        ("get", "/healthz"),
    ],
)
def test_exempt_views(client, db, method, url):
    client.force_login(UserFactory(first_name="", last_name=""))
    r = getattr(client, method)(url)
    location = r.headers.get("Location", "")
    assert location != "/ru/register/" and not location.startswith("/ru/register/?")


def test_setlang_not_redirected(client, db):
    client.force_login(UserFactory(first_name="", last_name=""))
    r = client.post("/i18n/setlang/", {"language": "kk", "next": "/ru/"})
    assert r.headers["Location"] == "/kk/"


def test_staff_without_name_reaches_admin(client, db):
    client.force_login(
        UserFactory(first_name="", last_name="", is_staff=True, is_superuser=True)
    )
    assert client.get("/ru/admin/").status_code == 200


def test_user_with_name_not_redirected(client, db):
    client.force_login(UserFactory())
    assert client.get("/ru/").status_code == 200
