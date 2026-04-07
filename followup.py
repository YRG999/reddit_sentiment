#!/usr/bin/env python3

import os
import json
import click
from datetime import datetime

from summarize_claude_openai import RedditSummarizer


def list_session_files():
    """List available summary/raw_data files in the current directory."""
    files = [f for f in os.listdir(".") if f.startswith(("summary_", "raw_data_"))]
    files.sort()
    return files


def choose_session_file():
    """Prompt user to pick a session file."""
    files = list_session_files()
    if not files:
        print("No summary/raw_data files found in current directory.")
        return None

    print("Available session files:")
    for i, fname in enumerate(files, 1):
        print(f"{i}. {fname}")

    while True:
        choice = input("Select a file by number (or press Enter to cancel): ").strip()
        if not choice:
            return None
        try:
            idx = int(choice)
            if 1 <= idx <= len(files):
                return files[idx - 1]
            print("Please enter a valid number from the list.")
        except ValueError:
            print("Please enter a valid number.")


def load_context_from_file(filepath):
    """
    Load context from either:
    - raw_data_<subreddit>_<timestamp>.json  (has full content)
    - summary_<subreddit>_<timestamp>.txt   (summary only; minimal context)
    """
    basename = os.path.basename(filepath)

    if basename.startswith("raw_data_") and basename.endswith(".json"):
        with open(filepath, "r", encoding="utf-8") as f:
            content = json.load(f)
        parts = basename[len("raw_data_") : -len(".json")].split("_")
        subreddit = "_".join(parts[:-1]) if len(parts) > 1 else "unknown"
        return {
            "subreddit": subreddit,
            "content": content,
            "formatted_summary": None,
            "source_file": filepath,
        }

    if basename.startswith("summary_") and basename.endswith(".txt"):
        with open(filepath, "r", encoding="utf-8") as f:
            summary_text = f.read()
        parts = basename[len("summary_") : -len(".txt")].split("_")
        subreddit = "_".join(parts[:-1]) if len(parts) > 1 else "unknown"
        return {
            "subreddit": subreddit,
            "content": None,
            "formatted_summary": summary_text,
            "source_file": filepath,
        }

    raise ValueError(f"Unsupported session file type: {basename}")


def build_followup_prompt(context, question):
    """
    Build a prompt for follow-up questions using whatever context we have
    (summary, raw content, or both).
    """
    subreddit = context.get("subreddit", "unknown")
    summary = context.get("formatted_summary")
    content = context.get("content")

    base = [
        f"You are a helpful assistant answering follow-up questions about Reddit discussions from r/{subreddit}.",
        "You may be given:",
        "- A previously generated summary (with references), and/or",
        "- Raw posts/comments data.",
        "",
        "Use the provided information to answer the user's follow-up question accurately.",
        "",
    ]

    if summary:
        base.append("=== PREVIOUS SUMMARY ===")
        base.append(summary.strip())
        base.append("=== END SUMMARY ===")
        base.append("")

    if content:
        base.append("=== RAW CONTENT (TRUNCATED) ===")
        posts = content.get("posts", [])[:10]
        comments = content.get("comments", [])[:20]

        base.append("POSTS:")
        for i, p in enumerate(posts, 1):
            base.append(
                f"- Post {i}: title='{p.get('title', '')[:120]}' "
                f"content='{p.get('content', '')[:200]}' url={p.get('url', '')}"
            )

        base.append("")
        base.append("COMMENTS (sample):")
        for i, c in enumerate(comments, 1):
            base.append(
                f"- Comment {i}: body='{c.get('body', '')[:200]}' url={c.get('url', '')}"
            )

        base.append("=== END RAW CONTENT ===")
        base.append("")

    base.append("Now answer the user's follow-up question below.")
    base.append(f"Question: {question.strip()}")
    return "\n".join(base)


