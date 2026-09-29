from core import views
from django.urls import path
from rest_framework_simplejwt.views import TokenBlacklistView, TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("healthz/", views.healthcheck),
    path("api/auth/register/", views.register),
    path("api/auth/login/", TokenObtainPairView.as_view()),
    path("api/auth/refresh/", TokenRefreshView.as_view()),
    path("api/auth/logout/", TokenBlacklistView.as_view()),
    path("api/today/", views.today),
    path("api/actions/", views.actions),
    path("api/habits/", views.Habits.as_view()),
    path("api/habits/<int:pk>/", views.HabitDetail.as_view()),
    path("api/health/sync/", views.health),
    path("api/profile/", views.profile),
    path("api/account/", views.account),
    path("api/pet/generations/", views.generations),
    path("api/sessions/<int:pk>/", views.cancel_session),
]
from core import ai_views

urlpatterns += [
    path("api/pet/chat/", ai_views.chat),
    path("api/memories/", ai_views.memories),
    path("api/memories/<int:pk>/", ai_views.memory_detail),
    path("api/diary/", ai_views.diary),
    path("api/reminders/", ai_views.reminders),
    path("api/reminders/<int:pk>/ack/", ai_views.acknowledge),
]
urlpatterns += [path("api/devices/", views.devices)]
