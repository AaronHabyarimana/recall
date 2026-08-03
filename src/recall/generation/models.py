import hashlib

from pydantic import BaseModel, computed_field


class Card(BaseModel):
    """Eine Lernkarte (Frage/Antwort) mit Herkunftsangabe zur Quellfolie."""

    question: str
    answer: str
    source_file: str
    page_number: int  # 1-basiert

    @computed_field  # type: ignore[prop-decorator]
    @property
    def card_id(self) -> str:
        """Stabile Kennung aus dem Inhalt.

        Bewusst abgeleitet statt zufällig: schon gespeicherte Karten bekommen beim
        erneuten Laden dieselbe ID, ohne Migration. Die Antwort geht nicht ein, damit
        eine korrigierte Antwort die Identität der Karte nicht zerstört.
        """
        key = f"{self.question}|{self.source_file}|{self.page_number}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
