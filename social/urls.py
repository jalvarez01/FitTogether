from django.urls import path
from . import views

app_name = "social"

urlpatterns = [
    path("", views.feed_view, name="feed"),
]