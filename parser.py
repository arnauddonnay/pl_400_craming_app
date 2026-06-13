"""Parse MCQ questions from Markdown files."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


HEADER_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
CHOICE_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.+?)\s*$")


def _question_id(source_file: str, title: str, statement: str, choices: list[str]) -> str:
    content = "\n".join([source_file, title, statement, *choices])
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:24]


def parse_markdown(content: str, source_file: str = "") -> list[dict]:
    """Return every valid question found in a Markdown string."""
    headers = list(HEADER_RE.finditer(content))
    questions = []

    for index, header in enumerate(headers):
        title = header.group(1).strip()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(content)
        lines = content[header.end() : end].strip().splitlines()

        tags: list[str] = []
        statement_lines: list[str] = []
        choices: list[str] = []
        correct_indexes: list[int] = []
        explanation_lines: list[str] = []
        in_explanation = False

        for raw_line in lines:
            line = raw_line.strip()

            if line.lower().startswith("tags:") and not choices and not statement_lines:
                tags = [tag.strip() for tag in line[5:].split(",") if tag.strip()]
                continue

            if line.lower() == "explanation:":
                in_explanation = True
                continue

            if in_explanation:
                explanation_lines.append(raw_line.strip())
                continue

            choice_match = CHOICE_RE.match(raw_line)
            if choice_match:
                choices.append(choice_match.group(2).strip())
                if choice_match.group(1).lower() == "x":
                    correct_indexes.append(len(choices) - 1)
                continue

            if not choices:
                statement_lines.append(raw_line.strip())

        statement = "\n".join(line for line in statement_lines if line).strip()
        explanation = "\n".join(line for line in explanation_lines if line).strip()

        if statement and choices and correct_indexes:
            questions.append(
                {
                    "id": _question_id(source_file, title, statement, choices),
                    "source_file": source_file,
                    "title": title,
                    "statement": statement,
                    "choices": choices,
                    "correct_indexes": correct_indexes,
                    "explanation": explanation,
                    "tags": tags,
                }
            )

    return questions


def load_questions(directory: str | Path) -> list[dict]:
    """Parse all .md files in a directory, including its subdirectories."""
    directory = Path(directory)
    questions = []

    if not directory.exists():
        return questions

    for path in sorted(directory.rglob("*.md")):
        relative_path = path.relative_to(directory).as_posix()
        questions.extend(parse_markdown(path.read_text(encoding="utf-8"), relative_path))

    return questions
