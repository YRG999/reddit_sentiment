# config.py
# Loads model configuration from config.yaml with sensible defaults.
# Environment variables override config.yaml values when set.

from pathlib import Path

import yaml


_DEFAULT_CONFIG = {
    "models": {
        "openai": "gpt-4o",
        "claude": "claude-sonnet-4-5-20250929",
        "ollama": "gemma3:12b",
    },
    "openai": {
        "service_tier": None,
    },
    "ollama": {
        "url": "http://localhost:11434/api/chat",
    },
}


def load_config() -> dict:
    """Load configuration from config.yaml, falling back to defaults."""
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            if config:
                return config
    return _DEFAULT_CONFIG
