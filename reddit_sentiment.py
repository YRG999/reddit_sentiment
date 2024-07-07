# reddit_sentiment4b.py
# Claude 3.5 Sonnet-created app to perform sentiment analysis on Reddit posts and comments.
# Add a function to interpret the sentiment and add a function to log the results to a csv file.
# Add a function to get credentials from an .env file.
# Add a function that summarizes the number of comments in a post and lists the number of comments by sentiment and adds it to a separate csv file.

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

# Initialize Reddit API client
credentials = get_credentials()
reddit = praw.Reddit(
    client_id=credentials['client_id'],
    client_secret=credentials['client_secret'],
    user_agent=credentials['user_agent']
)

# Function to get sentiment
def get_sentiment(text):
    return TextBlob(text).sentiment.polarity

# Function to interpret sentiment
def interpret_sentiment(score):
    if score > 0.6:
        return "Strongly Positive"
    elif score > 0.3:
        return "Moderately Positive"
    elif score > 0:
        return "Slightly Positive"
    elif score == 0:
        return "Neutral"
    elif score > -0.3:
        return "Slightly Negative"
    elif score > -0.6:
        return "Moderately Negative"
    else:
        return "Strongly Negative"

# Function to log results to CSV
def log_to_csv(results, filename):
    with open(filename, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Type", "Content", "Sentiment Score", "Sentiment Interpretation", "Timestamp"])
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
        writer.writerow(["Post Title", "Total Comments", "Strongly Positive", "Moderately Positive", 
                         "Slightly Positive", "Neutral", "Slightly Negative", "Moderately Negative", 
                         "Strongly Negative"])
        for summary in summaries:
            writer.writerow([
                summary["post_title"],
                summary["total_comments"],
                summary["sentiment_breakdown"].get("Strongly Positive", 0),
                summary["sentiment_breakdown"].get("Moderately Positive", 0),
                summary["sentiment_breakdown"].get("Slightly Positive", 0),
                summary["sentiment_breakdown"].get("Neutral", 0),
                summary["sentiment_breakdown"].get("Slightly Negative", 0),
                summary["sentiment_breakdown"].get("Moderately Negative", 0),
                summary["sentiment_breakdown"].get("Strongly Negative", 0)
            ])

# Get subreddit name and max posts to read
subreddit = reddit.subreddit(input("Subreddit? "))
limit = int(input("Limit (int)? "))

results = []
summaries = []
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for post in subreddit.hot(limit=limit):
    post_sentiment_score = get_sentiment(post.title)
    post_sentiment_interpret = interpret_sentiment(post_sentiment_score)
    results.append(["Post", post.title, post_sentiment_score, post_sentiment_interpret, timestamp])
    
    post_comments = []
    post.comments.replace_more(limit=0)
    for comment in post.comments.list():
        comment_sentiment_score = get_sentiment(comment.body)
        comment_sentiment_interpret = interpret_sentiment(comment_sentiment_score)
        comment_data = ["Comment", comment.body[:100], comment_sentiment_score, comment_sentiment_interpret, timestamp]
        results.append(comment_data)
        post_comments.append(comment_data)
    
    summary = summarize_comments(post, post_comments)
    summaries.append(summary)

log_to_csv(results, f"reddit_sentiment_analysis_{subreddit}.csv")
print("Detailed results have been logged to reddit_sentiment_analysis.csv")

log_summaries_to_csv(summaries, f"reddit_sentiment_summaries_{subreddit}.csv")
print(f"Comment summaries have been logged to reddit_sentiment_summaries_{subreddit}.csv")