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
    "prompt": {
        "system": (
            "You are an expert analyst summarizing Reddit community discussions. "
            "Your summaries are structured, objective, and grounded in the source content."
        ),
        "user": (
            "Analyze the Reddit content from r/{subreddit} and provide a structured summary with these sections:\n\n"
            "**Themes**: Identify the 3–5 dominant topics or recurring themes in this period's posts and comments.\n\n"
            "**Sentiment**: Describe the overall emotional tone of the community — positive, negative, mixed, or neutral — and note any polarizing topics or strong reactions.\n\n"
            "**Notable Discussions**: Highlight 2–3 standout posts or comment threads, explaining why they are significant.\n\n"
            "**Other Discussions by Topic**: Summarize any secondary or miscellaneous topics that emerged but didn't fit into the main themes. Group these by topic and include brief context. If there are no outlier discussions, omit this section.\n\n"
            "**Summary**: A concise 2–3 sentence overview of what this subreddit was focused on during this period.\n\n"
            "Use numbered references [n] to cite specific posts and comments. Be objective and base everything on the provided content."
        ),
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
