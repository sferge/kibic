"""A cselek (coupok) sématára: a hozzátevési sémák és a védő hívására tett lap (2026-11-22).

A példák saját leosztások (claude/sematar-naplo-cselek.md)."""
import pytest

from kibic.domain import Lap
from kibic.motor import tervjatszo as tj
from kibic.motor.tervkonyvelo import KICSI
from kibic.motor.tervsema import Allas, hozzatetelek, technikak_betoltese
from kibic.szolgaltatas import tervmuhely as tm


def _kez(s):
    ki = set()
    for sz, r in zip("SHDC", s.split(".")):
        ki |= {Lap.parse(sz + c) for c in r}
    return ki


# Bath-csel: 3NT Dél, Nyugat a ♠K-val indul; ♠ÁB4 / ♠75, a ♦Á-t (Kelet) ki kell ütni.
# DD a ♠K–♠5–♠2 után: ♠4 11 ütés, ♠B 10, ♠Á 8 (bukás).
BATH = {"N": _kez("75.A84.KQJT.Q762"), "E": _kez("932.962.A764.T94"),
        "S": _kez("AJ4.KQ5.853.AK83"), "W": _kez("KQT86.JT73.92.J5")}
# ellenpélda: 10 felső ütés, a kőrben a védőké öt — a kiengedés után Nyugat kőrre vált
NEM_BATH = {"N": _kez("75.32.AKQ2.AKQJT"), "E": _kez("632.QJT98.76.765"),
            "S": _kez("AJ4.654.J543.432"), "W": _kez("KQT98.AK7.T98.98")}


def _keres(j: tj.Jatek, n: int, deadline_ms: int = 60000) -> dict:
    u = j.soron()
    utes = j.aktualis()
    van = [l for l in j.kezek[u] if utes and l.szin == utes[0][1].szin]
    return {"protocol": "mohabridzs-ai/1.0", "request_id": f"r{n}", "decision": "play",
            "deadline_ms": deadline_ms,
            "game": {"match_id": "cselek", "table_index": 0, "board_number": 1, "vulnerability": "none"},
            "actor": {"seat": "S", "acting_for_seat": u},
            "state": {"phase": "play", "dealer": "S", "contract": {"level": 3, "strain": "NT", "multiplier": 1},
                      "declarer": "S", "dummy": "N",
                      "visible_hands": {x: sorted(str(l) for l in j.kezek[x]) for x in "NS"}},
            "history": {"auction": [], "play": [{"seat": s, "card": str(l)} for s, l in j.lapok]},
            "legal_actions": {"cards": sorted(str(l) for l in (van or j.kezek[u]))}}


def _allas(kezek, utes, adu=None) -> Allas:
    mieink = kezek["N"] | kezek["S"]
    lement = {l for _, l in utes}
    kint = {Lap.parse(s + r) for s in "SHDC" for r in "23456789TJQKA"} - mieink - lement
    return Allas(felvevo="S", adu=adu, kezek={u: set(kezek[u]) - lement for u in "NS"}, kint=kint,
                 cel=9, hatra=13, soron="N", utes=list(utes))


def test_bath_sema_szerepei():
    """A ♠K-ra (védő hívta) a séma alkalmazható: a sorozat párja a kint lévő ♠D, nálunk
    ♠Á és ♠B; a megtartott lapok a fogások."""
    hz = hozzatetelek(_allas(BATH, [("W", Lap.parse("SK"))]), technikak_betoltese())
    assert [h.nev for h in hz] == ["BATH S"]
    h = hz[0]
    assert h.szerepek["D"] == Lap.parse("SQ") and h.szerepek["FELSO"] == Lap.parse("SA")
    assert h.szerepek["ALSO"] == Lap.parse("SJ")
    assert h.teendo == "kicsi"
    assert h.rovid == "♠ Bath-csel"
    # az asztal már tett: a felvevő lapja még hátra van — a séma él
    assert hozzatetelek(_allas(BATH, [("W", Lap.parse("SK")), ("N", Lap.parse("S5")),
                                      ("E", Lap.parse("S2"))]), technikak_betoltese())


def test_bath_sema_nem_alkalmazhato():
    t = technikak_betoltese()
    # nincs folyó ütés, vagy mi hívtunk
    assert not hozzatetelek(_allas(BATH, []), t)
    assert not hozzatetelek(_allas(BATH, [("S", Lap.parse("S4"))]), t)
    # kis lapot hívott: nincs sorozat-pár kint közvetlenül alatta, ami fölött az Á…
    assert not hozzatetelek(_allas(BATH, [("W", Lap.parse("S6"))]), t)
    # az aduban nem
    assert not hozzatetelek(_allas(BATH, [("W", Lap.parse("SK"))], adu="S"), t)
    # a B nélkül (♠Á54): nincs fogás a D alatt
    # — ott a sima visszatartás (VISSZATARTAS, BM A-13) a jelölt
    k = dict(BATH, S=_kez("A54.KQ5.853.AK83"), W=_kez("KQT86.JT73.92.J"), E=_kez("J932.962.A764.T9"))
    assert [h.sema.azon for h in hozzatetelek(_allas(k, [("W", Lap.parse("SK"))]), t)] == ["VISSZATARTAS"]


def _vegig_elso_utes(kezek, monkeypatch, tmp_path):
    monkeypatch.setattr(tm, "TAR", tmp_path)
    j = tj.Jatek({u: set(kezek[u]) for u in "NESW"}, "S", None, [], tj.Terv(()))
    j.tesz("W", Lap.parse("SK"))
    p = tm.plan_valasz(_keres(j, 0))
    r1 = tm.step_valasz(_keres(j, 1))
    j.tesz("N", Lap.parse(r1["action"]["card"]))
    j.tesz("E", Lap.parse("S2"))
    r2 = tm.step_valasz(_keres(j, 2))
    return p, r1, r2


