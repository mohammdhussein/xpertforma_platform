from django.urls import path
from accounts.views.player_dashboard import PlayerDashboardAPIView


urlpatterns = [
    path("player/dashboard/", PlayerDashboardAPIView.as_view(), name="player-dashboard"),
]

