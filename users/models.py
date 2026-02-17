# Aquí se define modelos -> bases de datos

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)

    weekly_training_days = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)]
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

# Se crea un User con username y password
# Se crea un Profile con weekly_training_days: entre 1 a 7 dias de entrenamiento

