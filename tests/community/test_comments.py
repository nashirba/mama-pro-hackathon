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
