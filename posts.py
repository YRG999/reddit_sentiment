# reddit_posts12.py

import praw
import os
import datetime
from dotenv import load_dotenv

class RedditScraper:
    def __init__(self):
        load_dotenv()
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT')
        )

    def get_subreddit(self, subreddit_name):
        try:
            return self.reddit.subreddit(subreddit_name)
        except praw.exceptions.SubredditNotFound as e:
            print(f"Subreddit not found: {e}")
            return None

    def get_posts(self, subreddit, time_limit=1, include_comments=False):
        now = datetime.datetime.now()
        filename = self._generate_filename(subreddit, time_limit, include_comments, now)
        
        print(f"Fetching {'recent posts with comments' if include_comments else 'recent posts'} from subreddit: {subreddit.display_name}")
        print(f"Time Limit: {time_limit} hour(s)")

        try:
            with open(filename, 'w') as outfile:
                self._write_header(outfile, subreddit, time_limit, include_comments, now)
                
                for submission in subreddit.hot(limit=25):
                    if self._is_post_within_time_limit(submission, time_limit, include_comments, now):
                        self._write_post(outfile, submission, now)
        except Exception as e:
            print(f"An error occurred: {e}")

    def _generate_filename(self, subreddit, time_limit, include_comments, now):
        return f"{subreddit.display_name}_{'comments_' if include_comments else ''}{time_limit}hours_{now.strftime('%Y%m%d_%H%M%S')}.txt"

    def _write_header(self, outfile, subreddit, time_limit, include_comments, now):
        outfile.write(f"Subreddit: {subreddit.display_name}\n")
        outfile.write(f"Time Limit: {time_limit} hour(s)\n")
        outfile.write(f"Include Comments: {include_comments}\n")
        outfile.write(f"Timestamp: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n")

    def _is_post_within_time_limit(self, submission, time_limit, include_comments, now):
        submission_time = datetime.datetime.fromtimestamp(submission.created_utc)
        last_comment_time = submission_time

        if include_comments and submission.num_comments > 0:
            last_comment_time = self._get_last_comment_time(submission, submission_time)

        time_difference = (now - last_comment_time).total_seconds() / 3600
        return time_difference <= time_limit

    def _get_last_comment_time(self, submission, default_time):
        last_comment_time = default_time

        for comment in submission.comments:
            if isinstance(comment, praw.models.Comment):
                comment_time = datetime.datetime.fromtimestamp(comment.created_utc)
                if comment_time > last_comment_time:
                    last_comment_time = comment_time
            elif isinstance(comment, praw.models.MoreComments):
                for child_comment in comment.comments():
                    if isinstance(child_comment, praw.models.Comment):
                        child_comment_time = datetime.datetime.fromtimestamp(child_comment.created_utc)
                        if child_comment_time > last_comment_time:
                            last_comment_time = child_comment_time

        return last_comment_time
    
    def _write_post(self, outfile, submission, now):
        submission_time = datetime.datetime.fromtimestamp(submission.created_utc)
        time_difference = (now - submission_time).total_seconds() / 3600
        
        post_info = f"Time Difference: {time_difference:.2f} hours\nTitle: {submission.title}\nURL: {submission.url}\n{'-' * 20}\n"
        print(post_info)
        outfile.write(post_info)

def main():
    scraper = RedditScraper()
    
    subreddit_name = input("Enter the subreddit name (e.g., python): ")
    subreddit = scraper.get_subreddit(subreddit_name)
    
    if subreddit:
        hours = int(input("In the last how many hours? "))
        include_comments = input("Do you want to see posts with comments? (y/n): ").lower() == 'y'
        
        scraper.get_posts(subreddit, hours, include_comments)

if __name__ == "__main__":
    main()
