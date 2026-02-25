from rest_framework import serializers
from django.db import transaction
from accounts.models import User, Role, UserRole, CoachProfile
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


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
        data = super().validate(attrs)  # authenticates user/password and builds tokens
        user = self.user

        # If this user is a coach, require approval before allowing login
        if hasattr(user, "coach_profile"):
            status = user.coach_profile.approval_status
            if status != "approved":
                # you can customize messages per status
                if status == "pending":
                    raise serializers.ValidationError("Coach account is pending admin approval.")
                if status == "rejected":
                    reason = user.coach_profile.rejection_reason or "Your application was rejected."
                    raise serializers.ValidationError(f"Coach account rejected: {reason}")
                raise serializers.ValidationError("Coach account is not approved.")

        # IMPORTANT: return tokens only (no user info)
        return data
