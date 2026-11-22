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


def test_harmadik_kez_a_tenylegesen_latott_lapra():
    """A védő egy ugyanolyan jó, de a védőmodelltől eltérő lapot tesz (minta: BM A-2 #2,
    az MB-asztalon): KQT876 / A2, 5 ütés legfeljebb 1 vesztéssel; az asztal a 6-ost hívja,
    Kelet B9543-ból a 9-est teszi. Kiengedés (2) után Keletnél B543 marad, és még egy
    ütés elveszik; az ászt kell tenni. Kicsire (3) a kiengedés a jó."""
    from kibic.motor.tervszinpolitika import SzinPolitika
    R = {c: i for i, c in enumerate("23456789TJQKA", 2)}
    fs = lambda s: frozenset(R[c] for c in s)
    p = SzinPolitika(fs("A2"), fs("KQT876"), fs("J9543"), 12, 13, 5, 1)
    d = p.dontes()
    assert d == ("Y", 6)
    assert p.harmadik(d, 9) == 14
    assert p.harmadik(d, 3) == 2


def test_lopasos_kimagasitas_atmenetkorlattal():
    """A mellékszín elemzője lophat is, és számol az átmenetekkel (minta: BM A-2 #3,
    saját lapokkal): 86 / AK7532, kint QJT94, a kéz kétszer lophat, az asztalra egy
    átmenet van. Vesztés nélkül csak a 3-2 jó (két lopás után nincs visszaút); egy
    kiengedéssel (az első kör kicsi-kicsi) a 4-1 is."""
    from kibic.motor.tervszinkezeles import Elemzo, Feladat
    R = {c: i for i, c in enumerate("23456789TJQKA", 2)}
    fs = lambda s: frozenset(R[c] for c in s)
    f = Feladat(X=fs("86"), Y=fs("AK7532"), kint=fs("QJT94"), ures1=12, ures2=13,
                lop_x=2, lop_y=0, atm_x=5, atm_y=1, hivas="-")
    e = Elemzo(f)
    p0, s0, _ = e.megold(4, 0)
    p1, _, l1 = e.megold(4, 1)
    # (2026-11-22, RELEVANS_LAPOK) vesztés nélkül a 3-2 és azok a 4-1-ek jók, ahol a
    # hosszú védőnél a kis 4-es is ott van (a harmadik körben az 5-ös üt); a Q, J, 10,
    # 9 egyformák (mind a K és a 8 közé esnek): a szingli figura és a szingli 9-es
    # Nyugatnál ugyanúgy jár
    assert p0 < 0.85
    szingli = [i for i, (v1, v2, _) in enumerate(e.tart) if len(v1) == 1 and min(v1) > 8]
    assert len({i in s0 for i in szingli}) == 1
    assert p1 > 0.95
    assert "kicsit tesz: 2" in l1
