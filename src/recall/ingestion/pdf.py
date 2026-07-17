"""PDF → rohe Chunks, eine Seite = ein Chunk."""

from pathlib import Path

import pymupdf

from recall.ingestion.models import Chunk


def extract_chunks(pdf_path: str | Path) -> list[Chunk]:
    pdf_path = Path(pdf_path)
    with pymupdf.open(pdf_path) as doc:
        return [
            Chunk(text=page.get_text(), source_file=pdf_path.name, page_number=page.number + 1)
            for page in doc
        ]
