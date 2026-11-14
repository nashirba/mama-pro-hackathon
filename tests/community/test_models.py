import pytest
from django.db import IntegrityError, transaction

from apps.catalog.models import DevelopmentalCondition
from apps.community.models import Like, Post
from apps.community.names import author_name, is_specialist, needs_nickname
from apps.core.text import normalize_kk
from tests.factories import CommentFactory, PostFactory, SpecialistFactory, UserFactory


@pytest.mark.django_db
def test_two_users_without_nickname_coexist():
    a = UserFactory(display_name="")
    b = UserFactory(display_name="")
    a.refresh_from_db()
    b.refresh_from_db()
    assert a.display_name is None and b.display_name is None


@pytest.mark.django_db
def test_review_requires_specialist():
    with pytest.raises(IntegrityError), transaction.atomic():
        PostFactory(kind=Post.Kind.REVIEW, specialist=None)


@pytest.mark.django_db
def test_question_with_specialist_rejected():
    with pytest.raises(IntegrityError), transaction.atomic():
        PostFactory(kind=Post.Kind.QUESTION, specialist=SpecialistFactory())


@pytest.mark.django_db
def test_second_live_review_rejected_after_delete_allowed():
    author, specialist = UserFactory(display_name="Автор"), SpecialistFactory()
    first = PostFactory(author=author, kind=Post.Kind.REVIEW, specialist=specialist)
    with pytest.raises(IntegrityError), transaction.atomic():
        PostFactory(author=author, kind=Post.Kind.REVIEW, specialist=specialist)
    first.is_deleted = True
    first.save()
    PostFactory(author=author, kind=Post.Kind.REVIEW, specialist=specialist)


@pytest.mark.django_db
def test_like_needs_exactly_one_target():
    user = UserFactory()
    post = PostFactory()
    comment = CommentFactory(post=post)
    with pytest.raises(IntegrityError), transaction.atomic():
        Like.objects.create(user=user)
    with pytest.raises(IntegrityError), transaction.atomic():
        Like.objects.create(user=user, post=post, comment=comment)
    Like.objects.create(user=user, post=post)
    with pytest.raises(IntegrityError), transaction.atomic():
        Like.objects.create(user=user, post=post)


@pytest.mark.django_db
def test_search_fields_filled_on_save(reference):
    condition = DevelopmentalCondition.objects.get(slug="ras")
    post = PostFactory(body="Наш сын с аутизмом", condition=condition)
    post = Post.objects.get(pk=post.pk)
    assert normalize_kk("Наш сын с аутизмом") in post.search_norm
    for lang in ("ru", "kk"):
        name = condition.safe_translation_getter("name", language_code=lang)
        assert name and normalize_kk(name) in post.search_norm
    assert post.search_vector


@pytest.mark.django_db
def test_author_name():
    specialist = SpecialistFactory(display_name="Иванова Анна")
    parent = UserFactory(display_name="Мама Айя")
    bare = UserFactory()
    assert author_name(specialist.user) == "Иванова Анна"
    assert author_name(parent) == "Мама Айя"
    assert author_name(bare) == ""
    assert is_specialist(specialist.user) and not is_specialist(parent)
    assert needs_nickname(bare) and not needs_nickname(parent) and not needs_nickname(specialist.user)
