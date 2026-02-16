# summarize_claude_openai.py
# Fetches recent posts/comments from Reddit, summarizes with OpenAI, Claude, or Ollama, and saves outputs.
# Usage:
#   1. Configure API keys (.env) for Reddit + desired model provider(s).
#   2. Run: python summarize_claude_openai.py
#   3. Choose API (1=OpenAI, 2=Claude, 3=Ollama), enter subreddits/hours/topics, and decide on saving options.

import json
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

import anthropic
import praw
import pytz
import tiktoken
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from openai import OpenAI
from anthropic.types import TextBlockParam

from credentials import get_secret

def _make_text_block(text: str) -> TextBlockParam:
    """
    Create a simple Anthropics TextBlockParam-compatible dict for use in messages.
    Returns a dict with type "text" and the provided text content.
    """
    return {"type": "text", "text": text}

class RedditSummarizer:
    def __init__(self) -> None:
        self.reddit = praw.Reddit(
            client_id=get_secret("REDDIT_CLIENT_ID"),
            client_secret=get_secret("REDDIT_CLIENT_SECRET"),
            user_agent=get_secret("REDDIT_USER_AGENT"),
        )

        openai_key = get_secret("OPENAI_API_KEY")
        self.openai_client: Optional[OpenAI] = OpenAI(api_key=openai_key) if openai_key else None
        self.openai_model = get_secret("OPENAI_SUMMARY_MODEL", "gpt-4")

        anthropic_key = get_secret("ANTHROPIC_API_KEY")
        self.claude_client: Optional[anthropic.Anthropic] = (
            anthropic.Anthropic(api_key=anthropic_key) if anthropic_key else None
        )

        self.ollama_url = get_secret("OLLAMA_URL", "http://localhost:11434/api/chat")
        self.ollama_model = get_secret("OLLAMA_MODEL", "gemma3:12b")

        self.eastern_tz = pytz.timezone("America/New_York")
        self.MAX_TOKENS = 8000

        try:
            self.tokenizer = tiktoken.encoding_for_model(self.openai_model)
        except KeyError:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        try:
            tokens = word_tokenize(text.lower())
            stop_words = set(stopwords.words("english"))
            filtered = [t for t in tokens if t not in string.punctuation and t not in stop_words]
            return " ".join(filtered)
        except Exception as exc:
            print(f"Warning: Error cleaning text: {exc}")
            return text

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))

    def _format_timestamp(self, utc_ts: float) -> str:
        dt = datetime.fromtimestamp(utc_ts, pytz.UTC)
        return dt.astimezone(self.eastern_tz).strftime("%Y-%m-%d %H:%M:%S %Z")

    def get_recent_content(
        self,
        subreddit_name: str,
        hours: int,
        clean: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        subreddit = self.reddit.subreddit(subreddit_name)
        cutoff = datetime.now(pytz.UTC) - timedelta(hours=hours)

        posts: List[Dict[str, Any]] = []
        for post in subreddit.new(limit=100):
            post_time = datetime.fromtimestamp(post.created_utc, pytz.UTC)
            if post_time < cutoff:
                break
            body = post.selftext or ""
            posts.append(
                {
                    "title": post.title or "",
                    "content": self.clean_text(body) if clean else body,
                    "raw_content": body,
                    "score": post.score,
                    "url": f"https://www.reddit.com{post.permalink}",
                    "created_utc": self._format_timestamp(post.created_utc),
                }
            )

        comments: List[Dict[str, Any]] = []
        for comment in subreddit.comments(limit=500):
            comment_time = datetime.fromtimestamp(comment.created_utc, pytz.UTC)
            if comment_time < cutoff:
                break
            body = getattr(comment, "body", "") or ""
            comments.append(
                {
                    "body": self.clean_text(body) if clean else body,
                    "raw_body": body,
                    "score": comment.score,
                    "url": f"https://www.reddit.com{comment.permalink}",
                    "created_utc": self._format_timestamp(comment.created_utc),
                }
            )

        return {"posts": posts, "comments": comments}

    def prepare_summary_prompt(
        self,
        content: Dict[str, List[Dict[str, Any]]],
        subreddit_name: str,
        content_limit: Optional[int] = None,
    ) -> Tuple[str, List[str]]:
        references: List[str] = []
        parts: List[str] = [
            f"Summarize the following content from r/{subreddit_name}.",
            "Include key themes, notable discussions, and overall sentiment.",
            "Use numbered references [n].",
            "",
            "POSTS:",
        ]

        ref_counter = 1
        for post in content.get("posts", []):
            references.append(post.get("url", ""))
            body = post.get("content", "")
            snippet = f"{body[:content_limit]}..." if content_limit else body
            parts.append(f"- [{ref_counter}] {post.get('title', '')}")
            parts.append(f"  Content: {snippet}")
            ref_counter += 1

        parts.append("")
        parts.append("COMMENTS (sample):")
        for comment in content.get("comments", [])[:10]:
            references.append(comment.get("url", ""))
            body = comment.get("body", "")
            snippet = f"{body[:content_limit]}..." if content_limit else body
            parts.append(f"- [{ref_counter}] {snippet}")
            ref_counter += 1

        return "\n".join(parts), references

    def prepare_claude_content(
        self,
        content: Dict[str, List[Dict[str, Any]]],
        subreddit_name: str,
    ) -> Tuple[List[TextBlockParam], List[Tuple[str, str]]]:
        formatted = [f"Content from r/{subreddit_name}:", "", "POSTS:"]
        references: List[Tuple[str, str]] = []

        for idx, post in enumerate(content.get("posts", []), start=1):
            formatted.extend(
                [
                    f"Post {idx}:",
                    f"Title: {post.get('title', '')}",
                    f"Content: {post.get('content', '')}",
                    f"Posted: {post.get('created_utc', '')}",
                    "",
                ]
            )
            references.append((f"Post {idx}", post.get("url", "")))

        formatted.append("COMMENTS:")
        for idx, comment in enumerate(content.get("comments", [])[:10], start=1):
            formatted.extend(
                [
                    f"Comment {idx}:",
                    f"Content: {comment.get('body', '')}",
                    f"Posted: {comment.get('created_utc', '')}",
                    "",
                ]
            )
            references.append((f"Comment {idx}", comment.get("url", "")))

        content_block = _make_text_block("\n".join(formatted))
        return [content_block], references

    def summarize_with_claude(
        self,
        content: Dict[str, List[Dict[str, Any]]],
        subreddit_name: str,
    ) -> str:
        if not self.claude_client:
            return "Error: Anthropic API key not found."

        try:
            documents, references = self.prepare_claude_content(content, subreddit_name)
            message_content: List[TextBlockParam] = list(documents)
            message_content.append(
                _make_text_block(
                    f"Provide a comprehensive summary of this Reddit content from r/{subreddit_name}. "
                    "Reference specific posts/comments."
                )
            )
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[{"role": "user", "content": message_content}],
            )
            content_list = getattr(response, "content", None) or []
            summary_text = content_list[0].text if content_list else ""
            summary = summary_text.strip()
            if not summary:
                return "Error: Received empty summary from Claude"

            reference_block = "\n".join(f"[{ref}]({url})" for ref, url in references if url)
            return f"{summary}\n\nReferences:\n{reference_block}"
        except Exception as exc:
            return f"Error generating summary with Claude: {exc}"

    def summarize_with_openai(
        self,
        content: Dict[str, List[Dict[str, Any]]],
        subreddit_name: str,
        use_rate_limiting: bool = True,
        max_retries: int = 3,
    ) -> Tuple[str, List[str]]:
        if not self.openai_client:
            return "Error: OpenAI API key not found.", []

        retry_count = 0
        content_limit: Optional[int] = None
        target_tokens = self.MAX_TOKENS

        while retry_count < max_retries:
            try:
                summary_prompt, references = self.prepare_summary_prompt(
                    content, subreddit_name, content_limit
                )
                total_tokens = self.count_tokens(summary_prompt)

                if use_rate_limiting and total_tokens > target_tokens:
                    content_limit = 500 if content_limit is None else max(50, content_limit // 2)
                    retry_count += 1
                    print(f"Reducing content to {content_limit} chars (tokens: {total_tokens})")
                    continue

                print(f"Requesting with {total_tokens} tokens...")
                chat_completion = self.openai_client.chat.completions.create(
                    model=self.openai_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a helpful assistant that summarizes Reddit content. "
                                "Include key themes, notable discussions, and overall sentiment. "
                                "Use numbered references [n]."
                            ),
                        },
                        {"role": "user", "content": summary_prompt},
                    ],
                )
                message = chat_completion.choices[0].message
                summary_text = message.content or ""
                return summary_text, references
            except Exception as exc:
                error_str = str(exc)
                if use_rate_limiting and (
                    "Request too large" in error_str or "rate_limit_exceeded" in error_str
                ):
                    retry_count += 1
                    content_limit = 500 if content_limit is None else max(50, content_limit // 2)
                    print(
                        f"Hit rate limit. Reducing content to {content_limit} chars "
                        f"and retrying ({retry_count}/{max_retries})..."
                    )
                    continue
                return f"Error generating summary: {error_str}", []

        return (
            f"Error: Unable to generate summary after {max_retries} attempts due to rate limits.",
            [],
        )

    def summarize_with_ollama(
        self,
        content: Dict[str, List[Dict[str, Any]]],
        subreddit_name: str,
    ) -> Tuple[str, List[str]]:
        try:
            from ollama import chat  # type: ignore

            summary_prompt, references = self.prepare_summary_prompt(content, subreddit_name)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant that summarizes Reddit content. "
                        "Include key themes, notable discussions, and overall sentiment. "
                        "Use numbered references [n]."
                    ),
                },
                {"role": "user", "content": summary_prompt},
            ]
            response = chat(model=self.ollama_model, messages=messages)
            if isinstance(response, dict):
                summary = response.get("message", {}).get("content", "") or ""
            else:
                summary = getattr(getattr(response, "message", None), "content", "") or ""

            if not summary.strip():
                summary = "No summary generated by Ollama."
            return summary, references
        except Exception as exc:
            return f"Error generating summary with Ollama: {exc}", []

    def filter_content_by_topics(
        self,
        content: Dict[str, List[Dict[str, Any]]],
        topics: List[str],
    ) -> Dict[str, List[Dict[str, Any]]]:
        lowered = [topic.lower() for topic in topics]

        def contains_topics(text: Optional[str]) -> bool:
            text_lower = (text or "").lower()
            return any(topic in text_lower for topic in lowered)

        filtered_posts = [
            post
            for post in content.get("posts", [])
            if contains_topics(post.get("title")) or contains_topics(post.get("content"))
        ]
        filtered_comments = [
            comment for comment in content.get("comments", []) if contains_topics(comment.get("body"))
        ]
        return {"posts": filtered_posts, "comments": filtered_comments}

    def format_summary_with_footnotes(
        self,
        summary: str,
        references: List[str],
    ) -> str:
        reference_block = "\n".join(
            f"[{idx}] {url}" for idx, url in enumerate(references, start=1) if url
        )
        return f"{summary}\n\nReferences:\n{reference_block}"


