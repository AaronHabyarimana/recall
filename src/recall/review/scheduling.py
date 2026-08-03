"""Dünne Hülle um FSRS.

`fsrs.Card` heißt wie `recall.generation.models.Card`, meint aber etwas anderes
(Planungszustand statt Karteninhalt). Deshalb hier durchgängig als `FSRSCard`.
FSRS rechnet ausschließlich in UTC.
"""

from datetime import UTC, datetime
from functools import cache

from fsrs import Card as FSRSCard
from fsrs import Rating, ReviewLog, Scheduler

from recall.config import config


def now_utc() -> datetime:
    return datetime.now(UTC)


@cache
def scheduler() -> Scheduler:
    retention = config().get("review", {}).get("desired_retention", 0.9)
    return Scheduler(desired_retention=retention)


def new_card(now: datetime | None = None) -> FSRSCard:
    """Eine ungelernte Karte, ab `now` fällig. `now` injizierbar für Tests."""
    return FSRSCard(due=now or now_utc())


def review(
    fsrs_card: FSRSCard, rating: Rating, now: datetime | None = None
) -> tuple[FSRSCard, ReviewLog]:
    """Bewertung anwenden. `now` ist injizierbar, damit Tests nicht warten müssen."""
    return scheduler().review_card(fsrs_card, rating, review_datetime=now or now_utc())
