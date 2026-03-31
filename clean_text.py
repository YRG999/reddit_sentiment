#!/usr/bin/env python3

import os
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


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    tokens = word_tokenize(text)
    stop_words = set(stopwords.words("english"))
    tokens = [t for t in tokens if t not in string.punctuation and t not in stop_words]
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
def main(input_file, output, stdout, split):
    """Clean a text file to save tokens when pasting into an LLM.

    Lowercases text, removes punctuation and English stop words.
    """
    ensure_nltk_data()

    with open(input_file, "r", encoding="utf-8") as f:
        raw = f.read()

    cleaned = clean_text(raw)

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