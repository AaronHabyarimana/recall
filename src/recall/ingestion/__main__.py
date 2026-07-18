"""CLI: PDF einlesen und gesäuberte Chunks zum Durchlesen ausgeben.

Aufruf: uv run python -m recall.ingestion data/<foliensatz>.pdf [--raw]
"""

import argparse
import sys

from recall.ingestion.cleaning import clean_chunks
from recall.ingestion.pdf import extract_chunks


def main() -> None:
    # Windows-Konsolen nutzen oft cp1252, das an Sonderzeichen aus PDFs scheitert
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", help="Pfad zum PDF")
    parser.add_argument("--raw", action="store_true", help="rohe Extraktion ohne Cleaning zeigen")
    args = parser.parse_args()

    chunks = extract_chunks(args.pdf)
    total_pages = len(chunks)
    if not args.raw:
        chunks = clean_chunks(chunks)

    for chunk in chunks:
        print(f"--- Seite {chunk.page_number} ({chunk.source_file}) ---")
        print(chunk.text)
        print()
    print(f"{len(chunks)} Chunks aus {total_pages} Seiten.")


if __name__ == "__main__":
    main()
