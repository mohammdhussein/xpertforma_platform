from django.urls import path
from accounts.views.coach_dashboard import CoachDashboardAPIView

urlpatterns = [
    path("coach/dashboard/", CoachDashboardAPIView.as_view(), name="coach-dashboard"),
]
