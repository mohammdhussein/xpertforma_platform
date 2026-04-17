from django.urls import path

from accounts.views.player_profile import PlayerProfileAPIView
from training.views.player_home import PlayerHomeAPIView
from training.views.player_checkin import SubmitCheckinAPIView, TodayCheckinStatusAPIView
from training.views.player_session_status import PlayerSessionStatusAPIView
from training.views.player_training_day import PlayerTrainingDayAPIView

urlpatterns = [
    path("player/home/", PlayerHomeAPIView.as_view(), name="player-overview"),
    path("player/profile/", PlayerProfileAPIView.as_view(), name="player-profile"),
    path("player/training/day/", PlayerTrainingDayAPIView.as_view(), name="player-training-day"),
    path("player/training/sessions/<uuid:session_id>/status/", PlayerSessionStatusAPIView.as_view(), name="player-session-status"),
    path("player/checkins/today/status/", TodayCheckinStatusAPIView.as_view(), name="player-checkin-today-status"),
    path("player/checkins/", SubmitCheckinAPIView.as_view(), name="player-checkin-submit"),
]
