import re

import pytest
from django.db import IntegrityError

from apps.community.models import Post
from apps.community.ratings import NO_RATING, Rating, rating_for, ratings_for
from apps.onboarding.models import Application
from tests.factories import NicknamedUserFactory, PostFactory, UserFactory

NEW = "/ru/community/new/"


def _review(profile, rating, **kwargs):
    return PostFactory(kind=Post.Kind.REVIEW, specialist=profile, rating=rating, **kwargs)


def test_average_and_count_use_visible_rated_reviews_only(catalog_fixture):
    spec = catalog_fixture.specialists["ivanova-logoped"]
    _review(spec, 5)
    _review(spec, 4)
    _review(spec, 4)
    _review(spec, 1, is_hidden=True)
    _review(spec, 1, is_deleted=True)
    _review(spec, None)  # written before ratings existed
    assert rating_for(spec.pk) == Rating(4.3, 3)
    other = catalog_fixture.specialists["kim-neuro"]
    assert rating_for(other.pk) == NO_RATING
    assert ratings_for([spec.pk, other.pk]) == {spec.pk: Rating(4.3, 3)}


def test_rating_only_on_review_and_in_range(db):
    with pytest.raises(IntegrityError):
        PostFactory(kind=Post.Kind.QUESTION, rating=3)


def test_search_card_shows_rating_and_count(client, catalog_fixture):
    spec = catalog_fixture.specialists["ivanova-logoped"]
    _review(spec, 5)
    _review(spec, 4)
    html = client.get("/ru/specialists/").content.decode()
    card = re.search(r'<article data-specialist="ivanova-logoped".*?</article>', html, re.S).group(0)
    assert 'data-rating="4.5"' in card and "4,5" in card and "2 отзыва" in card
    other = re.search(r'<article data-specialist="kim-neuro".*?</article>', html, re.S).group(0)
    assert "Нет отзывов" in other


def test_nanny_card_and_page_show_rating_and_reviews(client, nannies):
    nanny = nannies["aigul-nanny"]
    _review(nanny, 5, body="Чудесная няня")
    html = client.get("/ru/nannies/").content.decode()
    card = re.search(r'<article data-nanny="aigul-nanny".*?</article>', html, re.S).group(0)
    assert 'data-rating="5.0"' in card and "1 отзыв" in card
    page = client.get("/ru/nanny/aigul-nanny/").content.decode()
    assert 'id="reviews"' in page and "Чудесная няня" in page and 'data-stars="5"' in page


def test_detail_header_links_rating_to_reviews(client, catalog_fixture):
    _review(catalog_fixture.specialists["ivanova-logoped"], 3)
    html = client.get("/ru/specialist/ivanova-logoped/").content.decode()
    assert 'href="#reviews"' in html and 'data-rating="3.0"' in html


def test_leave_review_button_by_role(client, catalog_fixture):
    spec = catalog_fixture.specialists["ivanova-logoped"]
    url = "/ru/specialist/ivanova-logoped/"
    target = f"/ru/community/new/?kind=review&amp;specialist={spec.pk}"
    guest = client.get(url).content.decode()
    assert "Оставить отзыв" in guest and "/ru/login/?next=" in guest
    client.force_login(UserFactory())
    assert target in client.get(url).content.decode()
    client.force_login(catalog_fixture.specialists["kim-neuro"].user)
    assert "Оставить отзыв" not in client.get(url).content.decode()


def test_mother_reviews_a_nanny_with_rating(client, nannies):
    client.force_login(NicknamedUserFactory())
    nanny = nannies["aigul-nanny"]
    page = client.get(NEW, {"kind": "review", "specialist": nanny.pk}).content.decode()
    assert f'value="{nanny.pk}" checked' in page and 'name="rating"' in page
    r = client.post(NEW, {"kind": "review", "body": "Хорошая няня", "specialist": nanny.pk, "rating": "5"})
    assert r.status_code == 302
    assert rating_for(nanny.pk) == Rating(5.0, 1)


def test_hidden_nanny_cannot_be_reviewed(client, nannies):
    client.force_login(NicknamedUserFactory())
    hidden = next(p for slug, p in nannies.items() if slug not in {"aigul-nanny", "marina-nanny"})
    r = client.post(NEW, {"kind": "review", "body": "Текст", "specialist": hidden.pk, "rating": "5"})
    assert r.status_code == 200 and not Post.objects.exists()


def test_applicant_cannot_review(client, catalog_fixture):
    applicant = NicknamedUserFactory(role="specialist")
    Application.objects.create(user=applicant, category="specialist")
    client.force_login(applicant)
    spec = catalog_fixture.specialists["ivanova-logoped"]
    assert 'value="review"' not in client.get(NEW).content.decode()
    r = client.post(NEW, {"kind": "review", "body": "Текст", "specialist": spec.pk, "rating": "5"})
    assert r.status_code == 200 and not Post.objects.exists()


def test_rating_out_of_range_is_refused(client, catalog_fixture):
    client.force_login(NicknamedUserFactory())
    spec = catalog_fixture.specialists["ivanova-logoped"]
    r = client.post(NEW, {"kind": "review", "body": "Текст", "specialist": spec.pk, "rating": "7"})
    assert r.status_code == 200 and not Post.objects.exists()


def test_feed_review_card_shows_stars_and_nanny_link(client, nannies):
    nanny = nannies["aigul-nanny"]
    _review(nanny, 4)
    html = client.get("/ru/community/?kind=review").content.decode()
    assert 'data-stars="4"' in html and "/ru/nanny/aigul-nanny/" in html
