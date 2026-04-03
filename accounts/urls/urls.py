from django.urls import path
from accounts.views.positions import PositionListAPIView
from accounts.views.user_info import UserInfoAPIView

urlpatterns = [
    path("positions/", PositionListAPIView.as_view(), name="positions-list"),
    path("user-info/", UserInfoAPIView.as_view(), name="user-info"),
]
