"""Die HTTP-Schnittstelle starten.

Aufruf: recall api [--db data/recall.db] [--host 127.0.0.1] [--port 8000]

Die interaktive Doku liegt danach unter /docs. FastAPI erzeugt sie aus denselben
Modellen, gegen die auch validiert wird, deshalb steht sie in keiner Extradatei.
"""

import argparse
import importlib.util

from recall.review.db import DEFAULT_DB_PATH

STANDARD_HOST = "127.0.0.1"
STANDARD_PORT = 8000


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Pfad zur Lerndatenbank")
    parser.add_argument(
        "--host",
        default=STANDARD_HOST,
        help=f"Adresse (Standard {STANDARD_HOST}, im Container 0.0.0.0)",
    )
    parser.add_argument(
        "--port", type=int, default=STANDARD_PORT, help=f"Port (Standard {STANDARD_PORT})"
    )
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    if importlib.util.find_spec("uvicorn") is None:
        raise SystemExit(
            "uvicorn ist nicht installiert. Die Schnittstelle liegt in einer eigenen "
            "Dependency-Gruppe:\n  uv sync --group api"
        )

    import uvicorn

    from recall.api.app import create_app

    uvicorn.run(create_app(args.db), host=args.host, port=args.port)


def main() -> None:
    parser = argparse.ArgumentParser(prog="recall api", description=__doc__)
    add_arguments(parser)
    run(parser.parse_args())
