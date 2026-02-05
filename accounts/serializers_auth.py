from rest_framework import serializers
from django.db import transaction
from accounts.models import User, Role, UserRole, CoachProfile, PlayerProfile

class CoachRegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    certification_level = serializers.CharField(max_length=80, required=False, allow_blank=True)
    years_experience = serializers.IntegerField(required=False, default=0)

    @transaction.atomic
    def create(self, validated_data):
        coach_role, _ = Role.objects.get_or_create(role_name="Coach")

        user = User.objects.create(
            name=validated_data["name"],
            email=validated_data["email"],
        )
        user.set_password(validated_data["password"])
        user.save()

        UserRole.objects.get_or_create(user=user, role=coach_role)
        CoachProfile.objects.create(
            user=user,
            certification_level=validated_data.get("certification_level", ""),
            years_experience=validated_data.get("years_experience", 0),
        )
        return user


class PlayerCreateByCoachSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    temp_password = serializers.CharField(min_length=8, write_only=True, required=False)
    position = serializers.CharField(max_length=40, required=False, allow_blank=True)

    @transaction.atomic
    def create(self, validated_data, coach_user):
        player_role, _ = Role.objects.get_or_create(role_name="Player")

        password = validated_data.get("temp_password") or "Player12345!"  # default for demo

        user = User.objects.create(
            name=validated_data["name"],
            email=validated_data["email"],
        )
        user.set_password(password)
        user.save()

        UserRole.objects.get_or_create(user=user, role=player_role)

        # link player to coach (1:N)
        PlayerProfile.objects.create(
            user=user,
            coach=coach_user,
            position=validated_data.get("position", ""),
        )

        return user, password
