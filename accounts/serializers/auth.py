import datetime

from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import User, Role, UserRole, CoachProfile


def _access_expires_at(access_token_str):
    exp = AccessToken(access_token_str)["exp"]
    dt = datetime.datetime.fromtimestamp(exp, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class CoachRegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    certificate_image = serializers.ImageField()

    @transaction.atomic
    def create(self, validated):
        coach_role, _ = Role.objects.get_or_create(role_name="Coach")

        user = User.objects.create(name=validated["name"], email=validated["email"])
        user.set_password(validated["password"])
        user.save()

        UserRole.objects.get_or_create(user=user, role=coach_role)

        CoachProfile.objects.create(
            user=user,
            certificate_image=validated["certificate_image"],
            approval_status="pending"
        )
        return user


class LoginTokenOnlySerializer(TokenObtainPairSerializer):
    """
    Returns ONLY tokens (access/refresh),
    but blocks coach accounts that are not approved.
    """

    def validate(self, attrs):
        """
        Always return JWT tokens on valid credentials and include
        role-specific status information for coaches/players.
        """
        data = super().validate(attrs)  # authenticates user/password and builds tokens
        user = self.user

        # Determine user roles (e.g. Coach, Player)
        role_names = set(
            user.user_roles.values_list("role__role_name", flat=True)
        )
        is_coach = "Coach" in role_names
        is_player = "Player" in role_names

        # Coach status block
        if is_coach and hasattr(user, "coach_profile"):
            coach_profile = user.coach_profile
            register_status = (coach_profile.approval_status or "").upper()
            if register_status == "PENDING" or register_status == "REJECTED":
                raise serializers.ValidationError({"register_status": "PENDING"})

            data["coach_status"] = {
                "register_status": register_status,
            }

        # Player status block
        if is_player and hasattr(user, "player_profile"):
            player_profile = user.player_profile
            has_coach = bool(player_profile.coach_id)

            raw_login_status = player_profile.login_status or "first_login"
            # API-friendly value: "first-login" or "complete"
            if raw_login_status == "first_login":
                login_status = "first-login"
            else:
                login_status = raw_login_status

            data["player_status"] = {
                "has_coach": has_coach,
                "login_status": login_status,
            }

        data["access_expires_at"] = _access_expires_at(data["access"])
        return data


class RefreshTokenSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["access_expires_at"] = _access_expires_at(data["access"])
        return data
