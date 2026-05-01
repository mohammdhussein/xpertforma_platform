from django.urls import path

from accounts.views.player_profile import PlayerProfileAPIView
from training.views.player_home import PlayerHomeAPIView
from training.views.player_checkin import SubmitCheckinAPIView, TodayCheckinStatusAPIView
from training.views.player_performance import PlayerPerformanceAPIView
from training.views.player_training import PlayerTrainingAPIView
from training.views.player_sessions_count import PlayerSessionsCountAPIView

urlpatterns = [
    path("player/home/", PlayerHomeAPIView.as_view(), name="player-overview"),
    path("player/performance/", PlayerPerformanceAPIView.as_view(), name="player-performance"),
    path("player/profile/", PlayerProfileAPIView.as_view(), name="player-profile"),
    path("player/training/", PlayerTrainingAPIView.as_view(), name="player-training"),
    path("player/sessions/count/", PlayerSessionsCountAPIView.as_view(), name="player-sessions-count"),
    path("player/checkins/today/status/", TodayCheckinStatusAPIView.as_view(), name="player-checkin-today-status"),
    path("player/checkins/", SubmitCheckinAPIView.as_view(), name="player-checkin-today"),
]
