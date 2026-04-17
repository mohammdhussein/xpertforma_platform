from django.urls import path

from accounts.views.player_dashboard import PlayerDashboardAPIView
from accounts.views.player_profile import PlayerProfileAPIView
from training.views.player_session_status import PlayerSessionStatusAPIView
from training.views.player_training_day import PlayerTrainingDayAPIView

urlpatterns = [
    path("player/dashboard/", PlayerDashboardAPIView.as_view(), name="player-dashboard"),
    path("player/profile/", PlayerProfileAPIView.as_view(), name="player-profile"),
    path("player/training/day/", PlayerTrainingDayAPIView.as_view(), name="player-training-day"),
    path("player/training/sessions/<uuid:session_id>/status/", PlayerSessionStatusAPIView.as_view(), name="player-session-status"),
]
