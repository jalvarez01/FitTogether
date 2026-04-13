from datetime import timedelta

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from posts.models import Post
from users.models import WorkoutCompletion, WeekCompletion


def _week_start(day):
    """Return the Monday date for the week containing `day` (a date)."""
    return day - timedelta(days=day.weekday())


@receiver(post_save, sender=Post)
def record_daily_workout_and_update_weekly_streak(sender, instance: Post, created: bool, **kwargs):
    """Record workout completion on post creation and update WEEKLY streak.

    Requirements:
    - If the user makes a post on the feed, record the completion of the daily workout.
    - After recording the completion, update the user's streak based on their training days.

    FitTogether rule:
    - weekly_training_days = N
    - User can complete a "training week" when they post on N distinct days inside the same Mon→Sun week.
    - Weekly streak counts consecutive *completed weeks*.
    """

    if not created:
        return

    workout_date = timezone.localdate(instance.created_at)
    user = instance.author

    with transaction.atomic():
        # 1) Record daily workout completion (idempotent)
        completion, was_created = WorkoutCompletion.objects.get_or_create(
            user=user,
            date=workout_date,
        )
        if not was_created:
            return

        profile = getattr(user, "profile", None)
        if not profile:
            return

        weekly_goal = int(getattr(profile, "weekly_training_days", 0) or 0)
        if weekly_goal < 1:
            return

        # 2) Check if the user has now completed the week
        wk_start = _week_start(workout_date)
        wk_end = wk_start + timedelta(days=7)

        workouts_this_week = WorkoutCompletion.objects.filter(
            user=user,
            date__gte=wk_start,
            date__lt=wk_end,
        ).count()

        if workouts_this_week < weekly_goal:
            return

        week_obj, week_created = WeekCompletion.objects.get_or_create(
            user=user,
            week_start=wk_start,
        )
        if not week_created:
            return

        # 3) Update weekly streak (consecutive completed weeks)
        last_wk = profile.last_completed_week_start
        if last_wk == wk_start:
            return

        if last_wk and wk_start == (last_wk + timedelta(days=7)):
            profile.current_weekly_streak = (profile.current_weekly_streak or 0) + 1
        else:
            profile.current_weekly_streak = 1

        profile.last_completed_week_start = wk_start
        profile.longest_weekly_streak = max(
            profile.longest_weekly_streak or 0,
            profile.current_weekly_streak or 0,
        )

        profile.save(update_fields=[
            "current_weekly_streak",
            "longest_weekly_streak",
            "last_completed_week_start",
        ])