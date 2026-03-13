#Post views.py
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import PostForm, PostEditForm
from .models import Post
from .services.gemini_moderation import moderate_post


def _week_bounds(local_day):
    start_day = local_day - timedelta(days=local_day.weekday())  # Monday
    start_dt = timezone.make_aware(datetime.combine(start_day, datetime.min.time()))
    end_dt = start_dt + timedelta(days=7)
    return start_dt, end_dt


@login_required
def create_post(request):
    if request.method != "POST":
        return redirect("social:feed")

    today = timezone.localdate()
    already_posted_today = Post.objects.filter(author=request.user, created_at__date=today).exists()
    if already_posted_today:
        messages.error(request, "You have already created a post today. Only 1 post per day is allowed.")
        return redirect("social:feed")

    weekly_limit = getattr(getattr(request.user, "profile", None), "weekly_training_days", None)
    if not weekly_limit or weekly_limit < 1:
        messages.error(request, "Your profile training days are not set yet. Please update your profile before posting.")
        return redirect("social:feed")

    start_dt, end_dt = _week_bounds(today)
    posts_this_week = Post.objects.filter(author=request.user, created_at__gte=start_dt, created_at__lt=end_dt).count()

    if posts_this_week >= weekly_limit:
        messages.error(
            request,
            f"You have already completed your {weekly_limit} training days for this week. You can post again next week.",
        )
        return redirect("social:feed")

    form = PostForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Could not create the post. Please check the form and try again.")
        return redirect("social:feed")

    content = (form.cleaned_data.get("content") or "").strip()
    image = form.cleaned_data.get("image")

    allowed, reason = moderate_post(content, image)
    if not allowed:
        messages.error(request, f"Post blocked: {reason}")
        return redirect("social:feed")

    post = form.save(commit=False)
    post.author = request.user
    post.save()

    remaining = weekly_limit - (posts_this_week + 1)
    if remaining > 0:
        messages.success(request, f"Post created successfully. Training days remaining this week: {remaining}.")
    else:
        messages.success(request, "Post created successfully. You completed your training days for this week!")

    return redirect("social:feed")


@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if post.author != request.user:
        return HttpResponseForbidden("You can only edit your own posts.")

    if not post.can_edit(request.user):
        return HttpResponseForbidden("You can only edit posts within 24 hours.")

    if request.method == "POST":
        form = PostEditForm(request.POST, request.FILES, instance=post)
        if not form.is_valid():
            messages.error(request, "Could not update the post. Please check the form and try again.")
            return redirect("posts:edit_post", post_id=post.id)

        content = (form.cleaned_data.get("content") or "").strip()
        image = form.cleaned_data.get("image")  # puede venir None si no cambian imagen

        allowed, reason = moderate_post(content, image)
        if not allowed:
            messages.error(request, f"Post blocked: {reason}")
            return redirect("posts:edit_post", post_id=post.id)

        form.save()
        messages.success(request, "Post updated successfully.")
        return redirect("social:feed")

    form = PostEditForm(instance=post)
    return render(request, "posts/edit_post.html", {"form": form, "post": post})