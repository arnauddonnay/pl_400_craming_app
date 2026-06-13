"""Streamlit MVP for reviewing Markdown multiple-choice questions."""

import hashlib
from datetime import date
from pathlib import Path

import streamlit as st

from db import (
    get_all_questions,
    get_due_questions,
    initialize_database,
    record_review,
    sync_questions,
)
from parser import load_questions, parse_markdown
from scheduler import schedule_review


QUESTIONS_DIR = Path("questions")


def refresh_questions() -> int:
    questions = load_questions(QUESTIONS_DIR)
    sync_questions(questions)
    return len(questions)


def reset_review_state() -> None:
    for key in (
        "review_queue",
        "review_index",
        "review_source",
        "submitted",
        "was_correct",
    ):
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith("choice_"):
            del st.session_state[key]


def sync_uploaded_files(uploaded_files) -> list[str]:
    """Parse uploads into session state without saving them on the server."""
    signature = hashlib.sha256()
    uploaded_questions = []
    errors = []

    for index, uploaded_file in enumerate(uploaded_files):
        content = uploaded_file.getvalue()
        signature.update(uploaded_file.name.encode("utf-8"))
        signature.update(content)
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{uploaded_file.name}: file must use UTF-8 encoding")
            continue
        parsed_questions = parse_markdown(
            text, source_file=f"upload/{index}-{uploaded_file.name}"
        )
        if not parsed_questions:
            errors.append(f"{uploaded_file.name}: no valid questions found")
        uploaded_questions.extend(parsed_questions)

    new_signature = signature.hexdigest() if uploaded_files else ""
    if new_signature != st.session_state.get("upload_signature", ""):
        reset_review_state()
        st.session_state.upload_progress = {}
        st.session_state.upload_signature = new_signature
        st.session_state.uploaded_questions = uploaded_questions

    return errors


def using_uploads() -> bool:
    return bool(st.session_state.get("uploaded_questions"))


def get_active_questions() -> list[dict]:
    if using_uploads():
        return st.session_state.uploaded_questions
    return get_all_questions()


def get_active_due_questions() -> list[dict]:
    if not using_uploads():
        return get_due_questions()

    progress = st.session_state.get("upload_progress", {})
    today = date.today().isoformat()
    return [
        question
        for question in st.session_state.uploaded_questions
        if progress.get(question["id"], {}).get("next_review", today) <= today
    ]


def start_review() -> None:
    st.session_state.review_queue = get_active_due_questions()
    st.session_state.review_source = "uploads" if using_uploads() else "library"
    st.session_state.review_index = 0
    st.session_state.submitted = False
    st.session_state.was_correct = False


def record_uploaded_review(question_id: str, was_correct: bool, rating: str) -> None:
    progress = st.session_state.setdefault("upload_progress", {})
    current = progress.get(question_id, {})
    next_review, interval_days, ease_score = schedule_review(
        rating,
        current.get("interval_days", 0),
        current.get("ease_score", 2.5),
    )
    progress[question_id] = {
        "times_seen": current.get("times_seen", 0) + 1,
        "correct_count": current.get("correct_count", 0) + int(was_correct),
        "next_review": next_review,
        "interval_days": interval_days,
        "ease_score": ease_score,
    }


def next_question(rating: str, question: dict) -> None:
    if st.session_state.review_source == "uploads":
        record_uploaded_review(question["id"], st.session_state.was_correct, rating)
    else:
        record_review(question["id"], st.session_state.was_correct, rating)
    for choice_index in range(len(question["choices"])):
        st.session_state.pop(f"choice_{question['id']}_{choice_index}", None)
    st.session_state.review_index += 1
    st.session_state.submitted = False
    st.session_state.was_correct = False
    st.rerun()