def test_bath_a_tervben_mindket_kez(monkeypatch, tmp_path):
    """A terv az asztal lapjánál készül, és a felvevő lapjáról is dönt: a ♠K-ra az
    asztalról és a kézből is kicsi (nem a végrehajtó „üt a legolcsóbbal: ♠Á”-ja)."""
    p, r1, r2 = _vegig_elso_utes(BATH, monkeypatch, tmp_path)
    assert r1["action"]["card"] in ("S5", "S7")
    assert r2["action"]["card"] == "S4", r2["summary"]
    # (2026-11-24 óta a KIENGEDES általános szabály is ezt teszi: ilyenkor a terv a
    # „♦ színkezelés” — a kicsi mindkét kézből a végrehajtó kiengedése)
    if not p["plan"]["name"].startswith("♠ Bath-csel → "):
        assert "kiengedés" in r1["summary"] and "kiengedés" in r2["summary"], (p["plan"], r2["summary"])
        return
    assert "Bath-csel" in r2["summary"] and r2["analysis_result"] == "existing_plan"
    k3 = _keres(_jatek_a_ket_lap_utan(), 3)
    rek = tm.betolt(tm._kulcs(k3, "S"), tm.helyzet(k3))
    assert rek is not None and rek.utes_dontes_nev == "♠ Bath-csel"
    assert [x[2] for x in rek.utes_dontes] == [KICSI, KICSI]


def _jatek_a_ket_lap_utan():
    j = tj.Jatek({u: set(BATH[u]) for u in "NESW"}, "S", None, [], tj.Terv(()))
    for u, l in (("W", "SK"), ("N", "S5"), ("E", "S2")):
        j.tesz(u, Lap.parse(l))
    return j


def test_bath_ellenpelda_az_asz_ut(monkeypatch, tmp_path):
    """Ha a kiengedés után Nyugat a kőrrel elveszi a felvételt, a terv nem engedi ki."""
    p, r1, r2 = _vegig_elso_utes(NEM_BATH, monkeypatch, tmp_path)
    assert "Bath" not in p["plan"]["name"]
    assert r2["action"]["card"] == "SA", r2["summary"]


def test_utes_dontes_azonos_vilagokon(monkeypatch, tmp_path):
    """HIVASRA_TETT_LAP: a változatok és az alap ugyanazokon a világokon, ugyanannyin
    futnak (a 2026-11-22-i fantom-nyereség: 20 világos becslés a 60 világos ellen)."""
    hivasok = []
    eredeti = tm.ertekel_lepcsos

    def figyel(tervek, vl, *a, **kw):
        hivasok.append((len(vl), tuple(id(w) for w in vl), kw.get("elso")))
        return eredeti(tervek, vl, *a, **kw)
    monkeypatch.setattr(tm, "ertekel_lepcsos", figyel)
    monkeypatch.setattr(tm, "TAR", tmp_path)
    monkeypatch.setattr(tm, "VILAG", 24)
    j = _jatek_a_ket_lap_utan()
    tm.plan_valasz(_keres(j, 0))
    osszevetes = hivasok[1:]                       # az első a fő értékelés
    assert len(osszevetes) >= 2
    assert len({h[1] for h in osszevetes}) == 1    # ugyanazok a világok
    assert all(h[2] == h[0] for h in osszevetes)   # mindegyik minden világon


def test_a_felvevo_lapja_a_lepesnel_is_a_terve(monkeypatch, tmp_path):
    """Ha a terv az asztal lapjánál készült, és a felvevő lapjáról nem döntött, a
    lépéskérés a felvevő lapjánál dönt (most, hogy a védő lapja is látszik) — egyszer."""
    monkeypatch.setattr(tm, "TAR", tmp_path)
    monkeypatch.setattr(tm, "VILAG", 8)
    monkeypatch.setattr(tm, "SZABALY_HIVASRA", False)
    j = tj.Jatek({u: set(BATH[u]) for u in "NESW"}, "S", None, [], tj.Terv(()))
    j.tesz("W", Lap.parse("SK"))
    tm.plan_valasz(_keres(j, 0))
    r1 = tm.step_valasz(_keres(j, 1))
    j.tesz("N", Lap.parse(r1["action"]["card"]))
    j.tesz("E", Lap.parse("S2"))
    monkeypatch.setattr(tm, "SZABALY_HIVASRA", True)
    hivas = []

    def kamu(keres, h, rek, dd_zar):
        hivas.append(len(h.lejatszott))
        return ([[3, "S", "SJ", "próba: a terv lapja"]], None, None)
    monkeypatch.setattr(tm, "_lepes_utes_dontes", kamu)
    r2 = tm.step_valasz(_keres(j, 2))
    assert hivas == [3]
    assert r2["action"]["card"] == "SJ" and "próba" in r2["summary"]
    # ugyanarra a lapra még egyszer: a döntés a fájlban van, nincs új számolás
    r3 = tm.step_valasz(_keres(j, 3))
    assert hivas == [3] and r3["action"]["card"] == "SJ"


# --- FOGAS_VEDES: a megfelelő fogás (a szerkesztő, 2026-11-23) ---------------------------

def _L(s):
    return [Lap.parse(x) for x in s.split()]


def test_fogas_menet():
    """Az Á első menet; az Á kint: a KD második menet, a Kx nem fogás; a DB10 az ÁK ellen
    harmadik menet. Színfelvételben az adu fogás: színhiánnyal első, szinglivel második
    menet."""
    from kibic.motor.tervfogas import fogas_menet
    assert fogas_menet({"N": _L("SA S2"), "S": _L("S3")}, _L("SK SQ SJ"), "S", None) == 1
    assert fogas_menet({"N": _L("SK SQ"), "S": _L("S3")}, _L("SA SJ ST"), "S", None) == 2
    assert fogas_menet({"N": _L("SK"), "S": _L("SQ")}, _L("SA SJ ST"), "S", None) == 2
    assert fogas_menet({"N": _L("SK S2"), "S": _L("S3")}, _L("SA SJ ST"), "S", None) is None
    assert fogas_menet({"N": _L("SQ SJ ST"), "S": _L("S3")}, _L("SA SK S9"), "S", None) == 3
    assert fogas_menet({"N": _L("H2"), "S": _L("S3 S4")}, _L("SA SK"), "S", "H") == 1
    assert fogas_menet({"N": _L("H2 S5"), "S": _L("S3 S4")}, _L("SA SK"), "S", "H") == 2
    assert fogas_menet({"N": _L("H2"), "S": _L("H3")}, _L("SA SK"), "S", None) is None
    assert fogas_menet({"N": _L("S2"), "S": _L("S3")}, _L("HA"), "S", None) == 0


