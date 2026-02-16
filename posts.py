# posts.py
# Fetches recent subreddit posts within the time period as well as posts with comments that fit within the time period and logs them to a timestamped text file and CSV.
# Usage:
#   1. Configure Reddit API credentials in a .env file (REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT).
#   2. Run: python posts.py
#   3. Enter the subreddit, hour window, and whether to require recent comments.
#   4. Check the generated posts_<subreddit>_<hours>h[_comments]_<timestamp>.txt file.

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Optional, TextIO
from zoneinfo import ZoneInfo

import praw
from praw.models import Comment, MoreComments, Submission, Subreddit
from praw.exceptions import PRAWException
from prawcore.exceptions import PrawcoreException

from credentials import get_secret

EASTERN_TZ = ZoneInfo("America/New_York")


class RedditScraper:
    def __init__(self) -> None:
        self.reddit: praw.Reddit = praw.Reddit(
            client_id=get_secret("REDDIT_CLIENT_ID"),
            client_secret=get_secret("REDDIT_CLIENT_SECRET"),
            user_agent=get_secret("REDDIT_USER_AGENT"),
        )

    def get_subreddit(self, subreddit_name: str) -> Optional[Subreddit]:
        try:
            subreddit = self.reddit.subreddit(subreddit_name)
            subreddit.id  # Trigger a request to validate the subreddit exists.
            return subreddit
        except (PRAWException, PrawcoreException) as exc:
            print(f"Unable to load subreddit '{subreddit_name}': {exc}")
            return None

    def get_posts(
        self,
        subreddit: Subreddit,
        time_limit: int = 1,
        include_comments: bool = False,
    ) -> None:
        now = dt.datetime.now(dt.timezone.utc)
        filename = self._generate_filename(subreddit.display_name, time_limit, include_comments, now)
        csv_filename = filename.with_suffix(".csv")
        csv_rows: list[list[str]] = []

        print(
            f"Fetching {'posts with recent comments' if include_comments else 'recent posts'} "
            f"from r/{subreddit.display_name} (last {time_limit} hour(s))"
        )

        try:
            with filename.open("w", encoding="utf-8") as outfile:
                self._write_header(outfile, subreddit, time_limit, include_comments, now, csv_filename.name)

                for submission in subreddit.hot(limit=25):
                    if self._is_post_within_time_limit(submission, time_limit, include_comments, now):
                        hours_diff = self._write_post(outfile, submission, now)
                        csv_rows.append(
                            [
                                f"{hours_diff:.2f}",
                                submission.title or "(no title)",
                                submission.url,
                            ]
                        )
        except (PRAWException, PrawcoreException) as exc:
            print(f"Reddit API error: {exc}")
            return

        try:
            with csv_filename.open("w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["Time Diff (hrs)", "Title", "URL"])
                writer.writerows(csv_rows)
        except OSError as exc:
            print(f"Failed to write CSV: {exc}")

    def _generate_filename(
        self,
        subreddit_name: str,
        time_limit: int,
        include_comments: bool,
        now: dt.datetime,
    ) -> Path:
        suffix = "_comments" if include_comments else ""
        return Path(f"posts_{subreddit_name}{suffix}_{time_limit}h_{now.strftime('%Y%m%d_%H%M%S')}.txt")

    @staticmethod
    def _write_header(
        outfile: TextIO,
        subreddit: Subreddit,
        time_limit: int,
        include_comments: bool,
        now: dt.datetime,
        csv_name: str,
    ) -> None:
        eastern_now = now.astimezone(EASTERN_TZ)
        outfile.write("ANALYSIS PARAMETERS:\n")
        outfile.write(f"Subreddit: {subreddit.display_name}\n")
        outfile.write(f"Hours analyzed: {time_limit}\n")
        outfile.write(f"Include recent comments: {'Yes' if include_comments else 'No'}\n")
        outfile.write(f"Generated at: {eastern_now.strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
        outfile.write(f"CSV file: {csv_name}\n")
        outfile.write("\n" + "=" * 50 + "\n\n")

    def _is_post_within_time_limit(
        self,
        submission: Submission,
        time_limit: int,
        include_comments: bool,
        now: dt.datetime,
    ) -> bool:
        submission_time = dt.datetime.fromtimestamp(submission.created_utc, dt.timezone.utc)
        cutoff_delta = dt.timedelta(hours=time_limit)

        if not include_comments or submission.num_comments == 0:
            return now - submission_time <= cutoff_delta

        last_comment_time = self._get_last_comment_time(submission, submission_time)
        return now - last_comment_time <= cutoff_delta

    def _get_last_comment_time(
        self,
        submission: Submission,
        default_time: dt.datetime,
    ) -> dt.datetime:
        latest = default_time

        try:
            for comment in submission.comments.list():
                if isinstance(comment, Comment):
                    comment_time = dt.datetime.fromtimestamp(comment.created_utc, dt.timezone.utc)
                    if comment_time > latest:
                        latest = comment_time
                elif isinstance(comment, MoreComments):
                    continue
        except (PRAWException, PrawcoreException):
            return latest

        return latest

    @staticmethod
    def _write_post(outfile: TextIO, submission: Submission, now: dt.datetime) -> float:
        submission_time = dt.datetime.fromtimestamp(submission.created_utc, dt.timezone.utc)
        hours_ago = (now - submission_time).total_seconds() / 3600.0

        post_info = (
            f"Time Difference: {hours_ago:.2f} hours\n"
            f"Title: {submission.title or '(no title)'}\n"
            f"URL: {submission.url}\n"
            f"{'-' * 40}\n"
        )
        print(post_info, end="")
        outfile.write(post_info)
        return hours_ago


def main() -> None:
    scraper = RedditScraper()

    subreddit_name = input("Enter the subreddit name (e.g., python): ").strip()
    subreddit = scraper.get_subreddit(subreddit_name)
    if not subreddit:
        return

    try:
        hours = int(input("In the last how many hours? ").strip())
        if hours <= 0:
            raise ValueError
    except ValueError:
        print("Hours must be a positive integer.")
        return

    include_comments = input("Require recent comments? (y/n): ").strip().lower() == "y"
    scraper.get_posts(subreddit, hours, include_comments)


if __name__ == "__main__":
    main()
