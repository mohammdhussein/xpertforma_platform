from rest_framework import serializers

from accounts.files import build_media_value_url
from accounts.models import PlayerProfile, Position
from accounts.serializers.position import PositionSummarySerializer, build_position_payload


def build_player_profile_payload(player_profile):
    return {
        "id": player_profile.user_id,
        "name": player_profile.user.name,
        "email": player_profile.user.email,
        "login_status": player_profile.login_status,
        "position": build_position_payload(player_profile.position),
        "team_id": str(player_profile.team_id) if getattr(player_profile, "team_id", None) else None,
        "avatar_url": build_media_value_url(player_profile.avatar),
        "height_cm": player_profile.height_cm,
        "weight_kg": player_profile.weight_kg,
        "age": player_profile.age,
        "phone": player_profile.phone,
        "foot": player_profile.foot,
        "state": player_profile.state,
        "fitness_level": player_profile.fitness_level,
    }


class PlayerProfileDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    login_status = serializers.CharField()
    position = PositionSummarySerializer()
    team_id = serializers.CharField(allow_null=True)
    avatar_url = serializers.CharField(allow_null=True)
    height_cm = serializers.FloatField(allow_null=True)
    weight_kg = serializers.FloatField(allow_null=True)
    age = serializers.IntegerField(allow_null=True)
    phone = serializers.CharField(allow_blank=True, allow_null=True)
    foot = serializers.CharField(allow_null=True)
    state = serializers.CharField()
    fitness_level = serializers.CharField(allow_blank=True)


class PlayerProfileUpdateSerializer(serializers.Serializer):
    position_id = serializers.PrimaryKeyRelatedField(
        source="position",
        queryset=Position.objects.all(),
        required=False,
        allow_null=True,
    )
    height_cm = serializers.FloatField(required=False, allow_null=True, min_value=0)
    weight_kg = serializers.FloatField(required=False, allow_null=True, min_value=0)
    age = serializers.IntegerField(required=False, allow_null=True, min_value=0, max_value=32767)
    phone = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=32)
    foot = serializers.ChoiceField(choices=PlayerProfile.FOOT_CHOICES, required=False, allow_null=True)
    state = serializers.ChoiceField(choices=PlayerProfile.STATE_CHOICES, required=False)
    fitness_level = serializers.CharField(required=False, allow_blank=True, max_length=40)

    def update(self, instance, validated_data):
        update_fields = []

        for field_name in ("position", "height_cm", "weight_kg", "age", "phone", "foot", "state", "fitness_level"):
            if field_name in validated_data:
                setattr(instance, field_name, validated_data[field_name])
                update_fields.append(field_name)

        if instance.login_status != "complete":
            instance.login_status = "complete"
            update_fields.append("login_status")

        if update_fields:
            instance.save(update_fields=update_fields)

        return instance
