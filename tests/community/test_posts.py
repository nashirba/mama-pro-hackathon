import re
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from apps.community.models import Post, PostImage
from apps.community.pii import looks_sensitive
from tests.factories import (
    NicknamedUserFactory,
    PostFactory,
)

pytestmark = pytest.mark.django_db

NEW = "/ru/community/new/"


def _html(response) -> str:
    return response.content.decode()


def _image(fmt="PNG", name="p.png", content_type="image/png"):
    buf = BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


@pytest.fixture
def member(client):
    user = NicknamedUserFactory()
    client.force_login(user)
    return user


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ИИН 150101500123", ["iin"]),
        ("звоните 8 701 123 45 67", ["phone"]),
        ("+7 701 123 45 67", ["phone"]),
        ("87011234567", ["phone"]),
        ("8 (701) 123-45-67", ["phone"]),
        ("701 123 45 67", ["phone"]),
        ("7011234567", ["phone"]),
        ("(701) 123-45-67", ["phone"]),
        ("пишите на 777 123 45 67 вечером", ["phone"]),
        ("номер заказа 1234567890123", []),
        ("сыну 5 лет", []),
        ("цена 15 000 тенге", []),
        ("стоит 700 000 тенге", []),
        ("в 2019 году, с 7 лет", []),
        ("700 123 45 6", []),
        ("70112345678", []),
        ("ИИН 701123456789", ["iin"]),
        ("ИИН 770112345678", ["iin"]),
    ],
)
def test_looks_sensitive(text, expected):
    assert looks_sensitive(text) == expected


def test_create_question_redirects_to_post(client, member):
    response = client.post(NEW, {"kind": "question", "body": "Куда обратиться?"})
    post = Post.objects.get()
    assert response.status_code == 302 and response["Location"] == reverse("community:post", args=[post.pk])
    assert post.author == member and post.specialist is None


def test_new_requires_login(client):
    response = client.get(NEW)
    assert response.status_code == 302 and "/login" in response["Location"]


def test_create_review_requires_visible_specialist(client, member, catalog_fixture):
    response = client.post(NEW, {"kind": "review", "body": "Хороший"})
    assert response.status_code == 200 and not Post.objects.exists()
    hidden = catalog_fixture.specialists["hidden-logoped"]
    response = client.post(NEW, {"kind": "review", "body": "Хороший", "specialist": hidden.pk})
    assert response.status_code == 200 and not Post.objects.exists()
    visible = catalog_fixture.specialists["ivanova-logoped"]
    response = client.post(NEW, {"kind": "review", "body": "Хороший", "specialist": visible.pk})
    assert response.status_code == 302 and Post.objects.get().specialist == visible


def test_specialist_cannot_choose_review(client, catalog_fixture):
    profile = catalog_fixture.specialists["ivanova-logoped"]
    client.force_login(profile.user)
    assert 'value="review"' not in _html(client.get(NEW))
    response = client.post(NEW, {"kind": "review", "body": "Сам себе", "specialist": profile.pk})
    assert response.status_code == 200 and not Post.objects.exists()


def test_second_review_redirects_to_edit_existing(client, member, catalog_fixture):
    visible = catalog_fixture.specialists["ivanova-logoped"]
    first = PostFactory(author=member, kind=Post.Kind.REVIEW, specialist=visible)
    response = client.post(NEW, {"kind": "review", "body": "Ещё раз", "specialist": visible.pk}, follow=True)
    assert response.redirect_chain[-1][0] == reverse("community:edit", args=[first.pk])
    assert "уже писали отзыв" in _html(response)
    assert Post.objects.count() == 1


def test_sensitive_text_needs_confirmation(client, member):
    data = {"kind": "story", "body": "Наш ИИН 150101500123"}
    response = client.post(NEW, data)
    assert response.status_code == 200 and not Post.objects.exists()
    html = _html(response)
    assert "Не публикуйте данные ребёнка" in html and "Всё равно опубликовать" in html
    assert client.post(NEW, {**data, "confirm_sensitive": "1"}).status_code == 302
    assert Post.objects.count() == 1


def test_image_upload_and_serve(client, member):
    client.post(NEW, {"kind": "story", "body": "С фото", "image": _image()})
    post = Post.objects.get()
    assert PostImage.objects.get(post=post).content_type == "image/png"
    response = client.get(reverse("community:image", args=[post.pk]))
    assert response.status_code == 200 and response["Content-Type"] == "image/png"
    assert response["Cache-Control"] == "public, max-age=86400"
    assert response.content.startswith(b"\x89PNG")


def test_hidden_post_image_is_not_publicly_cached(client, member):
    post = PostFactory(author=member, is_hidden=True)
    PostImage.objects.create(post=post, data=b"x", content_type="image/png")
    response = client.get(reverse("community:image", args=[post.pk]))
    assert response.status_code == 200 and response["Cache-Control"] == "private, no-store"


