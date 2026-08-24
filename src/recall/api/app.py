"""Die HTTP-Anwendung.

Hier steht kein SQL. Jede Abfrage kommt aus `recall.review.db`, wo sie schon für die
Streamlit-Oberfläche gebraucht und getestet wurde. Diese Schicht macht nur dreierlei:
Eingaben validieren, Zeilen in Antwortmodelle übersetzen und Fehlerfälle auf
Statuscodes abbilden.
"""

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fsrs import Rating as FSRSRating

from recall.api.models import CardOut, DueCardOut, HealthOut, ReviewIn, ReviewOut, StatsOut
from recall.review.db import (
    DEFAULT_DB_PATH,
    all_cards,
    card_by_id,
    connect,
    due_cards,
    save_review,
    scheduling_for,
    stats,
)
from recall.review.scheduling import review as fsrs_review


class Datenbank:
    """Eine Verbindung plus Schloss.

    SQLite verträgt hier genau eine Verbindung, aber FastAPI führt synchrone
    Endpunkte in einem Threadpool aus. Das Schloss serialisiert die Zugriffe, damit
    sich zwei Anfragen nicht in derselben Transaktion begegnen. Bei dieser Datenmenge
    ist das billiger als ein Verbindungspool und ehrlicher als die Annahme, dass
    schon nichts passieren wird.
    """

    def __init__(self, path: Path | str) -> None:
        self._conn = connect(path, check_same_thread=False)
        self._lock = threading.Lock()

    @contextmanager
    def __call__(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            yield self._conn

    def close(self) -> None:
        self._conn.close()


def hole_db(request: Request) -> Iterator[sqlite3.Connection]:
    with request.app.state.db() as conn:
        yield conn


Conn = Depends(hole_db)


def create_app(db_path: Path | str = DEFAULT_DB_PATH) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        app.state.db = Datenbank(db_path)
        try:
            yield
        finally:
            app.state.db.close()

    app = FastAPI(
        title="recall",
        version="0.1.0",
        summary="Lesezugriff auf die Kartensammlung und Bewertungen aus dem Lernpensum.",
        lifespan=lifespan,
    )

    @app.get("/health", response_model=HealthOut, tags=["Betrieb"])
    def health(conn: sqlite3.Connection = Conn) -> HealthOut:
        """Bereitschaft samt Kartenzahl. Der Docker-HEALTHCHECK zeigt hierher."""
        return HealthOut(status="ok", cards=stats(conn)["gesamt"])

    @app.get("/stats", response_model=StatsOut, tags=["Übersicht"])
    def lese_stats(conn: sqlite3.Connection = Conn) -> StatsOut:
        return StatsOut(**stats(conn))

    @app.get("/cards", response_model=list[CardOut], tags=["Karten"])
    def liste_karten(
        conn: sqlite3.Connection = Conn,
        suche: str | None = Query(None, description="Filtert über Frage und Antwort"),
        quelle: str | None = Query(None, description="Dateiname der Vorlesungsfolien"),
        verworfene: bool = Query(False, description="Auch die vom Critic aussortierten"),
    ) -> list[CardOut]:
        zeilen = all_cards(conn, nur_lernbar=not verworfene, suche=suche, quelle=quelle)
        return [CardOut.from_row(z) for z in zeilen]

    @app.get("/cards/{card_id}", response_model=CardOut, tags=["Karten"])
    def lese_karte(card_id: str, conn: sqlite3.Connection = Conn) -> CardOut:
        zeile = card_by_id(conn, card_id)
        if zeile is None:
            raise HTTPException(404, f"Keine Karte mit der id {card_id}.")
        return CardOut.from_row(zeile)

    @app.get("/due", response_model=list[DueCardOut], tags=["Lernen"])
    def liste_faellige(
        conn: sqlite3.Connection = Conn,
        limit: int | None = Query(None, ge=1, le=500),
    ) -> list[DueCardOut]:
        """Fällige Karten, die am längsten überfälligen zuerst."""
        return [
            DueCardOut(
                card_id=karte.card_id,
                question=karte.question,
                answer=karte.answer,
                source_file=karte.source_file,
                page_number=karte.page_number,
                due=plan.due,
            )
            for karte, plan in due_cards(conn, limit=limit)
        ]

    @app.post("/reviews", response_model=ReviewOut, status_code=201, tags=["Lernen"])
    def bewerte(eingabe: ReviewIn, conn: sqlite3.Connection = Conn) -> ReviewOut:
        """Eine Bewertung verbuchen und die nächste Fälligkeit zurückgeben."""
        zeile = card_by_id(conn, eingabe.card_id)
        if zeile is None:
            raise HTTPException(404, f"Keine Karte mit der id {eingabe.card_id}.")
        if not zeile["keep"]:
            # Der Critic hat die Karte aussortiert, sie ist nicht Teil des Pensums.
            # 409 statt 404: die Karte gibt es, sie ist nur nicht lernbar.
            raise HTTPException(409, f"Karte {eingabe.card_id} wurde vom Critic verworfen.")

        plan = scheduling_for(conn, eingabe.card_id)
        if plan is None:
            raise HTTPException(409, f"Karte {eingabe.card_id} hat keinen Lernstand.")

        neuer_plan, protokoll = fsrs_review(plan, FSRSRating(eingabe.rating))
        save_review(conn, eingabe.card_id, neuer_plan, protokoll)
        return ReviewOut(card_id=eingabe.card_id, rating=eingabe.rating, due=neuer_plan.due)

    return app
