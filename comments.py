# reddit_comments13.py
# v1 - didn't work as auth wasn't properly set up
# v2 - added dotenv & menu
# v3 - added 5. Stream comments with rate limiting
# v4 - added 6. Stream one comment per second
# v5 - added 7. Search for comments containing a specific string
# v6 - added 8. Search for comments containing specific words
# v7 - updated to `class RedditAPI`
# v8 - added 9. Stream formatted comments one per second
# v9 - added logging and rate limiting
# v10 - added datetime when post or comment created (error deleted needed code)
# v11 - convert datetime from utc to eastern, added back deleted code, added version updates
# v12 - Update praw search API
# v13 - Add reddit url

import praw
import time
from datetime import datetime
import pytz

from credentials import get_secret

class TimeConverter:
    """
    Handles all timezone conversion logic for the application.
    This separates timezone handling from the main business logic.
    """
    @staticmethod
    def convert_utc_to_eastern(utc_timestamp):
        """
        Convert a UTC timestamp to Eastern Time (handling DST automatically)
        
        Parameters:
        utc_timestamp (float): Unix timestamp in UTC
        
        Returns:
        str: Formatted date/time string in Eastern Time
        """
        # Create a UTC datetime object
        utc_dt = datetime.fromtimestamp(utc_timestamp, tz=pytz.UTC)
        
        # Get the Eastern timezone object
        eastern_tz = pytz.timezone('America/New_York')
        
        # Convert to Eastern time
        eastern_dt = utc_dt.astimezone(eastern_tz)
        
        # Format with timezone abbreviation (will show either EST or EDT)
        return eastern_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

class RedditAPI:
    def __init__(self):
        credentials = self.get_credentials()
        self.reddit = praw.Reddit(
            client_id=credentials['client_id'],
            client_secret=credentials['client_secret'],
            user_agent=credentials['user_agent']
        )
        # Create time converter instance for use across methods
        self.time_converter = TimeConverter()

    @staticmethod
    def get_credentials():
        return {
            'client_id': get_secret('REDDIT_CLIENT_ID'),
            'client_secret': get_secret('REDDIT_CLIENT_SECRET'),
            'user_agent': get_secret('REDDIT_USER_AGENT')
        }

    def get_top_posts(self, subreddit_name, limit=10):
        subreddit = self.reddit.subreddit(subreddit_name)
        for post in subreddit.top(limit=limit):
            yield {
                "title": post.title,
                "score": post.score,
                "url": post.url,
                "created_utc": self.time_converter.convert_utc_to_eastern(post.created_utc),
                "created_utc_raw": post.created_utc  # Keep raw UTC for potential future use
            }

    def search_posts(self, keyword, subreddit_name=None, limit=10):
        """
        Search for posts containing a keyword across Reddit or within a specific subreddit.
        
        Parameters:
        keyword (str): The search term
        subreddit_name (str, optional): Specific subreddit to search in
        limit (int): Maximum number of results to return
        
        Yields:
        dict: Post information including title, subreddit, score, URL, and creation time
        """
        try:
            if subreddit_name:
                # Search within a specific subreddit
                results = self.reddit.subreddit(subreddit_name).search(query=keyword, sort='relevance', limit=limit)
            else:
                # Search across all subreddits using a different syntax
                results = self.reddit.subreddit('all').search(query=keyword, sort='relevance', limit=limit)
            
            for post in results:
                yield {
                    "title": post.title,
                    "subreddit": post.subreddit.display_name,
                    "score": post.score,
                    "shared_url": post.url,
                    "reddit_url": f"https://www.reddit.com{post.permalink}",
                    "created_utc": self.time_converter.convert_utc_to_eastern(post.created_utc),
                    "created_utc_raw": post.created_utc
                }
        except Exception as e:
            print(f"Error during search: {e}")
            yield from []  # Return an empty generator in case of error


    def get_user_karma(self, username):
        user = self.reddit.redditor(username)
        return {
            "name": user.name,
            "comment_karma": user.comment_karma,
            "link_karma": user.link_karma,
            "created_utc": self.time_converter.convert_utc_to_eastern(user.created_utc),
            "created_utc_raw": user.created_utc
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
                "created_utc": self.time_converter.convert_utc_to_eastern(comment.created_utc),
                "created_utc_raw": comment.created_utc
            }

    def search_comments(self, subreddit_name, search_words, limit=100):
        subreddit = self.reddit.subreddit(subreddit_name)
        search_terms = [word.lower() for word in search_words.split()]
        
        for comment in subreddit.comments(limit=limit):
            if all(term in comment.body.lower() for term in search_terms):
                yield {
                    "author": str(comment.author),
                    "posted_on": self.time_converter.convert_utc_to_eastern(comment.created_utc),
                    "posted_on_raw": comment.created_utc,
                    "body": comment.body,
                    "permalink": f"https://www.reddit.com{comment.permalink}"
                }

    def stream_comments_formatted(self, subreddit_name):
        subreddit = self.reddit.subreddit(subreddit_name)
        for comment in subreddit.stream.comments():
            yield {
                "datetime": self.time_converter.convert_utc_to_eastern(comment.created_utc),
                "datetime_raw": comment.created_utc,
                "author": str(comment.author),
                "body": comment.body.replace('\n', ' '),  # Replace newlines with spaces
                "url": f"https://www.reddit.com{comment.permalink}"
            }

