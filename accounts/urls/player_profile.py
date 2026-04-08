from django.urls import path

from accounts.views.player_profile import PlayerProfileAPIView


urlpatterns = [
    path("player/profile/", PlayerProfileAPIView.as_view(), name="player-profile"),
]
