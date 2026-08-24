"""Gemeinsame Fixtures.

Die Verbindung auf :memory: und die geladenen Demokarten standen vorher in
mehreren Dateien nebeneinander.
"""

import json
import sqlite3
from collections.abc import Iterator

import pytest

from recall.review.db import connect
from tests.helpers import DEMO


@pytest.fixture
def conn() -> Iterator[sqlite3.Connection]:
    verbindung = connect(":memory:")
    yield verbindung
    verbindung.close()


@pytest.fixture
def demo_karten() -> list[dict]:
    return json.loads(DEMO.read_text(encoding="utf-8"))
