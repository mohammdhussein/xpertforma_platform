from django.urls import path
from accounts.views_coach_players import (
    CoachPlayersListAPIView,
    CoachPlayerTrainingProgressAPIView,
)

urlpatterns = [
    path("coach/players/", CoachPlayersListAPIView.as_view()),
    path("coach/players/<uuid:player_id>/", CoachPlayerTrainingProgressAPIView.as_view()),
]
