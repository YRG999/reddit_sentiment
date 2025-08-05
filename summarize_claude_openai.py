# summarizereddit14.py
# Update from v11 - Add a list of references that links the post and comment number to the URL
# Update from v12 - Add Ollama support
# Update from v13 - Optimized code: reduced comments, simplified input, reused functions, improved readability.

import os
import json
import string
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
import praw
from openai import OpenAI
import anthropic
import tiktoken
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

class RedditSummarizer:
    def __init__(self):
        load_dotenv()
        self.reddit = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID'),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
            user_agent=os.getenv('REDDIT_USER_AGENT')
        )
        openai_key = os.getenv("OPENAI_API_KEY")
        self.openai_client = OpenAI(api_key=openai_key) if openai_key else None
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        self.claude_client = anthropic.Anthropic(api_key=anthropic_key) if anthropic_key else None
        self.eastern_tz = pytz.timezone('America/New_York')
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        self.MAX_TOKENS = 8000
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/chat")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "gemma3:12b")

    def clean_text(self, text):
        if not text:
            return ""
        try:
            tokens = word_tokenize(text.lower())
            stop_words = set(stopwords.words('english'))
            tokens = [t for t in tokens if t not in string.punctuation and t not in stop_words]
            return ' '.join(tokens)
        except Exception as e:
            print(f"Warning: Error cleaning text: {str(e)}")
            return text

    def count_tokens(self, text):
        return len(self.tokenizer.encode(text))

    def get_recent_content(self, subreddit_name, hours, clean=True):
        subreddit = self.reddit.subreddit(subreddit_name)
        cutoff_time = datetime.now(pytz.UTC) - timedelta(hours=hours)
        posts, comments = [], []
        for post in subreddit.new(limit=100):
            post_time = datetime.fromtimestamp(post.created_utc, pytz.UTC)
            if post_time < cutoff_time: break
            post_content = post.selftext
            posts.append({
                'title': post.title,
                'content': self.clean_text(post_content) if clean else post_content,
                'raw_content': post_content,
                'score': post.score,
                'url': f"https://www.reddit.com{post.permalink}",
                'created_utc': post_time.astimezone(self.eastern_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            })
        for comment in subreddit.comments(limit=500):
            comment_time = datetime.fromtimestamp(comment.created_utc, pytz.UTC)
            if comment_time < cutoff_time: break
            comment_body = comment.body
            comments.append({
                'body': self.clean_text(comment_body) if clean else comment_body,
                'raw_body': comment_body,
                'score': comment.score,
                'url': f"https://www.reddit.com{comment.permalink}",
                'created_utc': comment_time.astimezone(self.eastern_tz).strftime('%Y-%m-%d %H:%M:%S %Z')
            })
        return {'posts': posts, 'comments': comments}

    def prepare_summary_prompt(self, content, subreddit_name, content_limit=None):
        references, ref_counter = [], 1
        prompt = f"Summarize the following content from r/{subreddit_name}.\nInclude key themes, notable discussions, and overall sentiment.\nUse numbered references [n].\n\nPOSTS:\n"
        for post in content['posts']:
            references.append(post['url'])
            post_entry = f"- [{ref_counter}] {post['title']}\n"
            post_entry += f"  Content: {post['content'][:content_limit]}...\n" if content_limit else f"  Content: {post['content']}\n"
            prompt += post_entry
            ref_counter += 1
        prompt += "\nCOMMENTS (sample):\n"
        for comment in content['comments'][:10]:
            references.append(comment['url'])
            prompt += f"- [{ref_counter}] {comment['body'][:content_limit]}...\n" if content_limit else f"- [{ref_counter}] {comment['body']}\n"
            ref_counter += 1
        return prompt, references

    def prepare_claude_content(self, content, subreddit_name):
        formatted = f"Content from r/{subreddit_name}:\n\nPOSTS:\n"
        references = []
        for i, post in enumerate(content['posts'], 1):
            formatted += f"Post {i}:\nTitle: {post['title']}\nContent: {post['content']}\nPosted: {post['created_utc']}\n\n"
            references.append((f"Post {i}", post['url']))
        formatted += "COMMENTS:\n"
        for i, comment in enumerate(content['comments'][:10], 1):
            formatted += f"Comment {i}:\nContent: {comment['body']}\nPosted: {comment['created_utc']}\n\n"
            references.append((f"Comment {i}", comment['url']))
        return [{"type": "text", "text": formatted}], references

    def summarize_with_claude(self, content, subreddit_name):
        if not self.claude_client:
            return "Error: Anthropic API key not found."
        try:
            documents, references = self.prepare_claude_content(content, subreddit_name)
            message_content = documents + [{
                "type": "text",
                "text": f"Provide a comprehensive summary of this Reddit content from r/{subreddit_name}. Reference specific posts/comments."
            }]
            response = self.claude_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                messages=[{"role": "user", "content": message_content}]
            )
            summary = response.content[0].text if hasattr(response, 'content') and response.content else ""
            if not summary.strip():
                return "Error: Received empty summary from Claude"
            summary += "\n\nReferences:\n" + "\n".join(f"[{ref}]({url})" for ref, url in references)
            return summary
        except Exception as e:
            return f"Error generating summary with Claude: {str(e)}"

    def summarize_with_openai(self, content, subreddit_name, use_rate_limiting=True, max_retries=3):
        retry_count, content_limit, target_tokens = 0, None, 8000
        while retry_count < max_retries:
            try:
                summary_prompt, references = self.prepare_summary_prompt(content, subreddit_name, content_limit)
                total_tokens = self.count_tokens(summary_prompt)
                if use_rate_limiting and total_tokens > target_tokens:
                    content_limit = 500 if content_limit is None else int(content_limit * 0.5)
                    print(f"Reducing content to {content_limit} chars (tokens: {total_tokens})")
                    continue
                print(f"Requesting with {total_tokens} tokens...")
                chat_completion = self.openai_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes Reddit content. Include key themes, notable discussions, and overall sentiment. Use numbered references [n]."},
                        {"role": "user", "content": summary_prompt}
                    ],
                    model="gpt-4",
                )
                return chat_completion.choices[0].message.content, references
            except Exception as e:
                error_str = str(e)
                if use_rate_limiting and ("Request too large" in error_str or "rate_limit_exceeded" in error_str):
                    retry_count += 1
                    content_limit = 500 if content_limit is None else int(content_limit * 0.5)
                    print(f"Hit rate limit. Reducing content to {content_limit} chars and retrying...")
                    if retry_count >= max_retries:
                        return f"Error: Unable to generate summary after {max_retries} attempts. Last error: {str(e)}", []
                else:
                    return f"Error generating summary: {str(e)}", []

    def summarize_with_ollama(self, content, subreddit_name):
        try:
            from ollama import chat
            summary_prompt, references = self.prepare_summary_prompt(content, subreddit_name)
            messages = [
                {"role": "system", "content": "You are a helpful assistant that summarizes Reddit content. Include key themes, notable discussions, and overall sentiment. Use numbered references [n]."},
                {"role": "user", "content": summary_prompt}
            ]
            response = chat(model=self.ollama_model, messages=messages)
            summary = response['message']['content'] if 'message' in response and 'content' in response['message'] else getattr(response.message, 'content', '')
            if not summary.strip():
                summary = "No summary generated by Olloma."
            return summary, references
        except Exception as e:
            return f"Error generating summary with Ollama: {str(e)}", []

    def filter_content_by_topics(self, content, topics):
        def contains_topics(text):
            return any(topic in text.lower() for topic in topics)
        filtered_posts = [p for p in content['posts'] if contains_topics(p['title']) or contains_topics(p['content'])]
        filtered_comments = [c for c in content['comments'] if contains_topics(c['body'])]
        return {'posts': filtered_posts, 'comments': filtered_comments}

    def format_summary_with_footnotes(self, summary, references):
        formatted = summary + "\n\nReferences:\n"
        formatted += "\n".join(f"[{i}] {url}" for i, url in enumerate(references, 1))
        return formatted

