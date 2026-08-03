import pytest
from pydantic import ValidationError

from recall.generation import Card
from recall.ingestion import Chunk


def _card(question: str = "Was ist k-Means?", page: int = 7) -> Card:
    return Card(
        question=question, answer="Ein Clusterverfahren.", source_file="v.pdf", page_number=page
    )


def test_card_id_is_stable_for_same_content():
    assert _card().card_id == _card().card_id


def test_card_id_differs_by_question_and_page():
    assert _card().card_id != _card(question="Was ist DBSCAN?").card_id
    assert _card().card_id != _card(page=8).card_id


def test_card_id_survives_json_roundtrip():
    original = _card()
    assert Card.model_validate(original.model_dump()).card_id == original.card_id


def test_card_id_ignores_answer():
    """Eine korrigierte Antwort darf die Identität der Karte nicht zerstören."""
    other = Card(
        question="Was ist k-Means?", answer="Andere Antwort.", source_file="v.pdf", page_number=7
    )
    assert other.card_id == _card().card_id


def test_chunk_minimal():
    chunk = Chunk(text="Hallo", source_file="foo.pdf", page_number=1)
    assert chunk.chapter is None


def test_chunk_requires_page_number():
    with pytest.raises(ValidationError):
        Chunk(text="Hallo", source_file="foo.pdf")
