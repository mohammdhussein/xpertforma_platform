from django.urls import path
from training.views_player_training import PlayerTrainingDayAPIView, PlayerSessionStatusAPIView

urlpatterns = [
    path("player/training/day/", PlayerTrainingDayAPIView.as_view()),
    path("player/training/sessions/<uuid:session_id>/status/", PlayerSessionStatusAPIView.as_view()),
]
