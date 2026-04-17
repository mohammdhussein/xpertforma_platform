from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from accounts.permissions import IsApprovedCoach
from accounts.serializers.coach_players import CoachCreatePlayerSerializer
from accounts.services.password_setup import (
    build_password_setup_deep_link,
    create_password_setup_token,
    send_password_setup_email,
)


class CoachCreatePlayerAPIView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedCoach]

    def post(self, request):
        s = CoachCreatePlayerSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user, position_payload, created, password_setup_required = s.create(
            s.validated_data,
            coach_user=request.user,
        )

        setup_password_link = ""
        setup_expires_at = None
        invitation_sent = False

        if password_setup_required:
            token_record, raw_token = create_password_setup_token(user)
            setup_password_link = build_password_setup_deep_link(raw_token)
            setup_expires_at = token_record.expires_at

            try:
                invitation_sent = send_password_setup_email(user, raw_token)
            except Exception:
                invitation_sent = False

        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK

        return Response({
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "position": position_payload,
            "created": created,
            "password_setup_required": password_setup_required,
            "setup_password": (
                {
                    "deep_link": setup_password_link,
                    "expires_at": setup_expires_at,
                }
                if password_setup_required
                else None
            ),
            "invitation_sent": invitation_sent
        }, status=response_status)