def save_summary_to_file(subreddit, summary, analysis_params, content=None):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    saved_files = []
    summary_filename = f"summary_{subreddit}_{timestamp}.txt"
    with open(summary_filename, 'w', encoding='utf-8') as f:
        f.write("ANALYSIS PARAMETERS:\n")
        f.write(f"Subreddit name: {analysis_params['subreddit']}\n")
        f.write(f"Hours analyzed: {analysis_params['hours']}\n")
        f.write(f"Topics: {', '.join(analysis_params['topics']) if analysis_params['topics'] else 'No topic filter'}\n")
        f.write(f"Clean text content: {'Yes' if analysis_params['clean_text'] else 'No'}\n")
        f.write(f"Summary generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}\n")
        f.write("\n" + "="*50 + "\n\n")
        f.write(summary)
    saved_files.append(summary_filename)
    if content:
        raw_filename = f"raw_data_{subreddit}_{timestamp}.json"
        with open(raw_filename, 'w', encoding='utf-8') as f:
            json.dump(content, f, indent=2, ensure_ascii=False)
        saved_files.append(raw_filename)
    return saved_files

def get_positive_int(prompt):
    while True:
        try:
            value = int(input(prompt))
            if value > 0:
                return value
            print("Enter a positive number.")
        except ValueError:
            print("Please enter a valid number.")

def main():
    summarizer = RedditSummarizer()
    api_choice = ""
    while api_choice not in ['1', '2', '3']:
        api_choice = input("Choose API for summarization (1=OpenAI, 2=Claude, 3=Ollama): ").strip()
    use_rate_limiting = api_choice == '1' and input("Use rate limiting for OpenAI? (y/n): ").lower() == 'y'
    subreddits = [s.strip() for s in input("Enter subreddit name(s) separated by commas: ").split(',')]
    hours = get_positive_int("Enter number of hours to analyze: ")
    topics_input = input("Enter topics to focus on (comma-separated, or press Enter for no filter): ")
    topics = [t.strip().lower() for t in topics_input.split(',')] if topics_input.strip() else []
    clean_text = input("Clean text content? (y/n): ").lower() == 'y'
    save_to_file = input("Save summaries to files? (y/n): ").lower() == 'y'
    save_raw_data = input("Save raw data too? (y/n): ").lower() == 'y' if save_to_file else False

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
                formatted_summary = summary
            else:
                summary, references = summarizer.summarize_with_ollama(content, subreddit)
                formatted_summary = summarizer.format_summary_with_footnotes(summary, references)
            print("\nSUMMARY:\n" + formatted_summary)
            if save_to_file:
                analysis_params = {
                    'subreddit': subreddit,
                    'hours': hours,
                    'topics': topics,
                    'clean_text': clean_text,
                    'api_used': 'OpenAI' if api_choice == '1' else 'Claude' if api_choice == '2' else 'Ollama',
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