def test_megtartando_fogas():
    """A Bath-csel után (♠ÁB4 / ♠75, kint ♠D10986 3): az ♠Á nélkül nincs fogás — megtartjuk;
    a ♠B nélkül az Á első menet — a B szabad. Színfelvételben (♥ÁD4 / ♥3 + adu): ha nem
    adhatunk ki több ütést, a ♥Á kell; ha egyet még igen, az asztal lopása (második menet)
    elég."""
    from kibic.motor.tervfogas import foglalt_fogas
    kint = _L("SQ ST S9 S8 S6 S3")
    assert foglalt_fogas({"N": _L("S7 S5"), "S": _L("SA SJ S4")}, kint, None, 2) == {Lap.parse("SA")}
    kezek = {"N": _L("H3 S2 S3"), "S": _L("HA HQ H4 SA SK")}
    kint = _L("HK HJ HT H9 H8")
    assert Lap.parse("HA") in foglalt_fogas(kezek, kint, "S", 0)
    assert Lap.parse("HA") not in foglalt_fogas(kezek, kint, "S", 1)


def test_bath_vegig_a_fogas_megmarad(monkeypatch, tmp_path):
    """A Bath-példa végig (a védők DD szerint): a kiengedés után a ♠Á nem átmenet a kézbe
    (FOGAS_VEDES), a ♦Á kiütése után szabad — legalább 9 ütés (DD: 11)."""
    from kibic.domain.kartya import Leosztas
    from kibic.domain.pontozas import Kontraktus
    from kibic.solver.dds import lap_elemzes
    monkeypatch.setattr(tm, "TAR", tmp_path)
    lo = Leosztas.pbn_bol("N:75.A84.KQJT.Q762 932.962.A764.T94 AJ4.KQ5.853.AK83 KQT86.JT73.92.J5")
    k = Kontraktus.parse("3NT", "S")
    j = tj.Jatek({u: set(BATH[u]) for u in "NESW"}, "S", None, [], tj.Terv(()))
    j.tesz("W", Lap.parse("SK"))
    tm.plan_valasz(_keres(j, 0))
    n = 1
    while len(j.lapok) < 52:
        u = j.soron()
        if j.mi(u):
            r = tm.step_valasz(_keres(j, n))
            lap = Lap.parse(r["action"]["card"])
            assert not (lap == Lap.parse("SA") and j.aktualis() == [] and len(j.lapok) < 12), r["summary"]
        else:
            ert = lap_elemzes(lo, [str(l) for _, l in j.lapok], k)
            lap = max(ert, key=lambda e: e.utesek).lap
            lap = Lap.parse(str(lap))
        j.tesz(u, lap)
        n += 1
    assert j.felvevo_utesek() >= 9


def test_fogas_nem_atmenet_amig_a_terv_kiad(monkeypatch, tmp_path):
    """A „♦ színkezelés” terv a Bath-kiengedés után (a védők DD szerint): a FOGAS_VEDES
    nélkül a végrehajtó az ♠Á-t viszi át a kézbe (átmenet), és Nyugat lehívja a pikkjeit
    (8 ütés); vele a ♥ / ♣ az átmenet, az ♠Á csak a ♦Á kiütése után szabad (11 ütés)."""
    from kibic.domain.kartya import Leosztas
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor import tervkonyvelo as tk
    monkeypatch.setattr(tm, "TAR", tmp_path)
    monkeypatch.setattr(tm, "VILAG", 20)
    j = _jatek_a_ket_lap_utan()
    tm.plan_valasz(_keres(j, 0))
    k3 = _keres(j, 0)
    rek = tm.betolt(tm._kulcs(k3, "S"), tm.helyzet(k3))
    terv = next(r.terv for r in rek.eredmenyek if r.terv.nev == "♦ színkezelés (3 ütés, ≤3 vesztés)")
    lo = Leosztas.pbn_bol("N:75.A84.KQJT.Q762 932.962.A764.T94 AJ4.KQ5.853.AK83 KQT86.JT73.92.J5")
    tar = tj.DDTar(tm._dd_fv(None), Kontraktus.parse("3NT", "S"))
    lej = [("W", Lap.parse("SK")), ("N", Lap.parse("S5")), ("E", Lap.parse("S2"))]

    def jatszik():
        naplo = []
        n = tk.lejatszik(terv, lo, "S", None, lej, lambda jj: tj._vedo_lap(tar(0, lo, jj.lapok)),
                         naplo=naplo, cel=9, utes_dontes={3: ("S", KICSI, "Bath")})
        return n, naplo
    n, naplo = jatszik()
    assert n == 11, naplo
    assert not any("átmenet SA" in s for s in naplo[:12])
    # (a TAKAREKOS döntő maga is elkerüli itt a ♠Á-átmenetet: a fogásvédelem nélküli
    # régi játékhoz azt is kikapcsoljuk; az elemzők tárát ürítjük)
    from kibic.motor import tervszinkezeles as ts, tervszinpolitika as tsp
    monkeypatch.setitem(tk.SZABALY, "FOGAS_VEDES", False)
    monkeypatch.setattr(ts, "TAKAREKOS", False)
    tsp.urites()
    n, naplo = jatszik()
    tsp.urites()
    assert n < 9 and any("átmenet SA" in s for s in naplo)


# --- A kiadási ALKALMAK (a szerkesztő, 2026-11-23; MB 49 szerkezete, saját lapokkal) -----
# 3NT Dél, Nyugat ♥D-vel indul. A ♦-ban kétszer kell kiadni (♦ÁK kint), a ♥ÁK közül az
# egyik az első ütésben elmegy: az első kiadás után kiütik a másikat, a második után
# lehívják a kőreiket. A ♠ (ÁKB109 a D876 ellen) egy kiadással (vagy impasszal) hozza a
# kilenc ütést.
ALK = {"S": _kez("AKJT9.AK.Q32.KJ2"), "N": _kez("32.32.JT9876.AT3"),
       "W": _kez("54.QJT987.A5.654"), "E": _kez("Q876.654.K4.Q987")}


