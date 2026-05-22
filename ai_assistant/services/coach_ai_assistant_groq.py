from django.conf import settings


class GroqConfigurationError(Exception):
    pass


class GroqServiceUnavailable(Exception):
    pass


class GroqTimeout(Exception):
    pass


class GroqChatClient:
    def __init__(self):
        self.api_key = getattr(settings, "GROQ_API_KEY", "")
        self.base_url = getattr(settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1")
        self.model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")
        self.fallback_model = getattr(settings, "GROQ_FALLBACK_MODEL", "openai/gpt-oss-20b")

    def chat_json(self, *, system_prompt, user_prompt):
        return self._chat(system_prompt=system_prompt, user_prompt=user_prompt, json_response=True)

    def chat_text(self, *, system_prompt, user_prompt):
        return self._chat(system_prompt=system_prompt, user_prompt=user_prompt, json_response=False)

    def _chat(self, *, system_prompt, user_prompt, json_response):
        self._ensure_config()

        try:
            from openai import APITimeoutError, OpenAI, OpenAIError
        except ImportError as exc:
            raise GroqServiceUnavailable("OpenAI client dependency is not installed.") from exc

        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        models = [self.model]
        if self.fallback_model and self.fallback_model != self.model:
            models.append(self.fallback_model)

        last_error = None
        json_modes = [True, False] if json_response else [False]
        for model in models:
            for use_response_format in json_modes:
                try:
                    return self._create_completion(
                        client=client,
                        model=model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        use_response_format=use_response_format,
                    )
                except APITimeoutError as exc:
                    last_error = exc
                except OpenAIError as exc:
                    last_error = exc
                    continue

        if last_error and last_error.__class__.__name__ == "APITimeoutError":
            raise GroqTimeout("Groq request timed out.") from last_error
        raise GroqServiceUnavailable(_safe_error_message(last_error)) from last_error

    def _create_completion(self, *, client, model, system_prompt, user_prompt, use_response_format):
        request_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": getattr(settings, "AI_RESPONSE_TEMPERATURE", 0.2),
            "seed": getattr(settings, "AI_RANDOM_SEED", 7),
            "timeout": 30,
        }
        if use_response_format:
            request_kwargs["response_format"] = {"type": "json_object"}

        completion = client.chat.completions.create(**request_kwargs)
        return completion.choices[0].message.content or ""

    def _ensure_config(self):
        if not self.api_key:
            raise GroqConfigurationError("Missing GROQ_API_KEY.")


def _safe_error_message(error):
    if error is None:
        return "Groq service is unavailable."
    status_code = getattr(error, "status_code", None)
    if status_code:
        return f"Groq service is unavailable. Provider status: {status_code}."
    return "Groq service is unavailable."
