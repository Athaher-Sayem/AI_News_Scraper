import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


def load_environment(path=BASE_DIR / ".env"):
    return load_dotenv(path, override=False)


load_environment()


def env_bool(name, default=False):
    value = os.environ.get(name, str(default)).strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no"}:
        raise ValueError(f"{name} must be true/false, 1/0, or yes/no")
    return value in {"true", "1", "yes"}
