from django.db import transaction

from .models import Post, PostImage


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