class UserInterface:
    def __init__(self):
        self.reddit_api = RedditAPI()
        eastern_tz = pytz.timezone('America/New_York')
        current_time = datetime.now(eastern_tz).strftime('%Y%m%d_%H%M%S')
        self.log_file = f"reddit_api_log_{current_time}.txt"

    def log(self, message):
        """
        Records a message both to the console and to the log file.
        The timestamp is always in Eastern Time for consistency.
        
        Parameters:
            message (str): The message to log
        """
        # Get current time in Eastern timezone for consistent logging
        eastern_tz = pytz.timezone('America/New_York')
        current_time = datetime.now(eastern_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
        
        # Format the log entry with timestamp
        log_entry = f"{current_time} - {message}"
        
        # Print to console for immediate feedback
        print(log_entry)
        
        # Write to log file for permanent record
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"{log_entry}\n")
        except IOError as e:
            print(f"Warning: Could not write to log file: {e}")
            print("Continuing execution, but logs may be incomplete.")

    def run(self):
        """
        Main entry point for the user interface.
        Displays menu and handles user interactions in a loop.
        """
        self.log(f"Session started at {datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        while True:
            self.display_menu()
            choice = input("Enter your choice (1-10): ")
            self.handle_choice(choice)

    def display_menu(self):
        """
        Displays the main menu options to the user.
        """
        print("\nReddit API Example Interface")
        print("1. Get top posts from a subreddit")
        print("2. Search for posts containing a keyword")
        print("3. Get user's karma")
        print("4. Stream comments from a subreddit")
        print("5. Stream comments with rate limiting")
        print("6. Stream one comment per second")
        print("7. Search for comments containing a string")
        print("8. Search for comments containing specific words")
        print("9. Stream formatted comments one per second")
        print("10. Exit")

    def handle_choice(self, choice):
        """
        Routes the user's menu selection to the appropriate method.
        
        Parameters:
        choice (str): The user's menu selection
        """
        if choice == '1':
            self.get_top_posts()
        elif choice == '2':
            self.search_posts()
        elif choice == '3':
            self.get_user_karma()
        elif choice == '4':
            self.stream_comments()
        elif choice == '5':
            self.stream_comments_rate_limited()
        elif choice == '6':
            self.stream_comments_one_per_second()
        elif choice == '7':
            self.search_comments()
        elif choice == '8':
            self.search_comments()
        elif choice == '9':
            self.stream_formatted_comments_one_per_second()
        elif choice == '10':
            self.log("Exiting the program. Goodbye!")
            exit()
        else:
            self.log("Invalid choice. Please try again.")

    def get_top_posts(self):
        """
        Retrieves and displays top posts from a specified subreddit.
        """
        subreddit = input("Enter subreddit name: ")
        limit = int(input("Enter number of posts to retrieve: "))
        self.log(f"Getting top {limit} posts from r/{subreddit}")
        for post in self.reddit_api.get_top_posts(subreddit, limit):
            self.log(f"Title: {post['title']}")
            self.log(f"Score: {post['score']}")
            self.log(f"URL: {post['url']}")
            self.log(f"Created: {post['created_utc']}")
            self.log("---")

    def search_posts(self):
        """
        Searches for posts containing a specified keyword across Reddit or within a subreddit.
        """
        keyword = input("Enter keyword to search: ")
        subreddit = input("Enter subreddit name (optional, press Enter to search all): ")
        limit = int(input("Enter number of posts to retrieve: "))
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
        """
        Retrieves and displays karma information for a specified Reddit user.
        """
        username = input("Enter Reddit username: ")
        self.log(f"Getting karma for user: {username}")
        karma = self.reddit_api.get_user_karma(username)
        self.log(f"User: {karma['name']}")
        self.log(f"Comment Karma: {karma['comment_karma']}")
        self.log(f"Link Karma: {karma['link_karma']}")
        self.log(f"Account Created: {karma['created_utc']}")

    def stream_comments(self):
        """
        Streams comments in real-time from a specified subreddit.
        """
        subreddit = input("Enter subreddit name: ")
        limit = int(input("Enter number of comments to stream: "))
        self.log(f"Streaming {limit} comments from r/{subreddit}")
        for comment in self.reddit_api.stream_comments(subreddit, limit):
            self.log(f"Author: {comment['author']}")
            self.log(f"Comment: {comment['body']}")
            self.log(f"Score: {comment['score']}")
            self.log(f"Link: {comment['permalink']}")
            self.log(f"Posted: {comment['created_utc']}")
            self.log("---")

    def search_comments(self):
        """
        Searches for comments containing specific words in a subreddit.
        """
        subreddit = input("Enter subreddit name: ")
        search_words = input("Enter the word(s) to search for in comments (separate multiple words with spaces): ")
        limit = int(input("Enter the number of recent comments to search through (default 100): ") or "100")
        
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
        """
        Streams comments in a formatted way, with optional rate limiting.
        """
        subreddit = input("Enter subreddit name: ")
        duration = input("Enter duration in seconds (optional, press Enter for unlimited): ")
        duration = int(duration) if duration else None
        
        rate_limit = input("Rate limit (y/n)? ").lower() == 'y'
        
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
        """
        Streams comments with a user-defined rate limit.
        """
        subreddit = input("Enter subreddit name: ")
        rate = int(input("Enter rate limit (comments per minute, default 30): ") or "30")
        duration = input("Enter duration in seconds (optional, press Enter for unlimited): ")
        duration = int(duration) if duration else None
        
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
        """
        Streams comments with a one-second delay between each comment.
        """
        subreddit = input("Enter subreddit name: ")
        duration = input("Enter duration in seconds (optional, press Enter for unlimited): ")
        duration = int(duration) if duration else None
        
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

if __name__ == "__main__":
    UserInterface().run()
