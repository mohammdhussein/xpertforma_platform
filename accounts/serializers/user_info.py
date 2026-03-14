from rest_framework import serializers


class UserInfoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()

    coach = serializers.DictField(allow_null=True)
    player = serializers.DictField(allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        role = data.get("role")
        if role == "Player":
            data.pop("coach", None)
        elif role == "Coach":
            data.pop("player", None)
        return data