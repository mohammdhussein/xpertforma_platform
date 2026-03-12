from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
from accounts.permissions import IsCoach
from accounts.serializers.coach import CoachCreatePlayerSerializer


class CoachCreatePlayerAPIView(APIView):
    permission_classes = [IsAuthenticated, IsCoach]

    def post(self, request):
        s = CoachCreatePlayerSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user, position = s.create(s.validated_data, coach_user=request.user)

        try:
            coach_name = getattr(request.user, "name", "") or "your coach"
            from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.com")
            position_text = position or "Not specified"

            subject = "You have been invited as a player"
            message = (
                f"Hi {user.name},\n\n"
                f"You have been added as a player by {coach_name}.\n\n"
                f"Position: {position_text}\n\n"
                f"Your coach or club will share login instructions separately."
            )

            send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[user.email],
                fail_silently=True,
            )
            invitation_sent = True
        except Exception:
            invitation_sent = False

        return Response({
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "position": position,
            "invitation_sent": invitation_sent
        }, status=status.HTTP_201_CREATED)
