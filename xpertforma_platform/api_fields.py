from rest_framework import serializers

from xpertforma_platform.api_values import normalize_api_value


class UppercaseTokenField(serializers.CharField):
    def to_representation(self, value):
        if value is None:
            return None
        rendered = super().to_representation(value)
        return normalize_api_value(rendered, default=rendered)
