import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import User
from apps.community.access import member_required
from tests.factories import NicknamedUserFactory, SpecialistFactory, UserFactory

pytestmark = pytest.mark.django_db


@member_required
def guarded(request, pk=None):
    return HttpResponse("ok")


@member_required(nickname=False)
def guarded_no_nickname(request, pk=None):
    return HttpResponse("ok")


def _request(method="get", user=None, path="/ru/community/5/", **extra):
    rf = RequestFactory()
    request = getattr(rf, method)(path, **extra)
    request.user = user or AnonymousUser()
    return request


def test_guest_write_redirects_to_login_with_next():
    response = guarded(_request("get", path="/ru/community/5/?x=1"))
    assert response.status_code == 302
    assert response["Location"] == reverse("accounts:login") + "?next=%2Fru%2Fcommunity%2F5%2F%3Fx%3D1"


def test_guest_post_request_next_points_to_page_not_endpoint():
    request = _request("post", path="/ru/community/5/like/", HTTP_HX_CURRENT_URL="http://testserver/ru/community/5/")
    response = guarded(request, pk=5)
    assert response["Location"] == reverse("accounts:login") + "?next=%2Fru%2Fcommunity%2F5%2F"


def test_guest_post_without_hx_header_uses_post_next_then_post_page():
    request = _request("post", path="/ru/community/5/like/", data={"next": "/ru/community/?kind=story"})
    assert guarded(request, pk=5)["Location"].endswith("next=%2Fru%2Fcommunity%2F%3Fkind%3Dstory")
    request = _request("post", path="/ru/community/5/like/", data={"next": "https://evil.example/"})
    assert guarded(request, pk=5)["Location"].endswith("next=" + "%2Fru%2Fcommunity%2F5%2F")
    request = _request("post", path="/ru/community/new/")
    assert guarded(request)["Location"].endswith("next=%2Fru%2Fcommunity%2F")


def test_guest_htmx_write_gets_hx_redirect():
    request = _request("post", HTTP_HX_REQUEST="true", HTTP_HX_CURRENT_URL="http://testserver/ru/community/5/")
    response = guarded(request, pk=5)
    assert response.status_code == 204
    assert response["HX-Redirect"] == reverse("accounts:login") + "?next=%2Fru%2Fcommunity%2F5%2F"


def test_nickname_false_skips_nickname():
    user = UserFactory()
    assert guarded_no_nickname(_request("post", user=user), pk=5).status_code == 200
    assert guarded(_request("post", user=user), pk=5).status_code == 302


def test_parent_without_nickname_redirected_to_nickname_then_back(client):
    user = UserFactory()
    client.force_login(user)
    response = client.get("/ru/community/nickname/?next=/ru/community/5/")
    assert response.status_code == 200
    response = client.post("/ru/community/nickname/", {"display_name": "Айгерим", "next": "/ru/community/5/"})
    assert response.status_code == 302 and response["Location"] == "/ru/community/5/"
    user.refresh_from_db()
    assert user.display_name == "Айгерим"

    other = UserFactory()
    htmx = _request("post", user=other, HTTP_HX_REQUEST="true", HTTP_HX_CURRENT_URL="http://testserver/ru/community/5/")
    response = guarded(htmx, pk=5)
    assert response.status_code == 204
    assert response["HX-Redirect"] == reverse("community:nickname") + "?next=%2Fru%2Fcommunity%2F5%2F"
    plain = guarded(_request("get", user=other))
    assert plain.status_code == 302 and plain["Location"].startswith(reverse("community:nickname"))


def test_specialist_never_asked_for_nickname():
    profile = SpecialistFactory()
    assert guarded(_request("post", user=User.objects.get(pk=profile.user_id)), pk=5).status_code == 200


def test_nickname_unique_case_insensitive(client):
    NicknamedUserFactory(display_name="Айгерим")
    user = UserFactory()
    client.force_login(user)
    response = client.post("/ru/community/nickname/", {"display_name": "айгерим"})
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.display_name is None


@pytest.mark.parametrize("name", ["ab", "a" * 41, "bad!name", "<b>x</b>"])
def test_nickname_rejects_invalid(client, name):
    user = UserFactory()
    client.force_login(user)
    assert client.post("/ru/community/nickname/", {"display_name": name}).status_code == 200
    user.refresh_from_db()
    assert user.display_name is None


def test_nickname_rejects_external_next(client):
    client.force_login(UserFactory())
    response = client.post("/ru/community/nickname/", {"display_name": "Мама_Асель", "next": "https://evil.example/"})
    assert response.status_code == 302 and response["Location"] == "/ru/community/"


def test_nickname_guest_redirected_to_login(client):
    response = client.get("/ru/community/nickname/")
    assert response.status_code == 302 and response["Location"].startswith(reverse("accounts:login"))
