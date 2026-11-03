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


def test_vedoi_utesek_versenyszin():
    """3NT: a ♥K az egyetlen megállítónk, kint ♥QT9 7532 — az első bejutáskor
    kiütik, a másodiknál leviszik a maradékot."""
    from kibic.motor.tervezo import Ertekelo, Terv
    a = Allas(felvevo="S", adu=None,
              kezek={"S": _lapok("HK SA SK DA DK DQ CA CK CQ"),
                     "N": _lapok("H4 S2 S3 D2 D3 D4 C2 C3 C4")},
              kint=_lapok("HQ HT H9 H7 H5 H3 H2 SQ SJ ST S9 S8 DJ DT D9 D8 CJ CT"),
              cel=9, hatra=9, soron="S")
    h = helyzetelemzes(a)
    e = Ertekelo(h, Terv("x", [], 0))
    o = osztalyok(a.kint, {"W": 9, "E": 9}, set())
    egy = next(x for x in o if x.kezhossz("W", "H") == 3 and x.kezhossz("E", "H") == 4
               and x.kezhossz("W", "S") == 2)
    assert e._menetek("H", 3, 4)[:4] == ("M", "V", "V", "V")
    assert e.vedoi_utesek(egy, 1) == 0
    assert e.vedoi_utesek(egy, 2) == 3


def test_lopas_a_rovid_kezben():
    """7 lapos végállás, ♠ adu: a felső ütések 5, a 6. a ♥ lopása az asztalon (a rövid adus
    kéz). A lopó kéz aduit nem viheti el előtte a kiaduzás (különben a lopás nem játszható)."""
    a = Allas(felvevo="N", adu="S",
              kezek={"N": _lapok("SA SK SQ H4 H3 H2 CA"), "S": _lapok("S5 S4 HA D3 D2 C3 C2")},
              kint=_lapok("SJ ST S9 HK HQ HJ HT H9 DA DK DQ CK CQ CJ"), cel=6, hatra=7, soron="N")
    pld = [p for p in peldanyok(a, technikak_betoltese()) if p.sema.azon == "LOPAS_ROVID_KEZBEN"]
    assert [(p.szin, p.hozam) for p in pld] == [("H", 1)]       # csak annyi lopás, amennyi hiányzik
    assert [k.fajta for k in pld[0].korok] == ["lehiv", "lop"]
    _, ert = tervez(a)
    e = ert[0]
    assert e.terv.nev == "♥ lopás a rövid kézben"
    assert e.elvi == pytest.approx(1.0)
    assert 0.7 < e.kockazattal < 0.9                             # a felüllopás kockázata
    assert e.terv.kiaduzas != "mind"                             # a kiaduzás nem viheti el az asztal aduit


def test_atmenet_lopassal():
    """A 6♦ (MB, 2026-11-03) 3. ütése: az asztal (N) pikkből színhiányos, van adója —
    a ♠K lopása átmenet az asztalra (a ♦Q és a ♣K mellett a harmadik)."""
    from kibic.motor.tervezo import Ertekelo, Terv, kezdo_allapot
    N = _lapok("HA HK H8 H4 H2 DQ D5 CK C7 C5 C2")
    S = _lapok("SK DA DK DJ DT D6 CA CJ C8 C6 C3")
    latott = N | S | _lapok("SA S2 S3 S4 D7 D4 D8 D9")
    minden = {Lap.parse(s + r) for s in "SHDC" for r in "23456789TJQKA"}
    a = Allas(felvevo="S", adu="D", kezek={"S": S, "N": N}, kint=minden - latott, cel=11, hatra=11, soron="S")
    e = Ertekelo(helyzetelemzes(a), Terv("", [], 0))
    st = kezdo_allapot(a)
    assert e._atmenetek(st, "N", "H", set()) == 3          # ♦Q, ♣K, a ♠ lopása
    sz, h, c = e._atmenet(st, "N", {Lap.parse("CK")})       # a ♣K foglalt: a lopás az átmenet
    assert (sz, str(h), c.szin) == ("S", "SK", "D")


def test_lopasos_kimagasitas_hosszu_lap():
    """A 6♦ (MB, 2026-11-03) 3. ütése — a szerkesztő: előbb a két kis kőrt lopjuk (♠K
    lopása és a ♦Q az átmenet), a ♥AK és az 5. kőr a kiaduzás után. 4-4-nél sikerül
    (34%), és a halasztott lehívás miatt nincs ellopási kockázat."""
    from kibic.motor.tervezo import Ertekelo, Eset, Terv, kezdo_allapot
    from kibic.motor.tervszamolo import osztalyok
    N = _lapok("HA HK H8 H4 H2 DQ D5 CK C7 C5 C2")
    S = _lapok("SK DA DK DJ DT D6 CA CJ C8 C6 C3")
    latott = N | S | _lapok("SA S2 S3 S4 D7 D4 D8 D9")
    minden = {Lap.parse(s + r) for s in "SHDC" for r in "23456789TJQKA"}
    a = Allas(felvevo="S", adu="D", kezek={"S": S, "N": N}, kint=minden - latott, cel=11, hatra=11, soron="S")
    h = helyzetelemzes(a)
    p = next(q for q in peldanyok(a, technikak_betoltese()) if q.sema.azon == "LOPASOS_KIMAGASITAS_HOSSZ")
    assert (p.szin, p.szerepek["R"], p.hozam) == ("H", 2, 1)
    assert [k.fajta for k in p.korok] == ["lop", "lop", "lehiv", "lehiv", "lehiv"]
    oszt = osztalyok(a.kint, {"E": 11, "W": 11}, p.relevans)
    W = sum(o.suly for o in oszt)
    for kock in (False, True):
        naplo = []
        e = Ertekelo(h, Terv("EGYETLEN_ESELY", [p], 0), kockazat=kock, naplo=naplo)
        st = e.kiaduzas(kezdo_allapot(a), 0)
        v = e.futtat([Eset(o, o.suly, h.tartalek, h.hiany) for o in oszt], 0, 0, st) / W
        assert v == pytest.approx(0.341, abs=0.003)
    assert naplo[0] == "átmenet: SK→D5"                              # a ♠K lopása az első átmenet
    assert any(x.startswith("begyűjtés halasztva") for x in naplo)
