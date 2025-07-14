# summarizereddit13.py
# Update from v11 - Add a list of references that links the post and comment number to the URL
# Update from v12 - Add Ollama support

import praw
import os
from openai import OpenAI
import anthropic
from dotenv import load_dotenv
from datetime import datetime, timedelta
import pytz
import tiktoken
import json
import string
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

class RedditSummarizer:
    def __init__(self):
        self._load_credentials()
        
        # Initialize Reddit client
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT')
        )
        
        # Initialize OpenAI client
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            self.openai_client = OpenAI(api_key=openai_key)
        else:
            self.openai_client = None
            
        # Initialize Anthropic client
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            self.claude_client = anthropic.Anthropic(api_key=anthropic_key)
        else:
            self.claude_client = None
        self.eastern_tz = pytz.timezone('America/New_York')
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        self.MAX_TOKENS = 8000
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "gemma3")


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
        for comment in subreddit.comments(limit=500): # Adjust limit as needed. 200 is a reasonable number to avoid rate limits.
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

When mentioning specific posts or comments, use numbered references [n]. 
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

    def prepare_claude_content(self, content, subreddit_name):
        """
        Prepare content in Claude's document format with citations
        """
        # Create a single document with all content
        formatted_content = f"Content from r/{subreddit_name}:\n\n"
        formatted_content += "POSTS:\n"
        
        # Store references
        references = []
        
        # Add posts
        for i, post in enumerate(content['posts'], 1):
            formatted_content += f"Post {i}:\n"
            formatted_content += f"Title: {post['title']}\n"
            if post['content']:
                formatted_content += f"Content: {post['content']}\n"
            formatted_content += f"Posted: {post['created_utc']}\n\n"
            references.append((f"Post {i}", post['url']))

        # Add comments
        formatted_content += "COMMENTS:\n"
        for i, comment in enumerate(content['comments'][:10], 1):  # Limit to 10 comments
            formatted_content += f"Comment {i}:\n"
            formatted_content += f"Content: {comment['body']}\n"
            formatted_content += f"Posted: {comment['created_utc']}\n\n"
            references.append((f"Comment {i}", comment['url']))

        # Return both the formatted content and references
        return [{
            "type": "text",
            "text": formatted_content
        }], references

        return {
            "type": "document",
            "source": {
                "type": "text",
                "media_type": "text/plain",
                "data": formatted_content
            },
            "title": f"r/{subreddit_name} Content",
            "citations": {"enabled": True}
        }

    def summarize_with_claude(self, content, subreddit_name):
        """
        Summarize content using Claude API with citations
        """
        if not self.claude_client:
            return "Error: Anthropic API key not found in environment variables. Please add ANTHROPIC_API_KEY to your .env file."
            
        try:
            documents, references = self.prepare_claude_content(content, subreddit_name)
            
            # Create the message content by adding the prompt after the content
            message_content = documents + [{
                "type": "text",
                "text": f"""Please provide a comprehensive summary of this Reddit content from r/{subreddit_name}. In your summary:
                
                1. Identify and analyze key themes and topics
                2. Highlight notable opinions and insights
                3. Describe the overall sentiment and mood
                4. Point out any significant debates or controversies
                
                Please reference specific posts and comments in your analysis. When mentioning content, specify which Post or Comment number you're referring to."""
            }]
            
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": message_content
                }]
            )
            
            # Extract and check the response
            if hasattr(response, 'content') and len(response.content) > 0:
                summary = response.content[0].text
                if not summary.strip():
                    return "Error: Received empty summary from Claude"
                    
                # Add references in markdown format
                summary += "\n\nReferences:\n"
                for ref_name, url in references:
                    summary += f"[{ref_name}]({url})\n"
                    
                return summary
            else:
                return "Error: Unable to get summary from Claude's response"
            
        except Exception as e:
            return f"Error generating summary with Claude: {str(e)}"

    def summarize_with_openai(self, content, subreddit_name, use_rate_limiting=True, max_retries=3):
        """
        Summarize content using OpenAI API (previous summarize_content method)
        
        Parameters:
        content (dict): Content to summarize
        subreddit_name (str): Name of the subreddit
        use_rate_limiting (bool): Whether to use rate limiting
        max_retries (int): Maximum number of retries if rate limited
        """
        retry_count = 0
        content_limit = None
        target_tokens = 8000  # Target total tokens for the request
        
        while retry_count < max_retries:
            try:
                summary_prompt, references = self.prepare_summary_prompt(content, subreddit_name, content_limit)
                
                # Count tokens in the entire prompt
                total_tokens = self.count_tokens(summary_prompt)
                
                # Only apply token limiting if use_rate_limiting is True
                if use_rate_limiting and total_tokens > target_tokens:
                    if content_limit is None:
                        content_limit = 500  # Start more conservatively
                    else:
                        content_limit = int(content_limit * 0.5)  # Reduce more aggressively
                    print(f"Preemptively reducing content to {content_limit} characters (total tokens: {total_tokens})")
                    continue
                
                print(f"Attempting request with {total_tokens} tokens...")
                
                chat_completion = self.openai_client.chat.completions.create(
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a helpful assistant that summarizes Reddit content clearly and concisely. Use numbered references [n] when mentioning specific posts or comments."""
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
                if use_rate_limiting and ("Request too large" in error_str or "rate_limit_exceeded" in error_str):
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

    def summarize_with_ollama(self, content, subreddit_name):
        """
        Summarize content using Ollama Python library (local LLM)
        """
        try:
            from ollama import chat
            summary_prompt, references = self.prepare_summary_prompt(content, subreddit_name)
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that summarizes Reddit content clearly and concisely. Use numbered references [n] when mentioning specific posts or comments."
                },
                {
                    "role": "user",
                    "content": summary_prompt
                }
            ]
            response = chat(model=self.ollama_model, messages=messages)
            # Try both dict and attribute access for compatibility
            summary = response['message']['content'] if 'message' in response and 'content' in response['message'] else getattr(response.message, 'content', '')
            if not summary.strip():
                summary = "No summary generated by Ollama."
            return summary, references
        except Exception as e:
            return f"Error generating summary with Ollama: {str(e)}", []

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
    
    # Get API choice
    while True:
        api_choice = input("Choose API for summarization (1 for OpenAI, 2 for Claude, 3 for Ollama): ").strip()
        if api_choice in ['1', '2', '3']:
            break
        print("Please enter 1 for OpenAI, 2 for Claude, or 3 for Ollama.")
    
    # Get rate limiting preference if using OpenAI
    use_rate_limiting = False
    if api_choice == '1':
        use_rate_limiting = input("Use rate limiting to handle large content? (y/n): ").lower() == 'y'
    
    # Rest of the input collection
    subreddits_input = input("Enter subreddit name(s) separated by commas: ")
    subreddits = [s.strip() for s in subreddits_input.split(',')]
    
    while True:
        try:
            hours = int(input("Enter number of hours to analyze: "))
            if hours > 0:
                break
            print("Please enter a positive number of hours.")
        except ValueError:
            print("Please enter a valid number.")
    
    topics_input = input("Enter topics to focus on (comma-separated, or press Enter for no filter): ")
    topics = [topic.strip().lower() for topic in topics_input.split(',')] if topics_input.strip() else []
    
    clean_text = input("Clean text content? (y/n): ").lower() == 'y'
    save_to_file = input("Save summaries to files? (y/n): ").lower() == 'y'
    save_raw_data = input("Save raw data too? (y/n): ").lower() == 'y' if save_to_file else False

    # Process each subreddit
    for subreddit in subreddits:
        print(f"\nAnalyzing r/{subreddit}...")
        try:
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
            if api_choice == '1':
                summary, references = summarizer.summarize_with_openai(content, subreddit, use_rate_limiting)
                formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
            elif api_choice == '2':
                summary = summarizer.summarize_with_claude(content, subreddit)
                formatted_summary = summary  # Claude's citations are already formatted
            else:
                summary, references = summarizer.summarize_with_ollama(content, subreddit)
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
                    'api_used': (
                        'OpenAI' if api_choice == '1'
                        else 'Claude' if api_choice == '2'
                        else 'Ollama'
                    ),
                    'rate_limiting': use_rate_limiting if api_choice == '1' else 'N/A'
                }
                
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