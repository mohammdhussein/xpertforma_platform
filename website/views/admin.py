from urllib.parse import quote

from django.conf import settings
from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from accounts.models import CoachProfile
from website.selectors.admin_panel import (
    build_admin_coaches_payload,
    build_admin_dashboard_payload,
    build_admin_players_payload,
    build_coach_requests_panel_payload,
    toggle_coach_active_status,
)
from website.serializers.admin_panel import (
    AdminCoachDirectoryResponseSerializer,
    AdminCoachToggleActionSerializer,
    AdminPlayerDirectoryResponseSerializer,
    CoachRequestPanelResponseSerializer,
)
from website.forms import StaffLoginForm


def _build_panel_payload():
    return CoachRequestPanelResponseSerializer(build_coach_requests_panel_payload()).data


def _build_forgot_password_href():
    support_email = (
        getattr(settings, "ADMIN_SUPPORT_EMAIL", "")
        or getattr(settings, "EMAIL_HOST_USER", "")
        or getattr(settings, "DEFAULT_FROM_EMAIL", "")
    )
    support_email = (support_email or "").strip()
    if not support_email:
        return ""
    subject = quote("XpertForma Admin Password Reset")
    return f"mailto:{support_email}?subject={subject}"


def _build_admin_nav(current_key):
    return [
        {
            "label": "Management",
            "items": [
                {"key": "dashboard", "label": "Users", "href": reverse("staff-dashboard"), "icon": "users"},
                {"key": "coaches", "label": "Coaches", "href": reverse("staff-coaches"), "icon": "briefcase"},
                {"key": "players", "label": "Players", "href": reverse("staff-players"), "icon": "activity"},
            ],
        },
        {
            "label": "Monitoring",
            "items": [
                {
                    "key": "coach_requests",
                    "label": "Coach Requests",
                    "href": reverse("staff-coach-requests"),
                    "icon": "clipboard",
                },
            ],
        },
    ], current_key


class StaffAccessMixin(AccessMixin):
    login_url = reverse_lazy("staff-login")

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_staff:
            raise PermissionDenied("Admin access is required.")
        return super().dispatch(request, *args, **kwargs)


class StaffLoginView(LoginView):
    template_name = "website/admin/login.html"
    authentication_form = StaffLoginForm
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["forgot_password_href"] = _build_forgot_password_href()
        return context

    def get_success_url(self):
        return self.get_redirect_url() or reverse("staff-dashboard")


class StaffLogoutView(LogoutView):
    next_page = reverse_lazy("staff-login")


class AdminPageMixin(StaffAccessMixin):
    template_name = ""
    current_admin_page = ""
    page_title = ""
    page_subtitle = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        nav_items, current_page = _build_admin_nav(self.current_admin_page)
        context.update(
            {
                "admin_nav_items": nav_items,
                "current_admin_page": current_page,
                "page_title": self.page_title,
                "page_subtitle": self.page_subtitle,
            }
        )
        return context


class DashboardPageView(AdminPageMixin, TemplateView):
    template_name = "website/admin/dashboard.html"
    current_admin_page = "dashboard"
    page_title = "User Management"
    page_subtitle = "Manage platform admins, coaches, and player access."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["dashboard_data"] = build_admin_dashboard_payload()
        return context


class CoachRequestsPageView(AdminPageMixin, TemplateView):
    template_name = "website/admin/coach_requests.html"
    current_admin_page = "coach_requests"
    page_title = "Coach Requests"
    page_subtitle = "Review and manage coach signup requests."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["panel_data"] = _build_panel_payload()
        context["panel_config"] = {
            "dataUrl": reverse("staff-coach-requests-data"),
            "approveUrlTemplate": reverse(
                "admin-coach-approve",
                kwargs={"coach_id": "00000000-0000-0000-0000-000000000000"},
            ),
            "rejectUrlTemplate": reverse(
                "admin-coach-reject",
                kwargs={"coach_id": "00000000-0000-0000-0000-000000000000"},
            ),
            "pollIntervalMs": 5000,
        }
        return context


class CoachRequestsDataView(StaffAccessMixin, View):
    def get(self, request, *args, **kwargs):
        return JsonResponse(_build_panel_payload())


class CoachesPageView(AdminPageMixin, TemplateView):
    template_name = "website/admin/coaches.html"
    current_admin_page = "coaches"
    page_title = "Coaches"
    page_subtitle = "Manage coach accounts, approval state, and platform access."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_config"] = {
            "kind": "coaches",
            "dataUrl": reverse("staff-coaches-data"),
            "toggleUrlTemplate": reverse(
                "staff-coach-toggle-active",
                kwargs={"coach_id": "00000000-0000-0000-0000-000000000000"},
            ),
        }
        return context


class CoachesDataView(StaffAccessMixin, View):
    def get(self, request, *args, **kwargs):
        payload = AdminCoachDirectoryResponseSerializer(build_admin_coaches_payload()).data
        return JsonResponse(payload)


class ToggleCoachActiveView(StaffAccessMixin, View):
    def post(self, request, coach_id, *args, **kwargs):
        coach_profile = get_object_or_404(CoachProfile.objects.select_related("user"), user_id=coach_id)
        payload = AdminCoachToggleActionSerializer(toggle_coach_active_status(coach_profile)).data
        return JsonResponse(payload)


class PlayersPageView(AdminPageMixin, TemplateView):
    template_name = "website/admin/players.html"
    current_admin_page = "players"
    page_title = "Players"
    page_subtitle = "Track player accounts, onboarding status, and coach assignments."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_config"] = {
            "kind": "players",
            "dataUrl": reverse("staff-players-data"),
        }
        return context


class PlayersDataView(StaffAccessMixin, View):
    def get(self, request, *args, **kwargs):
        payload = AdminPlayerDirectoryResponseSerializer(build_admin_players_payload()).data
        return JsonResponse(payload)
