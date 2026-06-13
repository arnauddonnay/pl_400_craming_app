"""SQLite persistence for questions and review progress."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

from scheduler import schedule_review


DB_PATH = Path("data/app.db")


@contextmanager
def connect(db_path: str | Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database(db_path: str | Path = DB_PATH) -> None:
    with connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                source_file TEXT NOT NULL,
                title TEXT NOT NULL,
                statement TEXT NOT NULL,
                choices_json TEXT NOT NULL,
                correct_indexes_json TEXT NOT NULL,
                explanation TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS progress (
                question_id TEXT PRIMARY KEY,
                times_seen INTEGER NOT NULL DEFAULT 0,
                correct_count INTEGER NOT NULL DEFAULT 0,
                last_review TEXT,
                next_review TEXT,
                ease_score REAL NOT NULL DEFAULT 2.5,
                interval_days INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (question_id) REFERENCES questions(id)
            );
            """
        )


def sync_questions(questions: list[dict], db_path: str | Path = DB_PATH) -> None:
    """Upsert parsed questions and hide questions removed from Markdown files."""
    with connect(db_path) as connection:
        connection.execute("UPDATE questions SET active = 0")
        for question in questions:
            connection.execute(
                """
                INSERT INTO questions (
                    id, source_file, title, statement, choices_json,
                    correct_indexes_json, explanation, tags_json, active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(id) DO UPDATE SET
                    source_file = excluded.source_file,
                    title = excluded.title,
                    statement = excluded.statement,
                    choices_json = excluded.choices_json,
                    correct_indexes_json = excluded.correct_indexes_json,
                    explanation = excluded.explanation,
                    tags_json = excluded.tags_json,
                    active = 1
                """,
                (
                    question["id"],
                    question["source_file"],
                    question["title"],
                    question["statement"],
                    json.dumps(question["choices"]),
                    json.dumps(question["correct_indexes"]),
                    question["explanation"],
                    json.dumps(question["tags"]),
                ),
            )


def _row_to_question(row: sqlite3.Row) -> dict:
    question = dict(row)
    question["choices"] = json.loads(question.pop("choices_json"))
    question["correct_indexes"] = json.loads(question.pop("correct_indexes_json"))
    question["tags"] = json.loads(question.pop("tags_json"))
    return question


def get_all_questions(db_path: str | Path = DB_PATH) -> list[dict]:
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT q.*, p.times_seen, p.correct_count, p.next_review
            FROM questions q
            LEFT JOIN progress p ON p.question_id = q.id
            WHERE q.active = 1
            ORDER BY q.source_file, q.title
            """
        ).fetchall()
    return [_row_to_question(row) for row in rows]


def get_due_questions(db_path: str | Path = DB_PATH) -> list[dict]:
    today = date.today().isoformat()
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT q.*, p.times_seen, p.correct_count, p.next_review
            FROM questions q
            LEFT JOIN progress p ON p.question_id = q.id
            WHERE q.active = 1
              AND (p.next_review IS NULL OR p.next_review <= ?)
            ORDER BY COALESCE(p.next_review, ''), q.source_file, q.title
            """,
            (today,),
        ).fetchall()
    return [_row_to_question(row) for row in rows]


def record_review(
    question_id: str,
    was_correct: bool,
    rating: str,
    db_path: str | Path = DB_PATH,
) -> None:
    with connect(db_path) as connection:
        progress = connection.execute(
            "SELECT * FROM progress WHERE question_id = ?", (question_id,)
        ).fetchone()

        current_interval = progress["interval_days"] if progress else 0
        ease_score = progress["ease_score"] if progress else 2.5
        next_review, interval_days, ease_score = schedule_review(
            rating, current_interval, ease_score
        )

        connection.execute(
            """
            INSERT INTO progress (
                question_id, times_seen, correct_count, last_review,
                next_review, ease_score, interval_days
            ) VALUES (?, 1, ?, ?, ?, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                times_seen = times_seen + 1,
                correct_count = correct_count + excluded.correct_count,
                last_review = excluded.last_review,
                next_review = excluded.next_review,
                ease_score = excluded.ease_score,
                interval_days = excluded.interval_days
            """,
            (
                question_id,
                int(was_correct),
                datetime.now().isoformat(timespec="seconds"),
                next_review,
                ease_score,
                interval_days,
            ),
        )
