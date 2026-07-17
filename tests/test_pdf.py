from pathlib import Path

import pytest

from recall.ingestion import extract_chunks

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def _first_pdf() -> Path | None:
    return next(iter(sorted(DATA_DIR.glob("*.pdf"))), None)


@pytest.mark.skipif(_first_pdf() is None, reason="kein Referenz-PDF in data/")
def test_extracts_one_chunk_per_page():
    pdf = _first_pdf()
    chunks = extract_chunks(pdf)
    assert chunks, "PDF ergab keine Chunks"
    assert [c.page_number for c in chunks] == list(range(1, len(chunks) + 1))
    assert all(c.source_file == pdf.name for c in chunks)
