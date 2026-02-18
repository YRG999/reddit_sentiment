# subreddit_summary.py
# CLI tool that fetches recent posts/comments from a subreddit and generates a summary using OpenAI, Claude, or Ollama.
# Usage:
#   1. Configure API keys (.env) for Reddit + desired model provider(s).
#   2. Run: python subreddit_summary.py <subreddit> [--hours N] [--api openai|claude|ollama] [--topics "a,b"]
#   3. Summary prints to terminal and saves to output/<subreddit>/.

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import click

from summarize_claude_openai import RedditSummarizer

logger = logging.getLogger(__name__)

# Eastern time is used for all timestamps — this is the preferred timezone
# for this project's output files and logs.
EASTERN_TZ = ZoneInfo("America/New_York")

MAX_HOURS_DEFAULT = 120

API_CHOICES = ["openai", "claude", "ollama"]


def validate_subreddit(subreddit: str) -> str:
    if not re.match(r"^[A-Za-z0-9_]+$", subreddit):
        raise click.BadParameter(
            "Subreddit name must contain only letters, numbers, and underscores."
        )
    return subreddit


def prompt_for_hours() -> int:
    while True:
        value = click.prompt("Enter number of hours to analyze", type=int)
        if value <= 0:
            click.echo("Enter a positive number.")
            continue
        if value > MAX_HOURS_DEFAULT:
            if not click.confirm(
                f"{value} hours exceeds {MAX_HOURS_DEFAULT}. Continue?"
            ):
                continue
        return value


def prompt_for_api() -> str:
    api_display = ", ".join(
        f"{i}={name.capitalize()}" for i, name in enumerate(API_CHOICES, 1)
    )
    mapping = {str(i): name for i, name in enumerate(API_CHOICES, 1)}
    while True:
        choice = click.prompt(f"Choose API for summarization ({api_display})")
        if choice in mapping:
            return mapping[choice]
        click.echo(f"Please enter a number from 1 to {len(API_CHOICES)}.")


def _summarize(summarizer: RedditSummarizer, api_choice: str, content, subreddit):
    """Dispatch to the appropriate summarizer and return (formatted_summary, model_used)."""
    if api_choice == "claude":
        formatted_summary = summarizer.summarize_with_claude(content, subreddit)
        return formatted_summary, summarizer.claude_model

    dispatch = {
        "openai": (summarizer.summarize_with_openai, summarizer.openai_model),
        "ollama": (summarizer.summarize_with_ollama, summarizer.ollama_model),
    }
    summarize_fn, model_used = dispatch[api_choice]
    summary, references = summarize_fn(content, subreddit)
    formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
    return formatted_summary, model_used


