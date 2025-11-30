# followup.py
# Loads a previously saved Reddit summary or raw_data file and lets you ask follow-up
# questions using the same OpenAI model configuration as summarize.py.
# Usage:
#   1. First run summarize.py to create summary_*.txt and/or raw_data_*.json files.
#   2. Run: python followup.py
#   3. Select a session file when prompted.
#   4. Enter follow-up questions; press Enter on a blank line to exit.
#   5. Each follow-up Q&A is saved as followup_*.txt in the current directory.

#!/usr/bin/env python3

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

from summarize import RedditSummarizer  # reuse client/model setup from summarize.py


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


def load_context_from_file(filename):
    """
    Load context from either:
    - raw_data_<subreddit>_<timestamp>.json  (has full content)
    - summary_<subreddit>_<timestamp>.txt   (summary only; minimal context)
    """
    if filename.startswith("raw_data_") and filename.endswith(".json"):
        with open(filename, "r", encoding="utf-8") as f:
            content = json.load(f)
        # Try to infer subreddit from filename: raw_data_<subreddit>_<timestamp>.json
        parts = filename[len("raw_data_") : -len(".json")].split("_")
        subreddit = "_".join(parts[:-1]) if len(parts) > 1 else "unknown"
        return {
            "subreddit": subreddit,
            "content": content,
            "formatted_summary": None,
            "source_file": filename,
        }

    if filename.startswith("summary_") and filename.endswith(".txt"):
        with open(filename, "r", encoding="utf-8") as f:
            summary_text = f.read()
        parts = filename[len("summary_") : -len(".txt")].split("_")
        subreddit = "_".join(parts[:-1]) if len(parts) > 1 else "unknown"
        return {
            "subreddit": subreddit,
            "content": None,
            "formatted_summary": summary_text,
            "source_file": filename,
        }

    raise ValueError(f"Unsupported session file type: {filename}")


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
        # Keep raw context compact to avoid huge prompts
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


def ask_followup(
    openai_client: OpenAI,
    model: str,
    prompt: str,
) -> str:
    """Send the follow-up prompt to OpenAI."""
    resp = openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a concise, accurate assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    content = resp.choices[0].message.content
    return content if content is not None else ""


def save_followup_to_file(
    subreddit: str,
    source_file: str,
    question: str,
    answer: str,
) -> str:
    """
    Save a follow-up Q&A to a timestamped text file, similar in spirit
    to save_summary_to_file in summarize.py.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"followup_{subreddit}_{timestamp}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write("FOLLOW-UP METADATA:\n")
        f.write(f"Subreddit: {subreddit}\n")
        f.write(f"Source session file: {source_file}\n")
        f.write(f"Follow-up asked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
        f.write("\n" + "=" * 50 + "\n\n")
        f.write("QUESTION:\n")
        f.write(question.strip() + "\n\n")
        f.write("ANSWER:\n")
        f.write(answer.strip() + "\n")

    return filename


def main():
    # Reuse environment loading and client config from summarize.py via RedditSummarizer
    load_dotenv()
    base_summarizer = RedditSummarizer()
    openai_client = base_summarizer.client
    model_name = base_summarizer.model_name  # single source of truth

    filename = choose_session_file()
    if not filename:
        print("No file selected. Exiting.")
        return

    context = load_context_from_file(filename)
    subreddit = context.get("subreddit", "unknown")
    print(f"Loaded context from: {filename}")
    print(f"Subreddit (inferred): {subreddit}")

    print("\nYou can now ask follow-up questions about this analysis.")
    print("Press Enter on an empty line to exit.\n")

    while True:
        question = input("Follow-up question (blank line to exit): ").strip()
        if not question:
            print("Exiting follow-up session.")
            break

        prompt = build_followup_prompt(context, question)
        print("\nThinking...\n")
        answer = ask_followup(openai_client, model_name, prompt)

        print("ANSWER:")
        print(answer)
        print("\n" + "=" * 50 + "\n")

        try:
            saved_file = save_followup_to_file(
                subreddit=subreddit,
                source_file=context.get("source_file", filename),
                question=question,
                answer=answer,
            )
            print(f"Follow-up saved to: {saved_file}\n")
        except Exception as e:
            print(f"Warning: could not save follow-up to file: {e}\n")


if __name__ == "__main__":
    main()
