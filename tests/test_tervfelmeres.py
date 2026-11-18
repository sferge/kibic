"""A helyzetfelmérés (2026-11-18): biztos ütés, biztosan kiadó, egyenleg, vesztők."""
from kibic.domain import Lap
from kibic.motor.tervfelmeres import felmeres


def _kez(s):
    ki = set()
    for sz, r in zip("SHDC", s.split(".")):
        ki |= {Lap.parse(sz + c) for c in r}
    return ki


MIND = {Lap.parse(s + r) for s in "SHDC" for r in "23456789TJQKA"}


def test_negy_pikk_keletrol():
    """MB 4♠ (2026-11-18): a ♠A biztosan kiadó; a vesztők a fő kézből (Kelet) kb. 5,
    a megengedett 3 — két-három vesztőtől kell megszabadulni."""
    E, W = _kez("K8752..Q982.AKJ2"), _kez("Q43.AKJ.AT43.543")
    f = felmeres({"E": E, "W": W}, "E", "W", MIND - E - W, (13, 13), "S", 10, 13)
    sz = {s.szin: s for s in f.szinek}
    assert (sz["S"].biztos, sz["S"].kiado) == (0, 1)
    assert (sz["H"].biztos, sz["D"].biztos, sz["C"].biztos) == (2, 1, 2)
    assert f.fo_kez == "E" and f.egyenleg == 2
    assert 2.0 < f.vesztotobblet < 3.0


def test_hosszu_adu_minden_lapja_biztos():
    """5♣ AKJT53 + Q2, kint 5 treff: a felső lapok kihúzzák a védőket, a hatodik is nyerő."""
    N, S = _kez("Q3.K4.AK2.AKJT53"), _kez("J62.AJ52.JT94.Q2")
    f = felmeres({"N": N, "S": S}, "N", "S", MIND - N - S, (13, 13), "C", 11, 13)
    sz = {s.szin: s for s in f.szinek}
    assert sz["C"].biztos == 6 and sz["S"].kiado == 2
    assert (f.biztos, f.hiany, f.egyenleg) == (10, 1, 0)


def test_forrasok_negy_pikk():
    """MB 4♠: a források a játékos szemével — két biztos dobás a ♥AK-ra, a ♣ lopás
    kiadás után (biztos, egy kiadással), a ♦ szöktetés és a ♣ impassz kb. 50%."""
    from kibic.motor.tervforras import forrasok
    from kibic.motor.tervsema import Allas, technikak_betoltese
    E, W = _kez("K8752..Q982.AKJ2"), _kez("Q43.AKJ.AT43.543")
    kint = MIND - E - W - {Lap.parse("H5")}
    a = Allas("E", "S", {"E": set(E), "W": set(W)}, kint, 10, 13, "W")
    fk = {f.nev: f for f in forrasok(a, technikak_betoltese(), {"N": 13, "S": 12})}
    assert fk["♥ vesztőcsere (dobás)"].hozam == 2 and fk["♥ vesztőcsere (dobás)"].biztos
    assert fk["♣ lopás a rövid kézben (kiadás után)"].biztos
    assert 0.45 < fk["♦ szöktetés"].esely < 0.6 and 0.45 < fk["♣ impassz"].esely < 0.6
    assert fk["♦ szöktetés (felső előbb)"].esely > fk["♦ szöktetés"].esely
