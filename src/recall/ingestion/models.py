from pydantic import BaseModel


class Chunk(BaseModel):
    """Ein atomarer Textabschnitt aus einer Quelle – bei Folien: eine Folie."""

    text: str
    source_file: str
    page_number: int  # 1-basiert
    chapter: str | None = None
