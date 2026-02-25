from rest_framework import serializers
from django.db import transaction
from accounts.models import User, Role, UserRole, PlayerProfile


class CoachCreatePlayerSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    temp_password = serializers.CharField(min_length=8, required=False)
    position = serializers.CharField(required=False)

    @transaction.atomic
    def create(self, validated, coach_user):
        player_role, _ = Role.objects.get_or_create(role_name="Player")
        pwd = validated.get("temp_password") or "Player12345!"
        position = validated.get("position")

        user = User.objects.create(name=validated["name"], email=validated["email"])
        user.set_password(pwd)
        user.save()

        UserRole.objects.get_or_create(user=user, role=player_role)
        PlayerProfile.objects.create(user=user, coach=coach_user, position=position)

        return user, pwd, position


class PlayerCardSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    position = serializers.CharField(allow_blank=True)
    state = serializers.CharField()  # active / needs_review / injured
    plan_chips = serializers.ListField(child=serializers.CharField())
    more_plans_count = serializers.IntegerField()


class PlayerListResponseSerializer(serializers.Serializer):
    counts = serializers.DictField(child=serializers.IntegerField())
    results = PlayerCardSerializer(many=True)
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()


class PlanProgressSerializer(serializers.Serializer):
    plan_id = serializers.UUIDField()
    title = serializers.CharField()
    started_at = serializers.DateField()
    status = serializers.CharField()  # active / completed
    overall_progress_percent = serializers.IntegerField()
    completed_sessions = serializers.IntegerField()
    remaining_sessions = serializers.IntegerField()


class PlayerHeaderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    age = serializers.IntegerField(allow_null=True)
    position = serializers.CharField(allow_blank=True)


class PlayerTrainingProgressResponseSerializer(serializers.Serializer):
    player = PlayerHeaderSerializer()
    plans = PlanProgressSerializer(many=True)
