from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Profile(models.Model):
    REMINDER_DAY_CHOICES = [
        ("mon", "Monday"),
        ("tue", "Tuesday"),
        ("wed", "Wednesday"),
        ("thu", "Thursday"),
        ("fri", "Friday"),
        ("sat", "Saturday"),
        ("sun", "Sunday"),
    ]

    REMINDER_DAY_ORDER = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to="profiles/", blank=True, null=True)
    banner_color = models.CharField(max_length=20, default="#efeff1")

    weekly_training_days = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(7)]
    )

    current_weekly_streak = models.PositiveIntegerField(default=0)
    longest_weekly_streak = models.PositiveIntegerField(default=0)
    last_completed_week_start = models.DateField(blank=True, null=True)

    training_reminders_enabled = models.BooleanField(default=False)
    training_reminder_days = models.CharField(max_length=32, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

    def get_training_reminder_days_list(self):
        return [
            day
            for day in self.training_reminder_days.split(",")
            if day in self.REMINDER_DAY_ORDER
        ]

    def set_training_reminder_days_list(self, days):
        cleaned = sorted(
            {day for day in days if day in self.REMINDER_DAY_ORDER},
            key=lambda day: self.REMINDER_DAY_ORDER[day],
        )
        self.training_reminder_days = ",".join(cleaned)


class WorkoutCompletion(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="workout_completions",
    )
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "date")
        ordering = ("-date",)

    def __str__(self):
        return f"{self.user.username} workout {self.date:%Y-%m-%d}"


class WeekCompletion(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="week_completions",
    )
    week_start = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "week_start")
        ordering = ("-week_start",)

    def __str__(self):
        return f"{self.user.username} week {self.week_start:%Y-%m-%d}"