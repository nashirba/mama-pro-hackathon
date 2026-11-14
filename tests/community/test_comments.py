import re

import pytest
from django.urls import reverse

from apps.community.models import Comment
from apps.community.names import author_name
from apps.community.services import add_comment
from tests.factories import CommentFactory, NicknamedUserFactory, PostFactory

pytestmark = pytest.mark.django_db


def _html(response) -> str:
    return response.content.decode()


@pytest.fixture
def member(client):
    user = NicknamedUserFactory()
    client.force_login(user)
    return user


def _url(name, pk):
    return reverse(f"community:{name}", args=[pk])


def test_guest_cannot_comment(client):
    post = PostFactory()
    response = client.post(_url("comment", post.pk), {"body": "Привет"})
    assert response.status_code == 302 and "/login" in response["Location"]
    assert not Comment.objects.exists()


def test_comment_and_reply_two_levels(client, member):
    post = PostFactory()
    response = client.post(_url("comment", post.pk), {"body": "Первый"})
    top = Comment.objects.get()
    assert response.status_code == 302 and response["Location"].endswith(f"{_url('post', post.pk)}#comment-{top.pk}")
    client.post(_url("comment", post.pk), {"body": "Ответ", "parent": top.pk})
    reply = Comment.objects.exclude(pk=top.pk).get()
    assert reply.parent == top and reply.author == member and reply.body == "Ответ"
    html = _html(client.get(_url("post", post.pk)))
    assert "Первый" in html and "Ответ" in html


def test_reply_to_reply_flattens_with_mention(client, member):
    post = PostFactory()
    top = CommentFactory(post=post)
    reply = CommentFactory(post=post, parent=top)
    client.post(_url("comment", post.pk), {"body": "Спасибо", "parent": reply.pk})
    new = Comment.objects.latest("pk")
    assert new.parent == top
    assert new.body == f"@{author_name(reply.author)} Спасибо"


def test_add_comment_service_rejects_foreign_parent():
    parent = CommentFactory()
    with pytest.raises(ValueError):
        add_comment(PostFactory(), NicknamedUserFactory(), "x", parent)


def test_parent_from_other_post_rejected(client, member):
    post = PostFactory()
    foreign = CommentFactory()
    response = client.post(_url("comment", post.pk), {"body": "Привет", "parent": foreign.pk})
    assert response.status_code == 404
    assert not Comment.objects.exclude(pk=foreign.pk).exists()


def test_htmx_comment_returns_tree_fragment(client, member):
    post = PostFactory()
    response = client.post(_url("comment", post.pk), {"body": "Через HTMX"}, HTTP_HX_REQUEST="true")
    html = _html(response)
    assert response.status_code == 200
    assert 'id="comments"' in html and "Через HTMX" in html and "<html" not in html


