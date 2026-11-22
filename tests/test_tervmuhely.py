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


def test_bedobas_kimutatas_utan_is_folytatodik(monkeypatch, tmp_path):
    """A szerkesztő (2026-11-21, BM A-6 #1 az MB-asztalon; saját leosztás): a kőr
    eliminálása közben Kelet nem ad kőrt. A bedobás biztos egység (nem függ az
    elosztástól), a kiaduzás után a kimutatás nem ok újratervezésre — a terv a ♣A után
    a ♣D kiadásával folytatódik, nem a ♣ impasszal."""
    monkeypatch.setattr(tm, "VILAG", 12)
    monkeypatch.setattr(tm, "TAR", tmp_path)
    K = {"S": _kez("AKQJ9.K43.KJT.32"), "N": _kez("87654.AQ2.A98.AQ"),
         "W": _kez("3.JT987.Q32.7654"), "E": _kez("T2.65.7654.KJT98")}

    def keres(j, n):
        r = _keres(j, n)
        r["actor"]["seat"] = "S"
        r["state"].update({"contract": {"level": 6, "strain": "S", "multiplier": 1},
                           "declarer": "S", "dummy": "N"})
        return r
    j = tj.Jatek({u: set(K[u]) for u in "NESW"}, "S", "S", [], tj.Terv(()))
    j.tesz("W", Lap.parse("HJ"))
    p = tm.plan_valasz(keres(j, 0))
    assert "bedobás" in p["plan"]["name"], p["plan"]["name"]
    n = 1
    lepesek = []
    while len(j.lapok) < 52:
        u = j.soron()
        if j.mi(u):
            r = tm.step_valasz(keres(j, n))
            lepesek.append(r["summary"])
            lap = Lap.parse(r["action"]["card"])
        else:
            lap = _egyszeru_vedo(j, u)
        j.tesz(u, lap)
        n += 1
    assert any("kiengedés (♣Q)" in s for s in lepesek), "\n".join(lepesek)
    assert j.felvevo_utesek() >= 12, "\n".join(lepesek)


def test_terv_borult_kuszob():
    """TERV_MEGTARTAS: csak az érezhető csökkenés borítja a tervet."""
    assert not tm.terv_borult(1.0, 1.0, 60)
    assert not tm.terv_borult(1.0, 0.95, 60)
    assert tm.terv_borult(1.0, 0.85, 60)
    assert not tm.terv_borult(0.5, 0.42, 60)          # a mintavétel szórásán belül
    assert tm.terv_borult(0.5, 0.3, 60)
    assert tm.terv_borult(0.05, 0.0, 60)              # nullára esett
    assert not tm.terv_borult(0.0, 0.0, 60)


def test_kimutatas_a_kritikus_szinben_ujraterv(monkeypatch, tmp_path):
    """TERV_MEGTARTAS (saját leosztás, a BM A-2 #5 szerkezete): a terv a ♠K-t Keletnél
    impasszolja. Ha az első pikkre Kelet nem ad pikket, a terv esélye nullára esik —
    ez már borult terv, újratervezés jön, az oka az esély csökkenése."""
    import json
    monkeypatch.setattr(tm, "VILAG", 12)
    monkeypatch.setattr(tm, "TAR", tmp_path)
    K = {"S": _kez("AQJ.QJ9876.5.A32"), "N": _kez("432.432.Q432.KQJ"),
         "W": _kez("KT98765.KT5.KJ.T"), "E": _kez(".A.AT9876.987654")}

    def keres(j, n):
        r = _keres(j, n)
        r["actor"]["seat"] = "S"
        r["state"].update({"contract": {"level": 4, "strain": "H", "multiplier": 1},
                           "declarer": "S", "dummy": "N"})
        return r
    j = tj.Jatek({u: set(K[u]) for u in "NESW"}, "S", "H", [], tj.Terv(()))
    j.tesz("W", Lap.parse("DJ"))
    tm.plan_valasz(keres(j, 0))
    n = 1
    while len(j.lapok) < 52 and not any(l.szin == "S" for u, l in j.lapok if u == "N"):
        u = j.soron()
        if j.mi(u):
            r = tm.step_valasz(keres(j, n), tartalek_fv=lambda k: {"action": {"type": "play", "card": k["legal_actions"]["cards"][0]}})
            lap = Lap.parse(r["action"]["card"])
        else:
            lap = _egyszeru_vedo(j, u)
        j.tesz(u, lap)
        n += 1
    while j.soron() != "S" or not j.aktualis():
        u = j.soron()
        lap = _egyszeru_vedo(j, u) if not j.mi(u) else min(j.kezek[u], key=lambda l: (l.szin != "S", l.rang))
        j.tesz(u, lap)
    assert any(u == "E" and l.szin != "S" for u, l in j.aktualis()), j.aktualis()
    tm.step_valasz(keres(j, n), tartalek_fv=lambda k: {"action": {"type": "play", "card": k["legal_actions"]["cards"][0]}})
    adat = json.loads(next(tmp_path.glob("*.json")).read_text(encoding="utf-8"))
    assert any("a terv esélye" in t["ok"] for t in adat["tortenet"]), adat["tortenet"]


def test_ellenfel_inditasa_osszhang():
    """ELLENFEL_INDITASA (BM A-12): a ♦10 indulás a megállapodás szerint dublóból vagy
    szingliből jön; B10x-ből a B, háromból kicsi, színfelvétel ellen ász alól nem."""
    from kibic.domain import Leosztas
    from kibic.domain.kartya import Kez
    if tm._ellenfel_jelzesei() is None:
        pytest.skip("nincs jelzésrendszer")
    S, N = "AKQJT9.A2.K32.32", "432.K43.Q94.KQJT"

    def vilag(w, e):
        return Leosztas({u: Kez(frozenset(_kez(x))) for u, x in zip("SNWE", (S, N, w, e))})
    ind = [("W", Lap.parse("DT"))]
    assert tm.inditas_osszhang(vilag("876.T98765.T5.A4", "5.QJ.AJ876.98765"), ind, "S") is True
    assert tm.inditas_osszhang(vilag("876.T9876.JT5.A4", "5.QJ5.A876.98765"), ind, "S") is False
    assert tm.inditas_osszhang(vilag("876.T9876.T85.A4", "5.QJ5.AJ76.98765"), ind, "S") is False
    assert tm.inditas_osszhang(vilag("876.T9876.AT5.A4", "5.QJ5.J876.98765"), ind, "S") is False
