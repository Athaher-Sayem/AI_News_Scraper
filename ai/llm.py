import requests

from .config import (
    OLLAMA_URL,
    MODEL_NAME,
    TEMPERATURE,
    MAX_TOKENS,
)


class LLMResponseError(requests.RequestException):
    """A successful HTTP response did not contain usable generated text."""


def generate_text(prompt):

    data = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE,
            "num_predict": MAX_TOKENS,
        }
    }

    response = requests.post(
        OLLAMA_URL,
        json=data,
        timeout=300
    )

    response.raise_for_status()

    try:
        result = response.json()
    except ValueError as error:
        raise LLMResponseError("Generation service returned invalid JSON") from error
    if not isinstance(result, dict) or result.get("error"):
        raise LLMResponseError("Generation service returned an error or invalid payload")
    text = result.get("response")
    if not isinstance(text, str) or not text.strip():
        raise LLMResponseError("Generation service returned no text response")
    if result.get("done") is False or result.get("done_reason") == "length":
        raise LLMResponseError("Generation service returned an incomplete response")
    return text
