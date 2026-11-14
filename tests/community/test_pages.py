import re

import pytest
from django.urls import reverse

from apps.catalog.models import PracticeContext
from apps.community.models import Like, Post, PostImage
from tests.factories import (
    CommentFactory,
    NicknamedUserFactory,
    PostFactory,
    PrivateContextFactory,
    SpecialistFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def _html(response) -> str:
    return response.content.decode()


def test_feed_renders_for_guest_with_noindex(client):
    PostFactory(body="Первый пост")
    response = client.get("/ru/community/")
    assert response.status_code == 200
    html = _html(response)
    assert '<meta name="robots" content="noindex">' in html and "Первый пост" in html
    assert 'placeholder="Поиск по постам"' in html


def test_feed_htmx_returns_page_fragment_with_next_sentinel(client):
    PostFactory.create_batch(25)
    first = client.get("/ru/community/", HTTP_HX_REQUEST="true")
    html = _html(first)
    assert "<html" not in html and html.count("<article") == 20
    assert "page=2" in html and 'hx-trigger="revealed"' in html
    second = _html(client.get("/ru/community/?page=2", HTTP_HX_REQUEST="true"))
    assert second.count("<article") == 5 and "page=3" not in second and "revealed" not in second
    assert _html(client.get("/ru/community/?page=9", HTTP_HX_REQUEST="true")).count("<article") == 0


def test_feed_sentinel_keeps_filters(client):
    PostFactory.create_batch(21, kind=Post.Kind.STORY)
    html = _html(client.get("/ru/community/?kind=story&q=&page=1", HTTP_HX_REQUEST="true"))
    assert "kind=story&amp;page=2" in html or "kind=story&page=2" in html


@pytest.mark.parametrize(
    "qs", ["?page=abc", "?page=-3", "?kind=zzz", "?condition=x", "?city=99999999999999999999", "?specialist=--", "?q=%00"]
)
def test_feed_garbage_params_no_500(client, qs):
    PostFactory()
    assert client.get("/ru/community/" + qs).status_code == 200


def test_feed_filter_controls_keep_state(client, reference):
    from apps.catalog.models import DevelopmentalCondition

    cond = DevelopmentalCondition.objects.get(slug="ras")
    PostFactory(body="мой сын", kind=Post.Kind.STORY, condition=cond)
    html = _html(client.get(f"/ru/community/?kind=story&condition={cond.pk}&q=сын"))
    assert re.search(r'aria-current="page"[^>]*>\s*Истории', html)
    assert not re.search(r'aria-current="page"[^>]*>\s*Все', html)
    assert f'<option value="{cond.pk}" selected>' in html
    assert 'value="сын"' in html
    # tabs keep the other params
    assert f"condition={cond.pk}" in html and "q=%D1%81%D1%8B%D0%BD" in html


def test_feed_city_select_marks_selected(client, kato_demo):
    city = kato_demo["almaty"]
    html = _html(client.get(f"/ru/community/?city={city.pk}"))
    assert f'<option value="{city.pk}" selected>' in html


def test_feed_specialist_chip_clears_filter(client):
    profile = SpecialistFactory(display_name="Иванова Анна")
    PrivateContextFactory(specialist=profile)
    html = _html(client.get(f"/ru/community/?specialist={profile.pk}&kind=review"))
    assert "Отзывы о Иванова Анна" in html
    chip = re.search(r'<a href="([^"]+)"[^>]*>\s*Отзывы о', html).group(1)
    assert "specialist" not in chip and "kind=review" in chip


def test_feed_specialist_chip_hidden_for_unlisted_or_unknown_profile(client):
    hidden = SpecialistFactory(display_name="Скрытая Соня")
    PrivateContextFactory(specialist=hidden, catalog_enabled=False)
    no_context = SpecialistFactory(display_name="Без Контекста")
    for pk in (hidden.pk, no_context.pk, 999999):
        html = _html(client.get(f"/ru/community/?specialist={pk}&kind=review"))
        assert "Отзывы о" not in html and "Скрытая Соня" not in html and "Без Контекста" not in html


def test_feed_page_fragment_like_next_is_post_page_not_fragment_url(client):
    posts = PostFactory.create_batch(21)
    fragment = _html(client.get("/ru/community/?page=1", HTTP_HX_REQUEST="true"))
    nexts = re.findall(r'name="next" value="([^"]*)"', fragment)
    assert len(nexts) == 20
    assert all(n.startswith("/ru/community/") and n.rstrip("/").split("/")[-1].isdigit() for n in nexts)
    assert f'name="next" value="/ru/community/{posts[-1].pk}/"' in fragment
    assert not any("page=" in n or "?" in n for n in nexts)


def test_like_next_on_full_pages_is_the_current_page(client, catalog_fixture):
    post = PostFactory()
    feed = _html(client.get("/ru/community/?kind=question"))
    assert 'name="next" value="/ru/community/?kind=question"' in feed
    assert f'name="next" value="/ru/community/{post.pk}/"' in _html(client.get(f"/ru/community/{post.pk}/"))
    assert 'name="next" value="/ru/"' in _html(client.get("/ru/"))


def test_comment_like_next_points_to_post_page_with_anchor(client):
    post = PostFactory()
    comment = CommentFactory(post=post)
    html = _html(client.get(f"/ru/community/{post.pk}/"))
    assert f'name="next" value="/ru/community/{post.pk}/#comment-{comment.pk}"' in html


def test_post_detail_404_for_deleted(client):
    post = PostFactory(is_deleted=True)
    assert client.get(f"/ru/community/{post.pk}/").status_code == 404
    assert client.get("/ru/community/999999/").status_code == 404


def test_post_detail_shows_placeholder_for_deleted_comment(client):
    post = PostFactory()
    parent = CommentFactory(post=post, is_deleted=True, body="секрет-удалён")
    CommentFactory(post=post, parent=parent, body="ответ остался")
    html = _html(client.get(f"/ru/community/{post.pk}/"))
    assert "Комментарий удалён" in html and "ответ остался" in html and "секрет-удалён" not in html


def test_specialist_badge_links_only_visible_profiles(client):
    visible = SpecialistFactory(display_name="Видимая Вера")
    PrivateContextFactory(specialist=visible, catalog_enabled=True)
    hidden = SpecialistFactory(display_name="Скрытая Соня")
    PrivateContextFactory(specialist=hidden, catalog_enabled=False)
    PostFactory(author=visible.user, body="пост видимой")
    PostFactory(author=hidden.user, body="пост скрытой")
    html = _html(client.get("/ru/community/"))
    assert f"/ru/specialist/{visible.slug}/" in html and f"/ru/specialist/{hidden.slug}/" not in html
    assert "Видимая Вера" in html and "Скрытая Соня" in html and html.count("Специалист</") >= 2


def test_review_card_links_only_visible_specialist(client):
    sp = SpecialistFactory(display_name="Отзывная Ольга")
    ctx = PrivateContextFactory(specialist=sp, catalog_enabled=True)
    post = PostFactory(kind=Post.Kind.REVIEW, specialist=sp, body="хороший специалист")
    assert f"/ru/specialist/{sp.slug}/" in _html(client.get(f"/ru/community/{post.pk}/"))
    PracticeContext.objects.filter(pk=ctx.pk).update(catalog_enabled=False)
    html = _html(client.get(f"/ru/community/{post.pk}/"))
    assert "Отзывная Ольга" in html and f"/ru/specialist/{sp.slug}/" not in html


def test_post_detail_shows_counts_and_image_flag(client):
    post = PostFactory()
    PostImage.objects.create(post=post, data=b"x", content_type="image/png")
    Like.objects.create(post=post, user=NicknamedUserFactory())
    Like.objects.create(post=post, user=NicknamedUserFactory())
    html = _html(client.get(f"/ru/community/{post.pk}/"))
    assert f'<img src="{reverse("community:image", args=[post.pk])}"' in html
    assert "Полезно 2" in html
    plain = PostFactory()
    assert "<img" not in _html(client.get(f"/ru/community/{plain.pk}/")).split("<main")[1]


def test_own_hidden_comment_marked(client):
    author = NicknamedUserFactory()
    post = PostFactory()
    CommentFactory(post=post, author=author, is_hidden=True, body="спорный комментарий")
    url = f"/ru/community/{post.pk}/"
    assert "спорный комментарий" not in _html(client.get(url))
    client.force_login(author)
    html = _html(client.get(url))
    assert "спорный комментарий" in html and "Скрыто модератором" in html
    client.force_login(NicknamedUserFactory())
    assert "спорный комментарий" not in _html(client.get(url))


def test_own_hidden_post_marked(client):
    author = NicknamedUserFactory()
    PostFactory(author=author, is_hidden=True, body="скрытый пост")
    assert "скрытый пост" not in _html(client.get("/ru/community/"))
    client.force_login(author)
    html = _html(client.get("/ru/community/"))
    assert "скрытый пост" in html and "Скрыто модератором" in html


def test_phone_never_rendered(client):
    author = NicknamedUserFactory(phone="+77015556677")
    post = PostFactory(author=author)
    CommentFactory(post=post, author=author)
    sp = SpecialistFactory(user=UserFactory(phone="+77018889900"))
    PrivateContextFactory(specialist=sp)
    PostFactory(author=sp.user)
    for url in ("/ru/community/", f"/ru/community/{post.pk}/"):
        html = _html(client.get(url))
        for needle in ("77015556677", "7015556677", "77018889900", "7018889900"):
            assert needle not in html


def test_header_has_community_link(client):
    html = _html(client.get("/ru/"))
    assert f'href="{reverse("community:feed")}"' in html and "Сообщество" in html


def test_rules_page(client):
    html = _html(client.get("/ru/community/rules/"))
    assert "Правила сообщества" in html and 'content="noindex"' in html


def test_kk_feed_renders(client):
    PostFactory(body="Қазақша пост")
    response = client.get("/kk/community/")
    assert response.status_code == 200
    html = _html(response)
    assert "Қазақша пост" in html and "Қауымдастық" in html
    assert client.get("/kk/community/rules/").status_code == 200


def _count_queries(client, url) -> int:
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx)


