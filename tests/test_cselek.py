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
    assert p["plan"]["name"].startswith("♠ Bath-csel → "), p["plan"]
    assert r1["action"]["card"] in ("S5", "S7")
    assert r2["action"]["card"] == "S4", r2["summary"]
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
    monkeypatch.setitem(tk.SZABALY, "FOGAS_VEDES", False)
    n, naplo = jatszik()
    assert n < 9 and any("átmenet SA" in s for s in naplo)


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
