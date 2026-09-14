import requests

from .config import (
    OLLAMA_URL,
    MODEL_NAME,
    TEMPERATURE
)


def generate_text(prompt):

    data = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": TEMPERATURE
        }
    }

    response = requests.post(
        OLLAMA_URL,
        json=data,
        timeout=300
    )

    response.raise_for_status()

    result = response.json()

    return result["response"]