"""
Responsabilidades:

- Registro de usuario
- Crear/editar perfil
- Ver perfil
- Configuración del perfil
- Autenticación (login/logout)
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from social.models import Follow
from posts.models import Post

from .forms import CustomUserCreationForm, ProfileSettingsForm
from .services import apply_weekly_training_days_change


@login_required(login_url="users:register")
def profile_view(request):
    user = request.user
    profile = user.profile

    friends = Follow.objects.filter(
        follower=user,
        status="accepted"
    ).select_related("following__profile")

    posts = Post.objects.filter(author=user).annotate(
        likes_count=Count("like", distinct=True),
        comments_count=Count("comment", distinct=True)
    ).order_by("-created_at")

    ctx = {
        "profile": profile,
        "friends": friends,
        "posts": posts,
        "posts_count": posts.count(),
        "friends_count": friends.count(),
    }
    return render(request, "users/profile.html", ctx)


@login_required
def settings_view(request):
    profile = request.user.profile
    old_goal = profile.weekly_training_days

    if request.method == "POST":
        form = ProfileSettingsForm(
            request.POST,
            instance=profile,
            user=request.user,
        )

        if form.is_valid():
            updated_profile = form.save()

            new_goal = updated_profile.weekly_training_days
            if new_goal != old_goal:
                apply_weekly_training_days_change(request.user, new_goal)

            messages.success(request, "Your settings were updated successfully.")
            return redirect("users:settings")
    else:
        form = ProfileSettingsForm(
            instance=profile,
            user=request.user,
        )

    return render(request, "users/settings.html", {
        "form": form,
    })


@login_required
@require_POST
def update_bio(request):
    bio = request.POST.get("bio", "").strip()
    if len(bio) > 60:
        return JsonResponse(
            {"success": False, "error": "Bio must be 60 characters or less."},
            status=400
        )

    request.user.profile.bio = bio
    request.user.profile.save()
    return JsonResponse({"success": True, "bio": bio})


@login_required
@require_POST
def update_banner(request):
    color = request.POST.get("color", "").strip()
    allowed = ["#eaf0ff", "#fde9fb", "#eaf9ee", "#efeff1"]

    if color not in allowed:
        return JsonResponse({"success": False, "error": "Invalid color"}, status=400)

    request.user.profile.banner_color = color
    request.user.profile.save()
    return JsonResponse({"success": True, "color": color})


@login_required
@require_POST
def update_avatar(request):
    action = request.POST.get("action", "upload")

    if action == "delete":
        profile = request.user.profile
        if profile.profile_picture:
            profile.profile_picture.delete(save=False)
            profile.profile_picture = None
            profile.save()
        return JsonResponse({"success": True, "picture_url": None})

    if "picture" in request.FILES:
        profile = request.user.profile

        if profile.profile_picture:
            profile.profile_picture.delete(save=False)

        profile.profile_picture = request.FILES["picture"]
        profile.save()
        return JsonResponse({"success": True, "picture_url": profile.profile_picture.url})

    return JsonResponse({"success": False, "error": "No file provided"}, status=400)


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