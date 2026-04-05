from django.urls import path

from accounts.views.coach_players import CoachPlayerTrainingProgressAPIView, CoachPlayersListAPIView

urlpatterns = [
    path("coach/players/", CoachPlayersListAPIView.as_view()),
    path("coach/players/<uuid:player_id>/", CoachPlayerTrainingProgressAPIView.as_view()),
]

