# Reddit sentiment

Perform simple sentiment analysis on subreddit posts.

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

## Run program

```sh
$ python program_name.py
```

## Uninstall all pip packages

Useful for debugging, for example, to see which packages are needed and which are not. This is just a helpful note for myself.

```bash
$ pip uninstall -y -r <(pip freeze)
```
