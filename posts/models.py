from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta


class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="posts")
    content = models.TextField(blank=True)
    image = models.ImageField(upload_to="posts/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.author.username} - {self.created_at:%Y-%m-%d %H:%M}"

    def can_edit(self, user):
        """
        True if:
        - user is authenticated
        - user is the author
        - post was created within last 24 hours
        """
        if not user.is_authenticated:
            return False
        if self.author != user:
            return False
        return timezone.now() <= self.created_at + timedelta(hours=24)