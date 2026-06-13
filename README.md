# MCQ Review App

A small local Streamlit app for reviewing Microsoft exam-style multiple-choice questions.

## Features

- Loads every `.md` file from `questions/`, including subdirectories
- Supports one or several correct answers
- Stores review progress locally in SQLite
- Uses a simple spaced-repetition schedule
- Includes review and question browsing pages

## Installation

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
```

Activate the virtual environment:

```powershell
.venv\Scripts\Activate.ps1
```

Install the dependency:

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

The SQLite database is created automatically at `data/app.db`.

## Add questions

Add or edit `.md` files inside `questions/`, then click **Reload Markdown files** in
the sidebar. Multiple questions can live in the same file.

```md
# Question title

Tags: Azure, Security

Question text goes here.

- [ ] Incorrect choice
- [x] Correct choice
- [ ] Another incorrect choice

Explanation:
An explanation shown after answering.
```

Mark every correct answer with `[x]`. Each question must have a heading, a
statement, at least one choice, and at least one correct answer.

## Review schedule

- **Again**: today
- **Hard**: tomorrow, then slowly increasing
- **Good**: in 3 days, then increasing
- **Easy**: in 7 days, then increasing faster
