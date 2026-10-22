"""A rendszer ember által olvasható leírása (teljes / kártya)."""
from pathlib import Path

import pytest

GYOKER = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def adat():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    from kibic.szolgaltatas.leiras import leiras_yamlbol
    g = betolt([GYOKER / "rendszerek" / "yaml"])
    return leiras_yamlbol(g, "MOHA_STAND")


def test_minden_feloldott_szabaly_benne(adat):
    db = sum(len(c["szabalyok"]) for f in adat["reszek"] for c in f["fejezetek"])
    assert db == adat["osszesen"] > 500
    kodok = [f["kod"] for f in adat["reszek"]]
    assert "MOHA_1M" in kodok and "RKC" in kodok and "WALSH" in kodok


def test_html_es_md(adat):
    from kibic.szolgaltatas.leiras import leiras_html, leiras_md
    h = leiras_html(adat)
    assert h.startswith("<!doctype html>") and "Moha standard" in h and "1NT–2♣" in h
    m = leiras_md(adat)
    assert m.startswith("# Moha standard") and "| Licit | Jelentés |" in m


def test_cli(tmp_path):
    from kibic.cli.rendszerleiras import main
    ki = tmp_path / "k.html"
    assert main(["--rendszer", "MOHA_STAND", "--kartya", "--ki", str(ki),
                 "--yaml", str(GYOKER / "rendszerek" / "yaml")]) == 0
    assert ki.read_text(encoding="utf-8").lower().startswith("<!doctype")
