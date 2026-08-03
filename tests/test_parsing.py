import pytest

from recall.parsing import parse_json_list


def test_parses_plain_json_list():
    assert parse_json_list('[{"a": 1}]') == [{"a": 1}]


def test_strips_code_fences():
    assert parse_json_list('```json\n[{"a": 1}]\n```') == [{"a": 1}]


def test_rejects_non_json():
    with pytest.raises(ValueError, match="kein JSON"):
        parse_json_list("Hier ist deine Antwort: ...")


def test_rejects_object_instead_of_list():
    with pytest.raises(ValueError, match="keine Liste"):
        parse_json_list('{"a": 1}')
