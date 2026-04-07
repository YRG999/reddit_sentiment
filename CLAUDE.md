# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project Overview

A collection of standalone Python CLI tools for fetching, summarizing, and analyzing Reddit data. Tools use OpenAI, Claude (Anthropic), or Ollama as LLM backends.

## Key Files

| File | Purpose |
| ---- | ------- |
| `subreddit_summary.py` | Primary CLI — fetch and summarize a subreddit (recommended entry point) |
| `summarize_claude_openai.py` | Multi-API summarizer; also exports `RedditSummarizer` used by other tools |
| `followup.py` | Follow-up Q&A on saved summaries; supports `--api openai/claude/ollama` |
| `clean_text.py` | Standalone text-cleaning CLI (NLTK stop-word removal) |
| `sentiment.py` | Sentiment analysis via TextBlob |
| `comments.py` / `posts.py` | Comment streaming and post scraping |
| `config.yaml` | Model names for OpenAI, Claude, Ollama |
| `config.py` | Config loader with defaults |
| `credentials.py` | `get_secret()` — resolves `.env` values or 1Password `op://` references |

## Architecture Notes

- **Credentials**: Always use `get_secret()` from `credentials.py`. Never use `os.getenv()` directly. Supports both `.env` plain values and 1Password `op://` references.
- **Config**: Model names come from `config.yaml` via `config.py`. Environment variables override `config.yaml` when set.
- **CLI style**: All CLIs use `click`. Use `click.prompt`, `click.confirm`, and `click.echo`. Interactive fallbacks when arguments are omitted.
- **Output**: Summaries and raw data save to `output/<subreddit>/`. Logs go to `logs/`.
- **Token management**: `clean_text()` in `summarize_claude_openai.py` lowercases text, removes punctuation, and strips NLTK English stop words before sending to LLMs.

## Conventions

- Python 3.10+, virtual environment in `venv/`
- `requirements.txt` for dependencies — update it when adding packages
- Keep `CHANGELOG.md` updated (Keep a Changelog format, semver)
- `_notes/` holds development history and experiments — untracked, local only

## Common Commands

```bash
# Activate venv
. venv/bin/activate

# Summarize a subreddit
python subreddit_summary.py technology --hours 24 --api openai

# Clean a text file for LLM input
python clean_text.py myfile.txt | pbcopy

# Run follow-up Q&A
python followup.py
```