def test_image_rejects_gif_text_and_oversize(client, member, settings):
    settings.COMMUNITY_IMAGE_MAX_BYTES = 1000
    big = BytesIO()
    Image.effect_noise((100, 100), 100).convert("RGB").save(big, "PNG")
    assert len(big.getvalue()) > 1000
    uploads = [
        (_image("GIF", "a.gif", "image/gif"), "Загрузите фото в формате JPEG или PNG"),
        (SimpleUploadedFile("a.png", b"not an image", content_type="image/png"), "Загрузите фото в формате JPEG или PNG"),
        (SimpleUploadedFile("b.png", big.getvalue(), content_type="image/png"), "Фото больше 2 МБ"),
    ]
    for upload, message in uploads:
        response = client.post(NEW, {"kind": "story", "body": "Текст", "image": upload})
        assert response.status_code == 200 and message in _html(response)
    assert not Post.objects.exists()


def test_image_of_hidden_post_404_for_guest(client):
    post = PostFactory(is_hidden=True)
    PostImage.objects.create(post=post, data=b"x", content_type="image/png")
    assert client.get(reverse("community:image", args=[post.pk])).status_code == 404


def test_image_404_without_photo(client):
    post = PostFactory()
    assert client.get(reverse("community:image", args=[post.pk])).status_code == 404


def test_edit_keeps_kind_specialist_and_hidden(client, member, catalog_fixture):
    visible = catalog_fixture.specialists["ivanova-logoped"]
    post = PostFactory(author=member, kind=Post.Kind.REVIEW, specialist=visible, is_hidden=True)
    page = client.get(reverse("community:edit", args=[post.pk]))
    assert page.status_code == 200 and "Скрыто модератором" in _html(page)
    response = client.post(reverse("community:edit", args=[post.pk]), {"kind": "story", "body": "Новый текст"})
    assert response.status_code == 302
    post.refresh_from_db()
    assert post.body == "Новый текст" and post.kind == Post.Kind.REVIEW and post.specialist == visible and post.is_hidden


def test_edit_replaces_and_removes_image(client, member):
    post = PostFactory(author=member)
    url = reverse("community:edit", args=[post.pk])
    client.post(url, {"body": "Текст", "image": _image()})
    assert PostImage.objects.filter(post=post).exists()
    client.post(url, {"body": "Текст", "remove_image": "1"})
    assert not PostImage.objects.filter(post=post).exists()


def test_only_author_edits_and_deletes(client, member):
    other = PostFactory()
    assert client.get(reverse("community:edit", args=[other.pk])).status_code == 404
    assert client.post(reverse("community:edit", args=[other.pk]), {"body": "x"}).status_code == 404
    assert client.post(reverse("community:delete", args=[other.pk])).status_code == 404
    own = PostFactory(author=member, body="Мой пост")
    assert client.get(reverse("community:delete", args=[own.pk])).status_code == 405
    response = client.post(reverse("community:delete", args=[own.pk]))
    assert response.status_code == 302 and response["Location"] == reverse("community:feed")
    assert "Мой пост" not in _html(client.get("/ru/community/"))
    own.refresh_from_db()
    assert own.is_deleted


def test_feed_has_write_button_and_author_sees_edit_delete(client, member):
    own = PostFactory(author=member)
    other = PostFactory()
    assert reverse("community:new") in _html(client.get("/ru/community/"))
    mine = _html(client.get(reverse("community:post", args=[own.pk])))
    assert reverse("community:edit", args=[own.pk]) in mine and reverse("community:delete", args=[own.pk]) in mine
    theirs = _html(client.get(reverse("community:post", args=[other.pk])))
    assert reverse("community:edit", args=[other.pk]) not in theirs and reverse("community:delete", args=[other.pk]) not in theirs


def test_post_form_links_to_rules(client, member):
    assert reverse("community:rules") in _html(client.get(NEW))


def test_malicious_kind_is_not_rendered_into_x_data(client, member):
    html = _html(client.get(NEW, {"kind": "' + alert(1) + '"}))
    assert "alert(1)" not in html
    assert "x-data=\"{ kind: 'question' }\"" in html
    assert "kind: 'review'" in _html(client.get(NEW, {"kind": "review"}))


def test_malicious_posted_kind_is_not_rendered_into_x_data(client, member):
    html = _html(client.post(NEW, {"kind": "' + alert(1) + '", "body": "x"}))
    assert "x-data=\"{ kind: 'question' }\"" in html  # the error text itself is HTML-escaped by Django


def test_kind_has_no_blank_radio_and_defaults_to_question(client, member):
    html = _html(client.get(NEW))
    assert 'name="kind" value=""' not in html and "---------" not in html
    assert re.search(r'value="question"[^>]*checked', html)


def test_specialist_cannot_prefill_review_kind(client, catalog_fixture):
    client.force_login(catalog_fixture.specialists["ivanova-logoped"].user)
    html = _html(client.get(NEW, {"kind": "review"}))
    assert "kind: 'question'" in html and 'value="review"' not in html


