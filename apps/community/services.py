from django.db import IntegrityError, transaction

from apps.accounts.models import User

from .models import Comment, Complaint, Like, Post, PostImage
from .names import author_name


def set_image(post: Post, upload: tuple[bytes, str] | None, *, remove: bool = False) -> None:
    """Replace the post photo with `upload` (data, content_type), or drop it when `remove`."""
    if upload is not None:
        PostImage.objects.update_or_create(post=post, defaults={"data": upload[0], "content_type": upload[1]})
    elif remove:
        PostImage.objects.filter(post=post).delete()


@transaction.atomic
def save_post(post: Post, upload: tuple[bytes, str] | None = None, *, remove_image: bool = False) -> Post:
    post.save()
    set_image(post, upload, remove=remove_image)
    return post


def soft_delete_post(post: Post) -> None:
    post.is_deleted = True
    post.save(update_fields=["is_deleted", "updated_at"])


def add_comment(post: Post, author: User, body: str, parent: Comment | None = None) -> Comment:
    """Comments nest two levels: a reply to a reply is attached to the top-level comment with an @mention."""
    if parent is not None:
        if parent.post_id != post.pk:
            raise ValueError("parent belongs to another post")
        if parent.parent_id is not None:
            body = f"@{author_name(parent.author)} {body}"
            parent = parent.parent
    return Comment.objects.create(post=post, author=author, parent=parent, body=body)


def soft_delete_comment(comment: Comment) -> None:
    comment.is_deleted = True
    comment.save(update_fields=["is_deleted"])


def toggle_like(user: User, *, post: Post | None = None, comment: Comment | None = None) -> tuple[bool, int]:
    """Flip the user's like on exactly one target; returns (liked now, like count)."""
    if (post is None) == (comment is None):
        raise ValueError("exactly one of post or comment")
    target = {"post": post} if post is not None else {"comment": comment}
    deleted, _ = Like.objects.filter(user=user, **target).delete()
    if not deleted:
        try:
            with transaction.atomic():
                Like.objects.create(user=user, **target)
        except IntegrityError:
            pass  # a concurrent request already liked it
    return not deleted, Like.objects.filter(**target).count()


def file_complaint(
    user: User, *, reason: str, text: str, post: Post | None = None, comment: Comment | None = None
) -> Complaint:
    if (post is None) == (comment is None):
        raise ValueError("exactly one of post or comment")
    return Complaint.objects.create(user=user, post=post, comment=comment, reason=reason, text=text)
