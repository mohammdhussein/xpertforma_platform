import datetime

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import CoachProfile, Role, User, UserRole
from accounts.services.password_setup import (
    ExpiredPasswordSetupTokenError,
    InvalidPasswordSetupTokenError,
    PasswordSetupUserNotFoundError,
    UsedPasswordSetupTokenError,
    complete_password_setup,
    get_valid_password_setup_token,
)
from accounts.statuses import (
    PLAYER_LOGIN_STATUS_FIRST_LOGIN,
    is_pending_coach_approval_status,
    normalize_player_login_status,
    is_rejected_coach_approval_status,
    normalize_coach_approval_status,
)


def _access_expires_at(access_token_str):
    exp = AccessToken(access_token_str)["exp"]
    dt = datetime.datetime.fromtimestamp(exp, tz=datetime.timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class CoachRegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=60)
    last_name = serializers.CharField(max_length=60)
    phone_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    certificate_image = serializers.CharField(max_length=500, allow_blank=True)

    def validate_email(self, value):
        email = User.objects.normalize_email(value)
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def validate_certificate_image(self, value):
        certificate_image = (value or "").strip()
        if not certificate_image:
            raise serializers.ValidationError("Certificate image path is required.")
        return certificate_image

    def validate(self, attrs):
        first_name = (attrs.get("first_name") or "").strip()
        last_name = (attrs.get("last_name") or "").strip()
        phone_number = (attrs.get("phone_number") or "").strip()
        full_name = f"{first_name} {last_name}".strip()

        if len(full_name) > 120:
            raise serializers.ValidationError(
                {"last_name": ["Combined first_name and last_name must be 120 characters or fewer."]}
            )

        attrs["first_name"] = first_name
        attrs["last_name"] = last_name
        attrs["phone_number"] = phone_number or None
        return attrs

    @transaction.atomic
    def create(self, validated):
        coach_role, _ = Role.objects.get_or_create(role_name="Coach")
        user = User.objects.create_user(
            first_name=validated["first_name"],
            last_name=validated["last_name"],
            email=validated["email"],
            password=validated["password"],
        )

        UserRole.objects.get_or_create(user=user, role=coach_role)

        CoachProfile.objects.create(
            user=user,
            certificate_image=validated["certificate_image"],
            phone_number=validated.get("phone_number"),
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
            register_status = normalize_coach_approval_status(coach_profile.approval_status)
            if is_pending_coach_approval_status(register_status) or is_rejected_coach_approval_status(register_status):
                raise serializers.ValidationError({f"coach_status": {"register_status": f"{register_status}"}})

            data["coach_status"] = {
                "register_status": register_status,
            }

        # Player status block
        if is_player and hasattr(user, "player_profile"):
            player_profile = user.player_profile
            has_coach = bool(player_profile.coach_id)
            login_status = normalize_player_login_status(
                player_profile.login_status,
                default=PLAYER_LOGIN_STATUS_FIRST_LOGIN,
            )

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


def _password_setup_error_to_validation_error(exc):
    if isinstance(exc, InvalidPasswordSetupTokenError):
        return serializers.ValidationError({"token": str(exc)})
    if isinstance(exc, ExpiredPasswordSetupTokenError):
        return serializers.ValidationError({"token": str(exc)})
    if isinstance(exc, UsedPasswordSetupTokenError):
        return serializers.ValidationError({"token": str(exc)})
    if isinstance(exc, PasswordSetupUserNotFoundError):
        return serializers.ValidationError({"token": str(exc)})
    raise exc


class CompleteSetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        try:
            token_record = get_valid_password_setup_token(attrs["token"])
        except (
                InvalidPasswordSetupTokenError,
                ExpiredPasswordSetupTokenError,
                UsedPasswordSetupTokenError,
                PasswordSetupUserNotFoundError,
        ) as exc:
            raise _password_setup_error_to_validation_error(exc) from exc

        try:
            validate_password(attrs["password"], user=token_record.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc

        attrs["user"] = token_record.user
        return attrs

    def save(self, **kwargs):
        try:
            user, _ = complete_password_setup(
                self.validated_data["token"],
                self.validated_data["password"],
            )
        except (
                InvalidPasswordSetupTokenError,
                ExpiredPasswordSetupTokenError,
                UsedPasswordSetupTokenError,
                PasswordSetupUserNotFoundError,
        ) as exc:
            raise _password_setup_error_to_validation_error(exc) from exc
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc

        return user
