"""
A DD-szolgáltatás bemenet-feldolgozása és hibakezelése.

A double dummy számítás maga az `endplay`-t igényli; azt itt álcázzuk,
így a validáció és a válaszszerkezet endplay nélkül is tesztelhető.
"""
import json
from dataclasses import dataclass

import pytest

from kibic.domain import kovetkezo_ules
from kibic.szolgaltatas.dd import DdHiba, dd_elemzes

KERES = {
    "request_id": "proba-1",
    "hands": {
        "N": ["SJ", "S3", "H9", "DA", "DQ", "DT", "D8",
              "CA", "CQ", "CJ", "C7", "C6", "C3"],
        "E": ["SA", "ST", "S6", "HA", "H7", "H5", "H4", "D4", "D2",
              "CK", "CT", "C8", "C5"],
        "S": ["SK", "S8", "S7", "S2", "HQ", "HJ", "H8", "H3",
              "DJ", "D7", "D3", "C9", "C2"],
        "W": ["SQ", "S9", "S5", "S4", "HK", "HT", "H6", "H2",
              "DK", "D9", "D6", "D5", "C4"],
    },
    "contract": {"level": 3, "strain": "C", "multiplier": 2},
    "declarer": "N",
    "vulnerability": "none",
    "play": [
        {"seat": "E", "card": "D4"}, {"seat": "S", "card": "DJ"},
        {"seat": "W", "card": "DK"}, {"seat": "N", "card": "DA"},
    ],
}


@dataclass
class _Ertekeles:
    lap: str
    utesek: int
    felvevo_osszesen: int
    legjobb: bool
    veszteseg: int


@pytest.fixture(autouse=True)
def alcazott_solver(monkeypatch):
    """A DDS helyett kitalált, de konzisztens értékek."""
    import kibic.solver.dds as dds

    def alca(leosztas, lapok, kontraktus):
        soron = kovetkezo_ules(kontraktus.felvevo)
        for _ in lapok:
            soron = kovetkezo_ules(soron)
        maradek = ({str(l) for l in leosztas.kezek[soron].lapok}
                   - {x.upper() for x in lapok})
        return [_Ertekeles(l, 9 - i % 3, 10 - i % 3, i == 0, i % 3)
                for i, l in enumerate(sorted(maradek))]

    monkeypatch.setattr(dds, "lap_elemzes", alca)


def _keres(**modositasok) -> dict:
    k = json.loads(json.dumps(KERES))
    k.update(modositasok)
    return k


# --- Helyes működés ---------------------------------------------------

def test_valasz_szerkezete():
    v = dd_elemzes(_keres())
    assert v["request_id"] == "proba-1"
    assert v["contract"] == "3CX" and v["declarer"] == "N"
    assert v["needed_tricks"] == 9
    assert v["tricks"]["completed"] == 1
    assert v["cards"] and v["best_cards"]
    assert "warning" in v


def test_pontszam_egyezik_a_pontozoval():
    """3CX beli nélkül, 10 ütés = 570 (a korábban validált pontozóból)."""
    v = dd_elemzes(_keres())
    tiz = [c for c in v["cards"] if c["declarer_total"] == 10]
    assert tiz and all(c["score_ns"] == 570 for c in tiz)
    assert all(c["result"] == "+1" for c in tiz)


def test_kontraktus_szovegkent_is_megadhato():
    v = dd_elemzes(_keres(contract="3CX"))
    assert v["contract"] == "3CX"


def test_szan_roviditese():
    """A protokollban `N` a szan, nem `NT`."""
    v = dd_elemzes(_keres(contract={"level": 3, "strain": "N",
                                    "multiplier": 1},
                          play=[]))
    assert v["contract"] == "3NT"


def test_hianyos_kezekbol_visszaallitja_az_eredetit():
    """A játékapp a MÉG KÉZBEN LÉVŐ lapokat küldi."""
    k = _keres()
    for ules, lap in [("E", "D4"), ("S", "DJ"), ("W", "DK"), ("N", "DA")]:
        k["hands"][ules].remove(lap)
    v = dd_elemzes(k)
    assert v["tricks"]["completed"] == 1


def test_lapok_sima_listaja_is_elfogadott():
    v = dd_elemzes(_keres(play=["D4", "DJ", "DK", "DA"]))
    assert v["tricks"]["completed"] == 1


# --- Hibakezelés ------------------------------------------------------

@pytest.mark.parametrize("modosit,reszlet", [
    (lambda k: k.pop("declarer"), "declarer"),
    (lambda k: k.__setitem__("vulnerability", "xx"), "vulnerability"),
    (lambda k: k["hands"].pop("W"), "W kéz"),
    (lambda k: k["play"].insert(0, {"seat": "N", "card": "SJ"}), "sorrend"),
    (lambda k: k["hands"]["N"].append("SA"), "53"),
    (lambda k: k["hands"]["N"].append("XY"), "lapjelölés"),
])
def test_hibas_bemenetek(modosit, reszlet):
    k = _keres()
    modosit(k)
    with pytest.raises(DdHiba) as e:
        dd_elemzes(k)
    assert reszlet in str(e.value)


def test_nem_szotar_bemenet():
    with pytest.raises(DdHiba):
        dd_elemzes("nem szótár")
