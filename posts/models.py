# Aquí se define modelos -> bases de datos

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError

class Post(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    image = models.ImageField(upload_to='posts/', blank=True, null=True)

    workout_date = models.DateField(default=timezone.now)  
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('author', 'workout_date')

    def clean(self):
        """
        Restricts the user to one post per workout day.
        """
        existing_post = Post.objects.filter(
            author=self.author,
            workout_date=self.workout_date
        ).exclude(pk=self.pk)

        if existing_post.exists():
            raise ValidationError("You can only create one post per workout day.")

    def __str__(self):
        return f"{self.author.username} - {self.workout_date}"

# Cada post está ligado a un día de entrenamiento workout_date
# Restricción de un post por día unique_together
