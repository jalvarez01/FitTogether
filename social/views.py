"""
Responsabilidades:
- Buscar usuarios
- Seguir/dejar de seguir
- Mostrar feed (posts de usuarios seguidos)
- Dar/quitar like
- Ver perfil de usuarios
- Agregar comentarios
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import datetime, timedelta
import calendar

from posts.models import Post
from .models import Follow, Like, Comment
from users.models import WorkoutCompletion



def _week_bounds(local_day):
    """(start_dt, end_dt) for the week (Mon 00:00 -> next Mon 00:00) in current TZ."""
    start_day = local_day - timedelta(days=local_day.weekday())  # Monday
    start_dt = timezone.make_aware(datetime.combine(start_day, datetime.min.time()))
    end_dt = start_dt + timedelta(days=7)
    return start_dt, end_dt


def _streak_calendar_context(request, *, today, posts_this_week, weekly_limit):
    """
    Context compartido para renderizar el panel derecho (calendario + streak),
    tanto en feed como en search.

    - today: date (timezone.localdate())
    - posts_this_week: int (posts del usuario en la semana actual)
    - weekly_limit: int (weekly_training_days)
    """
    # Month navigation via ?month=2&year=2026
    today_date = today
    try:
        month = int(request.GET.get("month", today_date.month))
        year = int(request.GET.get("year", today_date.year))
        if month < 1 or month > 12:
            raise ValueError
    except (TypeError, ValueError):
        month, year = today_date.month, today_date.year

    # calendar weeks: list[list[int]] (0 means padding)
    cal = calendar.Calendar(firstweekday=6)  # Sunday first like your mock
    weeks = cal.monthdayscalendar(year, month)

    completed_days = set(
        WorkoutCompletion.objects.filter(
            user=request.user,
            date__year=year,
            date__month=month,
        ).values_list("date__day", flat=True)
    )

    # Previous/next month
    prev_year, prev_month = year, month - 1
    next_year, next_month = year, month + 1
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    if next_month == 13:
        next_month = 1
        next_year += 1

    profile = getattr(request.user, "profile", None)
    current_weekly_streak = getattr(profile, "current_weekly_streak", 0) or 0
    longest_weekly_streak = getattr(profile, "longest_weekly_streak", 0) or 0

    # Weekly progress (this week): posts = workouts (1/day enforced elsewhere)
    weekly_progress = posts_this_week
    weekly_goal = weekly_limit

    return {
        "calendar_weeks": weeks,
        "calendar_month_label": calendar.month_name[month],
        "calendar_month": month,
        "calendar_year": year,
        "calendar_today_day": today_date.day if (today_date.month == month and today_date.year == year) else None,
        "calendar_completed_days": completed_days,
        "calendar_prev_month": prev_month,
        "calendar_prev_year": prev_year,
        "calendar_next_month": next_month,
        "calendar_next_year": next_year,
        "current_weekly_streak": current_weekly_streak,
        "longest_weekly_streak": longest_weekly_streak,
        "weekly_progress": weekly_progress,
        "weekly_goal": weekly_goal,
    }


@login_required(login_url="users:register")
def feed_view(request):
    # usuarios que yo sigo (mis "friends" para el feed)
    following_ids = Follow.objects.filter(
        follower=request.user
    ).values_list("following_id", flat=True)

    # Si todavía no sigue a nadie, muestra al menos los posts del usuario para que no se vea vacío
    base_filter = Q(author__in=following_ids) | Q(author=request.user)

    posts = (
        Post.objects
        .filter(base_filter)
        .select_related("author")
        .prefetch_related("like_set", "comment_set__user")
        .annotate(
            likes_count=Count("like", distinct=True),
            comments_count=Count("comment", distinct=True)
        )
        .order_by("-created_at")
    )

    # Marcar qué posts tienen like del usuario actual
    for post in posts:
        post.user_has_liked = post.like_set.filter(user=request.user).exists()

    for post in posts:
        post.can_edit_now = post.can_edit(request.user)

    # Posting rules (for UI):
    today = timezone.localdate()
    already_posted_today = Post.objects.filter(author=request.user, created_at__date=today).exists()

    weekly_limit = getattr(getattr(request.user, "profile", None), "weekly_training_days", 0) or 0
    start_dt, end_dt = _week_bounds(today)
    posts_this_week = Post.objects.filter(author=request.user, created_at__gte=start_dt, created_at__lt=end_dt).count()

    training_days_remaining = max(0, weekly_limit - posts_this_week)
    can_post = (weekly_limit >= 1) and (posts_this_week < weekly_limit) and (not already_posted_today)

    # Calendar / streak context
    streak_ctx = _streak_calendar_context(
        request,
        today=today,
        posts_this_week=posts_this_week,
        weekly_limit=weekly_limit,
    )

    ctx = {
        "posts": posts,
        "can_post": can_post,
        "training_days_remaining": training_days_remaining,
        "weekly_training_days": weekly_limit,
        "already_posted_today": already_posted_today,
    }
    ctx.update(streak_ctx)

    return render(request, "social/feed.html", ctx)


@login_required
def search_users(request):
    """
    Busca usuarios por username
    """
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        # Buscar usuarios que coincidan con el query
        users = User.objects.filter(
            username__icontains=query
        ).exclude(
            id=request.user.id
        ).select_related('profile')[:10]

        # Verificar qué usuarios ya sigo
        following_ids = Follow.objects.filter(
            follower=request.user
        ).values_list('following_id', flat=True)

        for user in users:
            results.append({
                'id': user.id,
                'username': user.username,
                'profile_picture': user.profile.profile_picture.url if hasattr(user, 'profile') and user.profile.profile_picture else None,
                'is_following': user.id in following_ids,
            })

    # Para que el calendario/streak funcione también en Search:
    today = timezone.localdate()
    weekly_limit = getattr(getattr(request.user, "profile", None), "weekly_training_days", 0) or 0
    start_dt, end_dt = _week_bounds(today)
    posts_this_week = Post.objects.filter(author=request.user, created_at__gte=start_dt, created_at__lt=end_dt).count()

    streak_ctx = _streak_calendar_context(
        request,
        today=today,
        posts_this_week=posts_this_week,
        weekly_limit=weekly_limit,
    )

    ctx = {
        "query": query,
        "results": results,
    }
    ctx.update(streak_ctx)

    return render(request, "social/search.html", ctx)


@login_required
@require_POST
def toggle_follow(request, user_id):
    """
    Seguir o dejar de seguir a un usuario
    """
    target_user = get_object_or_404(User, id=user_id)

    # No puedes seguirte a ti mismo
    if target_user == request.user:
        return JsonResponse({
            'success': False,
            'error': 'No puedes seguirte a ti mismo'
        }, status=400)

    # Verificar si ya lo sigo
    follow_obj = Follow.objects.filter(
        follower=request.user,
        following=target_user
    ).first()

    if follow_obj:
        follow_obj.delete()
        is_following = False
    else:
        Follow.objects.create(
            follower=request.user,
            following=target_user
        )
        is_following = True

    # Si es AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_following': is_following,
        })

    return redirect('social:feed')


@login_required
@require_POST
def toggle_like(request, post_id):
    """
    Dar o quitar like a un post
    """
    post = get_object_or_404(Post, id=post_id)

    like_obj = Like.objects.filter(
        user=request.user,
        post=post
    ).first()

    if like_obj:
        like_obj.delete()
        has_liked = False
    else:
        Like.objects.create(
            user=request.user,
            post=post
        )
        has_liked = True

    likes_count = Like.objects.filter(post=post).count()

    return JsonResponse({
        'success': True,
        'has_liked': has_liked,
        'likes_count': likes_count,
    })


@login_required
def user_profile(request, username):
    profile_user = get_object_or_404(User, username=username)

    is_following = Follow.objects.filter(
        follower=request.user,
        following=profile_user
    ).exists()

    posts = Post.objects.filter(
        author=profile_user
    ).annotate(
        likes_count=Count("like", distinct=True),
        comments_count=Count("comment", distinct=True)
    ).order_by("-created_at")

    for post in posts:
        post.user_has_liked = post.like_set.filter(user=request.user).exists()

    followers_count = Follow.objects.filter(following=profile_user).count()
    following_count = Follow.objects.filter(follower=profile_user).count()
    posts_count = posts.count()

    # context para el calendario/streak del usuario logueado
    today = timezone.localdate()
    weekly_limit = getattr(getattr(request.user, "profile", None), "weekly_training_days", 0) or 0
    start_dt, end_dt = _week_bounds(today)
    posts_this_week = Post.objects.filter(
        author=request.user,
        created_at__gte=start_dt,
        created_at__lt=end_dt
    ).count()

    streak_ctx = _streak_calendar_context(
        request,
        today=today,
        posts_this_week=posts_this_week,
        weekly_limit=weekly_limit,
    )

    ctx = {
        "profile_user": profile_user,
        "is_following": is_following,
        "is_own_profile": profile_user == request.user,
        "posts": posts,
        "followers_count": followers_count,
        "following_count": following_count,
        "posts_count": posts_count,
    }
    ctx.update(streak_ctx)

    return render(request, "social/profile.html", ctx)


@login_required
@require_POST
def add_comment(request, post_id):
    """
    Agregar un comentario a un post
    """
    post = get_object_or_404(Post, id=post_id)

    # Solo puede comentar si el post es propio o del alguien que sigue
    is_own = post.author == request.user
    is_following = Follow.objects.filter(
        follower=request.user,
        following=post.author
    ).exists()

    if not is_own and not is_following:
        return JsonResponse({'success': False, 'error': 'No tienes permiso para comentar este post.'}, status=403)

    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'success': False, 'error': 'El comentario no puede estar vacío.'}, status=400)

    comment = Comment.objects.create(
        user=request.user,
        post=post,
        content=content
    )

    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'username': comment.user.username,
            'content': comment.content,
            'created_at': comment.created_at.strftime("%b %d, %H:%M"),
        }
    })

