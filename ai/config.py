import os

from config.environment import BASE_DIR  # Load .env for standalone CLI use too.

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")

MODEL_NAME = os.environ.get("OLLAMA_MODEL", "qwen3:0.6b")

TEMPERATURE = float(os.environ.get("OLLAMA_TEMPERATURE", "0.2"))

MAX_TOKENS = int(os.environ.get("OLLAMA_MAX_TOKENS", "2000"))
if not 0 <= TEMPERATURE <= 2 or MAX_TOKENS < 1:
    raise ValueError("OLLAMA_TEMPERATURE must be 0–2 and OLLAMA_MAX_TOKENS must be positive")
