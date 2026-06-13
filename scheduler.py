"""Small, predictable spaced-repetition scheduler."""

from __future__ import annotations

from datetime import date, timedelta


def schedule_review(
    rating: str,
    current_interval: int = 0,
    ease_score: float = 2.5,
) -> tuple[str, int, float]:
    """Return next review date, interval in days, and updated ease score."""
    rating = rating.lower()

    if rating == "again":
        interval = 0
        ease_score = max(1.3, ease_score - 0.2)
    elif rating == "hard":
        interval = max(1, round(max(current_interval, 1) * 1.2))
        ease_score = max(1.3, ease_score - 0.1)
    elif rating == "good":
        interval = max(3, round(current_interval * 1.7))
        ease_score = min(3.0, ease_score + 0.05)
    elif rating == "easy":
        interval = max(7, round(current_interval * 2.2))
        ease_score = min(3.0, ease_score + 0.15)
    else:
        raise ValueError(f"Unknown rating: {rating}")

    next_review = date.today() + timedelta(days=interval)
    return next_review.isoformat(), interval, round(ease_score, 2)
