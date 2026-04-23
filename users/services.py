from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import WorkoutCompletion, WeekCompletion


def week_start_for(day):
    return day - timedelta(days=day.weekday())


def recalculate_profile_streak(profile):
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
def rebuild_streak_state_for_user(user):
    """
    Rebuild all streak-related projections from the source of truth:
    approved posts only.

    This keeps WorkoutCompletion, WeekCompletion and Profile streak fields
    consistent after post create/update/delete or moderation transitions.
    """

    from posts.models import Post

    approved_dates = set(
        Post.objects.filter(
            author=user,
            moderation_status=Post.MODERATION_APPROVED,
        )
        .values_list("created_at__date", flat=True)
        .distinct()
    )

    existing_dates = set(
        WorkoutCompletion.objects.filter(user=user).values_list("date", flat=True)
    )

    dates_to_create = approved_dates - existing_dates
    if dates_to_create:
        WorkoutCompletion.objects.bulk_create(
            [WorkoutCompletion(user=user, date=day) for day in sorted(dates_to_create)],
            ignore_conflicts=True,
        )

    dates_to_delete = existing_dates - approved_dates
    if dates_to_delete:
        WorkoutCompletion.objects.filter(user=user, date__in=dates_to_delete).delete()

    profile = getattr(user, "profile", None)
    if not profile:
        return

    weekly_goal = int(getattr(profile, "weekly_training_days", 0) or 0)

    if weekly_goal < 1:
        WeekCompletion.objects.filter(user=user).delete()
        profile.current_weekly_streak = 0
        profile.longest_weekly_streak = 0
        profile.last_completed_week_start = None
        profile.save(update_fields=[
            "current_weekly_streak",
            "longest_weekly_streak",
            "last_completed_week_start",
        ])
        return

    per_week_counts = {}
    for day in WorkoutCompletion.objects.filter(user=user).values_list("date", flat=True).iterator():
        wk = week_start_for(day)
        per_week_counts[wk] = per_week_counts.get(wk, 0) + 1

    qualifying_weeks = {wk for wk, cnt in per_week_counts.items() if cnt >= weekly_goal}

    existing_week_starts = set(
        WeekCompletion.objects.filter(user=user).values_list("week_start", flat=True)
    )

    weeks_to_create = qualifying_weeks - existing_week_starts
    if weeks_to_create:
        WeekCompletion.objects.bulk_create(
            [WeekCompletion(user=user, week_start=wk) for wk in sorted(weeks_to_create)],
            ignore_conflicts=True,
        )

    weeks_to_delete = existing_week_starts - qualifying_weeks
    if weeks_to_delete:
        WeekCompletion.objects.filter(user=user, week_start__in=weeks_to_delete).delete()

    recalculate_profile_streak(profile)


@transaction.atomic
def apply_weekly_training_days_change(user, new_goal):
    profile = user.profile
    profile.weekly_training_days = new_goal
    profile.save(update_fields=["weekly_training_days"])
    rebuild_streak_state_for_user(user)