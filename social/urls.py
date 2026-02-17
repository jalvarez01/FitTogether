
from django.urls import path
from . import views

app_name = "social"

urlpatterns = [
    path("", views.feed_view, name="feed"),
    path("search/", views.search_users, name="search"),
    path("follow/<int:user_id>/", views.toggle_follow, name="toggle_follow"),
    path("like/<int:post_id>/", views.toggle_like, name="toggle_like"),
    path("profile/<str:username>/", views.user_profile, name="user_profile"),
]