from django.urls import path

from website.views.admin import (
    CoachesDataView,
    CoachesPageView,
    CoachRequestsDataView,
    CoachRequestsPageView,
    DashboardPageView,
    PlayersDataView,
    PlayersPageView,
    StaffLoginView,
    StaffLogoutView,
    ToggleCoachActiveView,
)


urlpatterns = [
    path("", DashboardPageView.as_view(), name="staff-dashboard"),
    path("dashboard/", DashboardPageView.as_view(), name="staff-dashboard-explicit"),
    path("login/", StaffLoginView.as_view(), name="staff-login"),
    path("logout/", StaffLogoutView.as_view(), name="staff-logout"),
    path("coach-requests/", CoachRequestsPageView.as_view(), name="staff-coach-requests"),
    path("coach-requests/data/", CoachRequestsDataView.as_view(), name="staff-coach-requests-data"),
    path("coaches/", CoachesPageView.as_view(), name="staff-coaches"),
    path("coaches/data/", CoachesDataView.as_view(), name="staff-coaches-data"),
    path("coaches/<uuid:coach_id>/toggle-active/", ToggleCoachActiveView.as_view(), name="staff-coach-toggle-active"),
    path("players/", PlayersPageView.as_view(), name="staff-players"),
    path("players/data/", PlayersDataView.as_view(), name="staff-players-data"),
]
