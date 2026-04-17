def normalize_api_value(value, *, default=""):
    if value is None:
        return default

    normalized = str(value).strip()
    if not normalized:
        return default

    return normalized.replace("-", "_").replace(" ", "_").upper()
