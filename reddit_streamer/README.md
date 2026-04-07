# Reddit Streamer

This project is designed to stream posts and comments from a specified subreddit. It retrieves the most recent items and displays one item per second in the console. Additionally, it logs the full raw JSON data to a file named with the subreddit and timestamp.

## Project Structure

```text
reddit_streamer
├── src
│   └── streamer.py
├── requirements.txt
└── README.md
```

## Dependencies

`streamer.py` imports `credentials.py` from the **project root** (two levels up). This file must be present and accessible — `reddit_streamer` cannot be run as a fully standalone directory without it.

## Requirements

To run this project, you need to install the required dependencies. You can do this by running:

```bash
pip install -r requirements.txt
```

## Usage

1. Navigate to the project directory.
2. Run the streamer script:

```bash
python src/streamer.py
```

3. When prompted, enter the subreddit name you wish to stream from.
4. Specify the total number of items (posts and comments) you want to report.
5. The program will display one item per second in the console and log the raw JSON data to a file.

## Example

```text
Enter subreddit name: learnpython
Enter total number of items to report: 100
```

This will stream the latest 100 posts and comments from the `learnpython` subreddit.

## License

This project is licensed under the MIT License.
