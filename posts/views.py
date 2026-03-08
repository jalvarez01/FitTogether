from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils import timezone

from .forms import PostForm, PostEditForm
from .models import Post

from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseForbidden

def _week_bounds(local_day):
    """
    Returns (start_dt, end_dt) for the current week in the server/user timezone.
    Week starts on Monday 00:00 and ends next Monday 00:00.
    """
    start_day = local_day - timedelta(days=local_day.weekday())  # Monday
    start_dt = timezone.make_aware(datetime.combine(start_day, datetime.min.time()))
    end_dt = start_dt + timedelta(days=7)
    return start_dt, end_dt


@login_required
def create_post(request):
    if request.method != "POST":
        return redirect("social:feed")

    # 1) Enforce "1 post per (calendar) day"
    today = timezone.localdate()
    already_posted_today = Post.objects.filter(
        author=request.user,
        created_at__date=today,
    ).exists()
    if already_posted_today:
        messages.error(
            request,
            "You have already created a post today. Only 1 post per day is allowed.",
        )
        return redirect("social:feed")

    # 2) Enforce weekly training quota:
    # User can only post on as many distinct training days as their profile says.
    # We interpret this as: in the current week (Mon-Sun), you can create at most
    # `weekly_training_days` posts (and still max 1 per day).
    weekly_limit = getattr(getattr(request.user, "profile", None), "weekly_training_days", None)

    # If for some reason the profile isn't set yet, block posting to avoid breaking the rules.
    if not weekly_limit or weekly_limit < 1:
        messages.error(
            request,
            "Your profile training days are not set yet. Please update your profile before posting.",
        )
        return redirect("social:feed")

    start_dt, end_dt = _week_bounds(today)
    posts_this_week = Post.objects.filter(
        author=request.user,
        created_at__gte=start_dt,
        created_at__lt=end_dt,
    ).count()

    if posts_this_week >= weekly_limit:
        messages.error(
            request,
            f"You have already completed your {weekly_limit} training days for this week. "
            "You can post again next week.",
        )
        return redirect("social:feed")

    # 3) Create post
    form = PostForm(request.POST, request.FILES)
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        remaining = weekly_limit - (posts_this_week + 1)
        if remaining > 0:
            messages.success(
                request,
                f"Post created successfully. Training days remaining this week: {remaining}.",
            )
        else:
            messages.success(
                request,
                "Post created successfully. You completed your training days for this week!",
            )
    else:
        messages.error(request, "Could not create the post. Please check the form and try again.")

    return redirect("social:feed")

@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    # Solo el autor puede editar
    if post.author != request.user:
        return HttpResponseForbidden("You can only edit your own posts.")

    # Solo dentro de 24 horas
    if not post.can_edit(request.user):
        return HttpResponseForbidden("You can only edit posts within 24 hours.")

    if request.method == "POST":
        form = PostEditForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            return redirect("social:feed")  
    else:
        form = PostEditForm(instance=post)

    return render(request, "posts/edit_post.html", {"form": form, "post": post})