def save_to_output_dir(
    subreddit: str,
    summary: str,
    analysis_params: Dict[str, Any],
    content: Optional[Dict[str, Any]] = None,
) -> List[str]:
    timestamp = datetime.now(EASTERN_TZ).strftime("%Y%m%d_%H%M%S")

    output_dir = Path("output") / subreddit
    output_dir.mkdir(parents=True, exist_ok=True)

    saved_files: List[str] = []

    summary_path = output_dir / f"summary_{subreddit}_{timestamp}.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("ANALYSIS PARAMETERS:\n")
        f.write(f"Subreddit name: {analysis_params['subreddit']}\n")
        f.write(f"Hours analyzed: {analysis_params['hours']}\n")
        topics = analysis_params.get("topics") or []
        f.write(f"Topics: {', '.join(topics) if topics else 'No topic filter'}\n")
        f.write(f"Clean text content: {'Yes' if analysis_params.get('clean_text') else 'No'}\n")
        f.write(f"API used: {analysis_params.get('api_used', 'N/A')}\n")
        if analysis_params.get("model"):
            f.write(f"Model used: {analysis_params['model']}\n")
        now_eastern = datetime.now(EASTERN_TZ)
        f.write(f"Summary generated at: {now_eastern.strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
        f.write("\n" + "=" * 50 + "\n\n")
        f.write(summary)
    saved_files.append(str(summary_path))

    if content:
        raw_path = output_dir / f"raw_data_{subreddit}_{timestamp}.json"
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        saved_files.append(str(raw_path))

    return saved_files


def run_summary(
    subreddit: str,
    hours: int,
    api_choice: str,
    topics: List[str],
    clean_text: bool,
    save_files: bool,
    save_raw: bool,
) -> None:
    summarizer = RedditSummarizer()

    click.echo(f"\nAnalyzing r/{subreddit}...")
    try:
        content = summarizer.get_recent_content(subreddit, hours, clean=clean_text)
    except ConnectionError:
        logger.exception("Network error fetching r/%s", subreddit)
        click.echo(f"Network error: could not reach Reddit for r/{subreddit}. Check your connection.")
        return
    except Exception:
        logger.exception("Failed to fetch content from r/%s", subreddit)
        click.echo(f"Error fetching content from r/{subreddit}. Check logs for details.")
        return

    if topics:
        content = summarizer.filter_content_by_topics(content, topics)
        click.echo(
            f"Found {len(content['posts'])} posts and {len(content['comments'])} comments "
            f"matching topics: {', '.join(topics)}"
        )
    else:
        click.echo(f"Found {len(content['posts'])} posts and {len(content['comments'])} comments")

    if not content["posts"] and not content["comments"]:
        click.echo(f"No content found in r/{subreddit}")
        return

    api_label = api_choice.capitalize()
    click.echo(f"\nGenerating summary with {api_label}...")

    try:
        formatted_summary, model_used = _summarize(
            summarizer, api_choice, content, subreddit
        )
    except KeyError:
        click.echo(f"Unknown API choice: {api_choice}")
        return
    except Exception:
        logger.exception("Error generating summary for r/%s with %s", subreddit, api_choice)
        click.echo(f"Error generating summary with {api_label}. Check logs for details.")
        return

    click.echo("\nSUMMARY:")
    click.echo(formatted_summary)

    if save_files:
        analysis_params = {
            "subreddit": subreddit,
            "hours": hours,
            "topics": topics,
            "clean_text": clean_text,
            "api_used": api_label,
            "model": model_used,
        }
        saved = save_to_output_dir(
            subreddit,
            formatted_summary,
            analysis_params,
            content if save_raw else None,
        )
        click.echo("\nFiles saved:")
        for filepath in saved:
            click.echo(f"- {filepath}")

    click.echo("\n" + "=" * 50 + "\n")


@click.command()
@click.argument("subreddit", required=False, default=None)
@click.option("--hours", "-H", type=int, default=None, help="Hours to look back (prompts if omitted).")
@click.option(
    "--api",
    "-a",
    type=click.Choice(API_CHOICES, case_sensitive=False),
    default=None,
    help="LLM API to use (prompts if omitted).",
)
@click.option("--topics", "-t", default=None, help="Comma-separated topics to filter by.")
@click.option("--no-clean", is_flag=True, default=False, help="Skip NLTK text cleaning.")
@click.option("--no-save", is_flag=True, default=False, help="Skip saving output files.")
@click.option("--no-raw", is_flag=True, default=False, help="Skip saving raw data JSON.")
def main(subreddit, hours, api, topics, no_clean, no_save, no_raw):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        filename=log_dir / "subreddit_summary.log",
    )

    if subreddit is None:
        subreddit = click.prompt("Enter subreddit name")
    subreddit = validate_subreddit(subreddit)

    if hours is None:
        hours = prompt_for_hours()
    else:
        if hours > MAX_HOURS_DEFAULT:
            if not click.confirm(
                f"{hours} hours exceeds {MAX_HOURS_DEFAULT}. Continue?"
            ):
                hours = prompt_for_hours()
    if api is None:
        api = prompt_for_api()

    topic_list = [t.strip().lower() for t in topics.split(",") if t.strip()] if topics else []

    run_summary(
        subreddit=subreddit,
        hours=hours,
        api_choice=api.lower(),
        topics=topic_list,
        clean_text=not no_clean,
        save_files=not no_save,
        save_raw=not no_raw,
    )


if __name__ == "__main__":
    main()
