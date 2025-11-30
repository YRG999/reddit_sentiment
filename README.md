# README 

This repository contains a collection of small tools for working with Reddit data:

- Fetch and summarize recent posts/comments with OpenAI, Claude, or Ollama.
- Run follow‑up questions against saved summaries.
- Perform simple sentiment analysis on posts and comments.
- Stream posts and comments in real time.
- Fetch and log posts or comments from subreddits.

The code is organized as standalone scripts so you can run only what you need.

---

## Table of Contents

- [Environment Setup](#environment-setup)
- [Project Layout](#project-layout)
- [Quick Start (Summaries + Follow‑up)](#quick-start-summaries--follow-up)
  - [1. Summarize recent Reddit activity (`summarize.py`)](#1-summarize-recent-reddit-activity-summarizepy)
  - [2. Ask follow‑up questions (`followup.py`)](#2-ask-follow-up-questions-followuppy)
- [Summarization Scripts](#summarization-scripts)
  - [`summarize.py` (OpenAI, main entry)](#summarizepy-openai-main-entry)
  - [`followup.py` (follow‑up Q&A)](#followuppy-follow-up-qa)
  - [`summarize_claude_openai.py` (OpenAI / Claude / Ollama)](#summarize_claude_openaipy-openai--claude--ollama)
  - [`summarize_with_ollama.py` (Ollama only)](#summarize_with_ollamapy-ollama-only)
  - [`summarize_openai.py` (older OpenAI-only version)](#summarize_openaipy-older-openai-only-version)
  - [`clean_text.py` (text cleaning helper)](#clean_textpy-text-cleaning-helper)
- [Other Tools](#other-tools)
  - [`sentiment.py` (sentiment analysis)](#sentimentpy-sentiment-analysis)
  - [`comments.py` (comment/search utility + menu UI)](#commentspy-commentsearch-utility--menu-ui)
  - [`posts.py` (post scraper)](#postspy-post-scraper)
  - [`reddit_streamer/src/streamer.py` (streamer)](#reddit_streamersrcstreamerpy-streamer)
- [Notes](#notes)

---

## Environment Setup

Follow these steps to set up your environment.

### 1. Create and activate a virtual environment (recommended)

```bash
python3 -m venv venv
. venv/bin/activate
```

On Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

### 2. Install dependencies

From the repo root:

```bash
pip install -r requirements.txt
```

Or upgrade to the latest versions:

```bash
pip install -U -r requirements.txt
```

### 3. Create a `.env` file

Copy `.env.example` (if present) or create `.env` in the project root and set:

```env
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=your_user_agent_string

OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key   # optional, for Claude
OLLAMA_URL=http://localhost:11434/api/chat # optional, for Ollama
OLLAMA_MODEL=gemma3:12b                    # optional, for Ollama
```

Make sure Reddit API credentials are valid and the OpenAI key has access to the model configured in the code.

---

## Project Layout

Key files and folders:

```text
.
├── summarize.py                 # Main OpenAI-based summarizer (Quick Start focus)
├── followup.py                  # Follow-up Q&A on saved summaries (Quick Start focus)
├── summarize_claude_openai.py   # Summarizer using OpenAI, Claude, or Ollama
├── summarize_with_ollama.py     # Summarizer using Ollama only
├── summarize_openai.py          # Older OpenAI-only summarizer
├── clean_text.py                # Utility to clean arbitrary text using RedditSummarizer.clean_text
├── sentiment.py                 # Sentiment analysis on posts/comments
├── comments.py                  # Menu-driven Reddit comment/search utility
├── posts.py                     # Basic post scraper (time-windowed)
├── reddit_streamer/
│   ├── src/
│   │   └── streamer.py          # Streams mixed posts/comments with logging
│   └── README.md                # Streamer-specific documentation
├── README-summarize.md          # Extra details for Ollama summarizer
├── README_old.md                # Original setup notes
└── requirements.txt
```

---

## Quick Start (Summaries + Follow‑up)

The main workflow uses:

- `summarize.py` — generate summaries and optionally save raw data.
- `followup.py` — load a saved summary/raw file and ask follow‑up questions.

### 1. Summarize recent Reddit activity (`summarize.py`)

This script:

- Pulls recent posts and comments from one or more subreddits.
- Optionally cleans text and filters by topics.
- Sends the content to **OpenAI** for summarization.
- Prints a summary with numbered footnote references.
- Optionally saves:
  - `summary_<subreddit>_<timestamp>.txt`
  - `raw_data_<subreddit>_<timestamp>.json`

Run:

```bash
python summarize.py
```

You’ll be prompted for:

- Subreddit name(s), comma‑separated (e.g., `python, learnpython`)
- Number of hours to analyze (e.g., `24`)
- Topics to filter on (optional, comma‑separated; leave blank for no filter)
- Whether to clean text content
- Whether to save summaries and raw data

Outputs (when saving is enabled) are written to the current directory.

### 2. Ask follow‑up questions (`followup.py`)

This script:

- Reuses the same **OpenAI** client and model configuration as `summarize.py`.
- Loads either a `summary_*.txt` or `raw_data_*.json` file.
- Builds a prompt that includes the previous summary and/or truncated raw content.
- Lets you ask arbitrary follow‑up questions.
- Saves each Q&A as `followup_<subreddit>_<timestamp>.txt`.

Run:

```bash
python followup.py
```

Workflow:

1. Select one of the `summary_*.txt` or `raw_data_*.json` files when prompted.
2. Ask follow‑up questions at the prompt:
   - `Follow-up question (blank line to exit):`
3. Press Enter on a blank line to exit.

Each follow‑up is logged to a new `followup_*.txt` file containing:

- Basic metadata (subreddit, source session file, timestamp)
- The question text
- The model’s answer

---

## Summarization Scripts

### `summarize.py` (OpenAI, main entry)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/summarize.py
```

Features:

- Fetches recent posts and comments for one or more subreddits.
- Optional text cleaning (NLTK `punkt` + `stopwords`).
- Optional topic filtering (basic substring match, case‑insensitive).
- Summarization via OpenAI Chat Completions using a single, central `model_name`.
- Automatic token counting and content truncation on size/rate-limit errors.
- Footnote-style references `[1]`, `[2]`, … that link back to Reddit URLs.
- File saving via `save_summary_to_file`.

How to run:

```bash
python summarize.py
```

### `followup.py` (follow‑up Q&A)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/followup.py
```

Features:

- Uses `RedditSummarizer` from `summarize.py` to share:
  - OpenAI client configuration
  - Central chat model name.
- Lets you pick an existing `summary_*.txt` or `raw_data_*.json`.
- Builds a follow‑up prompt combining:
  - The previous summary (if available).
  - A truncated view of raw posts/comments (if available).
- Sends the prompt to the same model used in `summarize.py`.
- Saves each Q&A to a `followup_*.txt` file.

How to run:

```bash
python followup.py
```

---

### `summarize_claude_openai.py` (OpenAI / Claude / Ollama)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/summarize_claude_openai.py
```

Features:

- Unified `RedditSummarizer` that can use:
  - OpenAI (`summarize_with_openai`)
  - Claude (`summarize_with_claude`)
  - Ollama (`summarize_with_ollama`)
- Topic filtering and reference footnotes.
- Similar `save_summary_to_file` behavior.
- Interactive `main()` that asks you which API to use (1=OpenAI, 2=Claude, 3=Ollama).

Run:

```bash
python summarize_claude_openai.py
```

---

### `summarize_with_ollama.py` (Ollama only)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/summarize_with_ollama.py
```

Features:

- Uses `RedditSummarizer` from `summarize_claude_openai.py`.
- Fetches recent content from a single subreddit.
- Optional topic filtering.
- Summarizes content using Ollama.
- Always saves:
  - Summary text
  - Raw data JSON

Usage (see also `README-summarize.md`):

```bash
python summarize_with_ollama.py
```

Make sure:

- Ollama is installed and running.
- The configured Ollama model (e.g., `gemma3:12b`) is available.

---

### `summarize_openai.py` (older OpenAI-only version)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/summarize_openai.py
```

This is an older evolution of the OpenAI-only summarizer (versions v1–v9). It contains similar logic to `summarize.py` (text cleaning, topic filtering, footnotes, saving to files), but `summarize.py` is the preferred and more up-to-date version.

Run:

```bash
python summarize_openai.py
```

---

### `clean_text.py` (text cleaning helper)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/clean_text.py
```

Utility script that:

- Instantiates `RedditSummarizer` from `summarize_claude_openai.py`.
- Uses its `clean_text` method to clean an arbitrary text file.
- Writes the cleaned output to `<original>_cleaned.ext`.

Run:

```bash
python clean_text.py
```

You’ll be prompted for the path to a text file.

---

## Other Tools

### `sentiment.py` (sentiment analysis)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/sentiment.py
```

Features:

- Uses `TextBlob` for sentiment polarity.
- Interprets sentiment into buckets:
  - `Positive++`, `Positive+`, `Positive`, `Neutral`, `Negative`, `Negative-`, `Negative--`.
- Logs detailed results for posts and comments to:
  - `reddit_sentiment_analysis_<subreddit>_<sort>_<timestamp>.csv`
- Logs per‑post comment sentiment summaries to:
  - `reddit_sentiment_summaries_<subreddit>_<sort>_<timestamp>.csv`
- Lets you choose:
  - Subreddit
  - Number of posts
  - Sort method (`hot` or `new`)

Run:

```bash
python sentiment.py
```

---

### `comments.py` (comment/search utility + menu UI)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/comments.py
```

Features:

- `RedditAPI` class with methods to:
  - Get top posts.
  - Search posts across Reddit or within a subreddit.
  - Get user karma.
  - Stream comments.
  - Search comments for specific words.
  - Stream formatted comments with rate limiting.
- `UserInterface` class:
  - Menu-driven CLI (choices 1–10).
  - Logs all actions and data to a timestamped log file in the working directory.
  - Consistent timestamps in Eastern Time.

Run and use the menu:

```bash
python comments.py
```

---

### `posts.py` (post scraper)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/posts.py
```

Features:

- `RedditScraper` class:
  - Fetches recent posts from a subreddit.
  - Optional inclusion of comments when determining recency.
  - Filters posts by how recent the post/comment activity is (in hours).
  - Writes output to a timestamped `.txt` file.
- Interactively asks:
  - Subreddit
  - Hours back
  - Whether to include comments.

Run:

```bash
python posts.py
```

---

### `reddit_streamer/src/streamer.py` (streamer)

Located at:

```text
/Users/dark/Repos/reddit_sentiment/reddit_streamer/src/streamer.py
```

See the dedicated streamer README:

```text
/Users/dark/Repos/reddit_sentiment/reddit_streamer/README.md
```

Features:

- Streams recent posts and comments from a subreddit.
- Mixes and sorts by time, displays one item per second.
- Logs all streamed items to a JSON file under `reddit_streamer/src/logs`.

Typical usage:

```bash
cd reddit_streamer
pip install -r requirements.txt
python src/streamer.py
```

---

## Notes

- All summarization and follow‑up scripts expect valid Reddit API credentials and, where applicable, valid OpenAI / Anthropic / Ollama configuration.
- Topic filtering in summarizers is simple substring matching; for more advanced filtering, you can extend the `filter_content_by_topics` methods.
- The repository is designed modularly so you can swap in other models or APIs with minimal changes (e.g., updating a single `model_name` in `RedditSummarizer`).
