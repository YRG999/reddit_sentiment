from summarize_claude_openai import RedditSummarizer, save_summary_to_file

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
    """
    This function orchestrates the Reddit summarization process using the RedditSummarizer class and Ollama for summarization.

    It takes user input for the subreddit to analyze, the number of hours to analyze, and optional topics to focus on.
    It retrieves recent content from the specified subreddit, filters it based on the optional topics, summarizes the content using Ollama,
    and saves the summary and raw data (optionally) to files.  Error handling is included for invalid user input and processing errors.
    """
    summarizer = RedditSummarizer()
    subreddit = input("Enter subreddit name: ").strip()
    hours = get_positive_int("Enter number of hours to analyze: ")
    topics_input = input("Enter topics to focus on (comma-separated, or press Enter for no filter): ")
    topics = [t.strip().lower() for t in topics_input.split(',')] if topics_input.strip() else []

    clean_text = True  # Flag to control text cleaning (always True in this version)
    save_to_file = True # Flag to control whether to save to file (always True)
    save_raw_data = True # Flag to control whether to save raw data (always True)

    print(f"\nAnalyzing r/{subreddit} with Ollama summarization...")
    try:
        content = summarizer.get_recent_content(subreddit, hours, clean=clean_text)
        if topics:
            content = summarizer.filter_content_by_topics(content, topics)
            print(f"Found {len(content['posts'])} posts and {len(content['comments'])} comments matching topics: {', '.join(topics)}")
        else:
            print(f"Found {len(content['posts'])} posts and {len(content['comments'])} comments")

        if not content['posts'] and not content['comments']:
            print(f"No content found matching the specified topics in r/{subreddit}")
            return

        print("\nGenerating summary with Ollama...")
        summary, references = summarizer.summarize_with_ollama(content, subreddit)
        formatted_summary = summarizer.format_summary_with_footnotes(summary, references)

        print("\nSUMMARY:")
        print(formatted_summary)

        analysis_params = {
            'subreddit': subreddit,
            'hours': hours,
            'topics': topics,
            'clean_text': clean_text,
            'api_used': 'Ollama',
            'rate_limiting': 'N/A'
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

if __name__ == "__main__":
    main()
