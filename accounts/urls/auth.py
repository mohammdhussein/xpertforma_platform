from django.urls import path
from ..views import CoachRegisterAPIView
from ..views.auth import LoginAPIView, LogoutAPIView, PlayerSetPasswordAPIView, RefreshAPIView

urlpatterns = [
    path("login/", LoginAPIView.as_view(), name="login"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("refresh/", RefreshAPIView.as_view(), name="refresh"),
    path("player/set-password/", PlayerSetPasswordAPIView.as_view(), name="player-set-password"),
    path("register/coach/", CoachRegisterAPIView.as_view()),
]
