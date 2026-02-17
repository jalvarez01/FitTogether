from django.urls import path
from . import views
from .views import register_view

app_name = "users"

urlpatterns = [
    path("profile/", views.profile_view, name="profile"),
    path("register/", register_view, name="register"),
]