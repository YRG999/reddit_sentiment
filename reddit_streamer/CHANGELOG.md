# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-04-07

### Fixed

- Added missing `import os` to `streamer.py` (caused `NameError` at runtime when building the log path).

### Added

- `CHANGELOG.md` (this file).
- `README.md`: documented dependency on `credentials.py` from the project root.

## [1.0.0] - 2025-07-14

### Added

- `streamer.py`: streams posts and comments from a subreddit, sorts by recency, prints one item per second, and saves raw JSON to `src/logs/`.
- `requirements.txt` with `praw` dependency.
- `README.md` with usage instructions.
