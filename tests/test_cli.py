"""Der Dach-Befehl: Zerlegung der Argumente und Weiterreichen an die richtige Stufe."""

import subprocess
import sys

import pytest

from recall.api import cli as api_cli
from recall.cli import BEFEHLE, build_parser
from recall.critic import cli as critic_cli
from recall.generation import cli as generation_cli
from recall.ingestion import cli as ingestion_cli
from recall.review import cli as review_cli
from recall.ui import cli as ui_cli


@pytest.fixture
def parser():
    return build_parser()


@pytest.mark.parametrize("name", [name for name, _, _ in BEFEHLE])
def test_jede_stufe_hat_eine_hilfe(name, capsys):
    """--help darf an keiner Stufe krachen - das ist die Doku, die immer mitkommt."""
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args([name, "--help"])
    assert exc.value.code == 0
    assert name in capsys.readouterr().out


def test_ohne_stufe_ist_ein_fehler(parser):
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_ingest_reicht_an_die_ingestion_weiter(parser):
    args = parser.parse_args(["ingest", "folien.pdf", "--raw"])
    assert (args.func, args.pdf, args.raw) == (ingestion_cli.run, "folien.pdf", True)


def test_generate_kennt_limit_und_out(parser):
    args = parser.parse_args(["generate", "folien.pdf", "--limit", "3", "--out", "k.json"])
    assert (args.func, args.limit, args.out) == (generation_cli.run, 3, "k.json")


def test_critic_hat_eine_voreingestellte_batchgroesse(parser):
    args = parser.parse_args(["critic", "k.json"])
    assert args.func is critic_cli.run
    assert args.batch_size == critic_cli.BATCH_SIZE


def test_review_waehlt_den_unterbefehl(parser):
    args = parser.parse_args(["review", "import", "k.json"])
    assert (args.func, args.handler) == (review_cli.run, review_cli.cmd_import)
    assert args.karten == "k.json"


def test_review_nimmt_db_hinter_dem_unterbefehl(parser):
    """Die Reihenfolge, die man tippt: erst was man will, dann wo."""
    args = parser.parse_args(["review", "stats", "--db", "andere.db"])
    assert args.db == "andere.db"


def test_review_ohne_db_nutzt_den_standardpfad(parser):
    assert parser.parse_args(["review", "lernen"]).db.endswith("recall.db")


def test_ui_hat_db_und_port(parser):
    args = parser.parse_args(["ui", "--db", "demo.db", "--port", "8600"])
    assert (args.func, args.db, args.port) == (ui_cli.run, "demo.db", 8600)


def test_ui_port_hat_einen_festen_standard(parser):
    """Fester Port, damit wir wissen, welche Adresse wir im Browser öffnen."""
    assert parser.parse_args(["ui"]).port == ui_cli.STANDARD_PORT


def test_ui_meldet_fehlendes_streamlit_verstaendlich(parser, monkeypatch):
    monkeypatch.setattr(ui_cli.importlib.util, "find_spec", lambda name: None)
    with pytest.raises(SystemExit) as exc:
        ui_cli.run(parser.parse_args(["ui"]))
    assert "uv sync --group ui" in str(exc.value)


def test_api_port_hat_einen_festen_standard(parser):
    assert parser.parse_args(["api"]).port == api_cli.STANDARD_PORT


def test_api_bindet_standardmaessig_nur_lokal(parser):
    """Nach aussen horchen soll nur, wer es ausdruecklich verlangt oder im Container laeuft."""
    assert parser.parse_args(["api"]).host == "127.0.0.1"
    assert parser.parse_args(["ui"]).host == "127.0.0.1"


def test_api_meldet_fehlendes_uvicorn_verstaendlich(parser, monkeypatch):
    monkeypatch.setattr(api_cli.importlib.util, "find_spec", lambda name: None)
    with pytest.raises(SystemExit) as exc:
        api_cli.run(parser.parse_args(["api"]))
    assert "uv sync --group api" in str(exc.value)


def test_cli_zieht_fastapi_nicht_beim_start_herein():
    """recall.cli laedt das api-Paket, um die Argumente zu bauen.

    Wuerde dabei FastAPI importiert, waere die komplette CLI kaputt, sobald jemand
    ohne die Gruppe `api` installiert. Genau das war schon einmal der Fall.
    """
    code = "import recall.cli, sys; assert 'fastapi' not in sys.modules, 'FastAPI zu frueh geladen'"
    subprocess.run([sys.executable, "-c", code], check=True)


def test_cli_zieht_streamlit_nicht_beim_start_herein():
    code = "import recall.cli, sys; assert 'streamlit' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)
