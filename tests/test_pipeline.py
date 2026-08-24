"""Die Verdrahtung, die zwischen den Unit-Tests durchfaellt.

Die einzelnen Bausteine sind anderswo abgedeckt. Hier laeuft der Weg, den ein
Mensch tatsaechlich geht: `recall generate` auf ein PDF, `recall critic` auf das
Ergebnis, `recall review import` in die Datenbank, lernen, `recall review stats`.
Nur der LLM ist ersetzt, alles andere ist echt.

Anders als die uebrigen Tests laeuft dieser auf der echten Uhr. Die CLI nimmt
keinen Zeitpunkt entgegen, und eine eingefrorene Zeit vor dem Import haette zur
Folge, dass gerade erst importierte Karten noch gar nicht faellig sind.
"""

import json
from pathlib import Path

import pytest
from fsrs import Rating

from recall.cli import main
from recall.review.db import connect, due_cards, save_review, stats
from recall.review.scheduling import now_utc
from recall.review.scheduling import review as fsrs_review
from tests.helpers import DEMO, PDF


@pytest.fixture
def db(tmp_path) -> Path:
    return tmp_path / "lern.db"


def test_import_lernen_stats_am_stueck(db, capsys):
    """Der Weg vom geprueften JSON bis zur Statistik, ueber die echte CLI."""
    main(["review", "import", str(DEMO), "--db", str(db)])
    ausgabe = capsys.readouterr().out
    assert "17 Karten in der Datei, davon 14 lernbar" in ausgabe
    assert "17 neu übernommen, 0 aktualisiert" in ausgabe

    conn = connect(db)
    faellig = due_cards(conn)
    assert len(faellig) == 14, "verworfene Karten gehoeren nicht ins Pensum"

    # Drei Karten lernen, direkt ueber die Bibliothek: die interaktive Schleife
    # in cmd_lernen liest von stdin und ist hier nicht der Punkt.
    for karte, plan in faellig[:3]:
        neuer_plan, protokoll = fsrs_review(plan, Rating.Good, now=now_utc())
        save_review(conn, karte.card_id, neuer_plan, protokoll)

    zahlen = stats(conn)
    assert zahlen["gesamt"] == 17
    assert zahlen["lernbar"] == 14
    assert zahlen["faellig"] == 11, "die drei gelernten sind erst spaeter wieder dran"
    assert zahlen["bewertungen"] == 3
    conn.close()

    main(["review", "stats", "--db", str(db)])
    assert "17 gesamt, 14 lernbar" in capsys.readouterr().out


def test_erneuter_import_behaelt_den_lernstand(db, capsys):
    """Ein zweiter Critic-Lauf darf keine Wiederholungen loeschen."""
    main(["review", "import", str(DEMO), "--db", str(db)])
    capsys.readouterr()

    conn = connect(db)
    karte, plan = due_cards(conn)[0]
    neuer_plan, protokoll = fsrs_review(plan, Rating.Easy, now=now_utc())
    save_review(conn, karte.card_id, neuer_plan, protokoll)
    faellig_danach = len(due_cards(conn))
    conn.close()

    main(["review", "import", str(DEMO), "--db", str(db)])
    assert "0 neu übernommen, 17 aktualisiert" in capsys.readouterr().out

    conn = connect(db)
    assert len(due_cards(conn)) == faellig_danach
    assert stats(conn)["bewertungen"] == 1
    conn.close()


def test_verworfene_karten_auf_wunsch_mitlernen(db, capsys):
    main(["review", "import", str(DEMO), "--db", str(db), "--auch-verworfene"])
    assert "davon 17 lernbar" in capsys.readouterr().out

    conn = connect(db)
    assert len(due_cards(conn)) == 17
    conn.close()


def test_generate_und_critic_bis_in_die_datenbank(db, tmp_path, monkeypatch, capsys):
    """PDF rein, Datenbank raus. Nur der LLM ist ersetzt.

    Das Modell antwortet in beiden Stufen mit deutschen Schluesseln (frage/antwort
    beim Generieren, index/keep beim Bewerten), so wie es die Prompts verlangen.
    """
    antworten = iter(
        [
            # generate: eine Karte je Folie
            '[{"frage": "Was ist das Ziel?", "antwort": "Verstehen und Vorhersagen."}]',
            '[{"frage": "Was macht Clustering?", "antwort": "Es partitioniert Daten."}]',
            '[{"frage": "Was steht am Ende?", "antwort": "Zusammenfassung und Ausblick."}]',
            # critic: die dritte Karte fliegt als trivia raus
            '[{"index": 0, "keep": true, "issue": null, "reason": "prueft ein Konzept"},'
            ' {"index": 1, "keep": true, "issue": null, "reason": "prueft ein Konzept"},'
            ' {"index": 2, "keep": false, "issue": "trivia", "reason": "reine Gliederung"}]',
        ]
    )
    # complete wird in beide Module hineinimportiert, also dort ersetzen.
    monkeypatch.setattr("recall.generation.generate.complete", lambda prompt: next(antworten))
    monkeypatch.setattr("recall.critic.judge.complete", lambda prompt: next(antworten))

    roh = tmp_path / "karten.json"
    geprueft = tmp_path / "karten_geprueft.json"

    main(["generate", str(PDF), "--out", str(roh)])
    erzeugt = json.loads(roh.read_text(encoding="utf-8"))
    assert len(erzeugt) == 3
    assert all(k["source_file"] == "folien.pdf" for k in erzeugt)
    assert [k["page_number"] for k in erzeugt] == [1, 2, 3]

    main(["critic", str(roh), "--out", str(geprueft)])
    bewertet = json.loads(geprueft.read_text(encoding="utf-8"))
    assert sum(1 for k in bewertet if k["keep"]) == 2
    assert any(k["issue"] == "trivia" for k in bewertet)

    capsys.readouterr()
    main(["review", "import", str(geprueft), "--db", str(db)])
    assert "3 Karten in der Datei, davon 2 lernbar" in capsys.readouterr().out

    conn = connect(db)
    assert stats(conn)["lernbar"] == 2
    conn.close()


def test_abgebrochener_generate_lauf_behaelt_das_teilergebnis(db, tmp_path, monkeypatch, capsys):
    """Ein API-Fehler mittendrin darf die schon erzeugten Karten nicht verwerfen."""
    from google.genai import errors

    aufrufe = {"n": 0}

    def flaky(prompt: str) -> str:
        aufrufe["n"] += 1
        if aufrufe["n"] > 1:
            raise errors.ClientError(
                429, {"message": "Kontingent erschöpft", "status": "RESOURCE_EXHAUSTED"}
            )
        return '[{"frage": "Was ist das Ziel?", "antwort": "Verstehen und Vorhersagen."}]'

    monkeypatch.setattr("recall.generation.generate.complete", flaky)

    roh = tmp_path / "karten.json"
    main(["generate", str(PDF), "--out", str(roh)])

    ausgabe = capsys.readouterr().out
    assert "Abbruch bei Seite 2" in ausgabe
    assert len(json.loads(roh.read_text(encoding="utf-8"))) == 1