def test_menetsor_es_alkalmak():
    """„Az 1x 2 db kiadó szín esetét a 2x 1 db kiadó esetétől meg kell különböztetni.”
    A menetsor: ki üti a szín egyes meneteit, ha a védők hívják. Egy alkalommal a védők a
    színben az első fogásunkig visznek ütést; két alkalommal a másodikig (az elsőt kiütik)."""
    from kibic.motor.tervfogas import menetsor, vedo_utesek, fogasok_megfelelok
    # egy fogás (♥Á), a védőknél hét kőr: az első alkalommal kiütik, a másodikkal lehívják
    sor = menetsor({"S": _L("HA"), "N": _L("H3")}, _L("HJ HT H9 H8 H7 H6 H5"), "H", None)
    assert sor == "MVVVVVV"
    assert vedo_utesek(sor, 1) == 0 and vedo_utesek(sor, 2) == 6
    # két első menet fogás (♥ÁK): két alkalom sem ad nekik ütést
    sor = menetsor({"S": _L("HA HK"), "N": _L("H3")}, _L("HQ HJ HT H9 H8"), "H", None)
    assert sor.startswith("MM") and vedo_utesek(sor, 2) == 0
    # második menet fogás (♥KD az Á ellen): egy alkalommal egy ütés, a két fogás
    # (KDB) két alkalomra is elég — egy ütés árán
    sor = menetsor({"N": _L("HK HQ HJ"), "S": _L("H3")}, _L("HA HT H9"), "H", None)
    assert sor.startswith("VMM") and vedo_utesek(sor, 1) == 1 and vedo_utesek(sor, 2) == 1
    # a feltétel: egy alkalommal a ♥Á elég, kettővel nem
    kezek = {"S": _L("HA S2"), "N": _L("H3 S3")}
    kint = _L("HJ HT H9 H8 H7 H6 H5")
    assert fogasok_megfelelok(kezek, kint, None, 0, alkalom=1)
    assert not fogasok_megfelelok(kezek, kint, None, 2, alkalom=2)


def test_ket_kiadas_ket_fogas_kell():
    """MB 49 szerkezete: a két kiadású ♦ terv nem teljesíti a fogás feltételét (az indulás
    a ♥K-t viszi, egy kőrfogás marad két kiadásra); a ♠ terv igen, és előbb jut a
    szimulációba. A régi szabály (csak a kiadható ütések száma) mindkettőt elfogadta."""
    from kibic.motor.tervkonyvelo import tervjeloltek
    assert len(set().union(*ALK.values())) == 52
    a = _allas(ALK, [("W", Lap.parse("HQ"))])
    t = tervjeloltek(a, technikak_betoltese(), max_db=200, igeny=3, ures=(12, 12), max_szim=500)
    ok = {x.nev: x.fogas_ok for x in t}
    assert ok["♠ színkezelés (5 ütés, ≤2 vesztés) → ♦ színkezelés (3 ütés, ≤4 vesztés)"] is False
    assert ok["♠ színkezelés (4 ütés, ≤2 vesztés) → ♣ színkezelés (3 ütés, ≤2 vesztés)"] is True
    assert t[0].fogas_ok and "♦ színkezelés" not in t[0].nev


# --- Az esélyek kombinációja: feltételes folytatás (a szerkesztő, 2026-11-23, MB 49) ------
# A BM-vonal: ♣B a kézből (ráhívás az ♣Á10 felé). Ha nem ütik meg (vagy Nyugat fed): 3
# treffütés, a pikkből elég 4 (egy kiadással). Ha Kelet üt a ♣D-vel: két átmenet marad
# (♣2→♣10, a ♣K-t az ♣Á üti felül), két pikkimpassz az 5 pikkütésért.
KOMB_NYUGAT_D = {"S": _kez("AKJT9.AK.Q32.KJ2"), "N": _kez("32.32.JT9876.AT3"),
                 "W": _kez("54.QJT987.A5.Q65"), "E": _kez("Q876.654.K4.9874")}
KOMB_NINCS_10 = {"S": _kez("AKJT9.AK.Q32.KJ2"), "N": _kez("32.32.JT9876.A43"),
                 "W": _kez("54.QJT987.A5.765"), "E": _kez("Q876.654.K4.QT98")}
KOMB_TERV = "♣ impassz ráhívással → ♠ színkezelés (5 ütés, ≤2 vesztés)"


def test_feluletes_atmenet_redundanciaval():
    """A felülütés csak redundancia esetén átmenet (ahányszoros, annyi)."""
    from kibic.motor.tervkonyvelo import atmenet_szam
    def t(S, N, kint):
        return atmenet_szam({"S": set(_L(S)), "N": set(_L(N))}, "S", "N", _L(kint), "H")[1]
    assert t("DK D2", "DA DT", "D9 D8 D7 D6 D5 D4") == 2      # ♦2→10, ♦K-t az Á üti
    assert t("DK DJ D2", "DA DT D3", "DQ D9 D8 D7") == 1      # a D kint: nincs redundancia
    assert t("DK D2", "DA D4", "DT D9 D8 D7") == 1            # a 10 kint: egy átmenet
    assert t("DK DQ", "DA DJ", "DT D9 D8") == 1               # a B nem üti felül a D-t


def test_elemzo_halott_tartas_dupla_impassz():
    """♠AKB109 / ♠32 a D87654 ellen, 5 ütés: a dupla impassz az asztalról (Kelet D876
    is), nem a K lehívása — a testvérágban már elbukott tartás (Nyugat Dxx, kiengedte a
    9-et) a döntésben nem számít (HALOTT_TARTAS)."""
    from kibic.motor import tervszinkezeles as ts
    F = frozenset
    el = ts.Elemzo(ts.Feladat(F({9, 10, 11, 13, 14}), F({2, 3}), F({12, 8, 7, 6, 5, 4}), 13, 13))
    p, _, leiras = el.megold(5, 99)
    assert p > 0.4 and leiras.startswith("asztal hív")


