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
    assert h.teendo == "kicsi" and h.megtart == {Lap.parse("SA"), Lap.parse("SJ")}
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
    k = dict(BATH, S=_kez("A54.KQ5.853.AK83"), W=_kez("KQT86.JT73.92.J"), E=_kez("J932.962.A764.T9"))
    assert not hozzatetelek(_allas(k, [("W", Lap.parse("SK"))]), t)


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
    assert set(rek.utes_megtart) == {"SA", "SJ"}


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
