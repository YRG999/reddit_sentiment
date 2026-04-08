# comments.py
# Interactive Reddit comment/post browser.
# Usage:
#   python comments.py

import time
from datetime import datetime
from zoneinfo import ZoneInfo

import click
import praw

from credentials import get_reddit_client

EASTERN_TZ = ZoneInfo("America/New_York")


def convert_utc_to_eastern(utc_timestamp: float) -> str:
    """Convert a UTC timestamp to Eastern Time string (handles DST)."""
    dt = datetime.fromtimestamp(utc_timestamp, EASTERN_TZ)
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


class RedditAPI:
    def __init__(self):
        self.reddit: praw.Reddit = get_reddit_client()

    def get_top_posts(self, subreddit_name, limit=10):
        subreddit = self.reddit.subreddit(subreddit_name)
        for post in subreddit.top(limit=limit):
            yield {
                "title": post.title,
                "score": post.score,
                "url": post.url,
                "created_utc": convert_utc_to_eastern(post.created_utc),
                "created_utc_raw": post.created_utc,
            }

    def search_posts(self, keyword, subreddit_name=None, limit=10):
        try:
            if subreddit_name:
                results = self.reddit.subreddit(subreddit_name).search(query=keyword, sort="relevance", limit=limit)
            else:
                results = self.reddit.subreddit("all").search(query=keyword, sort="relevance", limit=limit)

            for post in results:
                yield {
                    "title": post.title,
                    "subreddit": post.subreddit.display_name,
                    "score": post.score,
                    "shared_url": post.url,
                    "reddit_url": f"https://www.reddit.com{post.permalink}",
                    "created_utc": convert_utc_to_eastern(post.created_utc),
                    "created_utc_raw": post.created_utc,
                }
        except Exception as e:
            click.echo(f"Error during search: {e}")
            yield from []

    def get_user_karma(self, username):
        user = self.reddit.redditor(username)
        return {
            "name": user.name,
            "comment_karma": user.comment_karma,
            "link_karma": user.link_karma,
            "created_utc": convert_utc_to_eastern(user.created_utc),
            "created_utc_raw": user.created_utc,
        }

    def stream_comments(self, subreddit_name, limit=None):
        subreddit = self.reddit.subreddit(subreddit_name)
        for i, comment in enumerate(subreddit.stream.comments()):
            if limit and i >= limit:
                break
            yield {
                "author": str(comment.author),
                "body": comment.body,
                "score": comment.score,
                "permalink": f"https://www.reddit.com{comment.permalink}",
                "created_utc": convert_utc_to_eastern(comment.created_utc),
                "created_utc_raw": comment.created_utc,
            }

    def search_comments(self, subreddit_name, search_words, limit=100):
        subreddit = self.reddit.subreddit(subreddit_name)
        search_terms = [word.lower() for word in search_words.split()]

        for comment in subreddit.comments(limit=limit):
            if all(term in comment.body.lower() for term in search_terms):
                yield {
                    "author": str(comment.author),
                    "posted_on": convert_utc_to_eastern(comment.created_utc),
                    "posted_on_raw": comment.created_utc,
                    "body": comment.body,
                    "permalink": f"https://www.reddit.com{comment.permalink}",
                }

    def stream_comments_formatted(self, subreddit_name):
        subreddit = self.reddit.subreddit(subreddit_name)
        for comment in subreddit.stream.comments():
            yield {
                "datetime": convert_utc_to_eastern(comment.created_utc),
                "datetime_raw": comment.created_utc,
                "author": str(comment.author),
                "body": comment.body.replace("\n", " "),
                "url": f"https://www.reddit.com{comment.permalink}",
            }


