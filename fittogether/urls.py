from django.contrib import admin
from django.urls import path
from django.shortcuts import render

def home(request):
    return render(request, "home.html")

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", home, name="home"),
]
