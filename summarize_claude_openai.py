# summarize_claude_openai.py
# Fetches recent posts/comments from Reddit, summarizes with OpenAI, Claude, or Ollama, and saves outputs.
# Usage:
#   1. Configure API keys (.env) for Reddit + desired model provider(s).
#   2. Run: python summarize_claude_openai.py
#   3. Choose API (1=OpenAI, 2=Claude, 3=Ollama), enter subreddits/hours/topics, and decide on saving options.

import json
import string
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any, TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize

from config import load_config
from credentials import get_reddit_client, get_secret

if TYPE_CHECKING:
    import anthropic
    import praw
    import tiktoken
    from openai import OpenAI

_UNSET = object()  # pyright: ignore[assignment] - Sentinel for lazy initialization

EASTERN_TZ = ZoneInfo("America/New_York")

class RedditSummarizer:
    def __init__(self) -> None:
        config = load_config()
        models = config.get("models", {})

        # Model names (cheap config lookups — always loaded)
        self.openai_model = get_secret("OPENAI_SUMMARY_MODEL") or models.get("openai", "gpt-4o")
        openai_config = config.get("openai", {})
        self.openai_service_tier = openai_config.get("service_tier")

        self.claude_model = models.get("claude", "claude-sonnet-4-5-20250929")

        ollama_config = config.get("ollama", {})
        self.ollama_url = get_secret("OLLAMA_URL") or ollama_config.get("url", "http://localhost:11434/api/chat")
        self.ollama_model = get_secret("OLLAMA_MODEL") or models.get("ollama", "gemma3:12b")

        # Load prompts from config
        prompt_config = config.get("prompt", {})
        self.system_prompt = prompt_config.get("system", "")
        self.user_prompt_template = prompt_config.get("user", "")

        self.eastern_tz = EASTERN_TZ
        self.MAX_TOKENS = 8000

        # Lazy-init backing fields (clients created on first access)
        self._reddit = _UNSET
        self._openai_client = _UNSET
        self._claude_client = _UNSET
        self._tokenizer = _UNSET

        # Cached text-cleaning sets (built once)
        self._stop_words = set(stopwords.words("english"))
        self._bad_chars = set(string.punctuation) | set("=~^`\\") | {"\u2022", "\u2013", "\u2014", "\u2015"}

    @property
    def reddit(self) -> Optional["praw.Reddit"]:
        if self._reddit is _UNSET:
            self._reddit = get_reddit_client()
        return cast(Optional["praw.Reddit"], self._reddit)

    @property
    def openai_client(self) -> Optional["OpenAI"]:
        if self._openai_client is _UNSET:
            from openai import OpenAI
            key = get_secret("OPENAI_API_KEY")
            self._openai_client = OpenAI(api_key=key) if key else None
        return cast(Optional["OpenAI"], self._openai_client)

    @property
    def claude_client(self) -> Optional["anthropic.Anthropic"]:
        if self._claude_client is _UNSET:
            import anthropic
            key = get_secret("ANTHROPIC_API_KEY")
            self._claude_client = anthropic.Anthropic(api_key=key) if key else None
        return cast(Optional["anthropic.Anthropic"], self._claude_client)

    @property
    def tokenizer(self) -> "tiktoken.Encoding":
        if self._tokenizer is _UNSET:
            import tiktoken
            try:
                self._tokenizer = tiktoken.encoding_for_model(self.openai_model)
            except KeyError:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
        return cast("tiktoken.Encoding", self._tokenizer)

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        try:
            tokens = word_tokenize(text.lower())
            filtered = [t for t in tokens if t not in self._bad_chars and t not in self._stop_words]
            return " ".join(filtered)
        except Exception as exc:
            print(f"Warning: Error cleaning text: {exc}")
            return text

    def count_tokens(self, text: str) -> int:
        try:
            return len(self.tokenizer.encode(text))
        except Exception:
            return len(text) // 4

    def _format_datetime(self, dt: datetime) -> str:
        return dt.astimezone(self.eastern_tz).strftime("%Y-%m-%d %H:%M:%S %Z")

    def get_recent_content(
        self,
        subreddit_name: str,
        hours: int,
        clean: bool = True,
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not self.reddit:
            raise RuntimeError("Reddit client not initialized. Check REDDIT_* credentials in .env")
        # RuntimeError prevents execution from continuing, so self.reddit is guaranteed not None
        subreddit = self.reddit.subreddit(subreddit_name)  # pyright: ignore[union-attr]
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        posts: List[Dict[str, Any]] = []
        for post in subreddit.new(limit=100):
            post_time = post.created_datetime
            if post_time < cutoff:
                continue
            body = post.selftext or ""
            posts.append(
                {
                    "title": post.title or "",
                    "content": self.clean_text(body) if clean else body,
                    "raw_content": body,
                    "score": post.score,
                    "url": f"https://www.reddit.com{post.permalink}",
                    "created_utc": self._format_datetime(post_time),
                }
            )

        comments: List[Dict[str, Any]] = []
        for comment in subreddit.comments(limit=500):
            comment_time = comment.created_datetime
            if comment_time < cutoff:
                continue
            body = getattr(comment, "body", "") or ""
            comments.append(
                {
                    "body": self.clean_text(body) if clean else body,
                    "raw_body": body,
                    "score": comment.score,
                    "url": f"https://www.reddit.com{comment.permalink}",
                    "created_utc": self._format_datetime(comment_time),
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
            self.user_prompt_template.format(subreddit=subreddit_name),
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

    def summarize_with_claude(
        self,
        content: Dict[str, List[Dict[str, Any]]],
        subreddit_name: str,
    ) -> Tuple[str, List[str]]:
        if not self.claude_client:
            return "Error: Anthropic API key not found.", []

        try:
            summary_prompt, references = self.prepare_summary_prompt(content, subreddit_name)
            response = self.claude_client.messages.create(
                model=self.claude_model,
                max_tokens=4096,
                messages=[
                    {"role": "user", "content": summary_prompt}
                ],
                system=self.system_prompt,
            )
            if not response.content:
                return "Error: Claude returned empty response", []

            first_block = response.content[0]
            if not hasattr(first_block, "text"):
                return f"Error: Unexpected Claude response format: {type(first_block)}", []

            # Safe to cast to object with text attribute after hasattr check
            summary = cast(Any, first_block).text.strip()
            if not summary:
                return "Error: Received empty summary from Claude", []

            return summary, references
        except Exception as exc:
            return f"Error generating summary with Claude: {exc}", []

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
                create_kwargs: Dict[str, Any] = {
                    "model": self.openai_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": self.system_prompt,
                        },
                        {"role": "user", "content": summary_prompt},
                    ],
                }
                if self.openai_service_tier:
                    create_kwargs["service_tier"] = self.openai_service_tier
                chat_completion = self.openai_client.chat.completions.create(**create_kwargs)
                if not chat_completion.choices:
                    return "Error: OpenAI returned no choices", []
                message = chat_completion.choices[0].message
                if not message.content:
                    return "Error: OpenAI returned empty content", []
                summary_text = message.content.strip()
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
                    "content": self.system_prompt,
                },
                {"role": "user", "content": summary_prompt},
            ]
            response = chat(model=self.ollama_model, messages=messages)

            summary = ""
            if isinstance(response, dict):
                summary = response.get("message", {}).get("content", "").strip()
            else:
                message = getattr(response, "message", None)
                if message:
                    summary = getattr(message, "content", "").strip()

            if not summary:
                return "Error: Ollama returned empty response", []
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
            if contains_topics(post.get("title")) or contains_topics(post.get("raw_content"))
        ]
        filtered_comments = [
            comment for comment in content.get("comments", []) if contains_topics(comment.get("raw_body"))
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
    timestamp = datetime.now(EASTERN_TZ).strftime("%Y%m%d_%H%M%S")

    output_dir = Path("output") / subreddit
    output_dir.mkdir(parents=True, exist_ok=True)

    saved_files: List[str] = []

    summary_path = output_dir / f"summary_{subreddit}_{timestamp}.txt"
    with open(summary_path, "w", encoding="utf-8") as handle:
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
        now_eastern = datetime.now(EASTERN_TZ)
        handle.write(
            f"Summary generated at: {now_eastern.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        )
        handle.write("\n" + "=" * 50 + "\n\n")
        handle.write(summary)
    saved_files.append(str(summary_path))

    if content:
        raw_path = output_dir / f"raw_data_{subreddit}_{timestamp}.json"
        with open(raw_path, "w", encoding="utf-8") as handle:
            json.dump(content, handle, indent=2, ensure_ascii=False)
        saved_files.append(str(raw_path))

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
                summary, references = summarizer.summarize_with_claude(content, subreddit)
                formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
                model_used = summarizer.claude_model
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
