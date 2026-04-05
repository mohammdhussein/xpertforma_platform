from rest_framework import serializers

from accounts.serializers.position import PositionSummarySerializer


class CoachUserInfoSerializer(serializers.Serializer):
    approval_status = serializers.CharField()
    certificate_image = serializers.CharField(allow_null=True)
    approved_at = serializers.DateTimeField(allow_null=True)
    rejection_reason = serializers.CharField(allow_blank=True)


class PlayerUserInfoSerializer(serializers.Serializer):
    position = PositionSummarySerializer()
    team_id = serializers.CharField(allow_null=True)
    height_cm = serializers.FloatField(allow_null=True)
    weight_kg = serializers.FloatField(allow_null=True)
    avatar_url = serializers.CharField(allow_null=True)


class UserInfoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()

    coach = CoachUserInfoSerializer(allow_null=True)
    player = PlayerUserInfoSerializer(allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        role = data.get("role")
        if role == "Player":
            data.pop("coach", None)
        elif role == "Coach":
            data.pop("player", None)
        return data