def test_feed_query_count_does_not_grow_with_cards(client, reference, kato_demo):
    from apps.catalog.models import DevelopmentalCondition

    cond = DevelopmentalCondition.objects.get(slug="ras")
    city = kato_demo["almaty"]
    PostFactory(condition=cond, city=city)
    base = _count_queries(client, "/ru/community/")
    for _ in range(6):
        sp = SpecialistFactory()
        PrivateContextFactory(specialist=sp)
        PostFactory(condition=cond, city=city, author=sp.user)
        review_sp = SpecialistFactory()
        PrivateContextFactory(specialist=review_sp)
        PostFactory(kind=Post.Kind.REVIEW, specialist=review_sp, condition=cond, city=city)
    assert _count_queries(client, "/ru/community/") <= base + 1
    html = _html(client.get("/ru/community/"))
    assert html.count("<article") == 13 and html.count("/ru/specialist/") == 12


def test_post_page_query_count_does_not_grow_with_specialist_comments(client):
    post = PostFactory()
    first = SpecialistFactory()
    PrivateContextFactory(specialist=first)
    CommentFactory(post=post, author=first.user)
    base = _count_queries(client, f"/ru/community/{post.pk}/")
    for _ in range(6):
        sp = SpecialistFactory()
        PrivateContextFactory(specialist=sp)
        CommentFactory(post=post, author=sp.user)
    assert _count_queries(client, f"/ru/community/{post.pk}/") <= base + 1
    hidden = SpecialistFactory()
    PrivateContextFactory(specialist=hidden, catalog_enabled=False)
    CommentFactory(post=post, author=hidden.user)
    html = _html(client.get(f"/ru/community/{post.pk}/"))
    assert html.count("/ru/specialist/") == 7 and hidden.slug not in html


