"""PDF einlesen und gesäuberte Chunks zum Durchlesen ausgeben.

Aufruf: recall ingest data/<foliensatz>.pdf [--raw]
"""

import argparse

from recall.console import configure_stdout
from recall.ingestion.cleaning import clean_chunks
from recall.ingestion.pdf import extract_chunks


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("pdf", help="Pfad zum PDF")
    parser.add_argument("--raw", action="store_true", help="rohe Extraktion ohne Cleaning zeigen")
    parser.set_defaults(func=run)


def run(args: argparse.Namespace) -> None:
    chunks = extract_chunks(args.pdf)
    total_pages = len(chunks)
    if not args.raw:
        chunks = clean_chunks(chunks)

    for chunk in chunks:
        print(f"--- Seite {chunk.page_number} ({chunk.source_file}) ---")
        print(chunk.text)
        print()
    print(f"{len(chunks)} Chunks aus {total_pages} Seiten.")


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    run(parser.parse_args())
