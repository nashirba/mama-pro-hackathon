import pytest
from django.urls import reverse

from apps.community.models import Complaint, Like
from tests.factories import (
    CommentFactory,
    NicknamedUserFactory,
    PostFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def _html(response) -> str:
    return response.content.decode()


@pytest.fixture
def member(client):
    user = NicknamedUserFactory()
    client.force_login(user)
    return user


def _like(target, pk):
    return reverse("community:like", args=[target, pk])


def _complain(target, pk):
    return reverse("community:complain", args=[target, pk])


def test_like_toggles_and_counts(client, member):
    post = PostFactory()
    comment = CommentFactory(post=post)
    for target, obj in (("post", post), ("comment", comment)):
        first = client.post(_like(target, obj.pk), HTTP_HX_REQUEST="true")
        assert first.status_code == 200 and "1" in _html(first) and 'aria-pressed="true"' in _html(first)
        second = client.post(_like(target, obj.pk), HTTP_HX_REQUEST="true")
        assert 'aria-pressed="false"' in _html(second)
    assert not Like.objects.exists()
    client.post(_like("post", post.pk))
    assert Like.objects.filter(user=member, post=post).count() == 1


def test_like_without_htmx_redirects_back(client, member):
    post = PostFactory()
    response = client.post(_like("post", post.pk), {"next": "/ru/community/"})
    assert response.status_code == 302 and response["Location"] == "/ru/community/"


def test_like_bad_target_404(client, member):
    post = PostFactory()
    assert client.post(_like("user", post.pk)).status_code == 404
    assert client.get(_complain("user", post.pk)).status_code == 404


def test_guest_like_redirects_to_login(client):
    post = PostFactory()
    response = client.post(_like("post", post.pk))
    assert response.status_code == 302 and "/login" in response["Location"]
    assert not Like.objects.exists()


def test_like_without_nickname_allowed(client):
    user = UserFactory()
    client.force_login(user)
    post = PostFactory()
    assert client.post(_like("post", post.pk)).status_code == 302
    assert Like.objects.filter(user=user, post=post).exists()
    assert client.post(_complain("post", post.pk), {"reason": "ad"}).status_code == 302
    assert Complaint.objects.filter(user=user).exists()


def test_complaint_created_and_message_shown(client, member):
    comment = CommentFactory()
    assert client.get(_complain("comment", comment.pk)).status_code == 200
    response = client.post(_complain("comment", comment.pk), {"reason": "insult", "text": "грубо"}, follow=True)
    complaint = Complaint.objects.get()
    assert (complaint.user, complaint.comment, complaint.reason, complaint.text) == (member, comment, "insult", "грубо")
    assert response.redirect_chain[-1][0].startswith(reverse("community:post", args=[comment.post_id]))
    assert "Жалоба отправлена" in _html(response)


def test_complaint_requires_reason(client, member):
    post = PostFactory()
    response = client.post(_complain("post", post.pk), {"text": "x"})
    assert response.status_code == 200 and not Complaint.objects.exists()


def test_like_and_complain_hidden_target_404(client, member):
    post = PostFactory(is_hidden=True)
    comment = CommentFactory(is_hidden=True)
    for target, obj in (("post", post), ("comment", comment)):
        assert client.post(_like(target, obj.pk)).status_code == 404
        assert client.get(_complain(target, obj.pk)).status_code == 404
        assert client.post(_complain(target, obj.pk), {"reason": "ad"}).status_code == 404
    assert not Like.objects.exists() and not Complaint.objects.exists()


def test_admin_hide_action_hides_from_feed(admin_client, client, member):
    post = PostFactory(body="Спорный пост")
    client.post(_complain("post", post.pk), {"reason": "ad"})
    complaint = Complaint.objects.get()
    assert "Спорный пост" in _html(client.get("/ru/community/"))
    response = admin_client.post(
        reverse("admin:community_complaint_changelist"),
        {"action": "hide_and_resolve", "_selected_action": [complaint.pk]},
    )
    assert response.status_code == 302
    complaint.refresh_from_db()
    post.refresh_from_db()
    assert complaint.status == Complaint.Status.RESOLVED and post.is_hidden
    other = NicknamedUserFactory()
    client.force_login(other)
    assert "Спорный пост" not in _html(client.get("/ru/community/"))
