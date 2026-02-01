from django.urls import path
from training.views_player import PlayerMyPlansAPIView, PlayerMySessionsAPIView

urlpatterns = [
    path("player/plans/", PlayerMyPlansAPIView.as_view(), name="player-my-plans"),
    path("player/sessions/", PlayerMySessionsAPIView.as_view(), name="player-my-sessions"),
]
