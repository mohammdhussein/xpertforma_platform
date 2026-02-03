from django.urls import path
from accounts.views_auth import CoachRegisterAPIView, CoachCreatePlayerAPIView

urlpatterns = [
    path("register/coach/", CoachRegisterAPIView.as_view(), name="register-coach"),
    path("coach/create-player/", CoachCreatePlayerAPIView.as_view(), name="coach-create-player"),
]
