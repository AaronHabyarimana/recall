import pytest

from recall.generation import build_prompt, parse_cards
from recall.ingestion import Chunk

CHUNK = Chunk(
    text="k-Means minimiert die Summe quadrierter Abstände.", source_file="v.pdf", page_number=7
)


def test_prompt_contains_chunk_text_and_source():
    prompt = build_prompt(CHUNK)
    assert CHUNK.text in prompt
    assert "Seite 7" in prompt
    assert "v.pdf" in prompt


def test_parse_valid_json():
    response = '[{"frage": "Was minimiert k-Means?", "antwort": "Die Summe quadrierter Abstände."}]'
    cards = parse_cards(response, CHUNK)
    assert len(cards) == 1
    assert cards[0].question == "Was minimiert k-Means?"
    assert cards[0].source_file == "v.pdf"
    assert cards[0].page_number == 7


def test_parse_strips_code_fences():
    response = '```json\n[{"frage": "F?", "antwort": "A."}]\n```'
    cards = parse_cards(response, CHUNK)
    assert len(cards) == 1


def test_parse_empty_list_for_content_free_slides():
    assert parse_cards("[]", CHUNK) == []


def test_parse_rejects_non_json():
    with pytest.raises(ValueError, match="kein JSON"):
        parse_cards("Hier sind deine Karten: ...", CHUNK)


def test_parse_rejects_missing_keys():
    with pytest.raises(ValueError, match="frage/antwort"):
        parse_cards('[{"question": "englischer Key"}]', CHUNK)
