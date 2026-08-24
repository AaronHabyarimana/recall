"""Die Suchreihenfolge aus recall.config.

Der Fallback auf die Paketdatei ist der Grund, warum ein installiertes Wheel
überhaupt läuft: dort gibt es kein Projektwurzelverzeichnis mehr.
"""

import pytest

from recall.config import config

BEISPIEL = b'[llm]\nmodel = "aus-der-testdatei"\n'


@pytest.fixture(autouse=True)
def _ohne_cache():
    """config() ist gecached, sonst leckt der erste Testfall in alle weiteren."""
    config.cache_clear()
    yield
    config.cache_clear()


def test_umgebungsvariable_hat_vorrang(tmp_path, monkeypatch):
    datei = tmp_path / "eigene.toml"
    datei.write_bytes(BEISPIEL)
    monkeypatch.setenv("RECALL_CONFIG", str(datei))
    # Auch wenn im Arbeitsverzeichnis eine config.toml liegt, gewinnt die Variable.
    (tmp_path / "config.toml").write_bytes(b'[llm]\nmodel = "daneben"\n')
    monkeypatch.chdir(tmp_path)

    assert config()["llm"]["model"] == "aus-der-testdatei"


def test_arbeitsverzeichnis_wird_genutzt(tmp_path, monkeypatch):
    monkeypatch.delenv("RECALL_CONFIG", raising=False)
    (tmp_path / "config.toml").write_bytes(BEISPIEL)
    monkeypatch.chdir(tmp_path)

    assert config()["llm"]["model"] == "aus-der-testdatei"


def test_paketdatei_als_rueckfall(tmp_path, monkeypatch):
    """Kein RECALL_CONFIG, keine Datei im Arbeitsverzeichnis: das ist der Wheel-Fall."""
    monkeypatch.delenv("RECALL_CONFIG", raising=False)
    monkeypatch.chdir(tmp_path)

    geladen = config()
    assert "llm" in geladen
    assert "desired_retention" in geladen["review"]


def test_falscher_pfad_meldet_sich(tmp_path, monkeypatch):
    """Ein Tippfehler in RECALL_CONFIG darf nicht still zum Standard zurückfallen."""
    monkeypatch.setenv("RECALL_CONFIG", str(tmp_path / "gibtsnicht.toml"))

    with pytest.raises(SystemExit, match="gibtsnicht.toml"):
        config()
