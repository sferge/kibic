"""A sémákból dolgozó tervező — átvételi próba egy kombinációs állásra.

Az állás (5♣ Északról, a 4. ütéstől; a pikket már lopta Észak):
    Észak: ♥K4  ♦AK2  ♣AKJT5      Dél (asztal): ♥AJ52  ♦JT94  ♣Q2
A hátralévő 10 ütésből 10 kell; biztos 9. A 10. ütés: ♦ ejtés / impassz, ♥
impassz / ejtés / lopásos kimagasítás, és ezek kombinációi.
"""
from math import comb

import pytest

from kibic.domain import Lap
from kibic.motor.tervsema import Allas, KifejezesHiba, kifejezes, peldanyok, technikak_betoltese
from kibic.motor.tervszamolo import Korlat, osztalyok
from kibic.motor.tervezo import helyzetelemzes, tervez


def _lapok(s: str) -> set[Lap]:
    return {Lap.parse(x) for x in s.split()}


@pytest.fixture(scope="module")
def allas():
    return Allas(
        felvevo="N", adu="C",
        kezek={"N": _lapok("HK H4 DA DK D2 CA CK CJ CT C5"),
               "S": _lapok("HA HJ H5 H2 DJ DT D9 D4 CQ C2")},
        kint=_lapok("S7 S4 HQ HT H9 H8 H7 H6 H3 DQ D8 D7 D6 D5 D3 C9 C8 C7 C6 C4"),
        cel=10, hatra=10, soron="N")


def test_helyzetelemzes(allas):
    h = helyzetelemzes(allas)
    assert (sum(h.biztos.values()), h.hiany, h.tartalek) == (9, 1, 0)


def test_osztalyok_sulya(allas):
    o = osztalyok(allas.kint, {"E": 10, "W": 10}, _lapok("HQ DQ"))
    assert sum(x.suly for x in o) == comb(20, 10)
    o5 = osztalyok(allas.kint, {"E": 10, "W": 10}, _lapok("HQ DQ"), [Korlat("E", "S", 2)])
    assert sum(x.suly for x in o5) == comb(18, 8)


def test_technikak_a_lapokon(allas):
    nevek = {p.rovid for p in peldanyok(allas, technikak_betoltese())}
    assert {"♦ ejtés", "♥ ejtés", "♥ impassz", "♦ impassz", "♥ lopásos kimagasítás"} <= nevek


def test_valasztas_licit_nelkul(allas):
    _, ert = tervez(allas)
    # a ♥ impassz és a ♥ színkezelés (az egyszínű elemzőből: ♥K, aztán impassz) egyformán jó
    assert ert[0].terv.nev in ("♦ ejtés → ♥ impassz", "♦ ejtés → ♥ színkezelés (3 ütés, ≤0 vesztés)")
    assert ert[0].kockazattal == pytest.approx(0.597, abs=0.004)


def test_valasztas_kelet_5_pikkel(allas):
    feltetel = [Korlat("E", "S", 2, tudas="feltetelezett")]
    # a SZABAD_HELYEK szabály: a feltételezett hossz alapból nem súlyoz
    _, ert = tervez(allas, feltetel)
    assert ert[0].terv.nev.startswith("♦ ejtés → ♥")
    _, ert = tervez(allas, feltetel, feltevesbol=True)
    assert ert[0].terv.nev == "♥ ejtés → ♦ impassz"


def test_lopasos_kimagasitas_kockazata(allas):
    """Elvben a legjobb (68,5%), az ellopási kockázattal 50% alá esik: a ♥J
    átmenete (♣Q) miatt csak két adukör húzható le előtte."""
    _, ert = tervez(allas)
    e = next(x for x in ert if x.terv.nev == "♥ lopásos kimagasítás → ♦ impassz")
    assert e.elvi == pytest.approx(0.685, abs=0.002)
    assert 0.45 < e.kockazattal < 0.50
    assert e.terv.kiaduzas == 1


def test_kifejezes_szuk():
    with pytest.raises(KifejezesHiba):
        kifejezes("x.__class__", {"x": 1})
    assert kifejezes("a + 1 >= 2 and not b", {"a": 1, "b": False})
