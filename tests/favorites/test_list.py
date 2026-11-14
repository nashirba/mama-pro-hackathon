from datetime import timedelta

from django.utils import timezone

from apps.catalog.models import SpecialistProfile
from apps.search.builder import rebuild_all
from apps.search.query import cards_for_profiles
from tests.factories import FavoriteFactory, UserFactory


def _favorite(user, profile, minutes_ago=0):
    favorite = FavoriteFactory(user=user, profile=profile)
    type(favorite).objects.filter(pk=favorite.pk).update(
        created_at=timezone.now() - timedelta(minutes=minutes_ago)
    )
    return favorite


def test_list_requires_login(client, db):
    assert client.get("/ru/favorites/").headers["Location"].startswith("/ru/login/")


def test_empty_state(client, catalog_fixture):
    client.force_login(UserFactory())
    html = client.get("/ru/favorites/").content.decode()
    assert "Вы ещё ничего не добавили в избранное" in html
    assert 'href="/ru/specialists/"' in html and 'href="/ru/nannies/"' in html


def test_lists_specialists_then_nannies_newest_first(client, catalog_fixture, nannies):
    user = UserFactory()
    _favorite(user, catalog_fixture.specialists["ivanova-logoped"], minutes_ago=10)
    _favorite(user, catalog_fixture.specialists["serikov-aba"], minutes_ago=5)
    _favorite(user, nannies["aigul-nanny"], minutes_ago=1)
    client.force_login(user)
    html = client.get("/ru/favorites/").content.decode()
    assert "Вы ещё ничего не добавили" not in html
    serikov, ivanova, nanny = (
        html.index(n) for n in ("Сериков Данияр", "Иванова Анна", "Сапарова Айгуль")
    )
    assert serikov < ivanova < nanny
    assert html.index("Специалисты</h2>") < serikov and html.index("Няни</h2>") < nanny


def test_section_omitted_when_empty(client, catalog_fixture):
    user = UserFactory()
    _favorite(user, catalog_fixture.specialists["ivanova-logoped"])
    client.force_login(user)
    html = client.get("/ru/favorites/").content.decode()
    assert "Специалисты</h2>" in html and "Няни</h2>" not in html


def test_invisible_profile_is_hidden(client, catalog_fixture):
    profile = catalog_fixture.specialists["ivanova-logoped"]
    user = UserFactory()
    _favorite(user, profile)
    profile.contexts.update(catalog_enabled=False)
    rebuild_all()
    client.force_login(user)
    response = client.get("/ru/favorites/")
    assert response.status_code == 200
    assert "Иванова Анна" not in response.content.decode()


def test_only_own_favorites(client, catalog_fixture):
    FavoriteFactory(profile=catalog_fixture.specialists["ivanova-logoped"])
    client.force_login(UserFactory())
    assert "Иванова Анна" not in client.get("/ru/favorites/").content.decode()


def test_cabinet_links_to_favorites(client, db):
    client.force_login(UserFactory())
    assert 'href="/ru/favorites/"' in client.get("/ru/cabinet/").content.decode()


def test_cards_for_profiles_drops_profiles_without_offers(catalog_fixture):
    specialists = catalog_fixture.specialists
    profiles = [
        specialists["serikov-aba"],
        specialists["hidden-logoped"],
        specialists["ivanova-logoped"],
    ]
    cards = cards_for_profiles(profiles)
    assert [c.specialist.slug for c in cards] == ["serikov-aba", "ivanova-logoped"]
    assert isinstance(cards[0].specialist, SpecialistProfile)
