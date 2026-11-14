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
    html = client.post(
        "/ru/favorites/ivanova-logoped/toggle/", HTTP_HX_REQUEST="true"
    ).content.decode()
    assert 'aria-pressed="true"' in html and "<html" not in html


def test_toggle_requires_login(client, catalog_fixture):
    assert (
        client.post("/ru/favorites/ivanova-logoped/toggle/")
        .headers["Location"]
        .startswith("/ru/login/")
    )


def test_toggle_get_not_allowed(client, catalog_fixture):
    client.force_login(UserFactory())
    assert client.get("/ru/favorites/ivanova-logoped/toggle/").status_code == 405


def test_toggle_unknown_slug_404(client, db):
    client.force_login(UserFactory())
    assert client.post("/ru/favorites/nope/toggle/").status_code == 404


def test_toggle_redirects_to_safe_next(client, catalog_fixture):
    client.force_login(UserFactory())
    url = "/ru/favorites/ivanova-logoped/toggle/"
    assert (
        client.post(url, {"next": "/ru/specialists/"}).headers["Location"]
        == "/ru/specialists/"
    )
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
    assert (
        'href="/ru/login/?next=%2Fru%2Fspecialists%2F"' in html
        and "В избранное" in html
    )


def test_card_heart_shows_state_and_sits_above_overlay(client, catalog_fixture):
    user = UserFactory()
    client.force_login(user)
    FavoriteFactory(
        user=user, profile=SpecialistProfile.objects.get(slug="ivanova-logoped")
    )
    html = client.get("/ru/specialists/").content.decode()
    assert html.count('aria-pressed="true"') == 1 and "z-10" in html


def test_favorite_ids_one_query_per_request(client, catalog_fixture):
    user = UserFactory()
    client.force_login(user)
    with CaptureQueriesContext(connection) as without:
        client.get("/ru/specialists/")
    profiles = list(SpecialistProfile.objects.all()[:3])
    for profile in profiles:
        FavoriteFactory(user=user, profile=profile)
    assert user.favorites.count() == len(profiles) >= 2
    with CaptureQueriesContext(connection) as with_three:
        client.get("/ru/specialists/")
    assert len(without) == len(with_three)


def test_nanny_card_and_detail_have_heart(client, nannies):
    client.force_login(UserFactory())
    assert "В избранное" in client.get("/ru/nannies/").content.decode()
    assert "В избранное" in client.get("/ru/nanny/aigul-nanny/").content.decode()


def test_specialist_detail_has_heart(client, catalog_fixture):
    assert (
        "В избранное" in client.get("/ru/specialist/ivanova-logoped/").content.decode()
    )


def test_favorite_unique_per_user_profile(db):
    favorite = FavoriteFactory()
    with pytest.raises(IntegrityError):
        FavoriteFactory(user=favorite.user, profile=favorite.profile)
