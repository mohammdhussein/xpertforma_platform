from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
from accounts.permissions import IsCoach
from accounts.serializers.coach import CoachCreatePlayerSerializer
from accounts.serializers.auth import build_player_setup_token


class CoachCreatePlayerAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCoach]

    def post(self, request):
        s = CoachCreatePlayerSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user, position_payload, created, password_setup_required = s.create(
            s.validated_data,
            coach_user=request.user,
        )

        setup_payload = build_player_setup_token(user)
        deep_link_base = getattr(settings, "PLAYER_INVITE_DEEP_LINK_BASE", "").rstrip("/")
        setup_password_link = ""
        if deep_link_base:
            setup_password_link = (
                f"{deep_link_base}"
                f"?uid={setup_payload['uid']}&token={setup_payload['token']}"
            )

        try:
            coach_name = getattr(request.user, "name", "") or "your coach"
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
            position_text = position_payload["name"] or "Not specified"
            email_host_user = getattr(settings, "EMAIL_HOST_USER", "")
            email_host_password = getattr(settings, "EMAIL_HOST_PASSWORD", "")

            subject = "You have been invited as a player"
            message = (
                f"Hi {user.name},\n\n"
                f"You have been added as a player by {coach_name}.\n\n"
                f"Position: {position_text}\n\n"
                f"Use this link to set your password: {setup_password_link or 'setup link unavailable'}"
            )

            if password_setup_required and email_host_user and email_host_password and setup_password_link:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=from_email,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
                invitation_sent = True
            else:
                invitation_sent = False
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
            "setup_password": {
                "uid": setup_payload["uid"],
                "token": setup_payload["token"],
                "deep_link": setup_password_link,
            },
            "invitation_sent": invitation_sent
        }, status=response_status)
