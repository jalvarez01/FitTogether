"""
Responsabilidades:

- Crear publicación
- Validar restricción diaria
- Ver detalle de post
"""
from django.shortcuts import render
from datetime import date

def can_post_today(user):
    profile = user.profile

    # ejemplo simple: permitir postear los primeros N días de la semana
    weekday = date.today().weekday()  # 0=Monday, 6=Sunday

    if weekday >= profile.weekly_training_days:
        return False

    return True