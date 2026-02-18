from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .models import Post
from django.shortcuts import render, redirect


@login_required
def create_post(request):
    profile = request.user.profile

    today = timezone.now().date()

    already_posted = Post.objects.filter(
        author=request.user,
        workout_date=today
    ).exists()

    if already_posted:
        return render(request, 'posts/not_allowed.html', {
            'message': "You already posted today."
        })

    if request.method == 'POST':
        content = request.POST.get('content')
        image = request.FILES.get('image')

        Post.objects.create(
            author=request.user,
            content=content,
            image=image,
            workout_date=today
        )

        return redirect('feed')

    return render(request, 'posts/create_post.html')