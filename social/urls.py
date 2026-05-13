from django.urls import path
from . import views

app_name = "social"

urlpatterns = [
    path("", views.feed_view, name="feed"),
    path("search/", views.search_users, name="search"),
    path("follow/<int:user_id>/", views.toggle_follow, name="toggle_follow"),
    path("like/<int:post_id>/", views.toggle_like, name="toggle_like"),
    path("profile/<str:username>/", views.user_profile, name="user_profile"),
    path("friend-requests/", views.friend_requests, name="friend_requests"),
    path("accept-request/<int:request_id>/", views.accept_friend_request, name="accept_friend_request"),
    path("reject-request/<int:request_id>/", views.reject_friend_request, name="reject_friend_request"),
    path("remove-friend/<int:friend_id>/", views.remove_friend, name="remove_friend"),
    path("comment/<int:post_id>/", views.add_comment, name="add_comment"),  # 👈 NUEVA
    path('messages/', views.messages_inbox, name='messages_inbox'),
    path('messages/<str:username>/', views.conversation_view, name='conversation'),
    path('messages/<str:username>/send/', views.send_message, name='send_message'),
    path('messages/<str:username>/fetch/', views.fetch_messages, name='fetch_messages'),
]