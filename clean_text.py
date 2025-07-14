from summarize_claude_openai import RedditSummarizer
import os

def main():
    summarizer = RedditSummarizer()
    input_path = input("Enter the path to the text file to clean: ").strip()
    if not os.path.isfile(input_path):
        print("File does not exist.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        raw_text = f.read()

    cleaned_text = summarizer.clean_text(raw_text)

    base, ext = os.path.splitext(input_path)
    output_path = f"{base}_cleaned{ext}"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(cleaned_text)

    print(f"Cleaned text saved to {output_path}")

if __name__ == "__main__":
    main()