def test_mpo_photo_is_accepted_as_jpeg(client, member):
    buf = BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, "MPO", save_all=True, append_images=[Image.new("RGB", (10, 10), "blue")])
    assert Image.open(BytesIO(buf.getvalue())).format == "MPO"
    upload = SimpleUploadedFile("p.jpg", buf.getvalue(), content_type="image/jpeg")
    client.post(NEW, {"kind": "story", "body": "С телефона", "image": upload})
    assert PostImage.objects.get().content_type == "image/jpeg"


def test_decompression_bomb_gives_form_error(client, member, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)  # 100px image: warning level
    response = client.post(NEW, {"kind": "story", "body": "Текст", "image": _image()})
    assert response.status_code == 200 and "Загрузите фото в формате JPEG или PNG" in _html(response)
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 40)  # more than 2x: DecompressionBombError
    response = client.post(NEW, {"kind": "story", "body": "Текст", "image": _image()})
    assert response.status_code == 200 and not Post.objects.exists()


def test_review_race_integrity_error_redirects_to_existing(client, member, catalog_fixture, monkeypatch):
    from apps.community import views

    visible = catalog_fixture.specialists["ivanova-logoped"]
    real_save, competing = views.save_post, {}

    def racing_save(post, *args, **kwargs):
        competing["post"] = PostFactory(author=member, kind=Post.Kind.REVIEW, specialist=visible)
        return real_save(post, *args, **kwargs)

    monkeypatch.setattr(views, "save_post", racing_save)
    response = client.post(NEW, {"kind": "review", "body": "Гонка", "specialist": visible.pk})
    assert response.status_code == 302
    assert response["Location"] == reverse("community:edit", args=[competing["post"].pk])
    assert Post.objects.count() == 1


def test_specialist_options_only_visible(client, catalog_fixture):
    url = reverse("community:specialist_options")
    assert "hidden-logoped" not in _html(client.get(url, {"q": "Скрытов"}))
    visible = catalog_fixture.specialists["ivanova-logoped"]
    html = _html(client.get(url, {"q": "Иванова"}))
    assert f'value="{visible.pk}"' in html and 'name="specialist"' in html
    hidden = catalog_fixture.specialists["hidden-logoped"]
    assert f'value="{hidden.pk}"' not in _html(client.get(url, {"q": "Скрытов"}))


def test_form_rerender_asks_to_reattach_photo(client, member):
    data = {"kind": "story", "body": "Наш ИИН 150101500123"}
    with_photo = _html(client.post(NEW, {**data, "image": _image()}))
    assert "Не публикуйте данные ребёнка" in with_photo and "Прикрепите фото ещё раз" in with_photo
    assert "Прикрепите фото ещё раз" not in _html(client.post(NEW, data))
    assert "Прикрепите фото ещё раз" not in _html(client.get(NEW))
    invalid = _html(client.post(NEW, {"kind": "story", "body": "", "image": _image()}))
    assert "Прикрепите фото ещё раз" in invalid
    assert not Post.objects.exists()


def test_edit_form_rerender_asks_to_reattach_photo(client, member):
    post = PostFactory(author=member)
    html = _html(client.post(reverse("community:edit", args=[post.pk]), {"body": "ИИН 150101500123", "image": _image()}))
    assert "Прикрепите фото ещё раз" in html


def test_edit_save_does_not_revert_concurrent_hide(client, member, monkeypatch):
    from apps.community import views

    post = PostFactory(author=member, body="Старый")
    real_save = views.save_post_edit

    def hidden_meanwhile(instance, *args, **kwargs):
        Post.objects.filter(pk=post.pk).update(is_hidden=True)  # a moderator acts after the form loaded the post
        return real_save(instance, *args, **kwargs)

    monkeypatch.setattr(views, "save_post_edit", hidden_meanwhile)
    response = client.post(reverse("community:edit", args=[post.pk]), {"body": "Новый"})
    assert response.status_code == 302
    post.refresh_from_db()
    assert post.is_hidden is True and post.body == "Новый"


def test_save_post_edit_touches_only_editable_fields_and_search():
    from apps.community.forms import PostEditForm
    from apps.community.services import save_post_edit

    post = PostFactory(body="Старый текст")
    form = PostEditForm({"body": "Совсем другой"}, instance=post)
    assert form.is_valid()
    Post.objects.filter(pk=post.pk).update(is_hidden=True, is_deleted=True)
    before = Post.objects.get(pk=post.pk).updated_at
    save_post_edit(form.instance)
    fresh = Post.objects.get(pk=post.pk)
    assert fresh.is_hidden and fresh.is_deleted and fresh.body == "Совсем другой"
    assert fresh.updated_at > before and "другой" in fresh.search_norm


def test_nickname_form_does_not_mutate_user_when_save_fails():
    from apps.community.forms import NicknameForm

    user = NicknamedUserFactory(display_name="Старое_имя")
    form = NicknameForm({"display_name": "Новое_имя"}, user=user)
    assert form.is_valid()
    NicknamedUserFactory(display_name="Новое_имя")  # taken between validation and save
    assert form.save() is False
    assert user.display_name == "Старое_имя" and form.errors["display_name"]
    user.refresh_from_db()
    assert user.display_name == "Старое_имя"
