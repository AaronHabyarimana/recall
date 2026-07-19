import pytest
from google.genai import errors

from recall import llm_client


class _FakeResponse:
    text = "Antwort"


def _client_error(code: int) -> errors.ClientError:
    return errors.ClientError(code, {"error": {"code": code, "message": "quota", "status": "x"}})


def _fake_client(fail_times: int, code: int = 429):
    """Client-Attrappe, deren generate_content erst `fail_times`-mal scheitert."""
    calls = {"n": 0}

    class Models:
        def generate_content(self, model, contents):
            calls["n"] += 1
            if calls["n"] <= fail_times:
                raise _client_error(code)
            return _FakeResponse()

    class Client:
        models = Models()

    return Client(), calls


def test_retries_on_rate_limit(monkeypatch):
    client, calls = _fake_client(fail_times=2)
    monkeypatch.setattr(llm_client, "_client", lambda: client)
    monkeypatch.setattr(llm_client, "_model_name", lambda: "test-model")
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
    assert llm_client.complete("Prompt") == "Antwort"
    assert calls["n"] == 3


def test_gives_up_after_max_attempts(monkeypatch):
    client, calls = _fake_client(fail_times=99)
    monkeypatch.setattr(llm_client, "_client", lambda: client)
    monkeypatch.setattr(llm_client, "_model_name", lambda: "test-model")
    monkeypatch.setattr(llm_client.time, "sleep", lambda s: None)
    with pytest.raises(errors.ClientError):
        llm_client.complete("Prompt")
    assert calls["n"] == llm_client._MAX_ATTEMPTS


def test_other_errors_are_not_retried(monkeypatch):
    client, calls = _fake_client(fail_times=99, code=400)
    monkeypatch.setattr(llm_client, "_client", lambda: client)
    monkeypatch.setattr(llm_client, "_model_name", lambda: "test-model")
    with pytest.raises(errors.ClientError):
        llm_client.complete("Prompt")
    assert calls["n"] == 1
