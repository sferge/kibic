"""Az egyszínű elemző mint végrehajtható színkezelés (2026-11-18)."""
from kibic.motor import tervszinkezeles as ts
from kibic.motor.tervszinpolitika import SzinPolitika


def test_lepked_a_dontesi_fan():
    """♦Q982 / ♦A1043, legalább 3 ütés: a politika a felvevő kis lapjával indul, a
    második kéz lapjára megmondja a harmadikat, és egy ütés után a cél eggyel kisebb."""
    R = ts.rangok
    X, Y = R("Q982"), R("AT43")
    kint = frozenset(range(2, 15)) - X - Y
    p = SzinPolitika(X, Y, kint, 13, 13, 3, 99)
    assert 0.7 < p.p < 0.85
    akc = p.dontes()
    assert akc is not None and akc[0] in ("X", "Y")
    c3 = p.harmadik(akc, 5)
    assert c3 is not None
    p.lep(((akc[0], akc[1]), ("V1" if akc[0] == "X" else "V2", 5),
           ("Y" if akc[0] == "X" else "X", c3), ("V2" if akc[0] == "X" else "V1", 6)))
    assert p.k in (2, 3) and p.dontes() is not None


def test_vart_lapon_kivul_is_folytatja():
    """Ha a védő olyan lapot tesz, amire az elemző nem számított, a politika a
    megfigyeléssel összeférő elosztásokból számol tovább."""
    R = ts.rangok
    X, Y = R("KJ"), R("AT943")
    kint = frozenset(range(2, 15)) - X - Y
    p = SzinPolitika(X, Y, kint, 13, 13, 4, 99)
    akc = p.dontes()
    p.lep(((akc[0], akc[1]), ("V1" if akc[0] == "X" else "V2", 12),      # a dáma rögtön
           ("Y" if akc[0] == "X" else "X", max(Y if akc[0] == "X" else X)),
           ("V2" if akc[0] == "X" else "V1", 2)))
    assert p.node[1]                                                   # van még lehetséges elosztás
