def build_media_value_url(file_field):
    if not file_field:
        return None

    raw_name = getattr(file_field, "name", "") or ""
    if raw_name.startswith(("http://", "https://", "/")):
        return raw_name

    return file_field.url

