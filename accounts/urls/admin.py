from django.urls import path

from accounts.views.admin_coach_approval import ApproveCoachAPIView, PendingCoachesAPIView, RejectCoachAPIView

urlpatterns = [
    path("admin/coaches/pending/", PendingCoachesAPIView.as_view(), name="admin-coaches-pending"),
    path("admin/coaches/<uuid:coach_id>/approve/", ApproveCoachAPIView.as_view(), name="admin-coach-approve"),
    path("admin/coaches/<uuid:coach_id>/reject/", RejectCoachAPIView.as_view(), name="admin-coach-reject"),
]
