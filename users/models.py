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

    # ── Weekly streak ───────────────────────────────────────────────────────
    # In FitTogether, a "workout completed" is recorded when the user posts.
    # A "week completed" happens when the user posts on *weekly_training_days*
    # distinct days inside the same Monday→Sunday week.
    # Streak counts *consecutive completed weeks*.
    current_weekly_streak = models.PositiveIntegerField(default=0)
    longest_weekly_streak = models.PositiveIntegerField(default=0)
    # Stores the Monday date of the last week the user completed.
    last_completed_week_start = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username


class WorkoutCompletion(models.Model):
    """One row per user per day when they complete a workout (by posting)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="workout_completions")
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ("-date",)

    def __str__(self):
        return f"{self.user.username} workout {self.date:%Y-%m-%d}"


class WeekCompletion(models.Model):
    """One row per user per completed training week (Mon start date)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="week_completions")
    week_start = models.DateField()  # Monday
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "week_start")
        ordering = ("-week_start",)

    def __str__(self):
        return f"{self.user.username} week {self.week_start:%Y-%m-%d}"


# Se crea un User con username y password
# Se crea un Profile con weekly_training_days: entre 1 a 7 dias de entrenamiento