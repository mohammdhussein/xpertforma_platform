from django.core.cache import cache
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class BlacklistableJWTAuthentication(JWTAuthentication):
    def get_validated_token(self, raw_token):
        validated = super().get_validated_token(raw_token)
        jti = validated["jti"]
        if cache.get(f"blacklisted_jti_{jti}"):
            raise InvalidToken("Token has been invalidated.")
        return validated
