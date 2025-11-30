# sentiment.py
# Performs sentiment analysis on recent subreddit posts/comments, logs detailed results and comment-level summaries to CSV files.
# Usage:
#   1. Configure Reddit API credentials in a .env file (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT).
#   2. Run: python sentiment.py
#   3. Follow prompts for subreddit name, result limit, and sort order (hot/new).
#   4. Check the generated reddit_sentiment_analysis_*.csv and reddit_sentiment_summaries_*.csv files.

from __future__ import annotations

import csv
import os
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Literal, Sequence

import praw
from praw.models import Submission, Comment, Subreddit
from textblob import TextBlob
from dotenv import load_dotenv


@dataclass(frozen=True)
class SentimentRecord:
    item_type: Literal["Post", "Comment"]
    content: str
    score: float
    interpretation: str
    created: str

    def to_row(self) -> list[str | float]:
        return [self.item_type, self.content, self.score, self.interpretation, self.created]


@dataclass(frozen=True)
class CommentSummary:
    post_title: str
    total_comments: int
    sentiment_breakdown: Dict[str, int]

    def to_row(self) -> list[str | int]:
        sentiments = [
            "Positive++",
            "Positive+",
            "Positive",
            "Neutral",
            "Negative",
            "Negative-",
            "Negative--",
        ]
        return [
            self.post_title,
            self.total_comments,
            *[self.sentiment_breakdown.get(sentiment, 0) for sentiment in sentiments],
        ]


def get_credentials() -> Dict[str, str]:
    load_dotenv()
    return {
        "client_id": os.getenv("REDDIT_CLIENT_ID", ""),
        "client_secret": os.getenv("REDDIT_CLIENT_SECRET", ""),
        "user_agent": os.getenv("REDDIT_USER_AGENT", ""),
    }


def get_sentiment(text: str) -> float:
    sentiment: Any = TextBlob(text).sentiment
    return float(sentiment.polarity)


def interpret_sentiment(score: float) -> str:
    if score > 0.6:
        return "Positive++"
    if score > 0.3:
        return "Positive+"
    if score > 0:
        return "Positive"
    if score == 0:
        return "Neutral"
    if score > -0.3:
        return "Negative"
    if score > -0.6:
        return "Negative-"
    return "Negative--"


def log_to_csv(records: Sequence[SentimentRecord], filename: Path) -> None:
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Type", "Content", "Score", "Interpretation", "Created"])
        for record in records:
            writer.writerow(record.to_row())


def log_summaries_to_csv(summaries: Sequence[CommentSummary], filename: Path) -> None:
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Post Title",
                "Total Comments",
                "Positive++",
                "Positive+",
                "Positive",
                "Neutral",
                "Negative",
                "Negative-",
                "Negative--",
            ]
        )
        for summary in summaries:
            writer.writerow(summary.to_row())


def summarize_comments(post: Submission, comments: Sequence[SentimentRecord]) -> CommentSummary:
    sentiment_counts = Counter(record.interpretation for record in comments)
    return CommentSummary(
        post_title=post.title or "(no title)",
        total_comments=len(comments),
        sentiment_breakdown=dict(sentiment_counts),
    )


def format_timestamp(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds).strftime("%Y-%m-%d %H:%M:%S")


def get_user_input() -> tuple[str, int, Literal["hot", "new"]]:
    subreddit_name = input("Subreddit? ").strip()
    while not subreddit_name:
        subreddit_name = input("Subreddit cannot be blank. Subreddit? ").strip()

    limit_str = input("Limit (int)? ").strip()
    while not limit_str.isdigit() or int(limit_str) <= 0:
        limit_str = input("Please enter a positive integer for limit: ").strip()
    limit = int(limit_str)

    sort_method = input("Sort by (hot/new)? ").strip().lower()
    while sort_method not in {"hot", "new"}:
        sort_method = input("Invalid input. Please enter 'hot' or 'new': ").strip().lower()

    return subreddit_name, limit, sort_method  # type: ignore[return-value]


def get_sorted_posts(
    subreddit: Subreddit,
    sort_method: Literal["hot", "new"],
    limit: int,
) -> Iterable[Submission]:
    sorters = {
        "hot": subreddit.hot,
        "new": subreddit.new,
    }
    return sorters[sort_method](limit=limit)


def analyze_post(post: Submission) -> SentimentRecord:
    post_title = post.title or "(no title)"
    post_date = format_timestamp(post.created_utc)
    score = get_sentiment(post_title)
    interpretation = interpret_sentiment(score)
    return SentimentRecord("Post", post_title, score, interpretation, post_date)


def analyze_comments(post: Submission) -> list[SentimentRecord]:
    post.comments.replace_more(limit=0)
    records: list[SentimentRecord] = []
    for comment in post.comments.list():
        if not isinstance(comment, Comment):
            continue
        body = (comment.body or "").strip()
        if not body:
            continue
        comment_date = format_timestamp(comment.created_utc)
        score = get_sentiment(body)
        interpretation = interpret_sentiment(score)
        records.append(
            SentimentRecord(
                "Comment",
                body[:200],
                score,
                interpretation,
                comment_date,
            )
        )
    return records


def build_output_filename(prefix: str, subreddit: str, sort_method: str, timestamp: str) -> Path:
    safe_subreddit = subreddit.replace("/", "_")
    safe_sort = sort_method.replace("/", "_")
    return Path(f"{prefix}_{safe_subreddit}_{safe_sort}_{timestamp}.csv")


def main() -> None:
    credentials = get_credentials()
    reddit = praw.Reddit(
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
        user_agent=credentials["user_agent"],
    )

    subreddit_name, limit, sort_method = get_user_input()
    subreddit = reddit.subreddit(subreddit_name)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    detail_filename = build_output_filename(
        "reddit_sentiment_analysis", subreddit_name, sort_method, timestamp
    )
    summary_filename = build_output_filename(
        "reddit_sentiment_summaries", subreddit_name, sort_method, timestamp
    )

    all_records: list[SentimentRecord] = []
    summaries: list[CommentSummary] = []

    for post in get_sorted_posts(subreddit, sort_method, limit):
        post_record = analyze_post(post)
        all_records.append(post_record)

        comment_records = analyze_comments(post)
        all_records.extend(comment_records)
        summaries.append(summarize_comments(post, comment_records))

    log_to_csv(all_records, detail_filename)
    print(f"Detailed results saved to {detail_filename}")

    log_summaries_to_csv(summaries, summary_filename)
    print(f"Comment summaries saved to {summary_filename}")


if __name__ == "__main__":
    main()