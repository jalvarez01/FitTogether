"""
Responsabilidades:

- Buscar usuarios
- Seguir/dejar de seguir
- Mostrar feed (posts de usuarios seguidos)
- Dar/quitar like
"""

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from posts.models import Post
from .models import Follow

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
        .annotate(
            likes_count=Count("like", distinct=True),      # related_name default: like_set -> aquí depende
            comments_count=Count("comment", distinct=True) # igual
        )
        .order_by("-created_at")
    )

    return render(request, "social/feed.html", {"posts": posts})
