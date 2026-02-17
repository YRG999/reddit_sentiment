# subreddit_summary.py
# CLI tool that fetches recent posts/comments from a subreddit and generates a summary using OpenAI, Claude, or Ollama.
# Usage:
#   1. Configure API keys (.env) for Reddit + desired model provider(s).
#   2. Run: python subreddit_summary.py <subreddit> [--hours N] [--api openai|claude|ollama] [--topics "a,b"]
#   3. Summary prints to terminal and saves to output/<subreddit>/.

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import pytz

from summarize_claude_openai import RedditSummarizer


def prompt_for_hours() -> int:
    while True:
        try:
            value = int(input("Enter number of hours to analyze: "))
            if value > 0:
                return value
            print("Enter a positive number.")
        except ValueError:
            print("Please enter a valid number.")


def prompt_for_api() -> str:
    mapping = {"1": "openai", "2": "claude", "3": "ollama"}
    while True:
        choice = input("Choose API for summarization (1=OpenAI, 2=Claude, 3=Ollama): ").strip()
        if choice in mapping:
            return mapping[choice]
        print("Please enter 1, 2, or 3.")


def save_to_output_dir(
    subreddit: str,
    summary: str,
    analysis_params: Dict[str, Any],
    content: Optional[Dict[str, Any]] = None,
) -> List[str]:
    eastern_tz = pytz.timezone("America/New_York")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

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
        now_eastern = datetime.now(eastern_tz)
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

    print(f"\nAnalyzing r/{subreddit}...")
    try:
        content = summarizer.get_recent_content(subreddit, hours, clean=clean_text)

        if topics:
            content = summarizer.filter_content_by_topics(content, topics)
            print(
                f"Found {len(content['posts'])} posts and {len(content['comments'])} comments "
                f"matching topics: {', '.join(topics)}"
            )
        else:
            print(f"Found {len(content['posts'])} posts and {len(content['comments'])} comments")

        if not content["posts"] and not content["comments"]:
            print(f"No content found in r/{subreddit}")
            return

        api_label = api_choice.capitalize()
        print(f"\nGenerating summary with {api_label}...")

        if api_choice == "openai":
            summary, references = summarizer.summarize_with_openai(content, subreddit)
            formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
            model_used = summarizer.openai_model
        elif api_choice == "claude":
            formatted_summary = summarizer.summarize_with_claude(content, subreddit)
            model_used = summarizer.claude_model
        else:
            summary, references = summarizer.summarize_with_ollama(content, subreddit)
            formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
            model_used = summarizer.ollama_model

        print("\nSUMMARY:")
        print(formatted_summary)

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
            print("\nFiles saved:")
            for filepath in saved:
                print(f"- {filepath}")

        print("\n" + "=" * 50 + "\n")

    except Exception as exc:
        print(f"Error processing r/{subreddit}: {exc}")


@click.command()
@click.argument("subreddit")
@click.option("--hours", "-H", type=int, default=None, help="Hours to look back (prompts if omitted).")
@click.option(
    "--api",
    "-a",
    type=click.Choice(["openai", "claude", "ollama"], case_sensitive=False),
    default=None,
    help="LLM API to use (prompts if omitted).",
)
@click.option("--topics", "-t", default=None, help="Comma-separated topics to filter by.")
@click.option("--no-clean", is_flag=True, default=False, help="Skip NLTK text cleaning.")
@click.option("--no-save", is_flag=True, default=False, help="Skip saving output files.")
@click.option("--no-raw", is_flag=True, default=False, help="Skip saving raw data JSON.")
def main(subreddit, hours, api, topics, no_clean, no_save, no_raw):
    if hours is None:
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
