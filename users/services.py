from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import WorkoutCompletion, WeekCompletion


def week_start_for(day):
    return day - timedelta(days=day.weekday())


def recalculate_profile_streak(profile):
    """
    Recalculate current_weekly_streak, longest_weekly_streak and
    last_completed_week_start from WeekCompletion history.
    """
    completed_weeks = list(
        WeekCompletion.objects.filter(user=profile.user)
        .order_by("week_start")
        .values_list("week_start", flat=True)
    )

    if not completed_weeks:
        profile.current_weekly_streak = 0
        profile.longest_weekly_streak = 0
        profile.last_completed_week_start = None
        profile.save(update_fields=[
            "current_weekly_streak",
            "longest_weekly_streak",
            "last_completed_week_start",
        ])
        return

    longest = 1
    running = 1

    for i in range(1, len(completed_weeks)):
        if completed_weeks[i] == completed_weeks[i - 1] + timedelta(days=7):
            running += 1
        else:
            running = 1

        if running > longest:
            longest = running

    last_week = completed_weeks[-1]
    current_week_start = week_start_for(timezone.localdate())

    # current streak only counts if the most recent completed week
    # is the current week or a direct chain up to the current week.
    if last_week == current_week_start:
        current = 1
        idx = len(completed_weeks) - 1

        while idx > 0:
            if completed_weeks[idx] == completed_weeks[idx - 1] + timedelta(days=7):
                current += 1
                idx -= 1
            else:
                break
    else:
        current = 0

    profile.current_weekly_streak = current
    profile.longest_weekly_streak = longest
    profile.last_completed_week_start = last_week
    profile.save(update_fields=[
        "current_weekly_streak",
        "longest_weekly_streak",
        "last_completed_week_start",
    ])


@transaction.atomic
def apply_weekly_training_days_change(user, new_goal):
    """
    Update weekly_training_days and make the current week consistent with the new goal.

    Rules:
    - Past completed weeks remain untouched.
    - Current week is re-evaluated against the new goal.
    - Streak fields are recalculated from WeekCompletion history.
    """
    profile = user.profile
    profile.weekly_training_days = new_goal
    profile.save(update_fields=["weekly_training_days"])

    today = timezone.localdate()
    current_week_start = week_start_for(today)
    current_week_end = current_week_start + timedelta(days=7)

    workouts_this_week = WorkoutCompletion.objects.filter(
        user=user,
        date__gte=current_week_start,
        date__lt=current_week_end,
    ).count()

    week_completion = WeekCompletion.objects.filter(
        user=user,
        week_start=current_week_start,
    ).first()

    if workouts_this_week >= new_goal:
        if not week_completion:
            WeekCompletion.objects.create(
                user=user,
                week_start=current_week_start,
            )
    else:
        if week_completion:
            week_completion.delete()

    recalculate_profile_streak(profile)