from rest_framework.permissions import BasePermission

from accounts.statuses import is_approved_coach_approval_status


class IsCoach(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and hasattr(u, "coach_profile"))


class IsPlayer(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and hasattr(u, "player_profile"))


class IsApprovedCoach(BasePermission):
    message = "Coach account is not approved."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if not hasattr(user, "coach_profile"):
            return False
        return is_approved_coach_approval_status(user.coach_profile.approval_status)
