from django.urls import path
from ..views.create_players import CoachCreatePlayerAPIView

urlpatterns = [
    path("coach/create-player/", CoachCreatePlayerAPIView.as_view()),
]