def test_rahivas_peldany():
    from kibic.motor.tervsema import peldanyok
    for H, van in ((ALK, True), (KOMB_NYUGAT_D, True), (KOMB_NINCS_10, False)):
        a = _allas(H, [("W", Lap.parse("HQ"))])
        p = [x for x in peldanyok(a, technikak_betoltese()) if x.sema.azon == "IMPASSZ_RAHIVAS"]
        assert bool(p) == van
        if p:
            assert [(k.fajta, k.hivo, str(k.lap)) for k in p[0].korok] == [("impassz", "S", "CJ")]


def _komb_lejatszas(H, kenyszer):
    from kibic.domain import Leosztas
    from kibic.domain.kartya import Kez
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor.tervkonyvelo import lejatszik, tervjeloltek
    from kibic.solver.dds import lap_elemzes
    lo = Leosztas({u: Kez(frozenset(H[u])) for u in "NESW"})
    k = Kontraktus(3, "NT", "", "S")
    a = _allas(H, [("W", Lap.parse("HQ"))])
    t = next(t for t in tervjeloltek(a, technikak_betoltese(), max_db=400, igeny=3, ures=(12, 12),
                                     max_szim=800) if t.nev == KOMB_TERV)

    def vedo(jj):
        u, ut = jj.soron(), jj.aktualis()
        if u == kenyszer and ut and ut[0][1] == Lap.parse("CJ") and Lap.parse("CQ") in jj.kezek[u]:
            return Lap.parse("CQ")
        return tj._vedo_lap(lap_elemzes(lo, [str(l) for _, l in jj.lapok], k))
    nap: list = []
    return lejatszik(t, lo, "S", None, [("W", Lap.parse("HQ"))], vedo, nap, cel=9), nap


def test_kombinacio_kudarc_ag():
    """Kelet a ♣D-vel üti a ♣B-t: ♣2→♣10, ♠ impassz, a ♣K-t az ♣Á üti felül, ♠ impassz."""
    n, nap = _komb_lejatszas(ALK, "E")
    assert n == 9, nap
    assert any("átmenet CT" in s for s in nap) and any("átmenet CA" in s for s in nap)


def test_kombinacio_fedes_ag():
    """Nyugat fed a ♣D-vel: az Á üt, 3 treffütés — a pikkből elég 4 (FELTETELES)."""
    n, nap = _komb_lejatszas(KOMB_NYUGAT_D, "W")
    assert n == 9, nap
    assert any("a védő fedett" in s for s in nap)


# --- Vesztőre vesztő és visszatartás (BM A-13 szerkezete, saját lapokkal) -------------
# 4♥ Dél, Nyugat gyenge 2♦ után a ♦K-val indul. ♦Á42 / ♦63: a ♦K-t kiengedjük, a második
# kárót az ♦Á üti, a harmadikat kiadjuk — az asztal pikket dob; két adukör után a
# harmadik pikket az asztal lopja.
VV = {"S": _kez("K42.AKQJ9.A42.A8"), "N": _kez("A63.532.63.76543"),
      "W": _kez("QT9.876.KQJT87.2"), "E": _kez("J875.T4.95.KQJT9")}


def test_vesztore_vesztes_peldany():
    from kibic.motor.tervsema import peldanyok
    a = _allas(VV, [("W", Lap.parse("DK"))], adu="H")
    p = [x for x in peldanyok(a, technikak_betoltese()) if x.sema.azon == "VESZTORE_VESZTO"]
    assert [x.szin for x in p] == ["S"]
    korok = [(k.fajta, k.szin, k.dob) for k in p[0].korok]
    assert korok == [("lehiv", "D", None), ("kiad", "D", "S"), ("lehiv", "S", None), ("lehiv", "S", None),
                     ("lop", "S", None)]
    assert p[0].szerepek["L"] == "N" and p[0].hozam == 1
    # a visszatartás a ♦K-ra (a ♦Á nálunk, a sorozat alatti lap nem: nem Bath)
    assert [h.sema.azon for h in hozzatetelek(a, technikak_betoltese())] == ["VISSZATARTAS"]