class UserInterface:
    def __init__(self):
        self.reddit_api = RedditAPI()
        current_time = datetime.now(EASTERN_TZ).strftime("%Y%m%d_%H%M%S")
        self.log_file = f"reddit_api_log_{current_time}.txt"

    def log(self, message):
        current_time = datetime.now(EASTERN_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
        log_entry = f"{current_time} - {message}"
        click.echo(log_entry)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"{log_entry}\n")
        except IOError as e:
            click.echo(f"Warning: Could not write to log file: {e}")

    def run(self):
        self.log(f"Session started at {datetime.now(EASTERN_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        while True:
            self.display_menu()
            choice = click.prompt("Enter your choice (1-9)", type=str)
            self.handle_choice(choice)

    def display_menu(self):
        click.echo("\nReddit API Example Interface")
        click.echo("1. Get top posts from a subreddit")
        click.echo("2. Search for posts containing a keyword")
        click.echo("3. Get user's karma")
        click.echo("4. Stream comments from a subreddit")
        click.echo("5. Stream comments with rate limiting")
        click.echo("6. Stream one comment per second")
        click.echo("7. Search for comments containing specific words")
        click.echo("8. Stream formatted comments one per second")
        click.echo("9. Exit")

    def handle_choice(self, choice):
        if choice == "1":
            self.get_top_posts()
        elif choice == "2":
            self.search_posts()
        elif choice == "3":
            self.get_user_karma()
        elif choice == "4":
            self.stream_comments()
        elif choice == "5":
            self.stream_comments_rate_limited()
        elif choice == "6":
            self.stream_comments_one_per_second()
        elif choice == "7":
            self.search_comments()
        elif choice == "8":
            self.stream_formatted_comments_one_per_second()
        elif choice == "9":
            self.log("Exiting the program. Goodbye!")
            raise SystemExit
        else:
            self.log("Invalid choice. Please try again.")

    def get_top_posts(self):
        subreddit = click.prompt("Enter subreddit name")
        limit = click.prompt("Enter number of posts to retrieve", type=int)
        self.log(f"Getting top {limit} posts from r/{subreddit}")
        for post in self.reddit_api.get_top_posts(subreddit, limit):
            self.log(f"Title: {post['title']}")
            self.log(f"Score: {post['score']}")
            self.log(f"URL: {post['url']}")
            self.log(f"Created: {post['created_utc']}")
            self.log("---")

    def search_posts(self):
        keyword = click.prompt("Enter keyword to search")
        subreddit = click.prompt("Enter subreddit name (blank for all)", default="", show_default=False)
        limit = click.prompt("Enter number of posts to retrieve", type=int)
        self.log(f"Searching for '{keyword}' in {subreddit if subreddit else 'all subreddits'}")
        for post in self.reddit_api.search_posts(keyword, subreddit if subreddit else None, limit):
            self.log(f"Title: {post['title']}")
            self.log(f"Subreddit: {post['subreddit']}")
            self.log(f"Score: {post['score']}")
            self.log(f"Shared URL: {post['shared_url']}")
            self.log(f"Reddit Post: {post['reddit_url']}")
            self.log(f"Created: {post['created_utc']}")
            self.log("---")

    def get_user_karma(self):
        username = click.prompt("Enter Reddit username")
        self.log(f"Getting karma for user: {username}")
        karma = self.reddit_api.get_user_karma(username)
        self.log(f"User: {karma['name']}")
        self.log(f"Comment Karma: {karma['comment_karma']}")
        self.log(f"Link Karma: {karma['link_karma']}")
        self.log(f"Account Created: {karma['created_utc']}")

    def stream_comments(self):
        subreddit = click.prompt("Enter subreddit name")
        limit = click.prompt("Enter number of comments to stream", type=int)
        self.log(f"Streaming {limit} comments from r/{subreddit}")
        for comment in self.reddit_api.stream_comments(subreddit, limit):
            self.log(f"Author: {comment['author']}")
            self.log(f"Comment: {comment['body']}")
            self.log(f"Score: {comment['score']}")
            self.log(f"Link: {comment['permalink']}")
            self.log(f"Posted: {comment['created_utc']}")
            self.log("---")

    def search_comments(self):
        subreddit = click.prompt("Enter subreddit name")
        search_words = click.prompt("Enter word(s) to search for (space-separated)")
        limit = click.prompt("Number of recent comments to search through", type=int, default=100)

        self.log(f"Searching for comments containing '{search_words}' in r/{subreddit}")
        self.log(f"Checking the most recent {limit} comments...")

        matching_comments = list(self.reddit_api.search_comments(subreddit, search_words, limit))

        if not matching_comments:
            self.log(f"No comments found containing '{search_words}'.")
        else:
            self.log(f"Found {len(matching_comments)} comment(s) containing '{search_words}':")
            for comment in matching_comments:
                self.log(f"Author: {comment['author']}")
                self.log(f"Posted on: {comment['posted_on']}")
                self.log(f"Comment: {comment['body']}")
                self.log(f"Link: {comment['permalink']}")
                self.log("---")

    def stream_formatted_comments_one_per_second(self):
        subreddit = click.prompt("Enter subreddit name")
        duration_str = click.prompt("Duration in seconds (blank for unlimited)", default="", show_default=False)
        duration = int(duration_str) if duration_str else None

        rate_limit = click.confirm("Rate limit?", default=False)

        self.log(f"Streaming formatted comments from r/{subreddit}")
        if rate_limit:
            self.log("Rate limited to one comment per second")
        else:
            self.log("Streaming comments as fast as possible")
        if duration:
            self.log(f"Stream will run for {duration} seconds")

        start_time = time.time()

        try:
            for comment in self.reddit_api.stream_comments_formatted(subreddit):
                current_time = time.time()
                elapsed_time = current_time - start_time

                if duration and elapsed_time > duration:
                    self.log(f"Stream ended after {duration} seconds.")
                    break

                formatted_comment = f"{comment['datetime']}-{comment['author']}-{comment['body']}-{comment['url']}"
                self.log(formatted_comment)

                if rate_limit:
                    time_to_wait = 1 - (time.time() - current_time)
                    if time_to_wait > 0:
                        time.sleep(time_to_wait)

        except KeyboardInterrupt:
            self.log("Stream stopped by user.")

    def stream_comments_rate_limited(self):
        subreddit = click.prompt("Enter subreddit name")
        rate = click.prompt("Rate limit (comments per minute)", type=int, default=30)
        duration_str = click.prompt("Duration in seconds (blank for unlimited)", default="", show_default=False)
        duration = int(duration_str) if duration_str else None

        self.log(f"Streaming comments from r/{subreddit} at {rate} comments per minute")
        if duration:
            self.log(f"Stream will run for {duration} seconds")

        start_time = time.time()
        comment_count = 0

        try:
            for comment in self.reddit_api.stream_comments(subreddit):
                current_time = time.time()
                elapsed_time = current_time - start_time

                if duration and elapsed_time > duration:
                    self.log(f"Stream ended after {duration} seconds.")
                    break

                self.log(f"Author: {comment['author']}")
                self.log(f"Comment: {comment['body']}")
                self.log(f"Score: {comment['score']}")
                self.log(f"Link: {comment['permalink']}")
                self.log(f"Posted: {comment['created_utc']}")
                self.log("---")

                comment_count += 1

                if comment_count >= rate:
                    sleep_time = 60 - elapsed_time
                    if sleep_time > 0:
                        self.log(f"Rate limit reached. Pausing for {sleep_time:.2f} seconds...")
                        time.sleep(sleep_time)

                    start_time = time.time()
                    comment_count = 0

        except KeyboardInterrupt:
            self.log("Stream stopped by user.")

    def stream_comments_one_per_second(self):
        subreddit = click.prompt("Enter subreddit name")
        duration_str = click.prompt("Duration in seconds (blank for unlimited)", default="", show_default=False)
        duration = int(duration_str) if duration_str else None

        self.log(f"Streaming comments from r/{subreddit} at one comment per second")
        if duration:
            self.log(f"Stream will run for {duration} seconds")

        start_time = time.time()

        try:
            for comment in self.reddit_api.stream_comments(subreddit):
                current_time = time.time()
                elapsed_time = current_time - start_time

                if duration and elapsed_time > duration:
                    self.log(f"Stream ended after {duration} seconds.")
                    break

                self.log(f"Comment: {comment['body']}")
                self.log(f"Posted: {comment['created_utc']}")

                time_to_wait = 1 - (time.time() - current_time)
                if time_to_wait > 0:
                    time.sleep(time_to_wait)

        except KeyboardInterrupt:
            self.log("Stream stopped by user.")


@click.command()
def main():
    """Interactive Reddit comment and post browser."""
    UserInterface().run()


if __name__ == "__main__":
    main()
