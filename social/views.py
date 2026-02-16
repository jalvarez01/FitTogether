
"""
Responsabilidades:
- Buscar usuarios
- Seguir/dejar de seguir
- Mostrar feed (posts de usuarios seguidos)
- Dar/quitar like
- Ver perfil de otros usuarios
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


@login_required
def feed_view(request):
    """
    Muestra el feed con posts de usuarios que el usuario actual sigue
    + sus propios posts
    """
    # Usuarios que yo sigo
    following_ids = Follow.objects.filter(
        follower=request.user
    ).values_list("following_id", flat=True)

    # Posts de usuarios seguidos + mis propios posts
    base_filter = Q(author__in=following_ids) | Q(author=request.user)

    posts = (
        Post.objects
        .filter(base_filter)
        .select_related("author", "author__profile")
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

    return render(request, "social/feed.html", {
        "posts": posts,
    })


@login_required
def search_users(request):
    """
    Busca usuarios por username
    """
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        # Buscar usuarios que coincidan con el query (case insensitive)
        users = User.objects.filter(
            username__icontains=query
        ).exclude(
            id=request.user.id  # Excluir al usuario actual
        ).select_related('profile')[:10]  # Limitar a 10 resultados

        # Verificar qué usuarios ya sigo
        following_ids = Follow.objects.filter(
            follower=request.user
        ).values_list('following_id', flat=True)

        for user in users:
            results.append({
                'id': user.id,
                'username': user.username,
                'profile_picture': user.profile.profile_picture.url if user.profile.profile_picture else None,
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
        # Ya lo sigo -> dejar de seguir
        follow_obj.delete()
        is_following = False
        message = f"Dejaste de seguir a {target_user.username}"
    else:
        # No lo sigo -> seguir
        Follow.objects.create(
            follower=request.user,
            following=target_user
        )
        is_following = True
        message = f"Ahora sigues a {target_user.username}"

    # Si es una petición AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'is_following': is_following,
            'message': message,
        })

    # Si no es AJAX, redirigir
    messages.success(request, message)
    return redirect(request.META.get('HTTP_REFERER', 'social:feed'))


@login_required
@require_POST
def toggle_like(request, post_id):
    """
    Dar o quitar like a un post
    """
    post = get_object_or_404(Post, id=post_id)

    # Verificar si ya le di like
    like_obj = Like.objects.filter(
        user=request.user,
        post=post
    ).first()

    if like_obj:
        # Ya tiene like -> quitar
        like_obj.delete()
        has_liked = False
    else:
        # No tiene like -> dar like
        Like.objects.create(
            user=request.user,
            post=post
        )
        has_liked = True

    # Contar likes actuales
    likes_count = Like.objects.filter(post=post).count()

    # Responder con JSON para actualizar el frontend
    return JsonResponse({
        'success': True,
        'has_liked': has_liked,
        'likes_count': likes_count,
    })


@login_required
def user_profile(request, username):
    """
    Ver el perfil de otro usuario (o el propio)
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

    # Marcar likes del usuario actual
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