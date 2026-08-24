"""Die HTTP-Schicht.

Gegen eine echte SQLite-Datei im tmp_path, befüllt aus `samples/demo_cards.json`.
Kein Netz, kein API-Key: die Demokarten liegen im Repo, weil sie auch der
Quickstart im README braucht.
"""

import pytest
from fastapi.testclient import TestClient

from recall.api.app import create_app
from recall.review.db import connect, import_cards
from tests.helpers import JETZT


@pytest.fixture
def client(tmp_path, demo_karten) -> TestClient:
    db = tmp_path / "test.db"
    conn = connect(db)
    import_cards(conn, demo_karten, now=JETZT)
    conn.close()
    with TestClient(create_app(db)) as c:
        yield c


@pytest.fixture
def lernbare_id(demo_karten) -> str:
    return next(k["card_id"] for k in demo_karten if k["keep"])


@pytest.fixture
def verworfene_id(demo_karten) -> str:
    return next(k["card_id"] for k in demo_karten if not k["keep"])


def test_health_meldet_kartenzahl(client, demo_karten):
    antwort = client.get("/health")
    assert antwort.status_code == 200
    assert antwort.json() == {"status": "ok", "cards": len(demo_karten)}


def test_stats_zaehlt_lernbare_getrennt(client, demo_karten):
    daten = client.get("/stats").json()
    assert daten["gesamt"] == len(demo_karten)
    assert daten["lernbar"] == sum(1 for k in demo_karten if k["keep"])
    assert daten["lernbar"] < daten["gesamt"], "die Demodaten sollen verworfene enthalten"
    assert daten["bewertungen"] == 0


def test_cards_zeigt_verworfene_nur_auf_anfrage(client, demo_karten):
    ohne = client.get("/cards").json()
    mit = client.get("/cards", params={"verworfene": True}).json()
    assert len(ohne) == sum(1 for k in demo_karten if k["keep"])
    assert len(mit) == len(demo_karten)
    assert all(k["keep"] for k in ohne)


def test_cards_filtert_nach_suche(client):
    treffer = client.get("/cards", params={"suche": "Clustering"}).json()
    assert treffer, "die Demodaten enthalten eine Karte zum Clustering"
    assert all("Clustering" in k["question"] or "Clustering" in k["answer"] for k in treffer)


def test_cards_filtert_nach_quelle(client):
    assert client.get("/cards", params={"quelle": "bd1.pdf"}).json()
    assert client.get("/cards", params={"quelle": "gibtsnicht.pdf"}).json() == []


def test_einzelne_karte(client, lernbare_id):
    daten = client.get(f"/cards/{lernbare_id}").json()
    assert daten["card_id"] == lernbare_id
    assert daten["question"]


def test_unbekannte_karte_ist_404(client):
    antwort = client.get("/cards/gibtsnicht")
    assert antwort.status_code == 404
    assert "gibtsnicht" in antwort.json()["detail"]


def test_due_liefert_alle_lernbaren_beim_ersten_mal(client, demo_karten):
    faellig = client.get("/due").json()
    assert len(faellig) == sum(1 for k in demo_karten if k["keep"])
    assert all("issue" not in k for k in faellig), "Urteilsfelder gehören nicht ins Lernpensum"


def test_due_respektiert_limit(client):
    assert len(client.get("/due", params={"limit": 3}).json()) == 3


def test_due_weist_unsinniges_limit_ab(client):
    assert client.get("/due", params={"limit": 0}).status_code == 422


def test_bewertung_verschiebt_die_faelligkeit(client, lernbare_id):
    vorher = client.get(f"/cards/{lernbare_id}").json()["due"]

    antwort = client.post("/reviews", json={"card_id": lernbare_id, "rating": 3})
    assert antwort.status_code == 201
    assert antwort.json()["due"] > vorher

    nachher = client.get(f"/cards/{lernbare_id}").json()
    assert nachher["due"] == antwort.json()["due"]
    assert nachher["bewertungen"] == 1


def test_bewertung_verkleinert_das_pensum(client):
    vorher = len(client.get("/due").json())
    karte = client.get("/due", params={"limit": 1}).json()[0]
    client.post("/reviews", json={"card_id": karte["card_id"], "rating": 4})
    assert len(client.get("/due").json()) == vorher - 1


@pytest.mark.parametrize("rating", [0, 5, 7, -1, "gut", None])
def test_ungueltige_bewertung_ist_422(client, lernbare_id, rating):
    """FSRS kennt nur 1 bis 4. Der falsche Wert darf gar nicht erst bis FSRS kommen."""
    antwort = client.post("/reviews", json={"card_id": lernbare_id, "rating": rating})
    assert antwort.status_code == 422


def test_bewertung_unbekannter_karte_ist_404(client):
    antwort = client.post("/reviews", json={"card_id": "gibtsnicht", "rating": 3})
    assert antwort.status_code == 404


def test_bewertung_verworfener_karte_ist_409(client, verworfene_id):
    """Die Karte existiert, gehört aber nicht zum Pensum. Das ist kein 404."""
    antwort = client.post("/reviews", json={"card_id": verworfene_id, "rating": 3})
    assert antwort.status_code == 409
    assert "verworfen" in antwort.json()["detail"]


def test_openapi_ist_erreichbar(client):
    schema = client.get("/openapi.json").json()
    assert "/reviews" in schema["paths"]
