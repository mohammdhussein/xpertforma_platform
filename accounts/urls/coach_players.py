from django.urls import path

from accounts.views.coach_players import CoachPlayerAPIView, CoachPlayersListAPIView

urlpatterns = [
    path("coach/players/", CoachPlayersListAPIView.as_view()),
    path("coach/players/<uuid:player_id>/", CoachPlayerAPIView.as_view()),
]

