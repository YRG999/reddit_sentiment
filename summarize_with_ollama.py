from summarize_claude_openai import RedditSummarizer, save_summary_to_file

def main():
    summarizer = RedditSummarizer()
    subreddit = input("Enter subreddit name: ").strip()
    while True:
        try:
            hours = int(input("Enter number of hours to analyze: "))
            if hours > 0:
                break
            print("Enter a positive number of hours.")
        except ValueError:
            print("Please enter a valid number.")
    topics_input = input("Enter topics to focus on (comma-separated, or press Enter for no filter): ")
    topics = [topic.strip().lower() for topic in topics_input.split(',')] if topics_input.strip() else []

    clean_text = True
    save_to_file = True
    save_raw_data = True

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