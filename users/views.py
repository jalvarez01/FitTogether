"""
Responsabilidades:

- Registro de usuario
- Crear/editar perfil
- Ver perfil
- Autenticación (login/logout)
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from .forms import CustomUserCreationForm
from .models import Profile
from social.models import Follow
from posts.models import Post
from django.db.models import Count


@login_required(login_url="users:register")
def profile_view(request):
    user = request.user
    profile = user.profile

    # Amigos reales (accepted follows donde yo soy follower)
    friends = Follow.objects.filter(
        follower=user,
        status='accepted'
    ).select_related('following__profile')

    # Posts del usuario con conteos
    posts = Post.objects.filter(author=user).annotate(
        likes_count=Count('like', distinct=True),
        comments_count=Count('comment', distinct=True)
    ).order_by('-created_at')

    ctx = {
        'profile': profile,
        'friends': friends,
        'posts': posts,
        'posts_count': posts.count(),
        'friends_count': friends.count(),
    }
    return render(request, "users/profile.html", ctx)


@login_required
@require_POST
def update_bio(request):
    bio = request.POST.get('bio', '').strip()
    request.user.profile.bio = bio
    request.user.profile.save()
    return JsonResponse({'success': True, 'bio': bio})


@login_required
@require_POST
def update_banner(request):
    color = request.POST.get('color', '').strip()
    ALLOWED = ['#eaf0ff', '#fde9fb', '#eaf9ee', '#efeff1']
    if color not in ALLOWED:
        return JsonResponse({'success': False, 'error': 'Invalid color'}, status=400)
    request.user.profile.banner_color = color
    request.user.profile.save()
    return JsonResponse({'success': True, 'color': color})


@login_required
@require_POST
def update_avatar(request):
    action = request.POST.get('action', 'upload')
    if action == 'delete':
        profile = request.user.profile
        if profile.profile_picture:
            profile.profile_picture.delete(save=False)
            profile.profile_picture = None
            profile.save()
        return JsonResponse({'success': True, 'picture_url': None})

    if 'picture' in request.FILES:
        profile = request.user.profile
        # Delete old picture if exists
        if profile.profile_picture:
            profile.profile_picture.delete(save=False)
        profile.profile_picture = request.FILES['picture']
        profile.save()
        return JsonResponse({'success': True, 'picture_url': profile.profile_picture.url})

    return JsonResponse({'success': False, 'error': 'No file provided'}, status=400)


def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("social:feed")
    else:
        form = CustomUserCreationForm()

    return render(request, "users/register.html", {"form": form})