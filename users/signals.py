# Para que siempre que se cree un User exista un Profile

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    # Default to 1 so the profile is always valid.
    # The signup form will overwrite this with the user's real value.
    if created:
        Profile.objects.create(user=instance, weekly_training_days=1)