import re

import pytest
from django.db import IntegrityError, connection
from django.test.utils import CaptureQueriesContext

from apps.catalog.models import SpecialistProfile
from tests.factories import FavoriteFactory, UserFactory


def test_toggle_adds_and_removes(client, catalog_fixture):
    user = UserFactory()
    client.force_login(user)
    client.post("/ru/favorites/ivanova-logoped/toggle/")
    assert user.favorites.filter(profile__slug="ivanova-logoped").exists()
    client.post("/ru/favorites/ivanova-logoped/toggle/")
    assert not user.favorites.exists()


def test_toggle_htmx_returns_button(client, catalog_fixture):
    client.force_login(UserFactory())
    html = client.post("/ru/favorites/ivanova-logoped/toggle/", HTTP_HX_REQUEST="true").content.decode()
    assert 'aria-pressed="true"' in html and "<html" not in html


def test_toggle_requires_login(client, catalog_fixture):
    assert client.post("/ru/favorites/ivanova-logoped/toggle/").headers["Location"].startswith("/ru/login/")


def test_toggle_htmx_keeps_button_id_for_focus(client, catalog_fixture):
    client.force_login(UserFactory())
    profile = SpecialistProfile.objects.get(slug="ivanova-logoped")
    html = client.post("/ru/favorites/ivanova-logoped/toggle/", HTTP_HX_REQUEST="true").content.decode()
    assert f'id="fav-{profile.pk}"' in html


@pytest.mark.parametrize(
    "current, expected_next",
    [
        ("http://testserver/ru/specialists/?q=x", "/ru/specialists/%3Fq%3Dx"),
        ("https://evil.example/ru/specialists/", "/ru/specialist/ivanova-logoped/"),
        (None, "/ru/specialist/ivanova-logoped/"),
    ],
)
def test_toggle_htmx_anonymous_redirects_page_to_login(client, catalog_fixture, current, expected_next):
    headers = {"HTTP_HX_REQUEST": "true"}
    if current:
        headers["HTTP_HX_CURRENT_URL"] = current
    response = client.post("/ru/favorites/ivanova-logoped/toggle/", **headers)
    assert response.status_code == 204 and not response.content
    assert response.headers["HX-Redirect"] == f"/ru/login/?next={expected_next}"


def test_toggle_htmx_response_runs_no_city_query(client, catalog_fixture):
    client.force_login(UserFactory())
    with CaptureQueriesContext(connection) as ctx:
        client.post("/ru/favorites/ivanova-logoped/toggle/", HTTP_HX_REQUEST="true")
    assert not [q for q in ctx.captured_queries if "geo_katonode" in q["sql"]]


def test_toggle_get_not_allowed(client, catalog_fixture):
    client.force_login(UserFactory())
    assert client.get("/ru/favorites/ivanova-logoped/toggle/").status_code == 405


def test_toggle_unknown_slug_404(client, db):
    client.force_login(UserFactory())
    assert client.post("/ru/favorites/nope/toggle/").status_code == 404


def test_toggle_redirects_to_safe_next(client, catalog_fixture):
    client.force_login(UserFactory())
    url = "/ru/favorites/ivanova-logoped/toggle/"
    assert client.post(url, {"next": "/ru/specialists/"}).headers["Location"] == "/ru/specialists/"
    assert (
        client.post(url, {"next": "https://evil.example/"})
        .headers["Location"]
        .endswith("/ru/specialist/ivanova-logoped/")
    )


def test_toggle_nanny_without_next_redirects_to_nanny_page(client, nannies):
    client.force_login(UserFactory())
    response = client.post("/ru/favorites/aigul-nanny/toggle/")
    assert response.headers["Location"].endswith("/ru/nanny/aigul-nanny/")


def test_card_heart_for_anonymous_links_to_login(client, catalog_fixture):
    html = client.get("/ru/specialists/").content.decode()
    assert 'href="/ru/login/?next=%2Fru%2Fspecialists%2F"' in html and "В избранное" in html


def test_card_heart_shows_state_and_sits_above_overlay(client, catalog_fixture):
    user = UserFactory()
    client.force_login(user)
    FavoriteFactory(user=user, profile=SpecialistProfile.objects.get(slug="ivanova-logoped"))
    html = client.get("/ru/specialists/").content.decode()
    assert html.count('aria-pressed="true"') == 1
    wrapper = re.search(r'<div class="([^"]*)"><form[^>]*favorites/ivanova-logoped/toggle/', html)
    assert wrapper and {"absolute", "right-2", "top-2", "z-10"} <= set(wrapper.group(1).split())


def test_card_form_has_csrf_token(client, catalog_fixture):
    client.force_login(UserFactory())
    assert "csrfmiddlewaretoken" in client.get("/ru/specialists/").content.decode()


def test_second_htmx_toggle_unpresses(client, catalog_fixture):
    client.force_login(UserFactory())
    url = "/ru/favorites/ivanova-logoped/toggle/"
    client.post(url, HTTP_HX_REQUEST="true")
    html = client.post(url, HTTP_HX_REQUEST="true").content.decode()
    assert 'aria-pressed="false"' in html


def test_favorite_ids_one_query_per_request(client, catalog_fixture):
    user = UserFactory()
    client.force_login(user)
    for profile in SpecialistProfile.objects.all()[:3]:
        FavoriteFactory(user=user, profile=profile)
    with CaptureQueriesContext(connection) as ctx:
        response = client.get("/ru/specialists/")
    assert response.content.decode().count("data-specialist=") > 1
    assert len([q for q in ctx.captured_queries if "favorites_favorite" in q["sql"]]) == 1


def test_toggle_cannot_add_hidden_profile(client, catalog_fixture):
    user = UserFactory()
    client.force_login(user)
    assert client.post("/ru/favorites/hidden-logoped/toggle/").status_code == 404
    assert not user.favorites.exists()


def test_toggle_can_remove_favorite_of_hidden_profile(client, catalog_fixture):
    user = UserFactory()
    client.force_login(user)
    FavoriteFactory(user=user, profile=SpecialistProfile.objects.get(slug="hidden-logoped"))
    assert client.post("/ru/favorites/hidden-logoped/toggle/").status_code == 302
    assert not user.favorites.exists()


def test_nanny_card_and_detail_have_heart(client, nannies):
    client.force_login(UserFactory())
    assert "В избранное" in client.get("/ru/nannies/").content.decode()
    assert "В избранное" in client.get("/ru/nanny/aigul-nanny/").content.decode()


def test_specialist_detail_has_heart(client, catalog_fixture):
    assert "В избранное" in client.get("/ru/specialist/ivanova-logoped/").content.decode()


def test_favorite_unique_per_user_profile(db):
    favorite = FavoriteFactory()
    with pytest.raises(IntegrityError):
        FavoriteFactory(user=favorite.user, profile=favorite.profile)


def test_admin_can_delete_user_with_favorites(client, catalog_fixture):
    from django.contrib.admin.sites import site
    from django.contrib.admin.utils import get_deleted_objects
    from django.test import RequestFactory

    from apps.accounts.models import User

    owner = UserFactory()
    FavoriteFactory(user=owner, profile=SpecialistProfile.objects.get(slug="ivanova-logoped"))
    admin_user = User.objects.create_superuser(phone="+77019998877", password="x")
    request = RequestFactory().post("/")
    request.user = admin_user
    _, _, perms_needed, _ = get_deleted_objects([owner], request, site)
    assert not perms_needed


def test_anonymous_toggle_of_unknown_slug_redirects_to_login(client, db):
    assert client.post("/ru/favorites/nope/toggle/").headers["Location"].startswith("/ru/login/")
