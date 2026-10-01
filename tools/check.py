"""Run the same offline checks locally and in GitHub Actions."""

from pathlib import Path
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    commands = (
        ["manage.py", "check"],
        ["manage.py", "makemigrations", "--check", "--dry-run"],
        ["manage.py", "test", "--verbosity", "1"],
        ["-m", "pip", "check"],
    )
    for arguments in commands:
        print("Running:", sys.executable, *arguments, flush=True)
        result = subprocess.run([sys.executable, *arguments], cwd=root)
        if result.returncode:
            return result.returncode
    print("All offline checks passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