def test_specialist_page_shows_three_latest_reviews_and_all_link(client, catalog_fixture):
    from apps.catalog.models import SpecialistProfile

    spec = SpecialistProfile.objects.get(slug="ivanova-logoped")
    for i in range(4):
        PostFactory(kind=Post.Kind.REVIEW, specialist=spec, body=f"Отзыв номер {i}")
    html = _html(client.get("/ru/specialist/ivanova-logoped/"))
    assert "Отзывы в сообществе" in html
    assert html.count('id="post-') == 3
    assert "Отзыв номер 3" in html and "Отзыв номер 0" not in html
    assert f"/ru/community/?kind=review&amp;specialist={spec.pk}" in html


def test_specialist_page_without_reviews_has_no_section(client, catalog_fixture):
    html = _html(client.get("/ru/specialist/ivanova-logoped/"))
    assert "Отзывы в сообществе" not in html


def test_hidden_review_not_on_specialist_page(client, catalog_fixture):
    from apps.catalog.models import SpecialistProfile

    spec = SpecialistProfile.objects.get(slug="ivanova-logoped")
    PostFactory(kind=Post.Kind.REVIEW, specialist=spec, body="Скрытый отзыв", is_hidden=True)
    html = _html(client.get("/ru/specialist/ivanova-logoped/"))
    assert "Скрытый отзыв" not in html and "Отзывы в сообществе" not in html


