import pytest

from recall.critic import (
    build_dedupe_prompt,
    build_judge_prompt,
    find_duplicate_candidates,
    parse_dedupe_response,
    parse_verdicts,
)
from recall.generation import Card


def card(question: str, answer: str = "Eine Antwort.", page: int = 1) -> Card:
    return Card(question=question, answer=answer, source_file="bd1.pdf", page_number=page)


CARDS = [card("Was ist k-Means?", page=7), card("Was ist Clustering?", page=9)]


def test_judge_prompt_lists_all_cards_with_index():
    prompt = build_judge_prompt(CARDS)
    assert "[0] Frage: Was ist k-Means?" in prompt
    assert "[1] Frage: Was ist Clustering?" in prompt


def test_parse_verdicts_maps_index_to_card_id():
    response = """[
        {"index": 0, "keep": true, "issue": null, "reason": "Gutes Konzept."},
        {"index": 1, "keep": false, "issue": "trivia", "reason": "Nur ein Beispiel."}
    ]"""
    verdicts = parse_verdicts(response, CARDS)
    assert [v.card_id for v in verdicts] == [CARDS[0].card_id, CARDS[1].card_id]
    assert verdicts[0].keep is True
    assert verdicts[1].issue == "trivia"


def test_parse_verdicts_clears_issue_on_kept_cards():
    response = '[{"index": 0, "keep": true, "issue": "trivia", "reason": "x"}]'
    assert parse_verdicts(response, CARDS[:1])[0].issue is None


def test_parse_verdicts_normalizes_unknown_issue():
    response = '[{"index": 0, "keep": false, "issue": "quatsch", "reason": "x"}]'
    assert parse_verdicts(response, CARDS[:1])[0].issue == "unklar"


def test_parse_verdicts_rejects_missing_card():
    response = '[{"index": 0, "keep": true, "reason": "x"}]'
    with pytest.raises(ValueError, match="Kein Urteil"):
        parse_verdicts(response, CARDS)


def test_parse_verdicts_rejects_index_out_of_range():
    response = '[{"index": 5, "keep": true, "reason": "x"}]'
    with pytest.raises(ValueError, match="außerhalb"):
        parse_verdicts(response, CARDS)


def test_parse_verdicts_rejects_duplicate_index():
    response = (
        '[{"index": 0, "keep": true, "reason": "x"}, {"index": 0, "keep": false, "reason": "y"}]'
    )
    with pytest.raises(ValueError, match="doppelt"):
        parse_verdicts(response, CARDS)


def test_find_duplicate_candidates_finds_near_identical_questions():
    cards = [
        card("Was ist das Discard Set (DS) im BFR-Algorithmus?", page=40),
        card("Was zeichnet das Discard set (DS) im BFR-Algorithmus aus?", page=42),
    ]
    assert find_duplicate_candidates(cards) == [(0, 1)]


def test_find_duplicate_candidates_ignores_unrelated_questions():
    cards = [card("Was ist k-Means?"), card("Wozu dient der BFR-Algorithmus?")]
    assert find_duplicate_candidates(cards) == []


def test_agglomerativ_und_divisiv_bleiben_dem_modell_ueberlassen():
    """Das ähnlichste Paar im echten Foliensatz ist kein Duplikat.

    Die Heuristik meldet es (0.89) - erst das Modell darf es verwerfen.
    """
    cards = [
        card("Wie beginnt der agglomerative Prozess beim hierarchischen Clustering?", page=30),
        card("Wie beginnt der divisive Prozess beim hierarchischen Clustering?", page=31),
    ]
    pairs = find_duplicate_candidates(cards)
    assert pairs == [(0, 1)]
    assert parse_dedupe_response('[{"paar": 0, "gleich": false}]', pairs) == []


def test_dedupe_prompt_contains_both_questions():
    pairs = [(0, 1)]
    prompt = build_dedupe_prompt(CARDS, pairs)
    assert "[0] A: Was ist k-Means?" in prompt
    assert "B: Was ist Clustering?" in prompt


def test_parse_dedupe_response_keeps_confirmed_pairs_only():
    pairs = [(0, 1), (0, 2)]
    response = '[{"paar": 0, "gleich": true}, {"paar": 1, "gleich": false}]'
    assert parse_dedupe_response(response, pairs) == [(0, 1)]


def test_parse_dedupe_response_rejects_unknown_pair():
    with pytest.raises(ValueError, match="außerhalb"):
        parse_dedupe_response('[{"paar": 9, "gleich": true}]', [(0, 1)])
