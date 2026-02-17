
"""
Responsabilidades:
- Buscar usuarios
- Seguir/dejar de seguir
- Mostrar feed (posts de usuarios seguidos)
- Dar/quitar like
- Ver perfil de usuarios
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages

from posts.models import Post
from .models import Follow, Like


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
        .prefetch_related("like_set")
        .annotate(
            likes_count=Count("like", distinct=True),
            comments_count=Count("comment", distinct=True)
        )
        .order_by("-created_at")
    )

    # Marcar qué posts tienen like del usuario actual
    for post in posts:
        post.user_has_liked = post.like_set.filter(user=request.user).exists()

    return render(request, "social/feed.html", {"posts": posts})


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

    return render(request, "social/search.html", {
        "query": query,
        "results": results,
    })


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
    """
    Ver el perfil de otro usuario
    """
    profile_user = get_object_or_404(User, username=username)

    # Verificar si sigo a este usuario
    is_following = Follow.objects.filter(
        follower=request.user,
        following=profile_user
    ).exists()

    # Obtener posts del usuario
    posts = Post.objects.filter(
        author=profile_user
    ).annotate(
        likes_count=Count("like", distinct=True),
        comments_count=Count("comment", distinct=True)
    ).order_by("-created_at")

    # Marcar likes
    for post in posts:
        post.user_has_liked = post.like_set.filter(user=request.user).exists()

    # Estadísticas
    followers_count = Follow.objects.filter(following=profile_user).count()
    following_count = Follow.objects.filter(follower=profile_user).count()
    posts_count = posts.count()

    return render(request, "social/profile.html", {
        "profile_user": profile_user,
        "is_following": is_following,
        "is_own_profile": profile_user == request.user,
        "posts": posts,
        "followers_count": followers_count,
        "following_count": following_count,
        "posts_count": posts_count,
    })