#!/usr/bin/env python3

import os
import re
import string
import click
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords


def ensure_nltk_data():
    for path, resource in [("tokenizers/punkt_tab", "punkt_tab"), ("corpora/stopwords", "stopwords")]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(resource, quiet=True)


# Extend string.punctuation with chars that NLTK keeps but carry no meaning
_EXTRA_PUNCT = set("=~^`\\") | set("\u2022\u2013\u2014\u2015")  # bullets, en/em dashes

# Cached at module level to avoid rebuilding on every call
_STOP_WORDS: set[str] | None = None
_BAD_CHARS: set[str] | None = None


def _get_stop_words() -> set[str]:
    global _STOP_WORDS
    if _STOP_WORDS is None:
        _STOP_WORDS = set(stopwords.words("english"))
    return _STOP_WORDS


def _get_bad_chars() -> set[str]:
    global _BAD_CHARS
    if _BAD_CHARS is None:
        _BAD_CHARS = set(string.punctuation) | _EXTRA_PUNCT
    return _BAD_CHARS


def preprocess(text: str, strip_urls: bool = False) -> str:
    """Strip decorative markup before tokenisation to reduce noise."""
    if strip_urls:
        text = re.sub(r"https?://\S+", "", text)
    else:
        # Keep the domain as a readable token; drop protocol and path noise
        text = re.sub(r"https?://([^/\s]+)[^\s]*", r"\1", text)
    # Remove lines that are purely decorative separators (===, ---, ***, etc.)
    text = re.sub(r"^\s*[=\-*_]{2,}\s*$", "", text, flags=re.MULTILINE)
    # Remove markdown table separator rows: |---|  |:---:|  etc.
    text = re.sub(r"^\s*\|[\s\-:|]+\|\s*$", "", text, flags=re.MULTILINE)
    # Replace unicode arrows / dashes with a space
    text = re.sub(r"[→←↑↓—–\u2192\u2190]", " ", text)
    # Strip markdown bold/italic/header markers
    text = re.sub(r"[*_#|]", " ", text)
    return text


def clean_text(text: str, strip_urls: bool = False) -> str:
    if not text:
        return ""
    text = preprocess(text, strip_urls=strip_urls)
    text = text.lower()
    tokens = word_tokenize(text)
    stop_words = _get_stop_words()
    bad = _get_bad_chars()
    tokens = [t for t in tokens if t not in bad and t not in stop_words]
    return " ".join(tokens)


def split_text(text: str, max_chars: int) -> list[str]:
    blocks = []
    while len(text) > max_chars:
        split_at = text.rfind(" ", 0, max_chars)
        if split_at == -1:
            split_at = max_chars
        blocks.append(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        blocks.append(text)
    return blocks


@click.command()
@click.argument("input_file", type=click.Path(exists=True, readable=True))
@click.option("--output", "-o", type=click.Path(), default=None, help="Output file (default: <input>_cleaned.<ext>)")
@click.option("--stdout", is_flag=True, help="Print to stdout instead of writing a file")
@click.option("--split", "-s", type=int, default=None, help="Split output into blocks of N characters separated by ---")
@click.option("--strip-urls", is_flag=True, help="Remove URLs entirely (default: keep domain only)")
def main(input_file, output, stdout, split, strip_urls):
    """Clean a text file to save tokens when pasting into an LLM.

    Lowercases text, removes punctuation and English stop words.
    """
    ensure_nltk_data()

    with open(input_file, "r", encoding="utf-8") as f:
        raw = f.read()

    cleaned = clean_text(raw, strip_urls=strip_urls)

    if split:
        blocks = split_text(cleaned, split)
        final = "\n\n---\n\n".join(blocks)
    else:
        final = cleaned

    if stdout:
        click.echo(final)
    else:
        if output is None:
            base, ext = os.path.splitext(input_file)
            output = f"{base}_cleaned{ext}"
        with open(output, "w", encoding="utf-8") as f:
            f.write(final)
        original_words = len(raw.split())
        cleaned_words = len(cleaned.split())
        suffix = f", {len(blocks)} blocks" if split else ""
        click.echo(f"Saved to {output} ({original_words} → {cleaned_words} words, -{original_words - cleaned_words} saved{suffix})")


if __name__ == "__main__":
    main()