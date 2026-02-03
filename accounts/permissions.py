from rest_framework.permissions import BasePermission

class IsCoach(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and hasattr(u, "coach_profile"))
