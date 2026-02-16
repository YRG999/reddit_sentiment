# credentials.py
# Resolves environment variables, with support for 1Password op:// references.
# Usage:
#   from credentials import get_secret
#   value = get_secret("OPENAI_API_KEY")

import os
import subprocess

from dotenv import load_dotenv

load_dotenv()


def get_secret(key: str, default: str | None = None) -> str | None:
    """Get an environment variable, resolving 1Password op:// references if needed."""
    value = os.getenv(key, default)
    if value and value.startswith("op://"):
        try:
            result = subprocess.run(
                ["op", "read", value],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except FileNotFoundError:
            raise RuntimeError(
                f"1Password CLI (op) not found. Install it to resolve {key}, "
                "or set the environment variable directly."
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                f"Failed to resolve 1Password reference for {key}: {exc.stderr.strip()}"
            )
    return value
