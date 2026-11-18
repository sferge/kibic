"""A tervkönyvelő végrehajtója (2026-11-18): foglalások, második kéz, megfigyelés."""
from kibic.domain import Lap
from kibic.motor import tervjatszo as tj
from kibic.motor.tervkonyvelo import KTerv, Vegrehajto, _egyszeru_vedo, lejatszik
from kibic.motor.tervsema import Allas, peldanyok, technikak_betoltese


def _kez(s: str) -> set[Lap]:
    ki = set()
    for sz, r in zip("SHDC", s.split(".")):
        ki |= {Lap.parse(sz + c) for c in r}
    return ki


# saját szerkesztésű leosztás (nem gyűjteményből)
KEZEK = {"N": _kez("Q3.K4.AK2.AKJT53"), "S": _kez("J62.AJ52.JT94.Q2"),
         "E": _kez("AK87.Q98.Q53.864"), "W": _kez("T954.T763.876.97")}


def _allas(felvevo="N"):
    a = "S" if felvevo == "N" else "N"
    kint = KEZEK["E"] | KEZEK["W"]
    return Allas(felvevo=felvevo, adu="C", kezek={felvevo: set(KEZEK[felvevo]), a: set(KEZEK[a])},
                 kint=kint, cel=11, hatra=13, soron=felvevo)


def _pld(azon, szin, felvevo="N"):
    return next(p for p in peldanyok(_allas(felvevo), technikak_betoltese())
                if p.sema.azon == azon and p.szin == szin)


def test_foglalas_a_kisero_es_a_kez_fele_hivott_kis_lap():
    """♥ impassz (♥K deblokk, aztán kicsi a ♥J felé): a ♥4 az impassz hívása, és a
    deblokkhoz az asztalnak kell egy kísérő kis kőr — ezeket nem dobhatjuk el."""
    p = _pld("IMPASSZ_VILLA", "H")
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "N", "C", [], tj.Terv(()))
    v = Vegrehajto(KTerv([p]), j)
    f = v._foglalt()
    assert {Lap.parse("H4"), Lap.parse("H2")} <= f
    assert Lap.parse("H5") not in f
    assert v._dobas("S", f).szin != "H" or v._dobas("S", f) == Lap.parse("H5")


def test_masodik_kez_ut_ha_nincs_tartalek():
    """Nyugat kárót hív, az asztal (Észak) ♦AK2, a felvevő (Dél) nem tudja a ♦D-t
    megütni: a második kéz a nyerőjével üt (tartalék nélkül mindig; tartalékkal is,
    ha két biztos nyerője van)."""
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "S", "C", [("W", Lap.parse("D7"))], tj.Terv(()))
    v = Vegrehajto(KTerv([]), j)
    v.cel = 13
    assert v.lap("N") in {Lap.parse("DA"), Lap.parse("DK")}
    v.cel = 11
    j2 = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "S", "C", [("W", Lap.parse("D7"))], tj.Terv(()))
    v2 = Vegrehajto(KTerv([]), j2)
    v2.cel = 11
    # tartalékkal is üt, ha két biztos nyerője van (a ♦D-t a harmadik kéz se vigye)
    assert v2.lap("N") in {Lap.parse("DA"), Lap.parse("DK")}


def test_vegigjatszik_es_a_naplo_az_egysegeket_koveti():
    """A ♦ ejtés → ♥ impassz terv végigmegy (egyszerű védőkkel), a napló az egységek
    köreit és a megfigyelt kimenetet mutatja, szabálytalan lap nélkül."""
    t = KTerv([_pld("EJTES", "D"), _pld("IMPASSZ_VILLA", "H")])
    naplo: list[str] = []
    w = type("V", (), {"kezek": {u: type("K", (), {"lapok": frozenset(KEZEK[u])})() for u in "NESW"}})()
    n = lejatszik(t, w, "N", "C", [("E", Lap.parse("SK"))], lambda jj: _egyszeru_vedo(jj, jj.soron()),
                  naplo, cel=11)
    assert n >= 11
    assert any(s.endswith("♦ ejtés: sikerült") or "♦ ejtés: nem sikerült" in s for s in naplo)
    assert not any("szabálytalan" in s for s in naplo)


def test_ott_ut_ahonnan_a_terv_folytatodik():
    """MB 4♠ (2026-11-18): Dél kőrt indul, az asztal (Nyugat) ♥AKJ, Kelet kőrből
    színhiányos. A terv következő köre a ♣ impassz Nyugatról — az asztal a nyerővel
    üt (nem a ♥J-vel), Kelet nem lop, hanem dob."""
    E, W = _kez("K8752..Q982.AKJ2"), _kez("Q43.AKJ.AT43.543")
    N, S = _kez("J9.QT972.76.Q986"), _kez("AT6.86543.KJ5.T7")
    kezek = {"E": E, "W": W, "N": N, "S": S}
    allas = Allas(felvevo="E", adu="S", kezek={"E": set(E), "W": set(W)}, kint=N | S,
                  cel=10, hatra=13, soron="W")
    p = next(p for p in peldanyok(allas, technikak_betoltese())
             if p.sema.azon == "IMPASSZ_VILLA" and p.szin == "C")
    j = tj.Jatek({u: set(x) for u, x in kezek.items()}, "E", "S", [("S", Lap.parse("H5"))], tj.Terv(()))
    v = Vegrehajto(KTerv([p]), j)
    v.cel = 10
    lw = v.lap("W")
    assert lw in {Lap.parse("HA"), Lap.parse("HK")}
    j.tesz("W", lw)
    j.tesz("N", Lap.parse("H2"))
    le = v.lap("E")
    assert le.szin != "S"                                       # nem lop
