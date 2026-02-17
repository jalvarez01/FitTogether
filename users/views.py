"""
Responsabilidades:

- Registro de usuario
- Crear/editar perfil
- Ver perfil
- Autenticación (login/logout)
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.shortcuts import render, redirect
from .forms import CustomUserCreationForm

@login_required(login_url="users:register")
def profile_view(request):
    return render(request, "users/profile.html")

def register_view(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)              # auto login
            return redirect("social:feed")     # al feed
    else:
        form = CustomUserCreationForm()

    return render(request, "users/register.html", {"form": form})