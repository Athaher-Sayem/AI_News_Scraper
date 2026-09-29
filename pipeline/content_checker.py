def check_content(news):
    values = {}
    for field, label in (
        ("title", "title"),
        ("content", "content"),
        ("url", "URL"),
        ("source", "source"),
    ):
        value = news.get(field)
        # CSV text must be present; None/NaN must not become the strings
        # "None"/"nan" and pass the required-field checks.
        if not isinstance(value, str) or not value.strip():
            return False, f"Missing {label}"
        values[field] = value.strip()

    if len(values["content"]) < 200:
        return False, "Content too short"

    return True, "OK"
