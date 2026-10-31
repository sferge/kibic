"""
Életjel és sürgetés — POST /v1/bridge/urge (MB 1.1.76), 2026-10-31.

A kérés egy valódi MB-kijátszáskérés (2026-10-25, 14. parti, 4♥ Kelettől,
a 3. ütés indítása) — ennél akadt meg a négykibices futás.
"""
from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

import pytest

from kibic.szolgaltatas import surgetes as surg
from kibic.szolgaltatas.atjaro import play_dontes

KERES = json.loads((Path(__file__).parent / "adat" / "urge_play_keres.json").read_text("utf-8"))


def _keres(rid="m:1362:0:1:play:8"):
    k = copy.deepcopy(KERES)
    k["request_id"] = rid
    return k


def _urge(eredeti, parancs="status", rid="u1"):
    return {"protocol": "mohabridzs-ai/1.1", "request_id": rid,
            "original_request_id": eredeti, "command": parancs, "deadline_ms": 3000}


@pytest.fixture
def lassu_dd(monkeypatch):
    """A valódi DDS, mintánként +40 ms-mal (hogy legyen mit sürgetni)."""
    pytest.importorskip("endplay")
    from kibic.solver import dds
    eredeti = dds.lap_elemzes

    def lassu(*a, **kw):
        time.sleep(0.04)
        return eredeti(*a, **kw)
    monkeypatch.setattr(dds, "lap_elemzes", lassu)
    monkeypatch.setattr(dds, "parhuzamos", lambda: False)
    from kibic.szolgaltatas import atjaro
    monkeypatch.setattr(atjaro, "LEJATSZAS_MS", 20000)
    monkeypatch.setattr(atjaro, "GONDOLKODAS_MS", "0")


# --- a nyilvántartás és a válasz ------------------------------------------

def test_ismeretlen_kerés_unknown():
    tar = surg.Feladattar()
    v = surg.valasz(_urge("nincs-ilyen"), None, None, tar)
    assert v["status"] == "unknown"
    assert v["request_id"] == "u1" and v["original_request_id"] == "nincs-ilyen"


@pytest.mark.parametrize("keres", [
    {"original_request_id": "x"},
    {"request_id": "u"},
    {"request_id": "u", "original_request_id": "x", "command": "fallback"},
])
def test_hibas_eletjelkeres(keres):
    with pytest.raises(surg.UrgeHiba):
        surg.ellenoriz(keres)


def test_a_tarolt_kesz_valasz_ready():
    """Ha a döntés már nincs a nyilvántartásban, de az idempotencia-tárban
    megvan (pl. 2026-10-25: az MB perceken át ugyanazt kérte), ready megy."""
    kesz = {"request_id": "m:1", "action": {"type": "play", "card": "S2"}, "meta": {}}
    v = surg.valasz(_urge("m:1"), None, kesz, surg.Feladattar())
    assert v["status"] == "ready"
    assert v["response"] == kesz
    assert v["original_request_id"] == "m:1"


def test_working_szoveg_rovid_es_lapot_nem_arul_el():
    tar = surg.Feladattar()
    f, uj = tar.indul(_keres("m:2"), "play")
    assert uj
    f.keret(10.0, 3000)
    from types import SimpleNamespace as N
    for _ in range(10):
        f.dd_eredmeny([N(lap="SA", legjobb=True), N(lap="S2", legjobb=False)])
    v = surg.valasz(_urge("m:2"), f, None, tar)
    assert v["status"] == "working"
    assert len(v["message"]) <= 300
    assert "SA" not in v["message"] and "♠" not in v["message"]
    assert v["progress"]["samples"] == 10
    assert v["progress"]["leader_confidence"] == 1.0
    assert 5000 <= v["retry_after_ms"] <= 60000


def test_ugyanaz_a_futo_kerés_nem_indul_ketszer():
    tar = surg.Feladattar()
    f1, uj1 = tar.indul(_keres("m:3"), "play")
    f2, uj2 = tar.indul(_keres("m:3"), "play")
    assert uj1 and not uj2 and f1 is f2
    f1.kesz({"request_id": "m:3"})
    f3, uj3 = tar.indul(_keres("m:3"), "play")
    assert uj3 and f3 is not f1


def test_a_kesz_feladat_lejar():
    tar = surg.Feladattar(megorzes_s=0.0)
    f, _ = tar.indul(_keres("m:4"), "play")
    f.kesz({"request_id": "m:4"})
    time.sleep(0.01)
    tar.indul(_keres("m:5"), "play")             # takarít
    assert tar.keres("m:4") is None


# --- a lejátszás megállítása -----------------------------------------------

def test_megallito_a_mintavetelt_megallitja(lassu_dd):
    from kibic.motor import lejatszas as lj
    from kibic.solver.dds import lap_elemzes
    allas = lj.allas_keresbol(_keres())
    e = lj.jatek_dontes(allas, None, None, lambda *a: lap_elemzes(*a),
                        ido_keret_s=20, db=400, mag=1, megallito=lambda: True)
    assert e.megallt == "SURGETES"
    assert 6 <= e.mintak < 20
    assert e.dontes.lap in allas.legalis


