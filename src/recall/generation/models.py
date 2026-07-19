from pydantic import BaseModel


class Card(BaseModel):
    """Eine Lernkarte (Frage/Antwort) mit Herkunftsangabe zur Quellfolie."""

    question: str
    answer: str
    source_file: str
    page_number: int  # 1-basiert
