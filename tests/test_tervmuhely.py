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


def test_plan_es_step_vegig(monkeypatch):
    monkeypatch.setattr(tm, "VILAG", 6)
    tm.TERVEK.clear()
    j = tj.Jatek({u: set(KEZEK[u]) for u in "NESW"}, "N", "C", [], tj.Terv(()))
    j.tesz("E", Lap.parse("SK"))
    p = tm.plan_valasz(_keres(j, 0))
    assert p["status"] == "planned" and p["action"] is None
    assert "<html" in p["presentation"]["html"] and p["plan"]["name"]
    n = 1
    while len(j.lapok) < 52:
        u = j.soron()
        if j.mi(u):
            r = tm.step_valasz(_keres(j, n))
            assert r["status"] == "action_available", r["summary"]
            assert r["analysis_result"] == "existing_plan"
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
