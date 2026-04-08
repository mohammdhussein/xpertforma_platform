"""
URL configuration for xpertforma_platform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from django.urls import path, include


def api_reference_view(request):
    return FileResponse(
        open(Path(settings.BASE_DIR) / "api-reference.html", "rb"),
        content_type="text/html",
    )


urlpatterns = [
    path("", include("website.urls.public")),
    path("staff/", include("website.urls.admin")),
    path("api/auth/", include("accounts.urls.auth")),
    path("api/", include("accounts.urls.admin")),
    path("api/", include("accounts.urls.coach")),
    path("api/", include("accounts.urls.coach_players")),
    path("api/", include("accounts.urls.common")),
    path("api/", include("accounts.urls.coach_dashboard")),
    path("api/", include("accounts.urls.player_dashboard")),
    path("api/", include("accounts.urls.player_profile")),
    path("api/", include("training.urls.player_training")),
    path("api/", include("training.urls.coach")),
    path("api-reference/", api_reference_view),

]
