# summarizereddit9b.py
# v1 - Get posts & comments for subreddits & use OpenAI to summarize.
# v2 - update summarize_content to uses latest API pattern.
# v3 - Annotate summary w/ footnotes for links that go to the URLs for the actual post or comment.
# v4 - Add content limits to reduce tokens to handle rate limits if hit.
# v5 - Add text cleaning to reduce content token size.
# v6 - Add more aggressive content reduction.
# v7 - Add functions to focus on specific topics within the subreddit and save summaries to a file.
# v8 - Update save files to save results of questions. Ask user if they want to store the raw content.
# v9 - Remove duplicate "Summary generated" from output file
# v9b - name change to summarize_openai.py

import praw
import os
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import time
import tiktoken
import json
import string
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

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
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        self.MAX_TOKENS = 8000
        
        # Download required NLTK data
        try:
            nltk.data.find('tokenizers/punkt')
            nltk.data.find('corpora/stopwords')
        except LookupError:
            print("Downloading required NLTK data...")
            nltk.download('punkt')
            nltk.download('stopwords')

    def _load_credentials(self):
        """Load environment variables from .env file"""
        load_dotenv()

    def clean_text(self, text):
        """
        Clean and normalize text content
        
        Parameters:
        text (str): Raw text to clean
        
        Returns:
        str: Cleaned text
        """
        if not text:
            return ""
            
        try:
            # Convert to lowercase
            text = text.lower()
            
            # Tokenize the text
            tokens = word_tokenize(text)
            
            # Remove punctuation
            tokens = [token for token in tokens if token not in string.punctuation]
            
            # Remove stop words
            stop_words = set(stopwords.words('english'))
            tokens = [token for token in tokens if token not in stop_words]
            
            # Join tokens back together
            return ' '.join(tokens)
        except Exception as e:
            print(f"Warning: Error cleaning text: {str(e)}")
            return text

    def count_tokens(self, text):
        """Count the number of tokens in a text string"""
        return len(self.tokenizer.encode(text))

    def get_recent_content(self, subreddit_name, hours, clean=True):
        """
        Get recent posts and comments from a subreddit within specified timeframe
        
        Parameters:
        subreddit_name (str): Name of the subreddit
        hours (int): Number of hours to look back
        clean (bool): Whether to clean the text content
        """
        subreddit = self.reddit.subreddit(subreddit_name)
        current_time = datetime.now(pytz.UTC)
        cutoff_time = current_time - timedelta(hours=hours)
        
        posts = []
        for post in subreddit.new(limit=100):
            post_time = datetime.fromtimestamp(post.created_utc, pytz.UTC)
            if post_time < cutoff_time:
                break
                
            # Store both raw and cleaned content
            post_content = post.selftext
            cleaned_content = self.clean_text(post_content) if clean else post_content
            
            posts.append({
                'title': post.title,
                'content': cleaned_content,
                'raw_content': post_content,  # Keep original for reference
                'score': post.score,
                'url': f"https://www.reddit.com{post.permalink}",
                'created_utc': post_time.astimezone(self.eastern_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            })

        comments = []
        for comment in subreddit.comments(limit=200):
            comment_time = datetime.fromtimestamp(comment.created_utc, pytz.UTC)
            if comment_time < cutoff_time:
                break
                
            # Store both raw and cleaned content
            comment_body = comment.body
            cleaned_body = self.clean_text(comment_body) if clean else comment_body
            
            comments.append({
                'body': cleaned_body,
                'raw_body': comment_body,  # Keep original for reference
                'score': comment.score,
                'url': f"https://www.reddit.com{comment.permalink}",
                'created_utc': comment_time.astimezone(self.eastern_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            })

        return {'posts': posts, 'comments': comments}

    def prepare_summary_prompt(self, content, subreddit_name, content_limit=None):
        """Prepare the summary prompt, optionally with content limits"""
        references = []
        ref_counter = 1
        
        base_prompt = f"""Please summarize the following content from r/{subreddit_name}. 
Include key themes, notable discussions, and overall sentiment.

When mentioning specific posts or comments, use numbered references [n] that I will replace with proper links. 
For example: "Users discussed the impact of AI [1] and debated renewable energy [2]"

Here's the content to summarize:\n\n"""
        
        summary_prompt = base_prompt + "POSTS:\n"
        
        # Add posts
        for post in content['posts']:
            references.append(post['url'])
            post_entry = f"- [{ref_counter}] {post['title']}\n"
            if post['content']:  # Use cleaned content
                if content_limit:
                    post_entry += f"  Content: {post['content'][:content_limit]}...\n"
                else:
                    post_entry += f"  Content: {post['content']}\n"
            summary_prompt += post_entry
            ref_counter += 1
        
        # Add comments
        summary_prompt += "\nCOMMENTS (sample):\n"
        for comment in content['comments'][:10]:
            references.append(comment['url'])
            if content_limit:
                summary_prompt += f"- [{ref_counter}] {comment['body'][:content_limit]}...\n"
            else:
                summary_prompt += f"- [{ref_counter}] {comment['body']}\n"
            ref_counter += 1
        
        return summary_prompt, references

    def summarize_content(self, content, subreddit_name, max_retries=3):
        """Summarize content with automatic token reduction only if we hit rate limits"""
        retry_count = 0
        content_limit = None
        target_tokens = 8000  # Target total tokens for the request
        
        while retry_count < max_retries:
            try:
                summary_prompt, references = self.prepare_summary_prompt(content, subreddit_name, content_limit)
                
                # Count tokens in the entire prompt
                total_tokens = self.count_tokens(summary_prompt)
                
                # If we're over our target before even trying the API call
                if total_tokens > target_tokens:
                    if content_limit is None:
                        content_limit = 500  # Start more conservatively
                    else:
                        content_limit = int(content_limit * 0.5)  # Reduce more aggressively
                    print(f"Preemptively reducing content to {content_limit} characters (total tokens: {total_tokens})")
                    continue
                
                print(f"Attempting request with {total_tokens} tokens...")
                
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
                error_str = str(e)
                if "Request too large" in error_str or "rate_limit_exceeded" in error_str:
                    retry_count += 1
                    if content_limit is None:
                        content_limit = 500  # Start more conservatively
                    else:
                        content_limit = int(content_limit * 0.5)  # Reduce more aggressively
                    print(f"Hit rate limit. Reducing content to {content_limit} characters per item and retrying...")
                    if retry_count >= max_retries:
                        return f"Error: Unable to generate summary after {max_retries} attempts to reduce content. Last error: {str(e)}", []
                else:
                    return f"Error generating summary: {str(e)}", []

    def filter_content_by_topics(self, content, topics):
        """
        Filter content to only include posts and comments related to specified topics
        
        Parameters:
        content (dict): Dictionary containing posts and comments
        topics (list): List of topics to filter by
        
        Returns:
        dict: Filtered content dictionary
        """
        # Helper function to check if any topic is present in text
        def contains_topics(text):
            text_lower = text.lower()
            return any(topic in text_lower for topic in topics)
        
        # Filter posts
        filtered_posts = [
            post for post in content['posts']
            if contains_topics(post['title']) or contains_topics(post['content'])
        ]
        
        # Filter comments
        filtered_comments = [
            comment for comment in content['comments']
            if contains_topics(comment['body'])
        ]
        
        return {
            'posts': filtered_posts,
            'comments': filtered_comments
        }

    def format_summary_with_footnotes(self, summary, references):
        """
        Format the summary text with numbered footnotes and their corresponding URLs
        
        Parameters:
        summary (str): Summary text
        references (list): List of reference URLs
        
        Returns:
        str: Formatted summary with footnotes
        """
        formatted_text = summary + "\n\nReferences:\n"
        for i, url in enumerate(references, 1):
            formatted_text += f"[{i}] {url}\n"
        return formatted_text

def save_summary_to_file(subreddit, summary, analysis_params, content=None):
    """
    Save summary and optionally raw data to files with timestamp
    
    Parameters:
    subreddit (str): Name of the subreddit
    summary (str): Formatted summary text
    analysis_params (dict): Dictionary containing analysis parameters
    content (dict, optional): Raw content data to save
    
    Returns:
    tuple: Paths to saved files
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    saved_files = []

    # Create summary file with metadata
    summary_filename = f"summary_{subreddit}_{timestamp}.txt"
    with open(summary_filename, 'w', encoding='utf-8') as f:
        # Write analysis parameters
        f.write("ANALYSIS PARAMETERS:\n")
        f.write(f"Subreddit name: {analysis_params['subreddit']}\n")
        f.write(f"Hours analyzed: {analysis_params['hours']}\n")
        f.write(f"Topics: {', '.join(analysis_params['topics']) if analysis_params['topics'] else 'No topic filter'}\n")
        f.write(f"Clean text content: {'Yes' if analysis_params['clean_text'] else 'No'}\n")
        f.write(f"Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
        f.write("\n" + "="*50 + "\n\n")
        
        # Write the summary
        f.write(summary)
    
    saved_files.append(summary_filename)

    # Save raw data if provided
    if content:
        raw_filename = f"raw_data_{subreddit}_{timestamp}.json"
        with open(raw_filename, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        saved_files.append(raw_filename)

    return saved_files

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
    
    # Get topic filters
    topics_input = input("Enter topics to focus on (comma-separated, or press Enter for no filter): ")
    topics = [topic.strip().lower() for topic in topics_input.split(',')] if topics_input.strip() else []
    
    # Ask about text cleaning
    clean_text = input("Clean text content? (y/n): ").lower() == 'y'
    
    # Ask about saving files
    save_to_file = input("Save summaries to files? (y/n): ").lower() == 'y'
    save_raw_data = input("Save raw data too? (y/n): ").lower() == 'y' if save_to_file else False

    # Process each subreddit
    for subreddit in subreddits:
        print(f"\nAnalyzing r/{subreddit}...")
        try:
            # Get content and filter by topics if specified
            content = summarizer.get_recent_content(subreddit, hours, clean=clean_text)
            
            if topics:
                content = summarizer.filter_content_by_topics(content, topics)
                print(f"Found {len(content['posts'])} posts and {len(content['comments'])} comments matching topics: {', '.join(topics)}")
            else:
                print(f"Found {len(content['posts'])} posts and {len(content['comments'])} comments")
            
            if not content['posts'] and not content['comments']:
                print(f"No content found matching the specified topics in r/{subreddit}")
                continue
            
            print("\nGenerating summary...")
            summary, references = summarizer.summarize_content(content, subreddit)
            formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
            
            print("\nSUMMARY:")
            print(formatted_summary)
            
            # Save to file if requested
            if save_to_file:
                analysis_params = {
                    'subreddit': subreddit,
                    'hours': hours,
                    'topics': topics,
                    'clean_text': clean_text,
                }
                
                # Save with or without raw data based on user choice
                saved_files = save_summary_to_file(
                    subreddit,
                    formatted_summary,
                    analysis_params,
                    content if save_raw_data else None
                )
                
                print("\nFiles saved:")
                for filename in saved_files:
                    print(f"- {filename}")
            
            print("\n" + "="*50 + "\n")
            
        except Exception as e:
            print(f"Error processing r/{subreddit}: {str(e)}")
            continue

if __name__ == "__main__":
    main()
