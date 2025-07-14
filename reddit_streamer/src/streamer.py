# streamer2.py

import praw
import os
import json
import time
import re
from datetime import datetime
from dotenv import load_dotenv
import pathlib

# Load .env from two levels above
env_path = pathlib.Path(__file__).parents[2] / '.env'
load_dotenv(dotenv_path=env_path)

def sanitize_filename(name):
    # Only allow alphanumeric, dash, and underscore
    return re.sub(r'[^A-Za-z0-9_\-]', '_', name)

def main():
    # Prompt user for subreddit name and total items to report
    subreddit_name = input("Enter the subreddit name: ")
    total_items = int(input("Enter the total number of items to report: "))

    # Sanitize subreddit name for filename safety
    safe_subreddit = sanitize_filename(subreddit_name)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_filename = f"{safe_subreddit}_data_{timestamp}.json"
    log_path = os.path.join(log_dir, log_filename)

    # Initialize Reddit client
    reddit = praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent=os.getenv('REDDIT_USER_AGENT')
    )

    # Prepare to log data
    log_data = []

    # Stream posts and comments, mix and sort by date
    print(f"Streaming data from r/{subreddit_name}...")

    # Collect posts
    posts = []
    for submission in reddit.subreddit(subreddit_name).new(limit=total_items):
        posts.append({
            'type': 'post',
            'title': submission.title,
            'body': submission.selftext,
            'url': submission.url,
            'created_utc': submission.created_utc,
            'score': submission.score
        })

    # Collect comments
    comments = []
    for submission in reddit.subreddit(subreddit_name).new(limit=total_items):
        submission.comments.replace_more(limit=0)
        for comment in submission.comments.list():
            comments.append({
                'type': 'comment',
                'body': comment.body,
                'url': f"https://www.reddit.com{comment.permalink}",
                'created_utc': comment.created_utc,
                'score': comment.score
            })
            if len(comments) >= total_items:
                break
        if len(comments) >= total_items:
            break

    # Combine and sort by date (most recent first)
    combined = posts + comments
    combined.sort(key=lambda x: x['created_utc'], reverse=True)
    combined = combined[:total_items]

    # Print and log
    for item in combined:
        date_str = datetime.utcfromtimestamp(item['created_utc']).strftime('%Y-%m-%d %H:%M:%S UTC')
        if item['type'] == 'post':
            print(f"[{date_str}] Post: {item['title']}\n{item['body']}\n")
        else:
            print(f"[{date_str}] Comment:\n{item['body']}\n")
        log_data.append(item)
        time.sleep(1)

    # Save log data to file
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(log_data, f, ensure_ascii=False, indent=2)

    print(f"Data logged to {log_path}")

if __name__ == "__main__":
    main()