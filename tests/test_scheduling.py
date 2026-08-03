from datetime import UTC, datetime

from fsrs import Card as FSRSCard
from fsrs import Rating

from recall.review.scheduling import new_card, now_utc, review

JETZT = datetime(2026, 8, 3, 12, 0, tzinfo=UTC)


def test_new_card_is_due_immediately():
    assert new_card().due <= now_utc()
    assert new_card(JETZT).due == JETZT


def test_again_schedules_earlier_than_easy():
    schwer, _ = review(new_card(), Rating.Again, now=JETZT)
    leicht, _ = review(new_card(), Rating.Easy, now=JETZT)
    assert schwer.due < leicht.due


def test_review_returns_utc_aware_due():
    card, log = review(new_card(), Rating.Good, now=JETZT)
    assert card.due.tzinfo is not None
    assert card.due.utcoffset() == UTC.utcoffset(None)
    assert log.review_datetime == JETZT


def test_repeated_good_ratings_extend_the_interval():
    """Nach mehreren guten Bewertungen muss der Abstand deutlich wachsen."""
    card = new_card()
    jetzt = JETZT
    abstaende = []
    for _ in range(4):
        card, _ = review(card, Rating.Good, now=jetzt)
        abstaende.append(card.due - jetzt)
        jetzt = card.due
    assert abstaende[-1] > abstaende[0]


def test_json_roundtrip_preserves_state():
    card, _ = review(new_card(), Rating.Hard, now=JETZT)
    wieder = FSRSCard.from_json(card.to_json())
    assert wieder.due == card.due
    assert wieder.stability == card.stability
    assert wieder.difficulty == card.difficulty
