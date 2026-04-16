"""
Responsabilidades:
- Buscar usuarios
- Seguir/dejar de seguir
- Mostrar feed (posts de usuarios seguidos)
- Dar/quitar like
- Ver perfil de usuarios
- Agregar comentarios
- Gestión de solicitudes de amistad (aceptar, rechazar, eliminar)
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages

from posts.models import Post
from posts.services.gemini_moderation import moderate_post
from .models import Follow, Like, Comment
from fittogether.utils import week_bounds
from users.models import Profile


@login_required(login_url="users:register")
def feed_view(request):
    following_ids = Follow.objects.filter(
        follower=request.user,
        status="accepted",
    ).values_list("following_id", flat=True)

    base_filter = Q(author__in=following_ids) | Q(author=request.user)

    posts = (
        Post.objects
        .filter(base_filter)
        .select_related("author")
        .prefetch_related("like_set", "comment_set__user")
        .annotate(
            likes_count=Count("like", distinct=True),
            comments_count=Count("comment", distinct=True),
        )
        .order_by("-created_at")
    )

    for post in posts:
        post.user_has_liked = post.like_set.filter(user=request.user).exists()
        post.can_edit_now = post.can_edit(request.user)

    today = timezone.localdate()
    already_posted_today = Post.objects.filter(
        author=request.user,
        created_at__date=today,
    ).exists()

    weekly_limit = getattr(getattr(request.user, "profile", None), "weekly_training_days", 0) or 0
    start_dt, end_dt = week_bounds(today)
    posts_this_week = Post.objects.filter(
        author=request.user,
        created_at__gte=start_dt,
        created_at__lt=end_dt,
    ).count()

    training_days_remaining = max(0, weekly_limit - posts_this_week)
    can_post = (weekly_limit >= 1) and (posts_this_week < weekly_limit) and (not already_posted_today)

    weekday_codes = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    today_code = weekday_codes[today.weekday()]
    today_label = dict(Profile.REMINDER_DAY_CHOICES).get(today_code, "today")

    profile = request.user.profile
    selected_reminder_days = profile.get_training_reminder_days_list()

    should_show_training_reminder = (
        profile.training_reminders_enabled
        and today_code in selected_reminder_days
        and not already_posted_today
        and training_days_remaining > 0
    )

    session_key = f"training_reminder_seen_{today.isoformat()}"
    show_training_reminder_popup = False

    if should_show_training_reminder and not request.session.get(session_key, False):
        show_training_reminder_popup = True
        request.session[session_key] = True

    ctx = {
        "posts": posts,
        "can_post": can_post,
        "training_days_remaining": training_days_remaining,
        "weekly_training_days": weekly_limit,
        "already_posted_today": already_posted_today,
        "show_training_reminder_popup": show_training_reminder_popup,
        "training_reminder_day_label": today_label,
    }

    return render(request, "social/feed.html", ctx)


@login_required
def search_users(request):
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        users = User.objects.filter(
            username__icontains=query
        ).exclude(
            id=request.user.id
        ).select_related('profile')[:10]

        # Ids donde YO sigo a alguien con accepted
        following_accepted_ids = set(Follow.objects.filter(
            follower=request.user,
            status='accepted'
        ).values_list('following_id', flat=True))

        # Ids donde YO envié solicitud pending
        pending_sent_ids = set(Follow.objects.filter(
            follower=request.user,
            status='pending'
        ).values_list('following_id', flat=True))

        # Ids donde ALGUIEN me envió solicitud pending
        pending_received_ids = set(Follow.objects.filter(
            following=request.user,
            status='pending'
        ).values_list('follower_id', flat=True))

        # Ids donde alguien me sigue con accepted (para detectar amistad completa)
        followers_accepted_ids = set(Follow.objects.filter(
            following=request.user,
            status='accepted'
        ).values_list('follower_id', flat=True))

        for user in users:
            # is_friend = amistad mutua accepted
            is_friend = user.id in following_accepted_ids and user.id in followers_accepted_ids
            # is_following = yo lo sigo accepted (aunque no sea mutuo aún)
            is_following = user.id in following_accepted_ids

            results.append({
                'id': user.id,
                'username': user.username,
                'profile_picture': user.profile.profile_picture.url if hasattr(user, 'profile') and user.profile.profile_picture else None,
                'is_following': is_following or is_friend,
                'has_pending_sent': user.id in pending_sent_ids,
                'has_pending_received': user.id in pending_received_ids,
            })

    ctx = {
        "query": query,
        "results": results,
    }

    return render(request, "social/search.html", ctx)


@login_required
@require_POST
def toggle_follow(request, user_id):
    target_user = get_object_or_404(User, id=user_id)

    if target_user == request.user:
        return JsonResponse({'success': False, 'error': 'No puedes seguirte a ti mismo'}, status=400)

    follow_obj = Follow.objects.filter(
        follower=request.user,
        following=target_user
    ).first()

    if follow_obj:
        was_accepted = follow_obj.status == 'accepted'
        follow_obj.delete()

        # Si era amistad aceptada, eliminar AMBAS direcciones
        if was_accepted:
            Follow.objects.filter(
                follower=target_user,
                following=request.user
            ).delete()

        is_following = False
        is_pending = False
    else:
        # Antes de crear una nueva solicitud, limpiar cualquier Follow inverso
        # huérfano que haya quedado (por si acaso)
        Follow.objects.filter(
            follower=target_user,
            following=request.user,
            status='accepted'
        ).delete()

        Follow.objects.create(
            follower=request.user,
            following=target_user,
            status='pending'
        )
        is_following = False
        is_pending = True

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_following': is_following,
            'is_pending': is_pending,
        })

    return redirect('social:feed')


@login_required
@require_POST
def toggle_like(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    is_own = post.author == request.user
    is_friend = Follow.objects.filter(
        follower=request.user,
        following=post.author,
        status='accepted',
    ).exists()

    if not is_own and not is_friend:
        return JsonResponse({'success': False, 'error': 'No permission to like this post.'}, status=403)

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
        following=profile_user,
        status='accepted'
    ).exists()

    has_pending = Follow.objects.filter(
        follower=request.user,
        following=profile_user,
        status='pending'
    ).exists()

    received_pending = Follow.objects.filter(
        follower=profile_user,
        following=request.user,
        status='pending'
    ).exists()

    posts = Post.objects.filter(
        author=profile_user
    ).annotate(
        likes_count=Count("like", distinct=True),
        comments_count=Count("comment", distinct=True)
    ).order_by("-created_at")

    for post in posts:
        post.user_has_liked = post.like_set.filter(user=request.user).exists()

    followers_count = Follow.objects.filter(following=profile_user, status='accepted').count()
    following_count = Follow.objects.filter(follower=profile_user, status='accepted').count()
    posts_count = posts.count()

    ctx = {
        "profile_user": profile_user,
        "is_following": is_following,
        "has_pending": has_pending,
        "received_pending": received_pending,
        "is_own_profile": profile_user == request.user,
        "posts": posts,
        "followers_count": followers_count,
        "following_count": following_count,
        "posts_count": posts_count,
    }

    return render(request, "social/profile.html", ctx)


@login_required
@require_POST
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    is_own = post.author == request.user
    is_friend = Follow.objects.filter(
        follower=request.user,
        following=post.author,
        status='accepted',
    ).exists()

    if not is_own and not is_friend:
        return JsonResponse({'success': False, 'error': 'No permission to comment.'}, status=403)

    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'success': False, 'error': 'Comment cannot be empty.'}, status=400)

    allowed, reason = moderate_post(content)
    if not allowed:
        return JsonResponse({"success": False, "error": f"Comment blocked: {reason}"})

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


# ============================================================================
# FUNCIONES DE AMISTAD
# ============================================================================

@login_required
def friend_requests(request):
    received_requests = Follow.objects.filter(
        following=request.user,
        status='pending'
    ).select_related('follower')

    sent_requests = Follow.objects.filter(
        follower=request.user,
        status='pending'
    ).select_related('following')

    my_friends = Follow.objects.filter(
        follower=request.user,
        status='accepted'
    ).select_related('following')

    ctx = {
        "received_requests": received_requests,
        "sent_requests": sent_requests,
        "my_friends": my_friends,
    }

    return render(request, "social/friend_requests.html", ctx)


@login_required
@require_POST
def accept_friend_request(request, request_id):
    friend_request = get_object_or_404(
        Follow,
        id=request_id,
        following=request.user,
        status='pending'
    )

    friend_request.status = 'accepted'
    friend_request.save()

    # Crear o actualizar relación inversa
    reverse_follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=friend_request.follower,
        defaults={'status': 'accepted'}
    )
    if not created and reverse_follow.status != 'accepted':
        reverse_follow.status = 'accepted'
        reverse_follow.save()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f"You are now friends with {friend_request.follower.username}",
            'friend_id': friend_request.follower.id,
            'friend_username': friend_request.follower.username,
            'friend_profile_url': f"/profile/{friend_request.follower.username}/",
        })

    messages.success(request, f"You are now friends with {friend_request.follower.username}")
    return redirect('social:friend_requests')


@login_required
@require_POST
def reject_friend_request(request, request_id):
    friend_request = Follow.objects.filter(
        id=request_id,
        status='pending'
    ).filter(
        models.Q(following=request.user) | models.Q(follower=request.user)
    ).first()

    if not friend_request:
        from django.http import Http404
        raise Http404("No Follow matches the given query.")

    friend_request.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': "Request removed"})

    messages.success(request, "Request removed")
    return redirect('social:friend_requests')


@login_required
@require_POST
def remove_friend(request, friend_id):
    deleted, _ = Follow.objects.filter(
        Q(follower=request.user, following_id=friend_id) |
        Q(follower_id=friend_id, following=request.user)
    ).delete()

    if not deleted:
        return JsonResponse({'success': False, 'error': 'Not friends with this user.'}, status=404)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Friend removed'})

    messages.success(request, "Friend removed")
    return redirect('social:friend_requests')