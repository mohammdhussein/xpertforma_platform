from rest_framework import serializers

class UserInfoSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()
    roles = serializers.ListField(child=serializers.CharField())
    primary_role = serializers.CharField()

    coach = serializers.DictField(allow_null=True)
    player = serializers.DictField(allow_null=True)