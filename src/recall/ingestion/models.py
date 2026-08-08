from pydantic import BaseModel


class Chunk(BaseModel):
    """Ein atomarer Textabschnitt aus einer Quelle – bei Folien: eine Folie."""

    text: str
    source_file: str
    page_number: int  # 1-basiert
    # noch von niemandem gefüllt: Kapitel stünden in der Gliederung, nicht auf der
    # Folie selbst. Das Feld hält den Platz für eine Auswertung des Inhaltsverzeichnisses.
    chapter: str | None = None
