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
    megütni, és már nincs tartalék: a második kéz a nyerőjével üt."""
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "S", "C", [("W", Lap.parse("D7"))], tj.Terv(()))
    v = Vegrehajto(KTerv([]), j)
    v.cel = 13
    assert v.lap("N") in {Lap.parse("DA"), Lap.parse("DK")}
    v.cel = 11
    j2 = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "S", "C", [("W", Lap.parse("D7"))], tj.Terv(()))
    v2 = Vegrehajto(KTerv([]), j2)
    v2.cel = 11
    assert v2.lap("N") == Lap.parse("D2")                       # van tartalék: kicsi


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
