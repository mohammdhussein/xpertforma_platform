from django.urls import path

from website.views.public import LandingPageView


urlpatterns = [
    path("", LandingPageView.as_view(), name="home"),
]
