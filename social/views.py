"""
Responsabilidades:

- Buscar usuarios
- Seguir/dejar de seguir
- Mostrar feed (posts de usuarios seguidos)
- Dar/quitar like
"""

from django.shortcuts import render

def feed_view(request):
    return render(request, "social/feed.html")
