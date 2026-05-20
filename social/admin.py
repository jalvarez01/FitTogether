from django.contrib import admin
from .models import Follow, Like, Comment, Notification

admin.site.register(Follow)
admin.site.register(Like)
admin.site.register(Comment)
admin.site.register(Notification)
