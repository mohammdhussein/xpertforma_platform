from rest_framework import serializers

from accounts.files import build_media_value_url
from accounts.models import PlayerProfile
from accounts.serializers.position import PositionSummarySerializer, build_position_payload


def is_player_profile_setup_complete(player_profile):
    return all(
        [
            player_profile.position_id is not None,
            player_profile.height_cm is not None,
            player_profile.weight_kg is not None,
            bool(player_profile.foot),
            player_profile.user.date_of_birth is not None,
            bool((player_profile.user.phone or "").strip()),
        ]
    )


def build_player_profile_payload(player_profile):
    return {
        "id": player_profile.user_id,
        "name": player_profile.user.name,
        "email": player_profile.user.email,
        "date_of_birth": player_profile.user.date_of_birth,
        "login_status": player_profile.login_status,
        "position": build_position_payload(player_profile.position),
        "team_id": str(player_profile.team_id) if getattr(player_profile, "team_id", None) else None,
        "avatar_url": build_media_value_url(player_profile.avatar),
        "height_cm": player_profile.height_cm,
        "weight_kg": player_profile.weight_kg,
        "phone": player_profile.user.phone,
        "foot": player_profile.foot,
    }


class PlayerProfileDetailSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    date_of_birth = serializers.DateField(allow_null=True)
    login_status = serializers.CharField()
    position = PositionSummarySerializer()
    team_id = serializers.CharField(allow_null=True)
    avatar_url = serializers.CharField(allow_null=True)
    height_cm = serializers.FloatField(allow_null=True)
    weight_kg = serializers.FloatField(allow_null=True)
    phone = serializers.CharField(allow_blank=True, allow_null=True)
    foot = serializers.CharField(allow_null=True)


class PlayerProfileUpdateSerializer(serializers.Serializer):
    height_cm = serializers.FloatField(required=False, allow_null=True, min_value=0)
    weight_kg = serializers.FloatField(required=False, allow_null=True, min_value=0)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    phone = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=32)
    foot = serializers.ChoiceField(choices=PlayerProfile.FOOT_CHOICES, required=False, allow_null=True)

    def validate(self, attrs):
        unknown_fields = sorted(set(self.initial_data.keys()) - set(self.fields.keys()))
        if unknown_fields:
            raise serializers.ValidationError(
                {field_name: ["This field is not allowed."] for field_name in unknown_fields}
            )
        return attrs

    def update(self, instance, validated_data):
        update_fields = []
        user_update_fields = []

        if "date_of_birth" in validated_data:
            instance.user.date_of_birth = validated_data["date_of_birth"]
            user_update_fields.append("date_of_birth")

        if "phone" in validated_data:
            instance.user.phone = validated_data["phone"]
            user_update_fields.append("phone")

        for field_name in ("height_cm", "weight_kg", "foot"):
            if field_name in validated_data:
                setattr(instance, field_name, validated_data[field_name])
                update_fields.append(field_name)

        next_login_status = "complete" if is_player_profile_setup_complete(instance) else "first_login"
        if instance.login_status != next_login_status:
            instance.login_status = next_login_status
            update_fields.append("login_status")

        if user_update_fields:
            instance.user.save(update_fields=user_update_fields)

        if update_fields:
            instance.save(update_fields=update_fields)

        return instance
