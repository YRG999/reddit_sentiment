# reddit_sentiment6.py
# Claude 3.5 Sonnet-created app to perform sentiment analysis on Reddit posts and comments.
# Add a function to interpret the sentiment and add a function to log the results to a csv file.
# Add a function to get credentials from an .env file.
# Add a function that summarizes the number of comments in a post and lists the number of comments by sentiment and adds it to a separate csv file.
# Modify the code to also return the post date for the post or comment.
# Optimize the code. For example, create functions to ask the user whether to get posts that are "hot" or "new".

import praw
from textblob import TextBlob
import csv
from datetime import datetime
from dotenv import load_dotenv
import os
from collections import Counter

# Function to get credentials from .env file
def get_credentials():
    load_dotenv()  # This loads the .env file
    return {
        'client_id': os.getenv('REDDIT_CLIENT_ID'),
        'client_secret': os.getenv('REDDIT_CLIENT_SECRET'),
        'user_agent': os.getenv('REDDIT_USER_AGENT')
    }

# Function to get sentiment
def get_sentiment(text):
    return TextBlob(text).sentiment.polarity

# Function to interpret sentiment
def interpret_sentiment(score):
    if score > 0.6:
        return "Positive++"
    elif score > 0.3:
        return "Positive+"
    elif score > 0:
        return "Positive"
    elif score == 0:
        return "Neutral"
    elif score > -0.3:
        return "Negative"
    elif score > -0.6:
        return "Negative-"
    else:
        return "Negative--"

# Function to log results to CSV
def log_to_csv(results, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        # writer.writerow(["Type", "Content", "Sentiment Score", "Sentiment Interpretation", "Timestamp"])
        # writer.writerow(["Type", "Content", "Score", "Interpretation", "Timestamp", "Creation"])
        writer.writerow(["Type", "Content", "Score", "Interpretation", "Created"])
        for result in results:
            writer.writerow(result)

# Function to Summarize comments
def summarize_comments(post, comments):
    total_comments = len(comments)
    sentiment_counts = Counter(comment[3] for comment in comments)  # Count sentiments
    
    summary = {
        "post_title": post.title,
        "total_comments": total_comments,
        "sentiment_breakdown": dict(sentiment_counts)
    }
    return summary

# Function to log summaries to CSV
def log_summaries_to_csv(summaries, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Post Title", "Total Comments", "Positive++", "Positive+", 
                         "Positive", "Neutral", "Negative", "Negative-", 
                         "Negative--"])
        for summary in summaries:
            writer.writerow([
                summary["post_title"],
                summary["total_comments"],
                summary["sentiment_breakdown"].get("Positive++", 0),
                summary["sentiment_breakdown"].get("Positive+", 0),
                summary["sentiment_breakdown"].get("Positive", 0),
                summary["sentiment_breakdown"].get("Neutral", 0),
                summary["sentiment_breakdown"].get("Negative", 0),
                summary["sentiment_breakdown"].get("Negative-", 0),
                summary["sentiment_breakdown"].get("Negative--", 0)
            ])

def get_user_input():
    subreddit_name = input("Subreddit? ")
    limit = int(input("Limit (int)? "))
    sort_method = input("Sort by (hot/new)? ").lower()
    while sort_method not in ['hot', 'new']:
        sort_method = input("Invalid input. Please enter 'hot' or 'new': ").lower()
    return subreddit_name, limit, sort_method

def get_sorted_posts(subreddit, sort_method, limit):
    if sort_method == 'hot':
        return subreddit.hot(limit=limit)
    elif sort_method == 'new':
        return subreddit.new(limit=limit)

def analyze_post(post, current_timestamp):
    post_date = datetime.fromtimestamp(post.created_utc).strftime("%Y-%m-%d %H:%M:%S")
    post_sentiment_score = get_sentiment(post.title)
    post_sentiment_interpret = interpret_sentiment(post_sentiment_score)
    return ["Post", post.title, post_sentiment_score, post_sentiment_interpret, post_date]

def analyze_comments(post):
    post_comments = []
    post.comments.replace_more(limit=0)
    for comment in post.comments.list():
        comment_date = datetime.fromtimestamp(comment.created_utc).strftime("%Y-%m-%d %H:%M:%S")
        comment_sentiment_score = get_sentiment(comment.body)
        comment_sentiment_interpret = interpret_sentiment(comment_sentiment_score)
        comment_data = ["Comment", comment.body[:100], comment_sentiment_score, comment_sentiment_interpret, comment_date]
        post_comments.append(comment_data)
    return post_comments

def main():
    # Initialize Reddit API client
    credentials = get_credentials()
    reddit = praw.Reddit(
        client_id=credentials['client_id'],
        client_secret=credentials['client_secret'],
        user_agent=credentials['user_agent']
    )

    subreddit_name, limit, sort_method = get_user_input()
    subreddit = reddit.subreddit(subreddit_name)

    results = []
    summaries = []
    current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for post in get_sorted_posts(subreddit, sort_method, limit):
        post_data = analyze_post(post, current_timestamp)
        results.append(post_data)
        
        post_comments = analyze_comments(post)
        results.extend(post_comments)
        
        summary = summarize_comments(post, post_comments)
        summaries.append(summary)

    log_to_csv(results, f"reddit_sentiment_analysis_{subreddit_name}_{sort_method}.csv")
    print(f"Detailed results have been logged to reddit_sentiment_analysis_{subreddit_name}_{sort_method}.csv")

    log_summaries_to_csv(summaries, f"reddit_sentiment_summaries_{subreddit_name}_{sort_method}.csv")
    print(f"Comment summaries have been logged to reddit_sentiment_summaries_{subreddit_name}_{sort_method}.csv")

if __name__ == "__main__":
    main()