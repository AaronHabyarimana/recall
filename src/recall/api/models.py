"""Die Modelle, die über HTTP gehen.

Bewusst eigene Klassen statt `recall.generation.models.Card` durchzureichen. Das
interne Modell ist ein Pipeline-Zwischenstand und darf sich ändern, ohne dass ein
Client bricht. Umgekehrt taucht hier auf, was die Datenbank dazurechnet und was das
interne Modell gar nicht kennt: Fälligkeit, Anzahl Bewertungen, Urteil des Critics.
"""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, Field

# FSRS kennt genau vier Bewertungen. Als Literal statt als int, damit FastAPI einen
# falschen Wert mit 422 abweist, statt ihn an FSRS weiterzureichen.
Rating = Literal[1, 2, 3, 4]


class CardOut(BaseModel):
    card_id: str
    question: str
    answer: str
    source_file: str
    page_number: int
    keep: bool
    issue: str | None = None
    reason: str | None = None
    due: datetime | None = None
    bewertungen: int = 0

    @classmethod
    def from_row(cls, row) -> Self:  # type: ignore[no-untyped-def]
        return cls(**{**dict(row), "keep": bool(row["keep"])})


class DueCardOut(BaseModel):
    """Eine fällige Karte. Ohne Urteilsfelder, die sind beim Lernen irrelevant."""

    card_id: str
    question: str
    answer: str
    source_file: str
    page_number: int
    due: datetime


class StatsOut(BaseModel):
    gesamt: int
    lernbar: int
    faellig: int
    neu: int
    naechste: datetime | None = None
    bewertungen: int


class ReviewIn(BaseModel):
    card_id: str
    rating: Rating = Field(description="1 Again, 2 Hard, 3 Good, 4 Easy")


class ReviewOut(BaseModel):
    """Was der Client nach einer Bewertung wissen will: wann kommt die Karte wieder."""

    card_id: str
    rating: Rating
    due: datetime


class HealthOut(BaseModel):
    status: Literal["ok"]
    cards: int
