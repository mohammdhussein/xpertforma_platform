from rest_framework.permissions import BasePermission


class IsCoach(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and hasattr(u, "coach_profile"))


class IsPlayer(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and hasattr(u, "player_profile"))


from rest_framework.permissions import BasePermission


class IsApprovedCoach(BasePermission):
    """
    Allows access only to approved coaches.
    """

    message = "Coach account is not approved."

    def has_permission(self, request, view):
        user = request.user

        # Must be logged in
        if not user or not user.is_authenticated:
            return False

        # Must have coach profile
        if not hasattr(user, "coach_profile"):
            return False

        # Must be approved
        if user.coach_profile.approval_status != "APPROVED":
            return False

        return True
