from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils import timezone
from django.contrib import messages

from .forms import PostForm
from .models import Post


@login_required
def create_post(request):
    if request.method != "POST":
        return redirect("social:feed")

    today = timezone.localdate()

    already_posted = Post.objects.filter(
        author=request.user,
        created_at__date=today
    ).exists()

    if already_posted:
        messages.error(request, "You have already created a post today. Only 1 post per day is allowed.")
        return redirect("social:feed")

    form = PostForm(request.POST, request.FILES)
    if form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        messages.success(request, "Post created successfully.")
    else:
        messages.error(request, "You have already created a post today. Only 1 post per day is allowed.")

    return redirect("social:feed")