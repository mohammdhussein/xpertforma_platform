from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.serializers.position import build_position_payload
from accounts.serializers.user_info import UserInfoSerializer


ROLE_PRIORITY = ["Admin", "Manager", "Coach", "Player", "User"]


def get_user_roles(user):
    return list(
        user.user_roles.select_related("role")
        .values_list("role__role_name", flat=True)
    )


def get_primary_role(roles):
    for r in ROLE_PRIORITY:
        if r in roles:
            return r
    return roles[0] if roles else "User"


class UserInfoAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        roles = get_user_roles(user)
        primary = get_primary_role(roles)

        coach_data = None
        if hasattr(user, "coach_profile"):
            cp = user.coach_profile
            coach_data = {
                "approval_status": cp.approval_status,
                "certificate_image": cp.certificate_image.url if cp.certificate_image else None,
                "approved_at": cp.approved_at,
                "rejection_reason": cp.rejection_reason,
            }

        player_data = None
        if hasattr(user, "player_profile"):
            pp = user.player_profile
            player_data = {
                "position": build_position_payload(pp.position, pp.position_label),
                "team_id": str(pp.team_id) if getattr(pp, "team_id", None) else None,
                "height_cm": getattr(pp, "height_cm", None),
                "weight_kg": getattr(pp, "weight_kg", None),
                "avatar_url": pp.avatar.url if getattr(pp, "avatar", None) else None,
            }

        payload = {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": primary,
            "coach": coach_data,
            "player": player_data,
        }

        serializer = UserInfoSerializer(payload)
        return Response(serializer.data)
