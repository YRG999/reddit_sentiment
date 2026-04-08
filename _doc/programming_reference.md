# Programming reference

*Thematic reference — conceptual explanations of programming patterns and techniques used in this project. For dated session logs, see [claude_summaries/](claude_summaries/).*

- [Shared factory function](#shared-factory-function)
- [Lazy initialization](#lazy-initialization)
- [Lazy helpers and caching sets](#lazy-helpers-and-caching-sets)
- [The zoneinfo library](#the-zoneinfo-library)

## Shared factory function

A **factory function** is a function whose job is to create and return an object. Instead of building the object yourself every time you need one, you call the factory and it gives you a ready-made instance.

A **shared** factory function means there is one single function that every part of the codebase calls when it needs that object. The alternative — which this project had before — is each file building its own copy independently.

### Why it matters

In this project, four files (`comments.py`, `posts.py`, `sentiment.py`, `summarize_claude_openai.py`) all needed a Reddit API client. Each one had its own copy of the same three lines:

```python
reddit = praw.Reddit(
    client_id=get_secret("REDDIT_CLIENT_ID"),
    client_secret=get_secret("REDDIT_CLIENT_SECRET"),
    user_agent=get_secret("REDDIT_USER_AGENT"),
)
```

If the way we create a Reddit client ever needed to change — say, adding a timeout or switching credential sources — we'd have to find and update all four copies. Easy to miss one.

Now there is a single factory function in `credentials.py`:

```python
def get_reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=get_secret("REDDIT_CLIENT_ID"),
        client_secret=get_secret("REDDIT_CLIENT_SECRET"),
        user_agent=get_secret("REDDIT_USER_AGENT"),
    )
```

Every file just calls `get_reddit_client()`. One place to maintain, one place to change.

### Analogy

Think of it like a coffee machine in an office. Instead of each person buying their own machine, grinding their own beans, and maintaining their own equipment, there's one shared machine. If the office switches to a new brand of beans, you change it in one place.

---

## Lazy initialization

**Lazy initialization** means: don't create something until the moment you actually need it. The opposite is **eager initialization**, where you create everything up front, just in case.

### The problem it solves

The `RedditSummarizer` class connects to three different AI services (OpenAI, Anthropic/Claude, and Ollama) plus the Reddit API. But on any given run, you only use **one** of those AI services. Before lazy initialization, the constructor created all three clients immediately:

```python
def __init__(self):
    self.reddit = praw.Reddit(...)          # always created
    self.openai_client = OpenAI(...)        # always created, even if using Claude
    self.claude_client = anthropic.Anthropic(...)  # always created, even if using OpenAI
    self.tokenizer = tiktoken.encoding_for_model(...)  # always loaded
```

This meant:
1. **Wasted work** — creating clients you never use.
2. **All API keys required** — if you only have an OpenAI key but not an Anthropic key, the constructor would fail trying to resolve the Anthropic key, even though you never intended to use Claude.

### How it works in Python

The solution uses Python **properties** — special methods that look like regular attributes but run code behind the scenes when you access them. The pattern uses a **sentinel value** (a unique marker object) to track whether the real client has been created yet:

```python
_UNSET = object()  # a unique marker that means "not yet created"

class RedditSummarizer:
    def __init__(self):
        self._openai_client = _UNSET  # just a marker, not a real client

    @property
    def openai_client(self):
        if self._openai_client is _UNSET:     # first time accessing?
            from openai import OpenAI          # import only when needed
            key = get_secret("OPENAI_API_KEY")
            self._openai_client = OpenAI(api_key=key) if key else None
        return self._openai_client             # return the cached client
```

The first time any code accesses `summarizer.openai_client`, the property method runs, creates the real client, and stores it. Every subsequent access returns the stored client without recreating it. If nobody ever accesses the property, the client is never created at all.

### Analogy

Imagine a house with three guest bedrooms. Eager initialization is like making all three beds, stocking all three bathrooms, and turning on all three heaters before any guests arrive — even if only one person is coming. Lazy initialization is like preparing a room only when a guest actually shows up.

---

## Lazy helpers and caching sets

A **lazy helper** is a small function whose only job is to build an expensive object the first time it's called, save it, and return the saved copy on every subsequent call.

### The problem: rebuilding the same data repeatedly

In `clean_text.py`, the `clean_text()` function removes common English words ("the", "is", "and", etc.) and punctuation from text. To do this, it needs two **sets** — collections of items it can quickly check membership against:

1. A **stopwords set** — all common English words to remove (~180 words)
2. A **punctuation set** — all punctuation characters to strip

Before the optimization, these sets were rebuilt from scratch on every single function call:

```python
def clean_text(text):
    stop_words = set(stopwords.words("english"))  # loads 180 words from NLTK every time
    bad = set(string.punctuation) | _EXTRA_PUNCT   # rebuilds the punctuation set every time
    tokens = [t for t in tokens if t not in bad and t not in stop_words]
```

If you're cleaning 600 pieces of text (100 Reddit posts + 500 comments), that's 600 times loading the same 180-word list and building the same punctuation set. The result is identical every time — it's pure waste.

### How lazy helpers fix it

A lazy helper stores the result in a **module-level variable** (a variable that lives at the file level, outside any function, shared by all code in that file):

```python
_STOP_WORDS = None  # starts empty

def _get_stop_words():
    global _STOP_WORDS
    if _STOP_WORDS is None:                        # first call? build it
        _STOP_WORDS = set(stopwords.words("english"))
    return _STOP_WORDS                             # every call returns the same set
```

The first call builds the set and saves it. The next 599 calls just return the saved copy. The `global` keyword tells Python "I want to modify the file-level variable, not create a local one."

### Why sets specifically

A **set** in Python is a collection optimized for "is this item in the collection?" lookups. Checking whether a word is in a set of 180 items is nearly instant (technically O(1) — constant time), regardless of how many items the set contains. This is much faster than checking a list, which has to scan through items one by one. That's why stopwords and punctuation are stored as sets rather than lists — we're checking thousands of words against them.

### The same idea in `summarize_claude_openai.py`

The `RedditSummarizer` class uses the same approach but stores the sets as **instance attributes** (on `self`) rather than module globals:

```python
def __init__(self):
    self._stop_words = set(stopwords.words("english"))
    self._bad_chars = set(string.punctuation) | ...
```

Built once when the class is created, reused across all calls to `self.clean_text()`. Same principle, slightly different storage location.

---

## The zoneinfo library

**`zoneinfo`** is Python's built-in library (since Python 3.9) for working with time zones. It replaces the older third-party library **`pytz`**, which required a separate `pip install` and had some awkward quirks.

### What it does

Computers store time internally as UTC (Coordinated Universal Time) — a single, universal reference point with no daylight saving shifts. But humans want to see times in their local zone. `zoneinfo` handles the conversion:

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo("America/New_York")

# Start with a UTC timestamp (e.g., from the Reddit API)
utc_time = datetime.fromtimestamp(1712500000, timezone.utc)

# Convert to Eastern Time (automatically handles EST vs EDT)
eastern_time = utc_time.astimezone(EASTERN_TZ)
print(eastern_time)  # 2024-04-07 10:26:40 EDT
```

### Why switch from pytz

| | `pytz` | `zoneinfo` |
| --- | --- | --- |
| Install required? | Yes (`pip install pytz`) | No (built into Python 3.9+) |
| Part of the standard library? | No | Yes |
| DST handling | Works, but has a non-obvious `localize()` API that's easy to misuse | Standard `astimezone()` — hard to get wrong |
| Maintenance | Third-party, may lag behind tz database updates | Updated with Python itself |

Since this project requires Python 3.10+, `zoneinfo` is always available. Switching removes an external dependency and uses the approach Python officially recommends.

### The naive datetime problem

A **naive datetime** is one with no timezone information attached. Python's `datetime.fromtimestamp(epoch)` without a timezone argument returns a naive datetime in whatever timezone the computer happens to be set to. This is a common source of bugs:

```python
# Bad — naive datetime, depends on machine timezone
datetime.fromtimestamp(1712500000)  # could be EDT, PDT, UTC... depends on the computer

# Good — explicit UTC, then convert
datetime.fromtimestamp(1712500000, timezone.utc).astimezone(EASTERN_TZ)  # always EDT/EST
```

This was the bug in `sentiment.py` — it used the naive form, so timestamps would silently show different times depending on where the code was run. The fix makes the timezone conversion explicit.
