"""
Az ARANYKÉSZLET (a terv 0. fázisa): a kibic döntései egy rögzített
készleten nem változhatnak észrevétlenül.

Ha ez a teszt elbukik, a kibic valahol MÁST licitál, mint a rögzítéskor.
Ha a változás szándékos (pl. új szabály), a teljes készletet újra kell
rögzíteni, és a különbséget a szerkesztővel jóváhagyatni:

    python -m kibic.cli.aranykeszlet osszevet --be adat/arany/MOHA_STAND.jsonl
    python -m kibic.cli.aranykeszlet rogzit --rendszer MOHA_STAND --leosztas 300 \\
        --mag 1 --ki adat/arany/MOHA_STAND.jsonl
    (és a tests/adat/arany_mini.jsonl: az első 25 leosztás)
"""
from pathlib import Path

import pytest

GYOKER = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def betolto():
    pytest.importorskip("yaml")
    from kibic.cli.aranykeszlet import yaml_betolto
    return yaml_betolto([str(GYOKER / "rendszerek" / "yaml")])


def test_leosztas_rogzitett_maggal():
    from kibic.cli.aranykeszlet import kez_pbnbol, leosztas, pbn
    a, b = leosztas(1, 7), leosztas(1, 7)
    assert a == b and len({l for k in a.values() for l in k}) == 52
    assert kez_pbnbol(pbn(a["N"])) == sorted(a["N"], key=kez_pbnbol(pbn(a["N"])).index)


def test_vege():
    from kibic.cli.aranykeszlet import vege
    assert vege(["P", "P", "P", "P"])
    assert vege(["1S", "P", "P", "P"])
    assert not vege(["P", "P", "P"])
    assert not vege(["1S", "P", "2S", "P"])


def test_aranykeszlet_mini_nem_valtozott(betolto):
    from kibic.cli.aranykeszlet import _olvas, osszevet
    fej, sorok = _olvas(str(GYOKER / "tests" / "adat" / "arany_mini.jsonl"))
    elter = [(s, uj) for s, uj, ok in osszevet(betolto, sorok, fej["rendszer"]) if not ok]
    leiras = "\n".join(f"#{s['deal']} {s['seat']} [{' '.join(s['auction'])}] {s['hand']}: "
                       f"{s['call']} → {uj['call']} ({uj['source']}: {uj['explanation']})"
                       for s, uj in elter[:15])
    assert not elter, f"{len(elter)} eltérés az aranykészlettől:\n{leiras}"


def test_arnyek_mod(betolto):
    """Egy árnyék-döntéshozó lefut, a különbség a `shadow` mezőben, a licit a régi."""
    from kibic.motor import arnyek
    from kibic.szolgaltatas.licit import licit_elemzes
    arnyek.regisztral("_proba_mindig_passz", lambda ktx: "P")
    try:
        k = {"hand": ["SA", "SK", "SQ", "S9", "S2", "HA", "H3", "H2", "D2", "D3", "C2", "C3", "C4"],
             "seat": "N", "dealer": "N", "vulnerability": "none", "auction": [],
             "system": "MOHA_STAND", "test_mode": True, "inference": False,
             "shadow": ["_proba_mindig_passz"]}
        v = licit_elemzes(k, betolto)
        assert v["call"] == "1S"
        assert v["shadow"] == [{"name": "_proba_mindig_passz", "call": "P", "same": False}]
        k["shadow"] = []
        assert "shadow" not in licit_elemzes(k, betolto)
    finally:
        arnyek.torol("_proba_mindig_passz")
