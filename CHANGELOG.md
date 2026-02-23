# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.1] - 2026-02-23

### Changed

- Added documentation links to `config.yaml` model entries (OpenAI, Anthropic, Ollama).

### Removed

- Deleted outdated `README-summarize.md` and `README_old.md`.

## [1.4.0] - 2026-02-17

### Changed

- Replaced all `input()`/`print()` calls in `subreddit_summary.py` with `click.prompt`, `click.confirm`, and `click.echo` for consistent CLI behavior and graceful Ctrl+C handling.
- `SUBREDDIT` argument is now optional — prompts interactively via `click.prompt` when omitted.
- Replaced `pytz` with the standard library `zoneinfo` module in `subreddit_summary.py`.
- All file timestamps now consistently use Eastern time (previously the filename timestamp used naive local time while the summary header used Eastern).
- Refactored API dispatch from `if/elif/else` chain to a dict-based `_summarize()` helper. Unknown API choices now raise `KeyError` instead of falling through silently.
- Separated error handling in `run_summary()` into distinct try/except blocks for content fetching (catches `ConnectionError` specifically) and summarization, replacing the single broad `except Exception`.
- `validate_subreddit()` return value is now assigned back, so future normalization (e.g., lowercasing) will take effect.
- Eliminated mutual recursion between `confirm_hours()` and `prompt_for_hours()` — consolidated into a single iterative loop.

## [1.3.0] - 2026-02-17

### Added

- Input validation for subreddit names, rejecting path traversal characters and enforcing Reddit's alphanumeric/underscore naming rules.
- Confirmation prompt when `--hours` exceeds 120, preventing accidental high API usage.
- File-based logging to `logs/subreddit_summary.log` with full tracebacks on errors. User-facing error messages no longer expose internal details.

## [1.2.0] - 2026-02-16

### Added

- OpenAI [Flex processing](https://developers.openai.com/api/docs/guides/flex-processing) support via `openai.service_tier` in `config.yaml`. Set to `"flex"` for batch-rate pricing on non-urgent workloads.

## [1.1.0] - 2026-02-16

### Added

- `config.yaml` configuration file for setting OpenAI, Claude, and Ollama model names in one place instead of scattering them across code and environment variables.
- `config.py` loader with built-in defaults when `config.yaml` is absent.
- `pyyaml` dependency in `requirements.txt`.

### Changed

- `summarize_claude_openai.py` and `subreddit_summary.py` now read model names from `config.yaml` (with environment variable overrides still supported).
- Claude model is no longer hardcoded; stored as `self.claude_model` on `RedditSummarizer`, consistent with OpenAI and Ollama.

## [1.0.0] - 2026-02-16

### Added

- `subreddit_summary.py` CLI tool using `click` with positional subreddit argument, `--hours`, `--api`, `--topics` flags, and interactive fallbacks, inspired by [Reddit (read only - no auth)](https://clawhub.ai/buksan1950/reddit-readonly).
- `credentials.py` module with `get_secret()` helper that resolves 1Password `op://` references via the `op` CLI.
- `CHANGELOG.md` following Keep a Changelog format.

### Changed

- Rewrote `README.md`: added Quick Start guide for `subreddit_summary.py`, Prerequisites section, 1Password configuration docs, and consolidated tool reference with removed absolute paths.
- All credential loading across the project now uses `get_secret()` from `credentials.py` instead of `os.getenv()` with `load_dotenv()`, adding 1Password support to `summarize_claude_openai.py`, `summarize.py`, `summarize_openai.py`, `comments.py`, `posts.py`, `sentiment.py`, and `reddit_streamer/src/streamer.py`.
- `.env.example` updated to use 1Password `op://` reference format.

### Fixed

- "Olloma" typo renamed to "Ollama" in method name, error messages, and caller sites across `summarize_claude_openai.py` and `subreddit_summary.py`.

## [0.10.0] - 2025-12-09

### Added

- `followup.py` for follow-up Q&A on saved summaries using OpenAI.

### Changed

- Comprehensive README rewrite with full documentation for every tool.
- Optimized `posts.py`, `sentiment.py`, `summarize.py`, `summarize_claude_openai.py`, and `summarize_openai.py`.
- Removed unused import from `summarize.py`.

## [0.9.0] - 2025-08-04

### Added

- `README-summarize.md` with Ollama-specific guide.

### Changed

- Optimized `summarize_claude_openai.py` and `summarize_with_ollama.py`.

## [0.8.0] - 2025-07-14

### Added

- Ollama as third LLM backend in `summarize_claude_openai.py`.
- `summarize_with_ollama.py` standalone Ollama summarizer.
- `clean_text.py` text cleaning utility.
- `reddit_streamer/` real-time comment streaming tool with its own README and requirements.

## [0.7.0] - 2025-03-19

### Added

- `summarize_claude_openai.py` with multi-API support (OpenAI and Claude).
- `summarize_openai.py` standalone OpenAI summarizer.

## [0.6.0] - 2025-01-21

### Added

- `summarize.py` for summarizing Reddit posts and comments using OpenAI GPT.

### Changed

- Updated `comments.py` with expanded menu-driven CLI.
- Updated `requirements.txt` with summarization dependencies (`openai`, `tiktoken`, `nltk`).

## [0.5.0] - 2025-01-04

### Changed

- Renamed `reddit_comments.py` to `comments.py`.
- Renamed `reddit_posts.py` to `posts.py`.
- Renamed `reddit_sentiment.py` to `sentiment.py`.

## [0.4.0] - 2024-09-06

### Added

- `comments.py` (originally `reddit_comments.py`) with menu-driven CLI for streaming and searching Reddit comments.

## [0.3.0] - 2024-08-03

### Added

- `posts.py` (originally `reddit_posts.py`) for scraping posts within a time window.
- `.env.example` with Reddit API credential template.

## [0.2.0] - 2024-07-07

### Added

- Sort posts by "new" or "hot" in sentiment analysis.

### Changed

- Optimized sentiment analysis code.

## [0.1.0] - 2024-07-07

### Added

- Initial release with `sentiment.py` (originally `reddit_sentiment.py`) for Reddit sentiment analysis using TextBlob.
- `.gitignore` and `requirements.txt`.
- `README.md` with setup instructions.
