from recall.ingestion import Chunk, clean_chunks


def _chunk(text: str, page: int) -> Chunk:
    return Chunk(text=text, source_file="vorlesung.pdf", page_number=page)


def test_removes_repeated_header_and_page_numbers():
    chunks = [
        _chunk(f"Vorlesung Algorithmen – Prof. X\nInhalt von Seite {i}, ausreichend lang.\n{i}", i)
        for i in range(1, 11)
    ]
    cleaned = clean_chunks(chunks)
    assert len(cleaned) == 10
    for chunk in cleaned:
        assert "Prof. X" not in chunk.text
        assert chunk.text == f"Inhalt von Seite {chunk.page_number}, ausreichend lang."


def test_drops_empty_and_tiny_chunks():
    chunks = [
        _chunk("", 1),
        _chunk("   \n  \n", 2),
        _chunk("kurz", 3),
        _chunk("Dieser Chunk hat genug Inhalt, um behalten zu werden.", 4),
    ]
    cleaned = clean_chunks(chunks)
    assert [c.page_number for c in cleaned] == [4]


def test_normalizes_bullets_and_whitespace():
    chunks = [_chunk("•  Erster   Punkt mit Inhalt\n▪ Zweiter Punkt mit Inhalt", 1)]
    cleaned = clean_chunks(chunks)
    assert cleaned[0].text == "- Erster Punkt mit Inhalt\n- Zweiter Punkt mit Inhalt"


def test_no_header_removal_on_few_pages():
    # Bei sehr wenigen Seiten kann man Header nicht zuverlässig erkennen – nichts entfernen.
    chunks = [_chunk("Gleiche Zeile auf beiden Seiten, lang genug.", i) for i in (1, 2)]
    cleaned = clean_chunks(chunks)
    assert len(cleaned) == 2
    assert "Gleiche Zeile" in cleaned[0].text
