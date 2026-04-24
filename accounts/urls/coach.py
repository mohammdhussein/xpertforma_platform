from django.urls import include, path
from rest_framework.routers import DefaultRouter

from accounts.views.coach_dashboard import CoachDashboardAPIView
from accounts.views.coach_player_creation import CoachCreatePlayerAPIView
from accounts.views.coach_players import CoachPlayerProfileAPIView, CoachPlayersListAPIView
from accounts.views.coach_player_state import CoachPlayerStateAPIView
from training.views.coach_session_lifecycle import (
    CoachSessionEndAPIView,
    CoachSessionStartAPIView,
)
from training.views.coach_training_plans import CoachTrainingPlanViewSet

router = DefaultRouter()
router.register(r"coach/plans", CoachTrainingPlanViewSet, basename="coach-plans")

urlpatterns = [
    path("coach/dashboard/", CoachDashboardAPIView.as_view(), name="coach-dashboard"),
    path("coach/create-player/", CoachCreatePlayerAPIView.as_view(), name="coach-create-player"),
    path("coach/players/", CoachPlayersListAPIView.as_view(), name="coach-players-list"),
    path("coach/players/<uuid:player_id>/", CoachPlayerProfileAPIView.as_view(), name="coach-player-detail"),
    path("coach/players/<uuid:player_id>/state/", CoachPlayerStateAPIView.as_view(), name="coach-player-state"),
    path(
        "coach/plans/<uuid:plan_id>/sessions/<uuid:session_id>/start/",
        CoachSessionStartAPIView.as_view(),
        name="coach-session-start",
    ),
    path(
        "coach/plans/<uuid:plan_id>/sessions/<uuid:session_id>/end/",
        CoachSessionEndAPIView.as_view(),
        name="coach-session-end",
    ),
    path("", include(router.urls)),
]
