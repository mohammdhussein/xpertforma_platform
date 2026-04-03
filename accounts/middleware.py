from django.core.cache import cache
from django.utils import timezone


class UpdateLastSeenMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return response

        cache_key = f"user_last_seen_update:{user.pk}"
        if cache.get(cache_key):
            return response

        now = timezone.now()
        user.last_seen_at = now
        user.save(update_fields=["last_seen_at"])
        cache.set(cache_key, True, timeout=60)
        return response
