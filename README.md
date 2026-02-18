# Reddit Sentiment

A collection of standalone Python tools for fetching, summarizing, and analyzing Reddit data using OpenAI, Claude, or Ollama.

## Quick Start

### 1. Install and configure

```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your credentials (see Configuration)
```

### 2. Summarize a subreddit

```bash
python subreddit_summary.py technology --hours 24 --api openai
```

This fetches recent posts and comments from r/technology, sends them to OpenAI for summarization, prints the result, and saves it to `output/technology/`.

You can also omit any or all arguments and answer interactively:

```bash
python subreddit_summary.py technology
# or fully interactive:
python subreddit_summary.py
```

### 3. Ask follow-up questions

```bash
python followup.py
```

Select a previously saved summary or raw data file and ask questions about it.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Tools](#tools)
  - [`subreddit_summary.py` -- CLI summarizer (recommended)](#subreddit_summarypy----cli-summarizer-recommended)
  - [`summarize.py` -- OpenAI summarizer](#summarizepy----openai-summarizer)
  - [`followup.py` -- follow-up Q&A](#followuppy----follow-up-qa)
  - [`summarize_claude_openai.py` -- multi-API summarizer](#summarize_claude_openaipy----multi-api-summarizer)
  - [`summarize_with_ollama.py` -- Ollama-only summarizer](#summarize_with_ollamapy----ollama-only-summarizer)
  - [`summarize_openai.py` -- legacy OpenAI summarizer](#summarize_openaipy----legacy-openai-summarizer)
  - [`clean_text.py` -- text cleaning helper](#clean_textpy----text-cleaning-helper)
  - [`sentiment.py` -- sentiment analysis](#sentimentpy----sentiment-analysis)
  - [`comments.py` -- comment/search utility](#commentspy----commentsearch-utility)
  - [`posts.py` -- post scraper](#postspy----post-scraper)
  - [`reddit_streamer` -- real-time streamer](#reddit_streamer----real-time-streamer)
- [Project Layout](#project-layout)

---

## Prerequisites

- **Python 3.10+**
- **Reddit API credentials** -- create an app at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps) to get a client ID and secret.
- **At least one LLM provider** (for summarization):
  - [OpenAI API key](https://platform.openai.com/api-keys)
  - [Anthropic API key](https://console.anthropic.com/) (optional, for Claude)
  - [Ollama](https://ollama.com/) running locally (optional)

---

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
```

On Windows:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration

Copy the example and fill in your credentials:

```bash
cp .env.example .env
```

### Model configuration (`config.yaml`)

LLM model names are configured in `config.yaml`:

```yaml
models:
  openai: gpt-4o
  claude: claude-sonnet-4-5-20250929
  ollama: gemma3:12b

openai:
  service_tier: flex  # "flex" for batch-rate pricing, "auto" for default

ollama:
  url: http://localhost:11434/api/chat
```

Edit this file to change which models are used for summarization. Environment variables (`OPENAI_SUMMARY_MODEL`, `OLLAMA_MODEL`, `OLLAMA_URL`) override `config.yaml` when set.

Setting `openai.service_tier` to `"flex"` enables [Flex processing](https://developers.openai.com/api/docs/guides/flex-processing), which prices tokens at batch API rates. Responses may be slower and can return 429 during high demand. Remove the key or set it to `"auto"` for default processing.

### Standard `.env`

API keys and Reddit credentials go in `.env`:

```env
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=script:myapp:v1.0 (by /u/yourusername)

OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key   # optional, for Claude
```

### 1Password integration

If you use [1Password CLI](https://developer.1password.com/docs/cli/), you can use `op://` secret references in `.env`:

```env
REDDIT_CLIENT_ID=op://Private/REDDIT_CLIENT_ID/credential
REDDIT_CLIENT_SECRET=op://Private/REDDIT_CLIENT_SECRET/credential
REDDIT_USER_AGENT=op://Private/REDDIT_USER_AGENT/credential
OPENAI_API_KEY=op://Private/OPENAI_API_KEY/credential
```

All scripts use `credentials.py` which automatically detects `op://` references and resolves them via `op read`. Make sure the `op` CLI is installed and you are signed in.

---

## Tools

### `subreddit_summary.py` -- CLI summarizer (recommended)

The fastest way to summarize a subreddit. Uses `click` for CLI argument handling with interactive fallbacks.

```bash
# Fully specified
python subreddit_summary.py technology --hours 24 --api openai

# Prompts for hours and API choice
python subreddit_summary.py technology

# With topic filtering
python subreddit_summary.py technology --hours 12 --api claude --topics "AI,robots"

# Terminal only (skip file output)
python subreddit_summary.py singularity --hours 6 --api ollama --no-save
```

| Option | Description |
| ------------------ | --------------------------------------- |
| `SUBREDDIT` | Positional argument (prompts if omitted) |
| `--hours` / `-H` | Hours to look back (prompts if omitted; confirms if >120) |
| `--api` / `-a` | `openai`, `claude`, or `ollama` (prompts if omitted) |
| `--topics` / `-t` | Comma-separated topic filter |
| `--no-clean` | Skip NLTK text cleaning |
| `--no-save` | Skip saving output files |
| `--no-raw` | Skip saving raw data JSON |

Output is saved to `output/<subreddit>/` as `summary_<subreddit>_<timestamp>.txt` and `raw_data_<subreddit>_<timestamp>.json`.

---

### `summarize.py` -- OpenAI summarizer

Interactive summarizer using OpenAI. Supports multiple subreddits, topic filtering, text cleaning, and file saving.

```bash
python summarize.py
```

Prompts for subreddit name(s), hours, topics, cleaning, and save options.

---

### `followup.py` -- follow-up Q&A

Load a previously saved summary or raw data file and ask follow-up questions using the same OpenAI model.

```bash
python followup.py
```

1. Select a `summary_*.txt` or `raw_data_*.json` file when prompted.
2. Ask questions at the prompt. Press Enter on a blank line to exit.
3. Each Q&A session is saved to `followup_*.txt`.

---

### `summarize_claude_openai.py` -- multi-API summarizer

Interactive summarizer that lets you choose between OpenAI, Claude, and Ollama at runtime. This is also the shared library that other tools import `RedditSummarizer` from.

```bash
python summarize_claude_openai.py
```

---

### `summarize_with_ollama.py` -- Ollama-only summarizer

Simplified wrapper for Ollama summarization. Requires Ollama running locally with the configured model (default: `gemma3:12b`).

```bash
python summarize_with_ollama.py
```

See also `README-summarize.md` for Ollama-specific setup details.

---

### `summarize_openai.py` -- legacy OpenAI summarizer

Older evolution of the OpenAI summarizer (v1-v9). Superseded by `summarize.py`.

```bash
python summarize_openai.py
```

---

### `clean_text.py` -- text cleaning helper

Cleans an arbitrary text file using NLTK tokenization and stopword removal. Outputs to `<original>_cleaned.<ext>`.

```bash
python clean_text.py
```

---

### `sentiment.py` -- sentiment analysis

Analyzes sentiment polarity of posts and comments using TextBlob. Outputs two CSV files: detailed records and per-post summaries with sentiment buckets (Positive++, Positive+, Positive, Neutral, Negative, Negative-, Negative--).

```bash
python sentiment.py
```

Prompts for subreddit, number of posts, and sort method (`hot` or `new`).

---

### `comments.py` -- comment/search utility

Menu-driven CLI with 10 options for browsing Reddit: top posts, search, user karma, comment streaming (with rate limiting), and comment search. All actions are logged to a timestamped file.

```bash
python comments.py
```

---

### `posts.py` -- post scraper

Fetches recent posts from a subreddit within a time window. Optionally filters by recent comment activity. Outputs `.txt` and `.csv` files.

```bash
python posts.py
```

---

### `reddit_streamer` -- real-time streamer

Streams posts and comments from a subreddit in real time, displaying one item per second. Logs to JSON files under `reddit_streamer/src/logs/`.

```bash
cd reddit_streamer
pip install -r requirements.txt
python src/streamer.py
```

See `reddit_streamer/README.md` for details.

---

## Project Layout

```text
.
├── subreddit_summary.py            # CLI summarizer (recommended entry point)
├── summarize.py                    # OpenAI summarizer
├── followup.py                     # Follow-up Q&A on saved summaries
├── summarize_claude_openai.py      # Multi-API summarizer (shared RedditSummarizer class)
├── summarize_with_ollama.py        # Ollama-only summarizer
├── summarize_openai.py             # Legacy OpenAI summarizer
├── config.yaml                     # Model configuration (OpenAI, Claude, Ollama)
├── config.py                       # Config loader with defaults
├── credentials.py                  # Credential loader with 1Password op:// support
├── clean_text.py                   # Text cleaning utility
├── sentiment.py                    # Sentiment analysis
├── comments.py                     # Comment/search menu UI
├── posts.py                        # Post scraper
├── reddit_streamer/
│   ├── src/streamer.py             # Real-time post/comment streamer
│   └── README.md
├── output/                         # Generated summaries and data (gitignored)
├── logs/                           # Application logs (gitignored)
├── .env.example                    # Environment variable template
├── requirements.txt                # Python dependencies
├── CHANGELOG.md                    # Version history
├── README-summarize.md             # Ollama summarizer guide
└── README_old.md                   # Original setup notes
```
