from rest_framework.permissions import BasePermission

class IsPlayer(BasePermission):
    """
    Allows access only to users who have a PlayerProfile.
    (Simple + reliable in your current structure.)
    """
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return hasattr(user, "player_profile")
