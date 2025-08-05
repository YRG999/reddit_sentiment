# Reddit Summarizer with Ollama

This script analyzes recent Reddit posts and comments from a specified subreddit, filters by optional topics, and generates a summarized report using Ollama. The results are saved to files for later reference.

## Installation

1. **Install dependencies**.

Install dependencies for `summarize_with_ollama` and `summarize_claude_openai`.

```bash
pip install -r requirements.txt
```

2. Install Ollama (required for summarization).

   - https://ollama.com/download
   - Follow the installation instructions for your OS
   - Ensure Ollama is running and a model is loaded (e.g., `ollama run llama3`)

3. Set up environment.

    - Optional - Ensure your Ollama API key is configured (if required by your setup)
    - Verify your internet connection

## Usage

1. Run the script.

```bash
python summarize_with_ollama.py
```

2. Follow the prompts.

   - Enter a subreddit name (e.g., `python`)
   - Specify the number of hours to analyze (e.g., `24`)
   - Enter optional topics to filter content (comma-separated, e.g., `AI, machine learning`)

3. Output.

   - A formatted summary with footnotes about the source content
   - Files saved in the current directory (e.g., `summary_r_python_24h.md`, `raw_data.json`)

## Features

- Dynamic filtering - Focus on specific topics (e.g., AI, technology)
- Ollama integration - Leverages large language models for summarization
- Automated saving - Stores both summaries and raw data
- Error handling - Catches invalid inputs and processing issues

## Notes

- The script assumes Ollama is properly configured and a model is loaded
- Topics are case-insensitive and automatically normalized
- All text is cleaned by default (you can modify this behavior)
- Raw data is saved only if save_raw_data is enabled

## Contributions

This script is designed to be extended.

- Add support for different LLMs (e.g., OpenAI, Claude)
- Implement rate limiting for Reddit API
- Add export options (e.g., PDF, JSON)
- Improve topic filtering logic

## Example

```bash
Enter subreddit name: python
Enter number of hours to analyze: 72
Enter topics to focus on (comma-separated): AI, machine learning
```

Output:

```
SUMMARY:
Reddit analysis of r/python (72h) - 12 posts, 89 comments
...
```

## File Structure

```
summary_r_<subreddit>_<hours>h.md          # Formatted summary
raw_data_<subreddit>_<hours>h.json         # Raw content data
analysis_params_<subreddit>_<hours>h.json  # Configuration details
```
