"""Streamlit MVP for reviewing Markdown multiple-choice questions."""

from pathlib import Path

import streamlit as st

from db import (
    get_all_questions,
    get_due_questions,
    initialize_database,
    record_review,
    sync_questions,
)
from parser import load_questions


QUESTIONS_DIR = Path("questions")


def refresh_questions() -> int:
    questions = load_questions(QUESTIONS_DIR)
    sync_questions(questions)
    return len(questions)


def reset_review_state() -> None:
    for key in ("review_queue", "review_index", "submitted", "was_correct"):
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if key.startswith("choice_"):
            del st.session_state[key]


def start_review() -> None:
    st.session_state.review_queue = get_due_questions()
    st.session_state.review_index = 0
    st.session_state.submitted = False
    st.session_state.was_correct = False


def next_question(rating: str, question: dict) -> None:
    record_review(question["id"], st.session_state.was_correct, rating)
    for choice_index in range(len(question["choices"])):
        st.session_state.pop(f"choice_{question['id']}_{choice_index}", None)
    st.session_state.review_index += 1
    st.session_state.submitted = False
    st.session_state.was_correct = False
    st.rerun()


def render_review_page() -> None:
    st.header("Review")
    due_count = len(get_due_questions())
    total_count = len(get_all_questions())
    st.caption(f"{due_count} due today | {total_count} questions available")

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
    questions = get_all_questions()
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
st.sidebar.caption(f"{imported_count} questions loaded from `{QUESTIONS_DIR}/`")
if st.sidebar.button("Reload Markdown files"):
    reset_review_state()
    refresh_questions()
    st.rerun()

if page == "Review":
    render_review_page()
else:
    render_browse_page()
