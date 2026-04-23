from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from posts.models import Post
from users.services import rebuild_streak_state_for_user


def _is_approved(status: str) -> bool:
    return status == Post.MODERATION_APPROVED


@receiver(pre_save, sender=Post)
def capture_previous_post_state(sender, instance: Post, **kwargs):
    if not instance.pk:
        return

    previous = (
        Post.objects.filter(pk=instance.pk)
        .values("author_id", "moderation_status")
        .first()
    )

    instance._previous_author_id = previous["author_id"] if previous else None
    instance._previous_moderation_status = previous["moderation_status"] if previous else None


@receiver(post_save, sender=Post)
def sync_streaks_after_post_save(sender, instance: Post, created: bool, **kwargs):
    if created:
        if _is_approved(instance.moderation_status):
            rebuild_streak_state_for_user(instance.author)
        return

    previous_status = getattr(instance, "_previous_moderation_status", None)
    previous_author_id = getattr(instance, "_previous_author_id", None)

    author_changed = previous_author_id is not None and previous_author_id != instance.author_id
    approval_relevant_change = previous_status != instance.moderation_status and (
        _is_approved(previous_status) or _is_approved(instance.moderation_status)
    )

    if author_changed:
        from django.contrib.auth.models import User

        previous_author = User.objects.filter(pk=previous_author_id).first()
        if previous_author:
            rebuild_streak_state_for_user(previous_author)

        if _is_approved(instance.moderation_status):
            rebuild_streak_state_for_user(instance.author)
        return

    if approval_relevant_change:
        rebuild_streak_state_for_user(instance.author)


@receiver(post_delete, sender=Post)
def sync_streaks_after_post_delete(sender, instance: Post, **kwargs):
    if _is_approved(instance.moderation_status):
        rebuild_streak_state_for_user(instance.author)