def test_empty_comment_not_saved(client, member):
    post = PostFactory()
    response = client.post(_url("comment", post.pk), {"body": "  "}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200 and not Comment.objects.exists()


def test_cannot_comment_hidden_foreign_post(client, member):
    post = PostFactory(is_hidden=True)
    assert client.post(_url("comment", post.pk), {"body": "x"}).status_code == 404
    assert not Comment.objects.exists()


def test_only_author_edits_deletes_comment(client, member):
    comment = CommentFactory(author=member, body="Старый")
    other = CommentFactory()
    assert client.get(_url("comment_edit", other.pk)).status_code == 404
    assert client.post(_url("comment_edit", other.pk), {"body": "взлом"}).status_code == 404
    assert client.post(_url("comment_delete", other.pk)).status_code == 404
    other.refresh_from_db()
    assert other.body != "взлом" and not other.is_deleted

    assert client.get(_url("comment_edit", comment.pk)).status_code == 200
    response = client.post(_url("comment_edit", comment.pk), {"body": "Новый"})
    assert response.status_code == 302
    comment.refresh_from_db()
    assert comment.body == "Новый"
    assert client.post(_url("comment_delete", comment.pk)).status_code == 302
    comment.refresh_from_db()
    assert comment.is_deleted


def test_delete_requires_post(client, member):
    comment = CommentFactory(author=member)
    assert client.get(_url("comment_delete", comment.pk)).status_code == 405


def test_deleted_comment_with_reply_shows_placeholder(client):
    post = PostFactory()
    top = CommentFactory(post=post, body="Удалённый текст", is_deleted=True)
    CommentFactory(post=post, parent=top, body="Живой ответ")
    html = _html(client.get(_url("post", post.pk)))
    assert "Комментарий удалён" in html and "Живой ответ" in html and "Удалённый текст" not in html


def _htmx(client, post, body, **extra):
    return client.post(_url("comment", post.pk), {"body": body, **extra}, HTTP_HX_REQUEST="true")


def test_htmx_comment_response_updates_reply_counter(client, member):
    post = PostFactory()
    CommentFactory(post=post)
    html = _html(_htmx(client, post, "Ещё один"))
    assert re.search(r'<span id="reply-count" hx-swap-oob="true">2 ответа</span>', html)
    reply = _html(_htmx(client, post, "Ответ", parent=Comment.objects.filter(post=post).first().pk))
    assert 'id="reply-count"' in reply and "3 ответа</span>" in reply


def test_full_post_page_has_single_reply_counter_without_oob(client, member):
    post = PostFactory()
    CommentFactory(post=post)
    html = _html(client.get(_url("post", post.pk)))
    assert html.count('id="reply-count"') == 1 and "hx-swap-oob" not in html


SENSITIVE = "Звоните 8 701 123 45 67"


def test_sensitive_comment_needs_confirmation(client, member):
    post = PostFactory()
    response = client.post(_url("comment", post.pk), {"body": SENSITIVE})
    html = _html(response)
    assert response.status_code == 200 and not Comment.objects.exists()
    assert "Не публикуйте данные ребёнка" in html and "Всё равно опубликовать" in html and SENSITIVE in html
    assert client.post(_url("comment", post.pk), {"body": SENSITIVE, "confirm_sensitive": "1"}).status_code == 302
    assert Comment.objects.get().body == SENSITIVE


def test_sensitive_reply_needs_confirmation_and_opens_reply_box(client, member):
    post = PostFactory()
    top = CommentFactory(post=post)
    response = client.post(_url("comment", post.pk), {"body": SENSITIVE, "parent": top.pk})
    html = _html(response)
    assert response.status_code == 200 and Comment.objects.count() == 1
    assert "Всё равно опубликовать" in html and f'id="comment-form-{top.pk}"' in html
    assert re.search(r'<details class="text-sm" open>', html)
    client.post(_url("comment", post.pk), {"body": SENSITIVE, "parent": top.pk, "confirm_sensitive": "1"})
    assert Comment.objects.get(parent=top).body == SENSITIVE


def test_htmx_sensitive_comment_returns_form_with_warning_and_saves_nothing(client, member):
    post = PostFactory()
    response = _htmx(client, post, SENSITIVE)
    html = _html(response)
    assert response.status_code == 200 and not Comment.objects.exists()
    assert response["HX-Retarget"] == "#comment-form-new" and response["HX-Reswap"] == "outerHTML"
    assert html.lstrip().startswith("<form") and 'id="comments"' not in html
    assert "Не публикуйте данные ребёнка" in html and 'name="confirm_sensitive"' in html
    assert re.search(r"<textarea[^>]*>" + re.escape(SENSITIVE) + "</textarea>", html)
    assert _htmx(client, post, SENSITIVE, confirm_sensitive="1").status_code == 200
    assert Comment.objects.get().body == SENSITIVE


def test_htmx_sensitive_reply_targets_that_reply_form(client, member):
    post = PostFactory()
    top = CommentFactory(post=post)
    response = _htmx(client, post, SENSITIVE, parent=top.pk)
    assert response["HX-Retarget"] == f"#comment-form-{top.pk}"
    assert f'name="parent" value="{top.pk}"' in _html(response) and Comment.objects.count() == 1
    saved = _htmx(client, post, SENSITIVE, parent=top.pk, confirm_sensitive="1")
    assert 'id="comments"' in _html(saved) and not saved.has_header("HX-Retarget")
    assert Comment.objects.get(parent=top).body == SENSITIVE


def test_comment_edit_also_warns_about_sensitive_text(client, member):
    comment = CommentFactory(author=member, body="Старый")
    response = client.post(_url("comment_edit", comment.pk), {"body": SENSITIVE})
    assert response.status_code == 200 and "Всё равно опубликовать" in _html(response)
    comment.refresh_from_db()
    assert comment.body == "Старый"
    client.post(_url("comment_edit", comment.pk), {"body": SENSITIVE, "confirm_sensitive": "1"})
    comment.refresh_from_db()
    assert comment.body == SENSITIVE


def test_htmx_error_keeps_text_and_does_not_reset(client, member):
    post = PostFactory()
    too_long = "я" * 1001
    response = _htmx(client, post, too_long)
    html = _html(response)
    assert response["HX-Retarget"] == "#comment-form-new" and not Comment.objects.exists()
    assert re.search(r"<textarea[^>]*>я{1001}</textarea>", html) and 'role="alert"' in html
    assert "hx-on" not in html  # no client-side reset: the server decides what the form looks like


def _oob_form(html: str) -> str:
    match = re.search(r'<form id="comment-form-new"[^>]*hx-swap-oob="true"[^>]*>.*?</form>', html, re.S)
    assert match, "no out-of-band #comment-form-new"
    return match.group(0)


def test_htmx_success_returns_fresh_empty_top_level_form_oob(client, member):
    post = PostFactory()
    html = _html(_htmx(client, post, "Первый"))
    form = _oob_form(html)
    assert re.search(r"<textarea[^>]*></textarea>", form)
    assert "Всё равно опубликовать" not in form and 'role="alert"' not in form


def test_warning_then_confirm_yields_clean_form(client, member):
    post = PostFactory()
    warned = _htmx(client, post, SENSITIVE)
    assert "Всё равно опубликовать" in _html(warned) and "hx-swap-oob" not in _html(warned)
    done = _html(_htmx(client, post, SENSITIVE, confirm_sensitive="1"))
    form = _oob_form(done)
    assert SENSITIVE not in form and "Всё равно опубликовать" not in form and 'role="alert"' not in form
    assert re.search(r"<textarea[^>]*></textarea>", form) and 'name="confirm_sensitive"' not in form


def test_htmx_reply_success_also_resets_top_level_form(client, member):
    post = PostFactory()
    top = CommentFactory(post=post)
    form = _oob_form(_html(_htmx(client, post, "Ответ", parent=top.pk)))
    assert 'name="parent"' not in form


def test_empty_comment_without_htmx_rerenders_page_with_error(client, member):
    post = PostFactory()
    response = client.post(_url("comment", post.pk), {"body": "  "})
    assert response.status_code == 200 and 'role="alert"' in _html(response) and not Comment.objects.exists()


def test_reply_to_reply_with_mention_cannot_exceed_limit(client, member):
    post = PostFactory()
    top = CommentFactory(post=post)
    reply = CommentFactory(post=post, parent=top, author=NicknamedUserFactory(display_name="Длинное_имя_мамы"))
    prefix = f"@{author_name(reply.author)} "
    fits = "а" * (1000 - len(prefix))
    assert client.post(_url("comment", post.pk), {"body": fits, "parent": reply.pk}).status_code == 302
    assert len(Comment.objects.latest("pk").body) == 1000
    before = Comment.objects.count()
    response = client.post(_url("comment", post.pk), {"body": fits + "а", "parent": reply.pk})
    assert response.status_code == 200 and "С упоминанием имени ответ длиннее 1000 символов" in _html(response)
    assert Comment.objects.count() == before
    # a reply to a top-level comment has no mention, so the full 1000 chars fit
    assert client.post(_url("comment", post.pk), {"body": "б" * 1000, "parent": top.pk}).status_code == 302


@pytest.mark.parametrize("state", ["is_deleted", "is_hidden"])
def test_reply_to_unavailable_parent_is_404(client, member, state):
    post = PostFactory()
    parent = CommentFactory(post=post, **{state: True})
    assert client.post(_url("comment", post.pk), {"body": "Ответ", "parent": parent.pk}).status_code == 404
    assert _htmx(client, post, "Ответ", parent=parent.pk).status_code == 404
    assert Comment.objects.count() == 1


def test_reply_to_comment_of_hidden_post_is_404(client, member):
    parent = CommentFactory(post=PostFactory(is_hidden=True))
    assert client.post(_url("comment", parent.post_id), {"body": "Ответ", "parent": parent.pk}).status_code == 404


def test_htmx_reply_to_reply_flattens_with_mention(client, member):
    post = PostFactory()
    top = CommentFactory(post=post)
    reply = CommentFactory(post=post, parent=top)
    response = _htmx(client, post, "Спасибо", parent=reply.pk)
    new = Comment.objects.latest("pk")
    assert new.parent == top and new.body == f"@{author_name(reply.author)} Спасибо"
    assert response.status_code == 200 and new.body in _html(response)
