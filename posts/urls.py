from django.urls import path
from . import views

app_name = "posts"

urlpatterns = [
    path("create/", views.create_post, name="create_post"),
    path("post/<int:post_id>/edit/", views.edit_post, name="edit_post"),
]