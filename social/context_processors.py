import calendar

from django.utils import timezone

from posts.models import Post
from users.models import WorkoutCompletion
from fittogether.utils import week_bounds


def streak_calendar(request):
    if not request.user.is_authenticated:
        return {}

    today = timezone.localdate()

    try:
        month = int(request.GET.get("month", today.month))
        year = int(request.GET.get("year", today.year))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        month, year = today.month, today.year

    cal = calendar.Calendar(firstweekday=6)  # Sunday first
    weeks = cal.monthdayscalendar(year, month)

    completed_days = set(
        WorkoutCompletion.objects.filter(
            user=request.user,
            date__year=year,
            date__month=month,
        ).values_list("date__day", flat=True)
    )

    prev_year, prev_month = year, month - 1
    next_year, next_month = year, month + 1

    if prev_month == 0:
        prev_month = 12
        prev_year -= 1

    if next_month == 13:
        next_month = 1
        next_year += 1

    profile = getattr(request.user, "profile", None)
    weekly_goal = getattr(profile, "weekly_training_days", 0) or 0
    current_weekly_streak = getattr(profile, "current_weekly_streak", 0) or 0
    longest_weekly_streak = getattr(profile, "longest_weekly_streak", 0) or 0

    start_dt, end_dt = week_bounds(today)
    weekly_progress = Post.objects.filter(
        author=request.user,
        moderation_status=Post.MODERATION_APPROVED,
        created_at__gte=start_dt,
        created_at__lt=end_dt
    ).count()

    # Conteo de notificaciones no leídas (importación local para evitar import circular)
    from social.models import Notification
    unread_notifications_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    return {
        "calendar_weeks": weeks,
        "calendar_month_label": calendar.month_name[month],
        "calendar_month": month,
        "calendar_year": year,
        "calendar_today_day": today.day if (today.month == month and today.year == year) else None,
        "calendar_completed_days": completed_days,
        "calendar_prev_month": prev_month,
        "calendar_prev_year": prev_year,
        "calendar_next_month": next_month,
        "calendar_next_year": next_year,
        "current_weekly_streak": current_weekly_streak,
        "longest_weekly_streak": longest_weekly_streak,
        "weekly_progress": weekly_progress,
        "weekly_goal": weekly_goal,
        "unread_notifications_count": unread_notifications_count,
    }