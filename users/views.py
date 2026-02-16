"""
Responsabilidades:

- Registro de usuario
- Crear/editar perfil
- Ver perfil
- Autenticación (login/logout)
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def profile_view(request):
    return render(request, "users/profile.html")
