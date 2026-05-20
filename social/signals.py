# Señales para generar notificaciones automáticas:
# - Cuando un amigo crea un post (notif_type='post')
# - Cuando un amigo le da like a un post tuyo (notif_type='like')
# - Cuando alguien comenta en un post tuyo (notif_type='comment')

from django.db.models.signals import post_save
from django.dispatch import receiver

from posts.models import Post
from .models import Follow, Like, Comment, Notification


@receiver(post_save, sender=Post)
def notify_friends_on_new_post(sender, instance, created, **kwargs):
    """Notifica a todos los amigos cuando un usuario crea un post aprobado."""
    if not created:
        return
    if instance.moderation_status not in (Post.MODERATION_APPROVED, Post.MODERATION_PENDING):
        return

    # Amigos mutuos del autor: usuarios que siguen al autor y el autor los sigue de vuelta
    friends_ids = Follow.objects.filter(
        following=instance.author,
        status='accepted',
    ).filter(
        follower__in=Follow.objects.filter(
            follower=instance.author,
            status='accepted',
        ).values_list('following_id', flat=True)
    ).values_list('follower_id', flat=True)

    notifications = [
        Notification(
            recipient_id=friend_id,
            actor=instance.author,
            notif_type=Notification.TYPE_POST,
            post=instance,
        )
        for friend_id in friends_ids
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


@receiver(post_save, sender=Like)
def notify_author_on_like(sender, instance, created, **kwargs):
    """Notifica al autor de un post cuando un amigo le da like."""
    if not created:
        return

    # No notificar si el usuario se da like a sí mismo
    if instance.user == instance.post.author:
        return

    Notification.objects.create(
        recipient=instance.post.author,
        actor=instance.user,
        notif_type=Notification.TYPE_LIKE,
        post=instance.post,
    )


@receiver(post_save, sender=Comment)
def notify_author_on_comment(sender, instance, created, **kwargs):
    """Notifica al autor de un post cuando alguien comenta en él."""
    if not created:
        return

    # No notificar si el autor comenta en su propio post
    if instance.user == instance.post.author:
        return

    Notification.objects.create(
        recipient=instance.post.author,
        actor=instance.user,
        notif_type=Notification.TYPE_COMMENT,
        post=instance.post,
    )