# subreddit_summary.py
# CLI tool that fetches recent posts/comments from a subreddit and generates a summary using OpenAI, Claude, or Ollama.
# Usage:
#   1. Configure API keys (.env) for Reddit + desired model provider(s).
#   2. Run: python subreddit_summary.py <subreddit> [--hours N] [--api openai|claude|ollama] [--topics "a,b"]
#   3. Summary saves to output/<subreddit>/; use --print to also echo to terminal.

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from summarize_claude_openai import RedditSummarizer, save_summary_to_file

logger = logging.getLogger(__name__)

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


def run_summary(
    subreddit: str,
    hours: int,
    api_choice: str,
    topics: List[str],
    clean_text: bool,
    save_files: bool,
    save_raw: bool,
    print_output: bool = False,
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

    if print_output:
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
        saved = save_summary_to_file(
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
@click.option("--print", "-p", "print_output", is_flag=True, default=False, help="Print summary to terminal.")
def main(subreddit, hours, api, topics, no_clean, no_save, no_raw, print_output):
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
        print_output=print_output,
    )


if __name__ == "__main__":
    main()
