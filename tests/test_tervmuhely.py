"""A kibic tervműhelye (/v1/bridge/plan, /v1/bridge/step): egy teljes parti lépésenként."""
import pytest

from kibic.domain import Lap
from kibic.motor import tervjatszo as tj
from kibic.motor.tervkonyvelo import _egyszeru_vedo
from kibic.szolgaltatas import tervmuhely as tm


def _kez(s):
    ki = set()
    for sz, r in zip("SHDC", s.split(".")):
        ki |= {Lap.parse(sz + c) for c in r}
    return ki


KEZEK = {"N": _kez("Q3.K4.AK2.AKJT53"), "S": _kez("J62.AJ52.JT94.Q2"),
         "E": _kez("AK87.Q98.Q53.864"), "W": _kez("T954.T763.876.97")}


def _keres(j: tj.Jatek, n: int) -> dict:
    u = j.soron()
    utes = j.aktualis()
    van = [l for l in j.kezek[u] if utes and l.szin == utes[0][1].szin]
    legalis = sorted(str(l) for l in (van or j.kezek[u]))
    return {"protocol": "mohabridzs-ai/1.0", "request_id": f"r{n}", "decision": "play",
            "deadline_ms": 20000,
            "game": {"match_id": "proba", "table_index": 0, "board_number": 1, "vulnerability": "none"},
            "actor": {"seat": "N", "acting_for_seat": u},
            "state": {"phase": "play", "dealer": "N", "contract": {"level": 5, "strain": "C", "multiplier": 1},
                      "declarer": "N", "dummy": "S",
                      "visible_hands": {x: sorted(str(l) for l in j.kezek[x]) for x in "NS"}},
            "history": {"auction": [], "play": [{"seat": s, "card": str(l)} for s, l in j.lapok]},
            "legal_actions": {"cards": legalis}}


def test_plan_es_step_vegig(monkeypatch, tmp_path):
    """A terv fájlba kerül; a lépések a terv szerint mennek, újratervezés csak
    kimutatásnál (új színhiány)."""
    monkeypatch.setattr(tm, "VILAG", 6)
    monkeypatch.setattr(tm, "TAR", tmp_path)
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "N", "C", [], tj.Terv(()))
    j.tesz("E", Lap.parse("SK"))
    p = tm.plan_valasz(_keres(j, 0))
    assert p["status"] == "planned" and p["action"] is None
    assert "<html" in p["presentation"]["html"] and p["plan"]["name"]
    fajlok = sorted(x.name for x in tmp_path.iterdir())
    assert fajlok == ["proba_0_1_N.html", "proba_0_1_N.json"]
    n = 1
    ujra = 0
    while len(j.lapok) < 52:
        u = j.soron()
        if j.mi(u):
            r = tm.step_valasz(_keres(j, n))
            assert r["status"] == "action_available", r["summary"]
            if r["analysis_result"] != "existing_plan":
                assert r["replan_reason"].startswith("kimutatás"), r["replan_reason"]
                ujra += 1
            lap = Lap.parse(r["action"]["card"])
        else:
            lap = _egyszeru_vedo(j, u)
        j.tesz(u, lap)
        n += 1
    assert j.felvevo_utesek() >= 11


def test_vedokent_nincs_terv():
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "N", "C", [], tj.Terv(()))
    j.tesz("E", Lap.parse("SK"))
    k = _keres(j, 0)
    k["actor"] = {"seat": "E", "acting_for_seat": "E"}
    k["state"]["visible_hands"] = {"E": sorted(str(l) for l in KEZEK["E"])}
    assert tm.plan_valasz(k)["status"] == "unsupported_position"


def test_eltero_lap_utan_ujraterv_es_a_fajl_tortenete(monkeypatch, tmp_path):
    """Ha a mi oldalunkon nem a javasolt lap megy le, a következő lépés újratervez;
    a fájl megőrzi a korábbi tervek okát. A terv a fájlból jön (nincs memória)."""
    import json
    monkeypatch.setattr(tm, "VILAG", 4)
    monkeypatch.setattr(tm, "TAR", tmp_path)
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "N", "C", [], tj.Terv(()))
    j.tesz("E", Lap.parse("SK"))
    r = tm.step_valasz(_keres(j, 1))                     # nincs terv: tervez
    assert r["analysis_result"] == "new_plan" and r["replan_reason"] == "nincs terv ehhez a partihoz"
    javasolt = Lap.parse(r["action"]["card"])
    masik = next(l for l in sorted(j.kezek["S"], key=str) if l.szin == "S" and l != javasolt)
    j.tesz("S", masik)                                   # a tanár mást tesz
    j.tesz("W", _egyszeru_vedo(j, "W"))
    r = tm.step_valasz(_keres(j, 2))
    assert r["analysis_result"] == "new_plan" and r["replan_reason"].startswith("eltérés a tervtől")
    adat = json.loads((tmp_path / "proba_0_1_N.json").read_text(encoding="utf-8"))
    assert [t["ok"].split(":")[0] for t in adat["tortenet"]] == ["nincs terv ehhez a partihoz",
                                                                 "eltérés a tervtől"]
    r2 = tm.step_valasz(_keres(j, 3))                    # ugyanaz az állás: a fájlból folytat
    assert r2["analysis_result"] == "existing_plan" and r2["action"] == r["action"]


