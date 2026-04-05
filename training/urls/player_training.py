from django.urls import path

from training.views.player_training import PlayerSessionStatusAPIView, PlayerTrainingDayAPIView

urlpatterns = [
    path("player/training/day/", PlayerTrainingDayAPIView.as_view()),
    path("player/training/sessions/<uuid:session_id>/status/", PlayerSessionStatusAPIView.as_view()),
]
