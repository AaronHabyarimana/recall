"""Textextraktion aus PDFs.

Das Referenz-PDF liegt unter tests/fixtures und ist mit PyMuPDF selbst erzeugt.
Vorher zeigte dieser Test auf data/, das ist aber gitignored: der skipif griff in
der CI immer, und der Lauf war gruen, ohne PyMuPDF je auszufuehren. Ein stiller
Skip ist schlimmer als ein fehlender Test, weil er wie Abdeckung aussieht.
"""

from recall.ingestion import extract_chunks
from tests.helpers import PDF


def test_eine_seite_ergibt_einen_chunk():
    chunks = extract_chunks(PDF)
    assert len(chunks) == 3


def test_seitennummern_sind_einsbasiert_und_lueckenlos():
    chunks = extract_chunks(PDF)
    assert [c.page_number for c in chunks] == [1, 2, 3]


def test_quelle_ist_der_dateiname():
    assert all(c.source_file == "folien.pdf" for c in extract_chunks(PDF))


def test_text_landet_bei_der_richtigen_seite():
    chunks = extract_chunks(PDF)
    assert "Ziel der Vorlesung" in chunks[0].text
    assert "Clustering" in chunks[1].text
    assert "Ausblick" in chunks[2].text


def test_pfad_darf_ein_string_sein():
    """extract_chunks nimmt str | Path, die CLI reicht einen String durch."""
    assert extract_chunks(str(PDF)) == extract_chunks(PDF)