def render_review_page() -> None:
    st.header("Review")
    due_count = len(get_active_due_questions())
    total_count = len(get_active_questions())
    st.caption(f"{due_count} due today | {total_count} questions available")
    if using_uploads():
        st.caption("Using uploaded questions. Progress is private and session-only.")

    if "review_queue" not in st.session_state:
        if due_count == 0:
            st.success("Nothing due today.")
            return
        if st.button("Start review", type="primary"):
            start_review()
            st.rerun()
        return

    index = st.session_state.review_index
    queue = st.session_state.review_queue
    if index >= len(queue):
        st.success("Session complete.")
        if st.button("Return"):
            reset_review_state()
            st.rerun()
        return

    question = queue[index]
    st.progress((index + 1) / len(queue), text=f"Question {index + 1} of {len(queue)}")
    st.subheader(question["title"])
    if question["tags"]:
        st.caption(" | ".join(question["tags"]))
    st.markdown(question["statement"])

    selected = []
    for choice_index, choice in enumerate(question["choices"]):
        checked = st.checkbox(
            choice,
            key=f"choice_{question['id']}_{choice_index}",
            disabled=st.session_state.submitted,
        )
        if checked:
            selected.append(choice_index)

    if not st.session_state.submitted:
        if st.button("Check answer", type="primary", disabled=not selected):
            st.session_state.was_correct = set(selected) == set(question["correct_indexes"])
            st.session_state.submitted = True
            st.rerun()
        return

    if st.session_state.was_correct:
        st.success("Correct.")
    else:
        correct_answers = [question["choices"][i] for i in question["correct_indexes"]]
        st.error("Incorrect. Correct answer(s): " + ", ".join(correct_answers))

    if question["explanation"]:
        st.info(question["explanation"])

    st.write("How difficult was this question?")
    columns = st.columns(4)
    for column, rating in zip(columns, ("Again", "Hard", "Good", "Easy")):
        if column.button(rating, use_container_width=True):
            next_question(rating, question)


def render_browse_page() -> None:
    st.header("Browse questions")
    questions = get_active_questions()
    st.caption(f"{len(questions)} questions imported")

    for question in questions:
        tags = ", ".join(question["tags"]) or "No tags"
        with st.expander(f"{question['title']} | {tags}"):
            st.markdown(question["statement"])
            for index, choice in enumerate(question["choices"]):
                marker = "[correct]" if index in question["correct_indexes"] else "[ ]"
                st.write(f"{marker} {choice}")
            if question["explanation"]:
                st.info(question["explanation"])
            if using_uploads():
                progress = st.session_state.get("upload_progress", {}).get(
                    question["id"], {}
                )
                seen = progress.get("times_seen", 0)
                correct = progress.get("correct_count", 0)
            else:
                seen = question["times_seen"] or 0
                correct = question["correct_count"] or 0
            st.caption(
                f"Source: {question['source_file']} | Seen: {seen} | Correct: {correct}"
            )


st.set_page_config(page_title="MCQ Review", layout="centered")
initialize_database()
imported_count = refresh_questions()

st.title("MCQ Review")
page = st.sidebar.radio("Navigation", ("Review", "Browse questions"))
uploaded_files = st.sidebar.file_uploader(
    "Upload your Markdown questions",
    type="md",
    accept_multiple_files=True,
    help="Uploads stay private in this browser session and are not saved to SQLite.",
)
upload_errors = sync_uploaded_files(uploaded_files)
for error in upload_errors:
    st.sidebar.error(error)

if using_uploads():
    st.sidebar.success(
        f"Using {len(st.session_state.uploaded_questions)} uploaded questions"
    )
    st.sidebar.caption("Remove all uploaded files to return to the built-in library.")
else:
    st.sidebar.caption(f"{imported_count} questions loaded from `{QUESTIONS_DIR}/`")
if st.sidebar.button("Reload Markdown files"):
    reset_review_state()
    refresh_questions()
    st.rerun()

if page == "Review":
    render_review_page()
else:
    render_browse_page()