def test_nincs_megoldas_tartalek(monkeypatch, tmp_path):
    """Ha egyik terv sem teljesít egyik világban sem, a tartalék (az általános
    lejátszó) ad lapot."""
    monkeypatch.setattr(tm, "VILAG", 4)
    monkeypatch.setattr(tm, "TAR", tmp_path)
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "N", "C", [], tj.Terv(()))
    j.tesz("E", Lap.parse("SK"))
    k = _keres(j, 1)
    k["state"]["contract"]["level"] = 7                  # 7♣: két pikkvesztő, reménytelen
    hivas = []

    def tartalek(keres):
        hivas.append(keres["request_id"])
        return {"action": {"type": "play", "card": keres["legal_actions"]["cards"][0]},
                "explanation": "általános lejátszó"}
    r = tm.step_valasz(k, None, tartalek)
    assert hivas == ["r1"]
    assert r["meta"]["source"] == "fallback" and r["action"]["card"] == k["legal_actions"]["cards"][0]


def test_szaz_szazalekos_terv_terit(monkeypatch, tmp_path):
    """1♣: a terv minden világban teljesít; amikor a mi oldalunk hív, és a biztos
    terítés is megvan, a válasz terítést ajánl (meta.kibic.claim, mint a /play)."""
    monkeypatch.setattr(tm, "VILAG", 4)
    monkeypatch.setattr(tm, "TAR", tmp_path)
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "N", "C", [], tj.Terv(()))
    j.tesz("E", Lap.parse("SK"))
    claim = None
    n = 1
    while len(j.lapok) < 52 and claim is None:
        u = j.soron()
        if j.mi(u):
            k = _keres(j, n)
            k["state"]["contract"]["level"] = 1
            r = tm.step_valasz(k)
            claim = ((r["meta"].get("kibic") or {}).get("claim"))
            lap = Lap.parse(r["action"]["card"])
        else:
            lap = _egyszeru_vedo(j, u)
        j.tesz(u, lap)
        n += 1
    assert claim is not None and claim["total_tricks"] >= 7


def test_elemzos_terv_visszatoltheto(monkeypatch, tmp_path):
    """A terv elemzős színkezelési egységei (k ütés, legfeljebb m vesztés) a fájlból
    újraépülnek: a következő lépés nem tervez újra (a 2026-11-18-i MB-próba hibája:
    minden lapnál „nincs terv ehhez a partihoz”)."""
    monkeypatch.setattr(tm, "VILAG", 4)
    monkeypatch.setattr(tm, "TAR", tmp_path)
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "N", "C", [], tj.Terv(()))
    j.tesz("E", Lap.parse("SK"))
    h = tm.helyzet(_keres(j, 0))
    from kibic.motor.tervkonyvelo import KTerv, szinkezeles_peldany
    from kibic.motor.tervsema import technikak_betoltese
    allas, _ = tm._allas(h, h.lejatszott)
    p = szinkezeles_peldany(allas, technikak_betoltese(), "D", 3, 1, (12, 13))
    assert p is not None
    t = KTerv([p], 1, ("U",), True)
    from kibic.motor.tervkonyvelo import Eredmeny
    r = tm.Rekord("x", 1, t, [Eredmeny(t)], list(h.lejatszott),
                  {u: set(h.kezek[u]) for u in ("N", "S")}, "N", h.kontraktus, 4, 0.1)
    kulcs = tm._kulcs(_keres(j, 0), "N")
    tm.ment(kulcs, r, "próba")
    vissza = tm.betolt(kulcs, h)
    assert vissza is not None and vissza.terv.nev == t.nev
    assert vissza.terv.lepesek[0].szerepek["k"] == 3 and vissza.terv.lepesek[0].szerepek["m"] == 1


def test_step_vedokent_a_play_dontese_megy():
    """Ellenvonalon nincs terv: a /step nem hibát ad, hanem a /play döntését."""
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "N", "C", [], tj.Terv(()))
    j.tesz("E", Lap.parse("SK"))
    j.tesz("S", Lap.parse("S2"))
    k = _keres(j, 0)
    k["actor"] = {"seat": "W", "acting_for_seat": "W"}
    k["state"]["visible_hands"] = {x: sorted(str(l) for l in j.kezek[x]) for x in "WS"}
    v = tm.step_valasz(k, None, lambda kk: {"action": {"type": "play", "card": "S4"},
                                             "explanation": "a /play lapja"})
    assert v["status"] == "action_available"
    assert v["action"]["card"] == "S4"
    assert v["meta"]["source"] == "fallback"
