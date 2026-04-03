import datetime

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
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

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    @transaction.atomic
    def create(self, validated):
        coach_role, _ = Role.objects.get_or_create(role_name="Coach")
        user = User.objects.create_user(
            name=validated["name"],
            email=validated["email"],
            password=validated["password"],
        )

        UserRole.objects.get_or_create(user=user, role=coach_role)

        CoachProfile.objects.create(
            user=user,
            certificate_image=validated["certificate_image"],
            approval_status="PENDING"
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
        now = timezone.now()
        if user.last_login_at != now:
            user.last_login_at = now
            user.last_seen_at = now
            user.save(update_fields=["last_login_at", "last_seen_at"])

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


class PlayerSetPasswordSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        try:
            user_id = urlsafe_base64_decode(attrs["uid"]).decode()
            user = User.objects.get(pk=user_id)
        except Exception as exc:
            raise serializers.ValidationError({"uid": "Invalid user reference."}) from exc

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "Invalid or expired token."})

        validate_password(attrs["password"], user=user)
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password"])

        if hasattr(user, "player_profile"):
            user.player_profile.login_status = "complete"
            user.player_profile.save(update_fields=["login_status"])

        return user


def build_player_setup_token(user):
    return {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    }
