# reddit_comments9.py

import praw
import time
import os
from dotenv import load_dotenv
from datetime import datetime

class RedditAPI:
    def __init__(self):
        credentials = self.get_credentials()
        self.reddit = praw.Reddit(
            client_id=credentials['client_id'],
            client_secret=credentials['client_secret'],
            user_agent=credentials['user_agent']
        )

    @staticmethod
    def get_credentials():
        load_dotenv()
        return {
            'client_id': os.getenv('REDDIT_CLIENT_ID'),
            'client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
            'user_agent': os.getenv('REDDIT_USER_AGENT')
        }

    def get_top_posts(self, subreddit_name, limit=10):
        subreddit = self.reddit.subreddit(subreddit_name)
        for post in subreddit.top(limit=limit):
            yield {
                "title": post.title,
                "score": post.score,
                "url": post.url
            }

    def search_posts(self, keyword, subreddit_name=None, limit=10):
        if subreddit_name:
            results = self.reddit.subreddit(subreddit_name).search(keyword, limit=limit)
        else:
            results = self.reddit.search(keyword, limit=limit)
        
        for post in results:
            yield {
                "title": post.title,
                "subreddit": post.subreddit.display_name,
                "score": post.score,
                "url": post.url
            }

    def get_user_karma(self, username):
        user = self.reddit.redditor(username)
        return {
            "name": user.name,
            "comment_karma": user.comment_karma,
            "link_karma": user.link_karma
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
                "permalink": f"https://www.reddit.com{comment.permalink}"
            }

    def search_comments(self, subreddit_name, search_words, limit=100):
        subreddit = self.reddit.subreddit(subreddit_name)
        search_terms = [word.lower() for word in search_words.split()]
        
        for comment in subreddit.comments(limit=limit):
            if all(term in comment.body.lower() for term in search_terms):
                yield {
                    "author": str(comment.author),
                    "posted_on": datetime.fromtimestamp(comment.created_utc).strftime('%Y-%m-%d %H:%M:%S UTC'),
                    "body": comment.body,
                    "permalink": f"https://www.reddit.com{comment.permalink}"
                }

    def stream_comments_formatted(self, subreddit_name):
        subreddit = self.reddit.subreddit(subreddit_name)
        for comment in subreddit.stream.comments():
            yield {
                "datetime": datetime.fromtimestamp(comment.created_utc).strftime('%Y-%m-%d_%H:%M:%S'),
                "author": str(comment.author),
                "body": comment.body.replace('\n', ' '),  # Replace newlines with spaces
                "url": f"https://www.reddit.com{comment.permalink}"
            }

class UserInterface:
    def __init__(self):
        self.reddit_api = RedditAPI()
        self.log_file = f"reddit_api_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    def run(self):
        self.log(f"Session started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        while True:
            self.display_menu()
            choice = input("Enter your choice (1-10): ")
            self.handle_choice(choice)

    def display_menu(self):
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

    def log(self, message):
        print(message)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

    def get_top_posts(self):
        subreddit = input("Enter subreddit name: ")
        limit = int(input("Enter number of posts to retrieve: "))
        self.log(f"Getting top {limit} posts from r/{subreddit}")
        for post in self.reddit_api.get_top_posts(subreddit, limit):
            self.log(f"Title: {post['title']}")
            self.log(f"Score: {post['score']}")
            self.log(f"URL: {post['url']}")
            self.log("---")

    def search_posts(self):
        keyword = input("Enter keyword to search: ")
        subreddit = input("Enter subreddit name (optional, press Enter to search all): ")
        limit = int(input("Enter number of posts to retrieve: "))
        self.log(f"Searching for '{keyword}' in {subreddit if subreddit else 'all subreddits'}")
        for post in self.reddit_api.search_posts(keyword, subreddit if subreddit else None, limit):
            self.log(f"Title: {post['title']}")
            self.log(f"Subreddit: {post['subreddit']}")
            self.log(f"Score: {post['score']}")
            self.log(f"URL: {post['url']}")
            self.log("---")

    def get_user_karma(self):
        username = input("Enter Reddit username: ")
        self.log(f"Getting karma for user: {username}")
        karma = self.reddit_api.get_user_karma(username)
        self.log(f"User: {karma['name']}")
        self.log(f"Comment Karma: {karma['comment_karma']}")
        self.log(f"Link Karma: {karma['link_karma']}")

    def stream_comments(self):
        subreddit = input("Enter subreddit name: ")
        limit = int(input("Enter number of comments to stream: "))
        self.log(f"Streaming {limit} comments from r/{subreddit}")
        for comment in self.reddit_api.stream_comments(subreddit, limit):
            self.log(f"Author: {comment['author']}")
            self.log(f"Comment: {comment['body']}")
            self.log(f"Score: {comment['score']}")
            self.log(f"Link: {comment['permalink']}")
            self.log("---")

    def stream_comments_rate_limited(self):
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

                self.log(comment['body'])

                time_to_wait = 1 - (time.time() - current_time)
                if time_to_wait > 0:
                    time.sleep(time_to_wait)

        except KeyboardInterrupt:
            self.log("Stream stopped by user.")

    def stream_formatted_comments_one_per_second(self):
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
                else:
                    time_to_wait = 0

        except KeyboardInterrupt:
            self.log("Stream stopped by user.")

    def search_comments(self):
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

if __name__ == "__main__":
    UserInterface().run()