def test_specialist_page_review_card_shows_author_name(client, catalog_fixture):
    from apps.catalog.models import SpecialistProfile

    spec = SpecialistProfile.objects.get(slug="ivanova-logoped")
    author = NicknamedUserFactory(display_name="Мама Айгуль")
    PostFactory(kind=Post.Kind.REVIEW, specialist=spec, author=author)
    assert "Мама Айгуль" in _html(client.get("/ru/specialist/ivanova-logoped/"))


def test_home_shows_recent_posts(client, catalog_fixture):
    PostFactory(body="Свежий пост на главной")
    html = _html(client.get("/ru/"))
    assert "Свежие посты" in html and "Свежий пост на главной" in html
    assert "Перейти в сообщество" in html and 'href="/ru/community/"' in html


def test_home_without_posts_has_no_section(client, catalog_fixture):
    assert "Свежие посты" not in _html(client.get("/ru/"))


@pytest.mark.parametrize(("count", "label"), [(1, "1 ответ"), (2, "2 ответа"), (5, "5 ответов"), (21, "21 ответ")])
def test_feed_reply_count_uses_russian_plural_forms(client, count, label):
    post = PostFactory()
    CommentFactory.create_batch(count, post=post)
    html = _html(client.get("/ru/community/"))
    assert f"{label}</span>" in html


def test_home_query_count_does_not_grow_with_cards(client, catalog_fixture):
    PostFactory()
    base = _count_queries(client, "/ru/")
    for _ in range(2):
        sp = SpecialistFactory()
        PrivateContextFactory(specialist=sp)
        PostFactory(author=sp.user)
        PostFactory(kind=Post.Kind.REVIEW, specialist=sp)
    assert _count_queries(client, "/ru/") <= base + 1
    assert "Свежие посты" in _html(client.get("/ru/"))


def test_specialist_page_query_count_does_not_grow_with_community_posts(client, catalog_fixture):
    from apps.catalog.models import SpecialistProfile

    spec = SpecialistProfile.objects.get(slug="ivanova-logoped")
    PostFactory(kind=Post.Kind.REVIEW, specialist=spec)
    url = "/ru/specialist/ivanova-logoped/"
    base = _count_queries(client, url)
    for _ in range(2):
        PostFactory(kind=Post.Kind.REVIEW, specialist=spec)
    assert _count_queries(client, url) <= base + 1
    assert _html(client.get(url)).count('id="post-') == 3
