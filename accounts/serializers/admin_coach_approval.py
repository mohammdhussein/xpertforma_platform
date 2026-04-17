from rest_framework import serializers

from accounts.files import build_media_value_url
from accounts.models import CoachProfile
from xpertforma_platform.api_fields import UppercaseTokenField


class PendingCoachSerializer(serializers.ModelSerializer):
    coach_id = serializers.UUIDField(source="user.id", read_only=True)
    name = serializers.CharField(source="user.name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    certificate_image = serializers.SerializerMethodField()

    class Meta:
        model = CoachProfile
        fields = ["coach_id", "name", "email", "certificate_image"]

    def get_certificate_image(self, obj):
        return build_media_value_url(obj.certificate_image)


class CoachApprovalActionSerializer(serializers.Serializer):
    coach_id = serializers.UUIDField()
    status = UppercaseTokenField()
    reason = serializers.CharField(required=False, allow_blank=True)
