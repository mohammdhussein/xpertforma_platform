from django.urls import include, path
from rest_framework.routers import DefaultRouter
from training.views_coach import CoachTrainingPlanViewSet

router = DefaultRouter()
router.register(r"coach/plans", CoachTrainingPlanViewSet, basename="coach-plans")

urlpatterns = [
    path("", include(router.urls)),
]
