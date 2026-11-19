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


def test_keresztlopas_kiengedessel_bridgemasters_1():
    """BridgeMasters #1 (6♠ S, ♥K indul; a terv a felhasználó szavaival, 2026-11-19):
    ♥A, a szingli ♣A, ♦K-val át, a ♣K-ra ♥ dobás, egy kis káró kiengedése („mindegy,
    hogy ütik vagy lopják”), keresztlopás, a ♦A a kiaduzás után. A védők lapjai saját
    sorsolás (♦ 5-1, ♠ 3-2): itt a ♦A korai lehívását ellopnák, ez a terv viszont teljesül."""
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor.tervkonyvelo import szakasz_valtozatok, tervjeloltek
    from kibic.solver.dds import lap_elemzes

    K = {"S": _kez("AKQJT.A2.A5432.A"), "N": _kez("987.543.K6.K5432"),
         "W": _kez("543.K6.JT987.QJT"), "E": _kez("62.QJT987.Q.9876")}
    kint = K["E"] | K["W"]
    lead = Lap.parse("HK")
    allas = Allas(felvevo="S", adu="S", kezek={"S": set(K["S"]), "N": set(K["N"])},
                  kint=kint - {lead}, cel=12, hatra=13, soron="N")
    nev = "♣ vesztőcsere (dobás: ♥) → ♦ lopás a rövid kézben (kiengedéssel, a felső lap a végén) → kiaduzás"
    T = next(v for t in tervjeloltek(allas, technikak_betoltese(), max_db=200, igeny=2, ures=(12, 13))
             for v in szakasz_valtozatok(t) if v.nev == nev)
    from kibic.domain import Leosztas
    from kibic.domain.kartya import Kez
    w = Leosztas({u: Kez(frozenset(K[u])) for u in "NESW"})
    k = Kontraktus(6, "S", "", "S")
    naplo: list[str] = []
    n = lejatszik(T, w, "S", "S", [("W", lead)],
                  lambda jj: tj._vedo_lap(lap_elemzes(w, [str(l) for _, l in jj.lapok], k)), naplo, cel=12)
    assert n >= 12, "\n".join(naplo)
    assert any("kiengedés" in s for s in naplo)


def test_leghasznosabb_dobas_a_terv_tobbi_egysege_szerint():
    """LEGHASZNOSABB_DOBAS: a magas lapra abból a színből dobunk, amelynek a vesztőit a
    terv más egysége nem kezeli. MB 4♠ (Kelet): ha a ♦ szöktetés a terv része, a ♥AK-ra
    treffet; BridgeMasters #1: a ♦ lopás mellett a ♣K-ra kőrt."""
    from kibic.motor.tervkonyvelo import hasznos_dobas
    T = technikak_betoltese()

    def allas(F, A, kezek, adu, cel):
        kint = {Lap.parse(s + r) for s in "SHDC" for r in "23456789TJQKA"} - kezek[F] - kezek[A]
        return Allas(felvevo=F, adu=adu, kezek={F: set(kezek[F]), A: set(kezek[A])},
                     kint=kint, cel=cel, hatra=13, soron=F)

    a = allas("E", "W", {"E": _kez("K8752..Q982.AKJ2"), "W": _kez("Q43.AKJ.AT43.543")}, "S", 10)
    P = peldanyok(a, T)
    vcs = next(p for p in P if p.sema.azon == "VESZTOCSERE" and p.szin == "H")
    szok = next(p for p in P if p.sema.azon.startswith("SZOKTETES") and p.szin == "D")
    assert hasznos_dobas(vcs, [vcs, szok], a) == "C"

    b = allas("S", "N", {"S": _kez("AKQJT.A2.A5432.A"), "N": _kez("987.543.K6.K5432")}, "S", 12)
    P = peldanyok(b, T)
    vcs = next(p for p in P if p.sema.azon == "VESZTOCSERE" and p.szin == "C")
    lop = next(p for p in P if p.sema.azon == "LOPAS_ROVID_KEZBEN" and p.szin == "D")
    assert hasznos_dobas(vcs, [vcs, lop], b) == "H"


def test_szanban_a_teljes_keret_is_jelolt_bridgemasters_2():
    """BridgeMasters #2 (6NT S, ♦Q indul; a szerkesztő kérdése 2026-11-19): a ♣KQT876 /
    ♣A2 színből 5 ütés legfeljebb 1 vesztéssel — a teljes kiengedés minden elosztásban
    biztos. A ♥ és a ♦ „biztosan kiadó” vesztőit a treffekre dobjuk, ezért a ♣ egység a
    teljes megengedett kiadást (1) is megkapja, nem csak a maradékot (0)."""
    from kibic.motor.tervkonyvelo import szinkezeles_peldanyok
    K = {"S": _kez("KQJ.J9876.AK2.A2"), "N": _kez("A32.AK.43.KQT876")}
    kint = {Lap.parse(s + r) for s in "SHDC" for r in "23456789TJQKA"} - K["S"] - K["N"] - {Lap.parse("DQ")}
    a = Allas(felvevo="S", adu=None, kezek={"S": set(K["S"]), "N": set(K["N"])},
              kint=kint, cel=12, hatra=13, soron="N")
    P = szinkezeles_peldanyok(a, technikak_betoltese(), 2, (12, 13))
    c = {(p.szerepek["k"], p.szerepek["m"]): p.szerepek["esely"] for p in P if p.szin == "C"}
    assert c[(5, 1)] == 1.0
    assert c[(5, 0)] < 0.8
