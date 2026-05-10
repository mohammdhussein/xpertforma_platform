from django.conf import settings


class GeminiServiceUnavailable(Exception):
    pass


class GeminiClient:
    def __init__(self):
        if not getattr(settings, "GEMINI_API_KEY", None):
            raise GeminiServiceUnavailable("GEMINI_API_KEY is missing")

        try:
            from google import genai
        except ImportError as exc:
            raise GeminiServiceUnavailable("google-genai is not installed") from exc

        self._types = self._load_types()
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        try:
            return self._generate(settings.GEMINI_MODEL, system_prompt, user_prompt)
        except Exception:
            try:
                return self._generate(settings.GEMINI_FALLBACK_MODEL, system_prompt, user_prompt)
            except Exception as exc:
                raise GeminiServiceUnavailable(str(exc)) from exc

    def _generate(self, model: str, system_prompt: str, user_prompt: str) -> str:
        response = self.client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=self._types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=getattr(settings, "AI_RESPONSE_TEMPERATURE", 0),
                response_mime_type="application/json",
            ),
        )
        return response.text or ""

    @staticmethod
    def _load_types():
        try:
            from google.genai import types
        except ImportError as exc:
            raise GeminiServiceUnavailable("google-genai is not installed") from exc
        return types
