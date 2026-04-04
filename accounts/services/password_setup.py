import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.mail import send_mail
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import PasswordSetupToken


class PasswordSetupTokenError(Exception):
    default_message = "Password setup token is invalid."

    def __init__(self, message=None):
        super().__init__(message or self.default_message)


class InvalidPasswordSetupTokenError(PasswordSetupTokenError):
    default_message = "Invalid token."


class ExpiredPasswordSetupTokenError(PasswordSetupTokenError):
    default_message = "Token has expired."


class UsedPasswordSetupTokenError(PasswordSetupTokenError):
    default_message = "Token has already been used."


class PasswordSetupUserNotFoundError(PasswordSetupTokenError):
    default_message = "User not found for this token."


def _password_setup_ttl():
    return timedelta(hours=getattr(settings, "PASSWORD_SETUP_TOKEN_TTL_HOURS", 24))


def _hash_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_password_setup_token(user, *, invalidate_existing=True, expires_in=None):
    now = timezone.now()
    expires_at = now + (expires_in or _password_setup_ttl())

    with transaction.atomic():
        if invalidate_existing:
            PasswordSetupToken.objects.filter(
                user=user,
                purpose=PasswordSetupToken.PURPOSE_SET_PASSWORD,
                is_used=False,
                expires_at__gt=now,
            ).update(expires_at=now)

        for _ in range(5):
            raw_token = secrets.token_urlsafe(32)
            try:
                token_record = PasswordSetupToken.objects.create(
                    user=user,
                    token=_hash_token(raw_token),
                    purpose=PasswordSetupToken.PURPOSE_SET_PASSWORD,
                    expires_at=expires_at,
                )
                return token_record, raw_token
            except IntegrityError:
                continue

    raise RuntimeError("Unable to generate a unique password setup token.")


def build_password_setup_deep_link(raw_token):
    deep_link_base = getattr(
        settings,
        "PASSWORD_SETUP_DEEP_LINK_BASE",
        getattr(settings, "PLAYER_INVITE_DEEP_LINK_BASE", ""),
    ).rstrip("/")
    if not deep_link_base:
        return ""
    return f"{deep_link_base}?{urlencode({'token': raw_token})}"


def send_password_setup_email(user, raw_token):
    deep_link = build_password_setup_deep_link(raw_token)
    if not deep_link:
        return False

    ttl_hours = getattr(settings, "PASSWORD_SETUP_TOKEN_TTL_HOURS", 24)
    subject = "Set your XpertForma password"
    message = (
        f"Hi {user.name},\n\n"
        "You have been invited to XpertForma.\n"
        "Use the link below to set your password:\n"
        f"{deep_link}\n\n"
        f"This link expires in {ttl_hours} hours."
    )

    return bool(
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    )


def get_valid_password_setup_token(raw_token, *, for_update=False):
    if not raw_token:
        raise InvalidPasswordSetupTokenError()

    token_queryset = PasswordSetupToken.objects.select_related("user")
    if for_update:
        token_queryset = token_queryset.select_for_update()

    token_record = token_queryset.filter(token=_hash_token(raw_token)).first()
    if token_record is None:
        raise InvalidPasswordSetupTokenError()
    if token_record.purpose != PasswordSetupToken.PURPOSE_SET_PASSWORD:
        raise InvalidPasswordSetupTokenError("Invalid token purpose.")
    if token_record.is_used:
        raise UsedPasswordSetupTokenError()
    if token_record.expires_at <= timezone.now():
        raise ExpiredPasswordSetupTokenError()
    if token_record.user_id is None or token_record.user is None:
        raise PasswordSetupUserNotFoundError()

    return token_record


@transaction.atomic
def complete_password_setup(raw_token, password):
    token_record = get_valid_password_setup_token(raw_token, for_update=True)
    user = token_record.user
    if user is None:
        raise PasswordSetupUserNotFoundError()

    try:
        validate_password(password, user=user)
    except DjangoValidationError:
        raise

    user.set_password(password)
    user.save(update_fields=["password"])

    if hasattr(user, "player_profile"):
        user.player_profile.login_status = "complete"
        user.player_profile.save(update_fields=["login_status"])

    now = timezone.now()
    token_record.is_used = True
    token_record.expires_at = now
    token_record.save(update_fields=["is_used", "expires_at"])

    PasswordSetupToken.objects.filter(
        user=user,
        purpose=PasswordSetupToken.PURPOSE_SET_PASSWORD,
        is_used=False,
        expires_at__gt=now,
    ).exclude(pk=token_record.pk).update(expires_at=now)

    return user, token_record
