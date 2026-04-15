from django.urls import path

from . import views
from .views import register_view

app_name = "users"

urlpatterns = [
    path("profile/", views.profile_view, name="profile"),
    path("settings/", views.settings_view, name="settings"),
    path("register/", register_view, name="register"),
    path("profile/update-bio/", views.update_bio, name="update_bio"),
    path("profile/update-banner/", views.update_banner, name="update_banner"),
    path("profile/update-avatar/", views.update_avatar, name="update_avatar"),
]