def ask_followup(summarizer: RedditSummarizer, api: str, prompt: str) -> tuple[str, str]:
    """Send the follow-up prompt to the chosen API. Returns (answer, model_used)."""
    system = "You are a concise, accurate assistant."
    messages = [{"role": "user", "content": prompt}]

    if api == "claude":
        if not summarizer.claude_client:
            raise click.ClickException("Anthropic API key not found. Set ANTHROPIC_API_KEY in .env.")
        resp = summarizer.claude_client.messages.create(
            model=summarizer.claude_model,
            max_tokens=1024,
            system=system,
            messages=messages,
        )
        answer = resp.content[0].text if resp.content else ""
        return answer, summarizer.claude_model

    if api == "ollama":
        from ollama import chat  # type: ignore
        response = chat(
            model=summarizer.ollama_model,
            messages=[{"role": "system", "content": system}] + messages,
        )
        if isinstance(response, dict):
            answer = response.get("message", {}).get("content", "") or ""
        else:
            answer = response.message.content or ""
        return answer, summarizer.ollama_model

    # default: openai
    resp = summarizer.client.chat.completions.create(
        model=summarizer.model_name,
        messages=[{"role": "system", "content": system}] + messages,
    )
    answer = resp.choices[0].message.content or ""
    return answer, summarizer.model_name


def save_followup_to_file(
    subreddit: str,
    source_file: str,
    question: str,
    answer: str,
    api: str,
    model: str,
) -> str:
    """Save a follow-up Q&A to a timestamped text file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"followup_{subreddit}_{timestamp}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write("FOLLOW-UP METADATA:\n")
        f.write(f"Subreddit: {subreddit}\n")
        f.write(f"Source session file: {source_file}\n")
        f.write(f"API: {api} ({model})\n")
        f.write(f"Follow-up asked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
        f.write("\n" + "=" * 50 + "\n\n")
        f.write("QUESTION:\n")
        f.write(question.strip() + "\n\n")
        f.write("ANSWER:\n")
        f.write(answer.strip() + "\n")

    return filename


@click.command()
@click.argument("file", type=click.Path(exists=True, readable=True), required=False, default=None)
@click.option("--api", "-a", type=click.Choice(["openai", "claude", "ollama"]), default="openai",
              show_default=True, help="LLM backend to use for follow-up answers.")
def main(file, api):
    """Ask follow-up questions about a saved Reddit summary or raw data file.

    FILE can be a summary_*.txt or raw_data_*.json file. If omitted, prompts
    interactively to select from files in the current directory.
    """
    summarizer = RedditSummarizer()

    if file:
        filepath = file
    else:
        filepath = choose_session_file()
        if not filepath:
            click.echo("No file selected. Exiting.")
            return

    try:
        context = load_context_from_file(filepath)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="FILE")

    subreddit = context.get("subreddit", "unknown")
    click.echo(f"Loaded context from: {filepath}")
    click.echo(f"Subreddit (inferred): {subreddit}")
    click.echo(f"API: {api}")
    click.echo("\nYou can now ask follow-up questions about this analysis.")
    click.echo("Press Enter on an empty line to exit.\n")

    while True:
        question = click.prompt("Follow-up question (blank line to exit)", default="", show_default=False).strip()
        if not question:
            click.echo("Exiting follow-up session.")
            break

        prompt = build_followup_prompt(context, question)
        click.echo("\nThinking...\n")

        try:
            answer, model_used = ask_followup(summarizer, api, prompt)
        except click.ClickException:
            raise
        except Exception as e:
            click.echo(f"Error: {e}\n")
            continue

        click.echo("ANSWER:")
        click.echo(answer)
        click.echo("\n" + "=" * 50 + "\n")

        try:
            saved_file = save_followup_to_file(
                subreddit=subreddit,
                source_file=context.get("source_file", filepath),
                question=question,
                answer=answer,
                api=api,
                model=model_used,
            )
            click.echo(f"Follow-up saved to: {saved_file}\n")
        except Exception as e:
            click.echo(f"Warning: could not save follow-up to file: {e}\n")


if __name__ == "__main__":
    main()