def save_summary_to_file(
    subreddit: str,
    summary: str,
    analysis_params: Dict[str, Any],
    content: Optional[Dict[str, Any]] = None,
) -> List[str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_files: List[str] = []

    summary_filename = f"summary_{subreddit}_{timestamp}.txt"
    with open(summary_filename, "w", encoding="utf-8") as handle:
        handle.write("ANALYSIS PARAMETERS:\n")
        handle.write(f"Subreddit name: {analysis_params['subreddit']}\n")
        handle.write(f"Hours analyzed: {analysis_params['hours']}\n")
        topics = analysis_params.get("topics") or []
        handle.write(f"Topics: {', '.join(topics) if topics else 'No topic filter'}\n")
        handle.write(
            f"Clean text content: {'Yes' if analysis_params.get('clean_text') else 'No'}\n"
        )
        handle.write(f"API used: {analysis_params.get('api_used', 'N/A')}\n")
        if analysis_params.get("model"):
            handle.write(f"Model used: {analysis_params['model']}\n")
        handle.write(
            f"Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        )
        handle.write("\n" + "=" * 50 + "\n\n")
        handle.write(summary)
    saved_files.append(summary_filename)

    if content:
        raw_filename = f"raw_data_{subreddit}_{timestamp}.json"
        with open(raw_filename, "w", encoding="utf-8") as handle:
            json.dump(content, handle, indent=2, ensure_ascii=False)
        saved_files.append(raw_filename)

    return saved_files


def get_positive_int(prompt: str) -> int:
    while True:
        try:
            value = int(input(prompt))
            if value > 0:
                return value
            print("Enter a positive number.")
        except ValueError:
            print("Please enter a valid number.")


def main() -> None:
    summarizer = RedditSummarizer()

    api_choice = ""
    while api_choice not in {"1", "2", "3"}:
        api_choice = input("Choose API for summarization (1=OpenAI, 2=Claude, 3=Ollama): ").strip()

    use_rate_limiting = api_choice == "1" and input(
        "Use rate limiting for OpenAI? (y/n): "
    ).lower() == "y"

    subreddits = [value.strip() for value in input(
        "Enter subreddit name(s) separated by commas: "
    ).split(",") if value.strip()]

    hours = get_positive_int("Enter number of hours to analyze: ")
    topics_input = input("Enter topics to focus on (comma-separated, or press Enter for no filter): ")
    topics = [token.strip().lower() for token in topics_input.split(",") if token.strip()]
    clean_text = input("Clean text content? (y/n): ").lower() == "y"
    save_to_file = input("Save summaries to files? (y/n): ").lower() == "y"
    save_raw_data = save_to_file and input("Save raw data too? (y/n): ").lower() == "y"

    for subreddit in subreddits:
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
                print(
                    f"Found {len(content['posts'])} posts and {len(content['comments'])} comments"
                )

            if not content["posts"] and not content["comments"]:
                print(f"No content found matching the specified topics in r/{subreddit}")
                continue

            print("\nGenerating summary...")
            if api_choice == "1":
                summary, references = summarizer.summarize_with_openai(
                    content, subreddit, use_rate_limiting
                )
                formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
                model_used = summarizer.openai_model
            elif api_choice == "2":
                summary_text = summarizer.summarize_with_claude(content, subreddit)
                formatted_summary = summary_text
                model_used = "claude-3-5-sonnet-20241022"
            else:
                summary, references = summarizer.summarize_with_ollama(content, subreddit)
                formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
                model_used = summarizer.ollama_model

            print("\nSUMMARY:\n" + formatted_summary)

            if save_to_file:
                analysis_params = {
                    "subreddit": subreddit,
                    "hours": hours,
                    "topics": topics,
                    "clean_text": clean_text,
                    "api_used": "OpenAI" if api_choice == "1" else "Claude" if api_choice == "2" else "Ollama",
                    "rate_limiting": use_rate_limiting if api_choice == "1" else "N/A",
                    "model": model_used,
                }
                saved_files = save_summary_to_file(
                    subreddit,
                    formatted_summary,
                    analysis_params,
                    content if save_raw_data else None,
                )
                print("\nFiles saved:")
                for filename in saved_files:
                    print(f"- {filename}")

            print("\n" + "=" * 50 + "\n")
        except Exception as exc:
            print(f"Error processing r/{subreddit}: {exc}")

if __name__ == "__main__":
    main()
