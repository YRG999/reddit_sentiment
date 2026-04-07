# Chat Summaries — 2026-04-07

## Session 1

### `clean_text.py` — preprocessing improvements

- Identified why `===` separator lines and `-- -|` table artifacts survived cleaning: `=` is not in `string.punctuation`, so NLTK kept it as a token; markdown table row pipes were stripped but `-` chars remained
- Added `preprocess()` function that runs before NLTK tokenization:
  - Removes pure-separator lines (`===`, `---`, `***`)
  - Removes markdown table separator rows (`|---|`)
  - Replaces unicode arrows and em/en dashes with spaces
  - Replaces markdown bold/italic/header markers with spaces
- Added `_EXTRA_PUNCT` set to catch characters not covered by `string.punctuation`: `=`, `~`, `^`, `` ` ``, `\`, bullets, em/en dashes
- Changed URL handling: default now collapses `https://example.com/path` → `example.com` (keeps attribution context); added `--strip-urls` flag to remove URLs entirely
- Updated CHANGELOG (v1.7.0), README (`clean_text.py` options table and description)
