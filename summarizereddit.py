# summarizereddit3.py
# v1- Use the following code (comments11.py and openai-quickstart-python/gpt4sample.py) to create a new program
# that asks the user for one to many subreddit names, a number of hours to get posts and comments, 
# gets posts and comments for from the subreddit for that timeframe, and uses an OpenAI model 
# to summarize the posts for each subreddit.
# v2 - update summarize_content so it uses the latest API pattern.
# v3- Add code that annotates the summary with links that go to the URLs for the actual post or comment, 
# in the form of a numbered footnote.

import praw
import os
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import time

class RedditSummarizer:
    def __init__(self):
        self._load_credentials()
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT')
        )
        self.client = OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.eastern_tz = pytz.timezone('America/New_York')

    def _load_credentials(self):
        """Load environment variables from .env file"""
        load_dotenv()

    def get_recent_content(self, subreddit_name, hours):
        """
        Get recent posts and comments from a subreddit within specified timeframe
        
        Parameters:
        subreddit_name (str): Name of the subreddit
        hours (int): Number of hours to look back
        
        Returns:
        dict: Dictionary containing posts and comments from the timeframe
        """
        subreddit = self.reddit.subreddit(subreddit_name)
        current_time = datetime.now(pytz.UTC)
        cutoff_time = current_time - timedelta(hours=hours)
        
        # Get recent posts
        posts = []
        for post in subreddit.new(limit=100):  # Adjust limit as needed
            post_time = datetime.fromtimestamp(post.created_utc, pytz.UTC)
            if post_time < cutoff_time:
                break
            posts.append({
                'title': post.title,
                'content': post.selftext,
                'score': post.score,
                'url': f"https://www.reddit.com{post.permalink}",
                'created_utc': post_time.astimezone(self.eastern_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            })

        # Get recent comments
        comments = []
        for comment in subreddit.comments(limit=200):  # Adjust limit as needed
            comment_time = datetime.fromtimestamp(comment.created_utc, pytz.UTC)
            if comment_time < cutoff_time:
                break
            comments.append({
                'body': comment.body,
                'score': comment.score,
                'url': f"https://www.reddit.com{comment.permalink}",
                'created_utc': comment_time.astimezone(self.eastern_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            })

        return {'posts': posts, 'comments': comments}

    def summarize_content(self, content, subreddit_name):
        """
        Use OpenAI to summarize the subreddit content
        
        Parameters:
        content (dict): Dictionary containing posts and comments
        subreddit_name (str): Name of the subreddit being summarized
        
        Returns:
        tuple: (Summary text, list of reference URLs)
        """
        # Initialize reference tracking
        references = []
        ref_counter = 1
        
        # Prepare content for summarization
        summary_prompt = f"""Please summarize the following content from r/{subreddit_name}. 
Include key themes, notable discussions, and overall sentiment.

When mentioning specific posts or comments, use numbered references [n] that I will replace with proper links. 
For example: "Users discussed the impact of AI [1] and debated renewable energy [2]"

Here's the content to summarize:\n\n"""
        
        # Add posts to prompt
        summary_prompt += "POSTS:\n"
        for post in content['posts']:
            references.append(post['url'])
            summary_prompt += f"- [{ref_counter}] {post['title']}\n"
            if post['content']:
                summary_prompt += f"  Content: {post['content'][:500]}...\n"
            ref_counter += 1
        
        # Add comments to prompt
        summary_prompt += "\nCOMMENTS (sample):\n"
        for comment in content['comments'][:10]:
            references.append(comment['url'])
            summary_prompt += f"- [{ref_counter}] {comment['body'][:200]}...\n"
            ref_counter += 1

        try:
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": """You are a helpful assistant that summarizes Reddit content clearly and concisely. 
                        Use numbered references [n] when mentioning specific posts or comments."""
                    },
                    {
                        "role": "user",
                        "content": summary_prompt
                    }
                ],
                model="gpt-4",
            )
            return chat_completion.choices[0].message.content, references
        except Exception as e:
            return f"Error generating summary: {str(e)}", []

    def format_summary_with_footnotes(self, summary, references):
        """
        Format the summary text with numbered footnotes and their corresponding URLs
        
        Parameters:
        summary (str): The summary text with [n] references
        references (list): List of URLs corresponding to the references
        
        Returns:
        str: Formatted summary with footnotes
        """
        formatted_text = summary + "\n\nReferences:\n"
        for i, url in enumerate(references, 1):
            formatted_text += f"[{i}] {url}\n"
        return formatted_text

def main():
    summarizer = RedditSummarizer()
    
    # Get subreddit names
    subreddits_input = input("Enter subreddit name(s) separated by commas: ")
    subreddits = [s.strip() for s in subreddits_input.split(',')]
    
    # Get timeframe
    while True:
        try:
            hours = int(input("Enter number of hours to analyze: "))
            if hours > 0:
                break
            print("Please enter a positive number of hours.")
        except ValueError:
            print("Please enter a valid number.")

    # Process each subreddit
    for subreddit in subreddits:
        print(f"\nAnalyzing r/{subreddit}...")
        try:
            # Get content
            content = summarizer.get_recent_content(subreddit, hours)
            
            # Print basic stats
            print(f"Found {len(content['posts'])} posts and {len(content['comments'])} comments")
            
            # Generate and print summary
            print("\nGenerating summary...")
            summary, references = summarizer.summarize_content(content, subreddit)
            formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
            print("\nSUMMARY:")
            print(formatted_summary)
            
            # Add a separator between subreddits
            print("\n" + "="*50 + "\n")
            
        except Exception as e:
            print(f"Error processing r/{subreddit}: {str(e)}")
            continue

if __name__ == "__main__":
    main()
