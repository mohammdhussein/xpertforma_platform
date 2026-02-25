from django.urls import path
from ..views import CoachRegisterAPIView
from ..views.auth import LoginAPIView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("login/", LoginAPIView.as_view(), name="login"),
    path("refresh/", TokenRefreshView.as_view(), name="refresh"),
    path("refresh/", TokenRefreshView.as_view()),
    path("register/coach/", CoachRegisterAPIView.as_view()),

]
