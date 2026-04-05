from django.urls import path

from ..views.auth import CompleteSetPasswordAPIView, CoachRegisterAPIView, LoginAPIView, LogoutAPIView, RefreshAPIView

urlpatterns = [
    path("login/", LoginAPIView.as_view(), name="login"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("refresh/", RefreshAPIView.as_view(), name="refresh"),
    path("complete-set-password/", CompleteSetPasswordAPIView.as_view(), name="complete-set-password"),
    path("register/coach/", CoachRegisterAPIView.as_view()),
]