def test_vesztore_vesztes_lejatszas():
    """A visszatartás után a terv: ♦Á, a ♦ vesztőre ♠ dobás, két adukör, ♠Á, ♠K, ♠ lopás."""
    from kibic.domain import Leosztas
    from kibic.domain.kartya import Kez
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor.tervkonyvelo import lejatszik, tervjeloltek
    from kibic.solver.dds import lap_elemzes
    a = _allas(VV, [("W", Lap.parse("DK"))], adu="H")
    t = [x for x in tervjeloltek(a, technikak_betoltese(), max_db=200, igeny=1, ures=(12, 12), max_szim=500)
         if "VESZTORE" in x.nev]
    assert t
    lo = Leosztas({u: Kez(frozenset(VV[u])) for u in "NESW"})
    k = Kontraktus(4, "H", "", "S")
    nap: list = []
    jk: list = []
    n = lejatszik(t[0], lo, "S", "H", [("W", Lap.parse("DK"))],
                  lambda jj: tj._vedo_lap(lap_elemzes(lo, [str(l) for _, l in jj.lapok], k)), nap, cel=10,
                  jatek_ki=jk, utes_dontes={3: ("S", KICSI, "visszatartás")})
    lapok = jk[0].lapok
    assert lapok[3] == ("S", Lap.parse("D2"))                # a ♦K-t kiengedtük
    dobas = [l for i, (u, l) in enumerate(lapok) if u == "N" and l.szin == "S" and lapok[4 * (i // 4)][1].szin == "D"]
    assert dobas, "az asztal a ♦ vesztőre pikket dobott"
    # két adukör a lopás előtt (LOPAS_ELOTT_ADU), aztán a harmadik pikk a lopásra
    assert sum(1 for q in nap if "adukör a lopás előtt" in q) == 2
    assert any("VESZTORE_VESZTO: lop" in q for q in nap)
    # (a mindent látó Nyugat itt a treffre egy pikket dob, és a harmadik pikket felülopja:
    # 9 ütés — a vonal a pikkben rövid, három adus Nyugat ellen bukik, ahogy a szerkesztő
    # leírta)
    assert n >= 9


def test_licit_kenyszer_szur():
    """LICIT_KENYSZER: a világokban Nyugatnak 6 kárója van (a gyenge 2♦), ha a
    kényszertár ezt mondja; nélküle a minta egyenletes."""
    from kibic.motor.helyzet import Igeret
    j = tj.Jatek({u: set(VV[u]) for u in "NESW"}, "S", "H", [("W", Lap.parse("DK"))], tj.Terv(()))
    kr = _keres(j, 0)
    kr["state"]["contract"] = {"level": 4, "strain": "H", "multiplier": 1}
    ig = Igeret()
    ig.hossz_min["D"], ig.hossz_max["D"] = 6, 6
    ig.pont_min, ig.pont_max = 5.0, 10.0
    regi = tm.LICIT_FV
    try:
        tm.LICIT_FV = lambda keres, F: {"W": ig}
        h = tm.helyzet(kr)
        _, kint = tm._allas(h, h.lejatszott)
        from kibic.domain import Leosztas
        from kibic.domain.kartya import Kez
        lo = Leosztas({u: Kez(frozenset(VV[u])) for u in "NESW"})
        vl = tm._vilagok(lo, h, kint, 20, h.vedok)
        assert len(vl) == 20
        assert sum(1 for w in vl if sum(1 for l in w.kezek["W"].lapok if l.szin == "D") == 6) >= 18
        tm.LICIT_FV = None
        h2 = tm.helyzet(kr)
        vl2 = tm._vilagok(lo, h2, kint, 20, h2.vedok)
        assert sum(1 for w in vl2 if sum(1 for l in w.kezek["W"].lapok if l.szin == "D") == 6) < 18
    finally:
        tm.LICIT_FV = regi


# --- VESZELYES_KEZ, KERULENDO_KEZ, TAKAREKOS (a szerkesztő, 2026-11-24, BM A-11) -----------
# Saját leosztás az A-11 szerkezetével (a színek felcserélve: ♠↔♥, ♦↔♣): 6NT Dél, Nyugat a
# ♥B-vel indul. A ♣ (itt) a káró szerepében: ♣DB2 / ♣K9876, Nyugat ♣ szingli, a ♣Á Keletnél.
# A ♦ (itt) a treff szerepében: ♦ÁKD109 / ♦32 — ha a ♣ csak 2 ütést hoz, 4 ♦ ütés kell, és
# egy ♦ kiadható, de csak Nyugat felé (ő nem tud ♣-t hívni): kis ♦ a ♦10/9-re, 100%.
VESZ = {"S": _kez("A32.32.QJ2.AKQT9"), "N": _kez("KQ4.AKQ.K9876.32"),
        "W": _kez("J98.JT98.3.J8765"), "E": _kez("T765.7654.AT54.4")}


def _vesz_jatek(lepesek):
    VESZ_ = {"S": _kez("A32.32.AKQT9.QJ2"), "N": _kez("KQ4.AKQ.32.K9876"),
             "W": _kez("J98.JT98.J8765.3"), "E": _kez("T765.7654.4.AT54")}
    j = tj.Jatek({u: set(VESZ_[u]) for u in "NESW"}, "S", None, [("W", Lap.parse("HJ"))], tj.Terv(()))
    for x in lepesek.split():
        j.tesz(x[0], Lap.parse(x[1:]))
    return j


def test_elemzo_vedonkenti_keret():
    """♦ÁKD109 / ♦32, kint ♦B87652: 4 ütés. Egyforma 0 keret: 57%; Nyugat (V1) felé 1, Kelet
    (V2) felé 0 vesztés: 100% (kis ♦ a 10-esre); fordítva nem."""
    from kibic.motor import tervszinkezeles as ts
    f = ts.Feladat(ts.rangok("AKQT9"), ts.rangok("32"), ts.rangok("J87654"), 9, 9)
    assert ts.Elemzo(f).megold(4, 0)[0] < 0.6
    assert ts.Elemzo(f).megold(4, (1, 1, 0))[0] == pytest.approx(1.0)
    assert ts.Elemzo(f).megold(4, (1, 0, 1))[0] < 0.8
    ki = ts.Elemzo(f).kimenetek(4, (1, 1, 0))
    assert all(km.vesztes2 == 0 for km in ki.values())


def test_elemzo_ketiranyu_impassz_kerulendo_kez():
    """KJ3 / A102: egyenlő esély — a D elleni impassz iránya a kerülendő kéztől függ: kudarc
    esetén a veszélytelen kéz kerül ütésbe."""
    from kibic.motor import tervszinkezeles as ts
    R = ts.rangok
    for kerul, masik in (("V1", "V2"), ("V2", "V1")):
        e = ts.Elemzo(ts.Feladat(R("KJ3"), R("AT2"), R("Q98765"), 10, 10, kerul=kerul))
        p, _, _ = e.megold(3, 1)
        ki = e.kimenetek(3, 1)
        w = {v: sum(e.tart[i][2] for i, km in ki.items() if getattr(km, "vesztes" + v[1])) / e.W
             for v in ("V1", "V2")}
        assert p == pytest.approx(0.5108, abs=1e-3)
        assert w[kerul] == 0 and w[masik] > 0.4


def test_elemzo_takarekos():
    """♣DB2 / ♣K9876 (asztal), az asztalon a hívás: kicsi az asztalról a B felé, nem a kézbe
    menet (egy átmenet) a ♣B hívásához — az esély ugyanaz."""
    from kibic.motor import tervszinkezeles as ts, tervszinpolitika as tsp
    R = ts.rangok
    f = ts.Feladat(R("QJ2"), R("K9876"), R("AT543"), 12, 12, atm_x=2, atm_y=2, hivas="Y")
    try:
        ts.OLCSO_KUDARC = False             # (az olcsó kudarc itt maga is az asztalt választaná)
        ts.TAKAREKOS = False
        p0, _, l0 = ts.Elemzo(f).megold(3, 1)
        ts.TAKAREKOS = True
        p1, _, l1 = ts.Elemzo(f).megold(3, 1)
    finally:
        ts.TAKAREKOS = True
        ts.OLCSO_KUDARC = True
        tsp.urites()
    assert p0 == pytest.approx(p1)
    assert l0.startswith("felvevő") and l1.startswith("asztal")


def test_vedo_hivas_atimpasszolas():
    """♥Kx a hívó bal kezén, az ÁDB10 kint: a hívás átmegy a K-n (legfeljebb 3 védőütés); a
    jobb kezén csak az Á (1)."""
    from kibic.motor.tervfogas import vedo_hivas
    F = frozenset
    # (amíg a hívó kimutathat a színből, a legkevesebb 0: lehet, hogy nem hívhatja)
    assert vedo_hivas(F({13, 2}), F({3, 4}), F({14, 12, 11, 10}), False, False) == (0, 3)
    assert vedo_hivas(F({3, 4}), F({13, 2}), F({14, 12, 11, 10}), False, False) == (0, 1)
    # ha a partnere kimutatott, az ÁDB10 mind a hívónál: a K mögötte nincs veszélyben (1)
    assert vedo_hivas(F({13, 2}), F({3, 4}), F({14, 12, 11, 10}), False, True) == (1, 1)
    assert vedo_hivas(F({2}), F({13, 9, 8}), F({14, 10, 5}), True, False) == (0, 0)


def test_veszelyes_kez_kimutatasbol():
    """A ♣ (káró-szerep) második körében Nyugat kimutatott, Kelet kiengedte a ♣Á-t: Kelet
    veszélyes (ütésbe kerülve lehívja a ♣Á-t), Nyugat nem — a ♦ keret (1, Ny 1, K 0).
    Ellenpélda: a kimutatás előtt a ♣Á bárhol lehet — nincs biztosan veszélyes kéz."""
    from kibic.motor.tervkonyvelo import KTerv, Vegrehajto
    j = _vesz_jatek("NHQ EH4 SH2 NC6 EC4 SCJ WC3 SCQ WD5 NC7 EC5")
    v = Vegrehajto(KTerv([]), j)
    v.cel = 12
    assert v._veszely("D", 1) == ((1, 1, 0), None)
    j = _vesz_jatek("NHQ EH4 SH2 NC6 EC4 SCJ WC3")
    v = Vegrehajto(KTerv([]), j)
    v.cel = 12
    assert v._veszely("D", 1) == (1, None)


# --- OLCSO_KUDARC (a szerkesztő, 2026-11-24, BM A-11 a valódi lapokkal) ------------------
def test_elemzo_olcso_kudarc_szoktetes():
    """♦D2 / ♦K987 a ♦B ütése után, kint ♦ÁT5: a ♦D lehívása (áldozat) és a kis káró a D
    felé (szöktetés) egyforma eséllyel hoz még 2 ütést; Nyugat káróhiányánál (Kelet ÁT5)
    mindkettő bukik, de a lehívásnál Kelet üti a D-t (kiadás), a szöktetésnél nem — a
    szöktetés a jobb."""
    from kibic.motor import tervszinkezeles as ts, tervszinpolitika as tsp
    R = ts.rangok
    f = ts.Feladat(R("Q2"), R("K987"), R("AT5"), 11, 11)
    try:
        ts.OLCSO_KUDARC = False
        p0, _, l0 = ts.Elemzo(f).megold(2, 1)
        ts.OLCSO_KUDARC = True
        p1, _, l1 = ts.Elemzo(f).megold(2, 1)
    finally:
        ts.OLCSO_KUDARC = True
        tsp.urites()
    assert p0 == pytest.approx(p1)
    assert l0.startswith("felvevő hív: Q") and l1.startswith("asztal hív: 7")


def test_politika_a_valodi_tartas_megmarad():
    """HALOTT_TARTAS mellett a politika a tervezett tartásokon dönt, de a lépés minden még
    lehetséges tartáson történik: ♦DB2 / ♦K9876 ellen Nyugat ♦3 szingli, Kelet ♦ÁT54 (a
    gyökérben bukó tartás). Kelet az Á-val üt a kis káróra — a ♦D és a ♦K még két ütés
    (eddig a kimutatás után egy tartás sem maradt: „a látott lapokkal már nem érhető el”)."""
    from kibic.motor import tervszinkezeles as ts
    from kibic.motor.tervszinpolitika import SzinPolitika
    R = ts.rangok
    p = SzinPolitika(R("QJ2"), R("K9876"), R("AT543"), 12, 12, 3, 1, False, 0, 0, 3, 3, "Y")
    assert p.dontes() == ("Y", 6)
    p.lep((("Y", 6), ("V2", 4), ("X", 11), ("V1", 3)))
    p.frissit(2, 3, "Y")
    assert p.dontes() == ("Y", 7)
    p.lep((("Y", 7), ("V2", 14), ("X", 2), ("V1", None)))
    p.frissit(2, 3, "X")
    assert p.dontes() == ("X", 12)


# --- ADU_LOPO_LAP (a szerkesztő, 2026-11-24, MB 56) -------------------------------------
# Saját leosztás az MB 56 szerkezetével (♠↔♥, ♦↔♣): 6♣ Dél, Nyugat ♥K, ♥Á. ♣ÁDB2 / ♣10987,
# a ♣K Keletnél harmadmagával: két impassz kell az asztalról, egyetlen beütés (♠K). A ♣10 alá
# a ♣2 megy (az asztal hívásban marad) — a ♣2-vel lopva ez elvész.
ADU56 = {"S": _kez("A2.2.AKQJT9.AQJ2"), "N": _kez("K543.6543.2.T987"),
         "W": _kez("6.AKJT9.87654.43"), "E": _kez("QJT987.Q87.3.K65")}


def test_lopo_adu_az_adukezelestol(monkeypatch, tmp_path):
    monkeypatch.setattr(tm, "TAR", tmp_path)
    monkeypatch.setattr(tm, "VILAG", 20)
    j = tj.Jatek({u: set(ADU56[u]) for u in "NESW"}, "S", "C", [("W", Lap.parse("HK"))], tj.Terv(()))

    def keres(n):
        k = _keres(j, n)
        k["state"]["contract"] = {"level": 6, "strain": "C", "multiplier": 1}
        return k
    tm.plan_valasz(keres(0))
    n = 1
    for x in "N- E7 S- WA N- E8".split():
        u = x[0]
        if x[1] == "-":
            v = tm.step_valasz(keres(n), None, None)
            j.tesz(u, Lap.parse(v["action"]["card"]))
        else:
            j.tesz(u, Lap.parse("H" + x[1]))
        n += 1
    v = tm.step_valasz(keres(n), None, None)
    assert v["action"]["card"] in ("CJ", "CQ"), v["summary"]


# --- DEBLOKK_DOBAS, LEHIVAS_SORREND (a szerkesztő, 2026-11-24) ---------------------------
# Saját leosztás a 3NT-parti szerkezetével (♠↔♥, ♦↔♣ cserével): Dél ♠32 ♥Á32 ♦D65432 ♣32,
# Észak ♠KD10 ♥54 ♦ÁK87 ♣ÁK87. Nyugat ♥-sel indul. Az asztal ♦8 / ♦7 BLOKKOLÓ lap: 3–0-nál a
# kéz két kis kárója beragad. A ♥Á-t kétszer kiengedjük; a harmadik kőrre (az asztal
# kőrhiánya után) a blokkoló kárót dobjuk, és a káró lehúz.
BLK = {"S": _kez("32.A32.Q65432.32"), "N": _kez("KQT.54.AK87.AK87"),
       "W": _kez("J7.KQJ96.JT9.QJ6"), "E": _kez("A98654.T87..T954")}


def test_blokkolo_lap():
    from kibic.motor.tervfogas import blokkolo_lap
    from kibic.motor import tervszinkezeles as ts
    R = ts.rangok
    assert blokkolo_lap(R("Q65432"), R("AK87"), R("JT9"), 10, 10, "Y") in (7, 8)
    # ha a 4. lap a 2-es: nem blokkol, csak a sorrend számít (a 3. kört a D üti át)
    assert blokkolo_lap(R("Q65432"), R("AK82"), R("JT97"), 10, 10, "Y") is None


def test_lehivas_sorrend_atutes():
    """♦ÁK87 / ♦D65432, 2–1 után: az asztal 8-asa üt, a 7-esre a D-t tesszük (vagy a 7 alá
    kicsit, és a 8-at ütjük át) — a hosszú kéz lapjai nem ragadnak be."""
    from kibic.motor.tervfogas import lehivas_lap
    from kibic.motor import tervszinkezeles as ts
    R = ts.rangok
    c, p, ert = lehivas_lap(R("Q654"), R("87"), frozenset(), 5, 5, "Y", (), 4)
    assert p == 1.0
    # az asztal a 7-est hívta (a 8-as még ott van): a D most rossz (a 8 ütne a kéz kis lapja
    # fölött, és a kéz utolsó lapja beragad), kicsi a 7 alá, és a 8-at üti át a D
    c, p, ert = lehivas_lap(R("Q65"), R("8"), frozenset(), 5, 5, "Y", (7, None), 3)
    assert c in (5, 6) and p == 1.0 and ert[12] == 0.0


def test_deblokk_dobas_a_fogasra():
    """Két kiengedett kőr után Nyugat a harmadikat hívja: az asztal (kőrhiány) a blokkoló
    kárót dobja; utána a kéz a ♥Á-val üt, és a káró megszakítás nélkül lehúz."""
    from kibic.motor.tervkonyvelo import KTerv, Vegrehajto
    j = tj.Jatek({u: set(BLK[u]) for u in "NESW"}, "S", None, [("W", Lap.parse("H6"))], tj.Terv(()))
    for x in "N4 E7 S2 E8 S3 W9 N5".split():
        j.tesz(x[0], Lap.parse("H" + x[1]))
    j.tesz("W", Lap.parse("HK"))
    v = Vegrehajto(KTerv([]), j)
    v.cel = 9
    l = v.lap("N")
    assert l in (Lap.parse("D7"), Lap.parse("D8")), v.naplo[-1:] if hasattr(v, "naplo") else l


def test_felmeres_feltetel_es_tempovesztok():
    """A helyzetfelmérés: a ♦ 6 biztos ütésének feltétele a deblokk; a biztos kiadás csak a
    ♠Á (a kint lévő lap a legnagyobb lapunk fölött), a többi tempóvesztő."""
    from kibic.motor.tervfelmeres import felmeres
    S, N = BLK["S"], BLK["N"]
    kint = {Lap.parse(s + r) for s in "SHDC" for r in "23456789TJQKA"} - S - N
    f = felmeres({"S": S, "N": N}, "S", "N", kint, (13, 13), None, 9, 13)
    d = next(s for s in f.szinek if s.szin == "D")
    assert d.biztos == 6 and "deblokk" in d.feltetel
    assert f.kiado_biztos == 1 and f.egyenleg_biztos == 3 and f.tempo == 4


# --- KIENGEDES (a szerkesztő, 2026-11-24, a 3NT-parti valódi lapjaival, színcserével) ----
# Nyugat ♥D-vel indul (figura). Két kiengedés után a harmadik kőrre az asztal a blokkoló
# kárót dobja; a káró Kelet ♦B109-e ellenére lehúz: 9 ütés. (Eddig: ♥Á az 1. ütésben, a
# káró beragadt, bukás.)
KI_W = _kez("A987.QJT98..9654")
KI_E = _kez("J654.K76.JT9.QJT")


def test_kiengedes_es_deblokk_dobas():
    from kibic.domain import Leosztas
    from kibic.domain.kartya import Kez
    from kibic.domain.pontozas import Kontraktus
    from kibic.motor.tervkonyvelo import KTerv, lejatszik
    from kibic.solver.dds import lap_elemzes
    H = {"S": BLK["S"], "N": BLK["N"], "W": KI_W, "E": KI_E}
    assert len(set().union(*H.values())) == 52
    lo = Leosztas({u: Kez(frozenset(H[u])) for u in "NESW"})
    k = Kontraktus(3, "NT", "", "S")
    nap: list = []
    n = lejatszik(KTerv([]), lo, "S", None, [("W", Lap.parse("HQ"))],
                  lambda jj: tj._vedo_lap(lap_elemzes(lo, [str(l) for _, l in jj.lapok], k)), nap, cel=9)
    assert n >= 9, "\n".join(nap)
    assert sum("kiengedés" in s for s in nap) >= 2, "\n".join(nap)
