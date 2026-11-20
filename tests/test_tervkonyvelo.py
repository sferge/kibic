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
    """Kiengedés, aztán keresztlopás (a minta forrása: BM A-2 #1; a lapok saját
    változat). A szerkesztő terve: ♥A, a szingli ♣A, ♦K-val át, a ♣K-ra ♥ dobás, egy kis
    káró kiengedése („mindegy, hogy ütik vagy lopják”), keresztlopás, a ♦A a kiaduzás
    után. ♦ 5-1, ♠ 3-2: a ♦A korai lehívását ellopnák, ez a terv viszont teljesül."""
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor.tervkonyvelo import szakasz_valtozatok, tervjeloltek
    from kibic.solver.dds import lap_elemzes

    K = {"S": _kez("AKQJT.A4.A7652.A"), "N": _kez("987.632.K3.K8542"),
         "W": _kez("543.K5.JT984.QJT"), "E": _kez("62.QJT987.Q.9763")}
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
    treffet; a ♦ lopás mellett (minta: BM A-2 #1, saját lapokkal) a ♣K-ra kőrt."""
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

    b = allas("S", "N", {"S": _kez("AKQJT.A4.A7652.A"), "N": _kez("987.632.K3.K8542")}, "S", 12)
    P = peldanyok(b, T)
    vcs = next(p for p in P if p.sema.azon == "VESZTOCSERE" and p.szin == "C")
    lop = next(p for p in P if p.sema.azon == "LOPAS_ROVID_KEZBEN" and p.szin == "D")
    assert hasznos_dobas(vcs, [vcs, lop], b) == "H"


def test_szanban_a_teljes_keret_is_jelolt_bridgemasters_2():
    """Szanban a teljes keret (minta: BM A-2 #2, saját lapokkal; 6NT, ♦Q indul): a ♣KQT986 /
    ♣A3 színből 5 ütés legfeljebb 1 vesztéssel — a teljes kiengedés minden elosztásban
    biztos. A ♥ és a ♦ „biztosan kiadó” vesztőit a treffekre dobjuk, ezért a ♣ egység a
    teljes megengedett kiadást (1) is megkapja, nem csak a maradékot (0)."""
    from kibic.motor.tervkonyvelo import szinkezeles_peldanyok
    K = {"S": _kez("KQJ.J9765.AK3.A3"), "N": _kez("A42.AK.54.KQT986")}
    kint = {Lap.parse(s + r) for s in "SHDC" for r in "23456789TJQKA"} - K["S"] - K["N"] - {Lap.parse("DQ")}
    a = Allas(felvevo="S", adu=None, kezek={"S": set(K["S"]), "N": set(K["N"])},
              kint=kint, cel=12, hatra=13, soron="N")
    P = szinkezeles_peldanyok(a, technikak_betoltese(), 2, (12, 13))
    c = {(p.szerepek["k"], p.szerepek["m"]): p.szerepek["esely"] for p in P if p.szin == "C"}
    assert c[(5, 1)] == 1.0
    assert c[(5, 0)] < 0.8


def test_a_terv_atmenetet_vedi():
    """ATMENET_VEDES — a terv által igényelt átmenet védése, és az elemző lopásai (minta:
    BM A-2 #3, saját lapokkal; 6♥, ♥9 indul): a ♣ kiengedése után Nyugat ♠B-t hív; a kéz
    a ♠A-val üti át az asztal ♠D-jét, hogy a ♠3 átmenet maradjon az asztal ♠K-jához — a
    ♣ terv szerinti kezeléséhez (kiengedés, lopás, visszamenet a kimagasított lapokért)."""
    from kibic.domain import Leosztas
    from kibic.domain.kartya import Kez
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor.tervkonyvelo import szakasz_valtozatok, tervjeloltek
    from kibic.solver.dds import lap_elemzes

    K = {"S": _kez("A3.AKQJT.A542.86"), "N": _kez("KQ.432.76.AK7532"),
         "W": _kez("JT98.98.T98.QJT9"), "E": _kez("76542.765.KQJ3.4")}
    lead = Lap.parse("H9")
    kint = (K["E"] | K["W"]) - {lead}
    allas = Allas(felvevo="S", adu="H", kezek={"S": set(K["S"]), "N": set(K["N"])},
                  kint=kint, cel=12, hatra=13, soron="N")
    nev = "kiaduzás → ♣ színkezelés (4 ütés, ≤1 vesztés)"
    T = next(v for t in tervjeloltek(allas, technikak_betoltese(), max_db=200, igeny=2, ures=(12, 13))
             for v in szakasz_valtozatok(t) if v.nev == nev)
    w = Leosztas({u: Kez(frozenset(K[u])) for u in "NESW"})
    k = Kontraktus(6, "H", "", "S")

    def vedo(jj):
        if len(jj.lapok) == 16 and jj.soron() == "W" and Lap.parse("SJ") in jj.kezek["W"]:
            return Lap.parse("SJ")               # a ♣ kiengedése után: ♠ vissza
        return tj._vedo_lap(lap_elemzes(w, [str(l) for _, l in jj.lapok], k))
    naplo: list[str] = []
    n = lejatszik(T, w, "S", "H", [("W", lead)], vedo, naplo, cel=12)
    assert n >= 12, "\n".join(naplo)
    assert any("a terv átmenetét védi" in x for x in naplo), "\n".join(naplo)


def test_deblokk_a_zart_szinben():
    """DEBLOKK (minta: BM A-2 #4, saját lapokkal; 4♠, ♥K indul): ♣A2 / ♣KQJ9 és ♦A2 /
    ♦KQJ9 — a rövid kéz (az asztal) az ászt adja az első körben, különben a hosszú kéz
    lapjai beragadnak. A 3-2 adunál 10 ütés felett."""
    from kibic.domain import Leosztas
    from kibic.domain.kartya import Kez
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor.tervkonyvelo import szakasz_valtozatok, tervjeloltek
    from kibic.solver.dds import lap_elemzes

    K = {"S": _kez("A5432..KQJ9.KQJ9"), "N": _kez("876.765432.A2.A2"),
         "W": _kez("KQ9.AKQJ.T87.T87"), "E": _kez("JT.T98.6543.6543")}
    lead = Lap.parse("HK")
    kint = (K["E"] | K["W"]) - {lead}
    allas = Allas(felvevo="S", adu="S", kezek={"S": set(K["S"]), "N": set(K["N"])},
                  kint=kint, cel=10, hatra=13, soron="N")
    T = next(v for t in tervjeloltek(allas, technikak_betoltese(), max_db=200, igeny=0, ures=(12, 13))
             for v in szakasz_valtozatok(t) if v.nev == "csak begyűjtés")
    w = Leosztas({u: Kez(frozenset(K[u])) for u in "NESW"})
    k = Kontraktus(4, "S", "", "S")
    naplo: list[str] = []
    n = lejatszik(T, w, "S", "S", [("W", lead)],
                  lambda jj: tj._vedo_lap(lap_elemzes(w, [str(l) for _, l in jj.lapok], k)), naplo, cel=10)
    assert n >= 10, "\n".join(naplo)
    assert any("deblokk" in x for x in naplo), "\n".join(naplo)


def test_adu_leallas_a_kiadasi_keretben():
    """ADU_LEALLAS (a szerkesztő terve, minta: BM A-2 #4, saját lapokkal; 4♠, ♥K indul):
    a kőrt ellopjuk, az adu ászt lehívjuk, aztán nem hívunk több adut — a védők maradék
    adui mind nagyobbak a mieinknél, és beleférnek a keretbe (3); a magas lapjainkat
    hívjuk, és hagyjuk, hogy ellopják. Így a 4-1-es adu ellen is 10 ütés."""
    from kibic.domain import Leosztas
    from kibic.domain.kartya import Kez
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor.tervkonyvelo import szakasz_valtozatok, tervjeloltek
    from kibic.solver.dds import lap_elemzes

    K = {"S": _kez("A6432..KQJT.KQJT"), "N": _kez("875.765432.A2.A2"),
         "W": _kez("T.AKQJ8.9876.987"), "E": _kez("KQJ9.T9.543.6543")}
    lead = Lap.parse("HK")
    kint = (K["E"] | K["W"]) - {lead}
    allas = Allas(felvevo="S", adu="S", kezek={"S": set(K["S"]), "N": set(K["N"])},
                  kint=kint, cel=10, hatra=13, soron="N")
    T = next(v for t in tervjeloltek(allas, technikak_betoltese(), max_db=200, igeny=0, ures=(12, 13))
             for v in szakasz_valtozatok(t) if v.nev == "csak begyűjtés")
    w = Leosztas({u: Kez(frozenset(K[u])) for u in "NESW"})
    k = Kontraktus(4, "S", "", "S")
    naplo: list[str] = []
    n = lejatszik(T, w, "S", "S", [("W", lead)],
                  lambda jj: tj._vedo_lap(lap_elemzes(w, [str(l) for _, l in jj.lapok], k)), naplo, cel=10)
    assert n >= 10, "\n".join(naplo)
    adukorok = [x for x in naplo if "adukör" in x]
    assert len(adukorok) == 1, "\n".join(naplo)       # csak az ász


def test_adu_leallas_ellenpelda_atmenet_csak_a_hosszu_szinben():
    """A szerkesztő ellenpéldája (2026-11-20) az ADU_LEALLAS első változatára: az
    asztalon sok nyerő egy mellékszínben (♥AKQJT9), és oda csak ebben a színben van
    átmenet; a kéz vesztőit (♦, ♣) ezekre kell dobni. Ha a magas adut kint hagyjuk, a
    védő akkor lop be, amikor az utolsó átmenetet használjuk — a többi kőr beragad.
    Itt tovább kell aduzni. (Saját leosztás.)"""
    from kibic.domain import Leosztas
    from kibic.domain.kartya import Kez
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor.tervkonyvelo import szakasz_valtozatok, tervjeloltek
    from kibic.solver.dds import lap_elemzes

    K = {"S": _kez("A43.5.AK543.AK43"), "N": _kez("87652.AKQJT9.2.2"),
         "W": _kez("KQ9.832.QJT.QJT9"), "E": _kez("JT.764.9876.8765")}
    lead = Lap.parse("CQ")
    kint = (K["E"] | K["W"]) - {lead}
    allas = Allas(felvevo="S", adu="S", kezek={"S": set(K["S"]), "N": set(K["N"])},
                  kint=kint, cel=10, hatra=13, soron="N")
    T = next(v for t in tervjeloltek(allas, technikak_betoltese(), max_db=200, igeny=0, ures=(12, 13))
             for v in szakasz_valtozatok(t) if v.nev == "csak begyűjtés")
    w = Leosztas({u: Kez(frozenset(K[u])) for u in "NESW"})
    k = Kontraktus(4, "S", "", "S")
    naplo: list[str] = []
    n = lejatszik(T, w, "S", "S", [("W", lead)],
                  lambda jj: tj._vedo_lap(lap_elemzes(w, [str(l) for _, l in jj.lapok], k)), naplo, cel=10)
    assert n >= 10, "\n".join(naplo)
    assert sum("adukör" in x for x in naplo) >= 2, "\n".join(naplo)
