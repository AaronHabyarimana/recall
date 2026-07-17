import pytest
from pydantic import ValidationError

from recall.ingestion import Chunk


def test_chunk_minimal():
    chunk = Chunk(text="Hallo", source_file="foo.pdf", page_number=1)
    assert chunk.chapter is None


def test_chunk_requires_page_number():
    with pytest.raises(ValidationError):
        Chunk(text="Hallo", source_file="foo.pdf")