def test_expedite_a_pillanatnyi_legjobb_lapot_adja(lassu_dd):
    tar = surg.FELADATOK
    k = _keres("m:urge:6")
    f, _ = tar.indul(k, "play")
    ki = {}
    t = threading.Thread(target=lambda: ki.setdefault("v", play_dontes(k, feladat=f)))
    t.start()
    # megvárjuk, hogy elkezdjen mintát venni
    hatar = time.time() + 15
    while f.minta < 8 and time.time() < hatar:
        time.sleep(0.02)
    st = surg.valasz(_urge("m:urge:6"), f)
    assert st["status"] == "working"
    assert st["progress"]["phase"] in ("mintavetel", "dds_var")
    assert st["progress"]["samples"] >= 8
    t0 = time.time()
    surg.parancs_vegrehajt(f, "expedite")
    f.kesz_esemeny.wait(5)
    assert time.time() - t0 < 2.0               # az MB 3 mp-ig vár
    v = surg.valasz(_urge("m:urge:6", "expedite"), f)
    assert v["status"] == "ready"
    r = v["response"]
    assert r["request_id"] == "m:urge:6"
    assert r["action"]["card"] in k["legal_actions"]["cards"]
    assert r["meta"]["kibic"]["stopped"] == "SURGETES"
    t.join(5)
    assert ki["v"] == r                          # az eredeti HTTP ugyanazt adja


def test_a_gondolkodasi_ido_sem_kesleltet_sürgetésnél(monkeypatch):
    """Kényszerű lap + gondolkodási idő: a kész lap azonnal kérdezhető, és az
    expedite a várakozást is megszakítja."""
    from kibic.szolgaltatas import atjaro
    monkeypatch.setattr(atjaro, "GONDOLKODAS_MS", "3000-3000")
    k = _keres("m:urge:7")
    k["legal_actions"] = {"cards": ["S2"]}
    f, _ = surg.FELADATOK.indul(k, "play")
    t = threading.Thread(target=play_dontes, args=(k,), kwargs={"feladat": f})
    t0 = time.time()
    t.start()
    f.kesz_esemeny.wait(2)
    assert surg.valasz(_urge("m:urge:7"), f)["status"] == "ready"
    surg.parancs_vegrehajt(f, "expedite")       # már kész: nem változtat
    f.siess.set()                                # (a végpont ugyanígy ébreszti)
    t.join(2)
    assert not t.is_alive() and time.time() - t0 < 2


# --- HTTP ------------------------------------------------------------------

@pytest.fixture
def kliens(monkeypatch):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    from kibic.szolgaltatas import api
    monkeypatch.setattr(api, "ATJARO_TITOK", "")
    return TestClient(api.app)


def test_http_unknown_es_400(kliens):
    r = kliens.post("/v1/bridge/urge", json=_urge("nincs"))
    assert r.status_code == 200 and r.json()["status"] == "unknown"
    r = kliens.post("/v1/bridge/urge", json={"request_id": "u"})
    assert r.status_code == 400


def test_http_kepessegek(kliens):
    k = kliens.get("/v1/bridge/capabilities").json()
    assert k["endpoints"]["urge"] is True
    assert k["services"]["urge"]["path"] == "/v1/bridge/urge"


def test_http_kesz_play_utan_ready(kliens, monkeypatch):
    from kibic.szolgaltatas import atjaro
    monkeypatch.setattr(atjaro, "GONDOLKODAS_MS", "0")
    k = _keres("m:urge:8")
    k["legal_actions"] = {"cards": ["S2"]}
    r = kliens.post("/v1/bridge/play", json=k, headers={"Idempotency-Key": "m:urge:8"})
    assert r.status_code == 200
    v = kliens.post("/v1/bridge/urge", json=_urge("m:urge:8", "expedite")).json()
    assert v["status"] == "ready" and v["response"] == r.json()


def test_urge_az_esemenyhurkon_fut():
    import inspect
    pytest.importorskip("fastapi")
    from kibic.szolgaltatas import api
    assert inspect.iscoroutinefunction(api.bridge_urge)


# --- párhuzamos DDS ----------------------------------------------------------

def test_dds_folyamatkeszlet_ugyanazt_adja(monkeypatch):
    """KIBIC_DDS_FOLYAMATOK: a lapelemzés külön folyamatban — ugyanaz az eredmény."""
    pytest.importorskip("endplay")
    from kibic.motor import lejatszas as lj
    from kibic.solver import dds
    allas = lj.allas_keresbol(_keres())
    m = lj.mintavetel(allas, None, db=4, mag=3)
    jatszott = [str(l) for _, l in allas.lejatszott]
    helyben = [dds.lap_elemzes(lo, jatszott, allas.kontraktus) for lo in m.leosztasok]
    monkeypatch.setattr(dds, "FOLYAMATOK", 2)
    try:
        assert dds.parhuzamos()
        tavol = [dds.lap_elemzes(lo, jatszott, allas.kontraktus) for lo in m.leosztasok]
    finally:
        dds.keszlet_leallit()
    assert tavol == helyben
