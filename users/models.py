# Aquí se define modelos -> bases de datos

from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    weekly_training_days = models.PositiveIntegerField(
        help_text="Number of training days per week"
    )

    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

# Se crea un User con username y password
# Se crea un Profile con weekly_training_days

