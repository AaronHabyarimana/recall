"""Die Weboberfläche starten.

Aufruf: recall ui [--db data/recall.db] [--port 8501]

Streamlit läuft als Unterprozess statt über seine Python-API: der Server bringt
eigenes Signal-Handling mit, ein Strg-C soll ihn sauber beenden. Der Datenbankpfad
geht über die Umgebung, weil Streamlit alle Argumente vor dem `--` für sich
beansprucht.
"""

import argparse
import importlib.util
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser

from recall.review.db import DEFAULT_DB_PATH
from recall.ui import APP_PATH

STANDARD_PORT = 8501


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Pfad zur Lerndatenbank")
    parser.add_argument(
        "--port", type=int, default=STANDARD_PORT, help=f"Port (Standard {STANDARD_PORT})"
    )
    parser.add_argument("--kein-browser", action="store_true", help="Browser nicht öffnen")
    parser.set_defaults(func=run)


def _browser_oeffnen(port: int, timeout: float = 20.0) -> None:
    """Wartet, bis der Server den Port annimmt, und öffnet dann den Browser."""
    ende = time.monotonic() + timeout
    while time.monotonic() < ende:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                webbrowser.open(f"http://localhost:{port}")
                return
        time.sleep(0.3)


def run(args: argparse.Namespace) -> None:
    if importlib.util.find_spec("streamlit") is None:
        raise SystemExit(
            "Streamlit ist nicht installiert. Die Oberfläche liegt in einer eigenen "
            "Dependency-Gruppe:\n  uv sync --group ui"
        )

    # headless, sonst fragt Streamlit beim ersten Start interaktiv nach einer
    # E-Mail-Adresse und blockiert. Den Browser öffnen wir stattdessen selbst.
    befehl = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.port",
        str(args.port),
        "--server.headless",
        "true",
    ]

    if not args.kein_browser:
        threading.Thread(target=_browser_oeffnen, args=(args.port,), daemon=True).start()

    raise SystemExit(subprocess.call(befehl, env={**os.environ, "RECALL_DB": args.db}))


def main() -> None:
    parser = argparse.ArgumentParser(prog="recall ui", description=__doc__)
    add_arguments(parser)
    run(parser.parse_args())
