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


def test_drops_single_character_plot_markers():
    chunks = [_chunk("k-Means Beispiel mit genug Inhalt\nx\nx\ne\nh\nClusters after round 1", 1)]
    cleaned = clean_chunks(chunks)
    assert cleaned[0].text == "k-Means Beispiel mit genug Inhalt\nClusters after round 1"


def test_buildup_slides_keep_only_fullest_version():
    # Aufbau-Folien: gleiche Folie erscheint mehrfach mit wachsendem Inhalt
    chunks = [
        _chunk("Partitionierung von Daten\n- Grundidee der Aufteilung erklärt", 3),
        _chunk(
            "Partitionierung von Daten\n- Grundidee der Aufteilung erklärt\n- within-cluster klein",
            4,
        ),
        _chunk(
            "Partitionierung von Daten\n- Grundidee der Aufteilung erklärt\n"
            "- within-cluster klein\n- between-cluster groß",
            5,
        ),
    ]
    cleaned = clean_chunks(chunks)
    assert [c.page_number for c in cleaned] == [5]
    assert "between-cluster" in cleaned[0].text


def test_identical_consecutive_slides_collapse_to_one():
    chunks = [_chunk("Exakt gleicher Folieninhalt, lang genug.", i) for i in (1, 2)]
    cleaned = clean_chunks(chunks)
    assert [c.page_number for c in cleaned] == [2]


def test_unrelated_consecutive_slides_are_kept():
    chunks = [
        _chunk("Erste Folie über k-Means und Zentroiden.", 1),
        _chunk("Zweite Folie über hierarchisches Clustering.", 2),
    ]
    cleaned = clean_chunks(chunks)
    assert [c.page_number for c in cleaned] == [1, 2]


def test_no_header_removal_on_few_pages():
    # Bei sehr wenigen Seiten kann man Header nicht zuverlässig erkennen – nichts entfernen.
    chunks = [
        _chunk(f"Gleiche Kopfzeile auf beiden Seiten\nEigener Inhalt der Seite {i}, lang genug.", i)
        for i in (1, 2)
    ]
    cleaned = clean_chunks(chunks)
    assert len(cleaned) == 2
    assert "Gleiche Kopfzeile" in cleaned[0].text
