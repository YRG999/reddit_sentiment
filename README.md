# Reddit sentiment and summarize

Perform simple sentiment analysis on subreddit posts. And summarize Reddit posts and comments.

## Set up env

Create & activate new virtual environment

```sh
$ python3 -m venv venv
$ . venv/bin/activate
```

Install the requirements

```sh
$ pip install -r requirements.txt
```

Or install the latest versions (`-U` for upgrade):

```sh
$ pip install -U -r requirements.txt
```

Create an `.env` file

Copy `.env.example` file and replace with your keys.

## Run program

```sh
$ python program_name.py
```

## Uninstall all pip packages

Useful for debugging, for example, to see which packages are needed and which are not. This is just a helpful note for myself.

```bash
$ pip uninstall -y -r <(pip freeze)
```

## uncommit & unstage

* [how-can-i-unstage-my-files-again-after-making-a-local-commit](https://stackoverflow.com/questions/6682740/how-can-i-unstage-my-files-again-after-making-a-local-commit)
* `git reset --soft HEAD~1` - reverts back to commit
* `git restore --staged <file>` - reverts to staged without overwriting changes. Use `.` for all files

## Reddit summarizer

* See [Reddit summarizer readme](README-summarize.md)
