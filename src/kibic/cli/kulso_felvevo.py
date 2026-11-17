"""
Külső felvevő a mérőpadon (2026-11-17): a felvevő (és az asztal) lapjait egy másik,
ugyanarra az MB-felületre írt robot adja HTTP-n (pl. a BridzsRobot `/v1/bridge/play`;
ha a robot titokkal fut: KIBIC_KULSO_TITOK vagy ROBI_SHARED_SECRET),
a védők a mérőpad szerint (DD) játszanak. Így két felvevő ugyanazon a mércén mérhető:

    # a robot fut (külön terminálban):
    python -m bridzsrobot.mb_gateway --host 127.0.0.1 --port 9050

    PYTHONPATH=src python -m kibic.cli.jatekmeres --pbn tanpartik/Pavlicek_felvevo \\
        --teljes --oldal felvevo --kulso-felvevo http://127.0.0.1:9050

A mérőpad kérése (`lejatszas_meres.pozicio_keres`, mohabridzs-ai 1.1, rövid) itt a
teljes 1.0-s kéréssé alakul: befejezett ütések a nyerővel, az aktuális ütés, az NS
ütésszám, a játszma azonosítói. A `match_id` a futás azonosítójával kezdődik, hogy a
robot tárolt tervei két futás között ne keveredjenek. A licitet nem küldjük (a robot
a nyilvános lapokból tervez; a licitkódok formátuma eltérhet).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import os

ULESEK = "NESW"


def titok() -> str | None:
    """A külső robot közös titka (Authorization: Bearer …): KIBIC_KULSO_TITOK, különben
    ROBI_SHARED_SECRET (a BridzsRobot ezt várja, ha a szerver titokkal indult)."""
    return os.environ.get("KIBIC_KULSO_TITOK") or os.environ.get("ROBI_SHARED_SECRET") or None
_PROTOKOLL = "mohabridzs-ai/1.0"


def _kovetkezo(u: str, n: int = 1) -> str:
    return ULESEK[(ULESEK.index(u) + n) % 4]


def _nyertes(utes: list[dict], adu: str | None) -> str:
    """utes: [{"seat", "card"}] négy lap; adu: S/H/D/C vagy None."""
    hivott = utes[0]["card"][0]
    rangok = "23456789TJQKA"

    def kulcs(x):
        sz, r = x["card"][0], x["card"][1]
        return (2 if adu and sz == adu else 1 if sz == hivott else 0, rangok.index(r))
    return max(utes, key=kulcs)["seat"]


def mb10_keres(keres: dict, futas: str, sorszam: int, hatarido_ms: int) -> dict:
    """A mérőpad rövid kéréséből a teljes mohabridzs-ai/1.0 kérés."""
    st = keres["state"]
    k = st["contract"]
    adu = None if k["strain"] in ("N", "NT") else k["strain"]
    jatszott = list(keres["history"]["play"])
    befejezett, ns = [], 0
    for i in range(0, len(jatszott) - len(jatszott) % 4, 4):
        lapok = jatszott[i:i + 4]
        ny = _nyertes(lapok, adu)
        ns += ny in "NS"
        befejezett.append({"cards": lapok, "winner": ny})
    aktualis = jatszott[len(jatszott) - len(jatszott) % 4:]
    g = keres["game"]
    a = keres["actor"]
    return {
        "protocol": _PROTOKOLL,
        "request_id": f"{futas}:{keres['request_id']}:{sorszam}",
        "decision": "play",
        "deadline_ms": hatarido_ms,
        "game": {"match_id": f"{futas}:{g.get('match_id')}", "state_version": len(jatszott),
                 "round_number": 1, "board_number": 1, "table_index": 0,
                 "vulnerability": g.get("vulnerability") or "none",
                 "scoring": g.get("scoring") or "IMP"},
        "actor": {"seat": a["seat"], "acting_for_seat": a["acting_for_seat"], "player_index": 0,
                  "is_declarer": bool(a.get("is_declarer")), "controls_dummy": bool(a.get("controls_dummy"))},
        "state": {"phase": "play", "dealer": st.get("dealer") or "N",
                  "current_seat": st["current_seat"], "ns_tricks": ns,
                  "contract": {"level": k["level"], "strain": "N" if k["strain"] in ("N", "NT") else k["strain"],
                               "multiplier": k.get("multiplier", 1)},
                  "declarer": st["declarer"], "dummy": st["dummy"],
                  "visible_hands": st["visible_hands"],
                  "current_trick": aktualis, "completed_tricks": befejezett},
        "history": {"auction": [], "play": jatszott},
        "legal_actions": {"cards": list(keres["legal_actions"]["cards"])},
    }


def ellenoriz(url: str, ido_s: float = 10.0) -> str:
    """A robot elérhető-e (GET /healthz); a válasz szövege, vagy RuntimeError érthető üzenettel."""
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/healthz", timeout=ido_s) as r:
            return r.read().decode(errors="replace")[:200]
    except (urllib.error.URLError, OSError) as e:
        if "," in url:
            raise RuntimeError(f"Több cím egyben érkezett ({url}): ezt a mérő régi változata nem "
                               f"bontja szét. git pull, majd újra.") from None
        p = urllib.parse.urlsplit(url)
        raise RuntimeError(f"A külső robot nem érhető el itt: {url} ({e}). Fut a szerver ezen a címen "
                           f"(python -m bridzsrobot.mb_gateway --host {p.hostname} --port {p.port})?") from None


class KulsoHiba(RuntimeError):
    """A külső robot sorozatosan nem válaszol: a mérés értelmetlen, leállunk."""


MAX_HIBA_SOROZAT = 5


def kulso_dontes(url: str, hatarido_ms: int = 60000, futas: str | None = None, ido_s: float = 300.0,
                 naplo: str | None = None, vegpont: str = "step"):
    """A mérőpad döntés-függvénye (`fv(keres) -> (lap, meta)`) a külső robottal.
    Hiba (elérhetetlen robot, rossz válasz) esetén a legkisebb szabályos lap, a meta jelzi.
    `naplo`: JSONL-fájl, döntésenként egy sor (a robot forrása: terv / tartalék / hiba).
    `vegpont`: "step" (a BridzsRobot tervműhelye: tárolt terv, megfigyelés, következő lépés —
    automatikus tervezéssel és újratervezéssel) vagy "play" (az MB-végpont; a robot a
    felvevőnél alapból ugyanazt a terv-lépés utat hívja)."""
    futas = futas or uuid.uuid4().hex[:8]
    vegpont = url.rstrip("/") + f"/v1/bridge/{vegpont}"
    szamlalo = {"n": 0, "hiba_sorozat": 0, "siker": 0}

    def jegyez(sor: dict) -> None:
        if naplo:
            with open(naplo, "a", encoding="utf-8") as f:
                f.write(json.dumps(sor, ensure_ascii=False) + "\n")

    def fv(keres: dict):
        legal = keres["legal_actions"]["cards"]
        if len(legal) == 1:
            return legal[0], {"kulso": {"situation": "KENYSZER"}}
        szamlalo["n"] += 1
        kr = mb10_keres(keres, futas, szamlalo["n"], hatarido_ms)
        t0 = time.time()
        try:
            req = urllib.request.Request(vegpont, data=json.dumps(kr).encode(),
                                         headers={"Content-Type": "application/json",
                                                  "X-MohaBridzs-Protocol": "1.0",
                                                  "Idempotency-Key": kr["request_id"],
                                                  **({"Authorization": f"Bearer {t}"} if (t := titok()) else {})})
            with urllib.request.urlopen(req, timeout=ido_s) as r:
                v = json.loads(r.read())
            lap = (v.get("action") or {}).get("card")
            if lap not in legal:
                raise ValueError(f"nincs szabályos lap a válaszban (status={v.get('status')!r}, "
                                 f"reason={v.get('reason')!r}): {lap!r}")
            meta = {k: v.get(k) for k in ("explanation", "meta", "status", "plan_id") if k in v}
            szamlalo["hiba_sorozat"] = 0
            szamlalo["siker"] += 1
            m = v.get("meta") or {}
            jegyez({"keres": keres["request_id"], "lap": lap, "ms": int((time.time() - t0) * 1000),
                    "pipeline": m.get("pipeline"), "source": m.get("source") or v.get("source"),
                    "status": v.get("status"), "plan_id": v.get("plan_id"),
                    "fallback": m.get("fallback_reason"), "magyarazat": (v.get("explanation") or "")[:200]})
            return lap, {"kulso": {"ms": int((time.time() - t0) * 1000), **meta}}
        except (urllib.error.URLError, ValueError, TimeoutError, OSError) as e:
            hiba = getattr(e, "read", None)
            szoveg = hiba().decode(errors="replace")[:300] if hiba else str(e)[:300]
            lap = min(legal, key=lambda c: ("23456789TJQKA".index(c[1]), c[0]))
            jegyez({"keres": keres["request_id"], "lap": lap, "hiba": szoveg})
            # a kapcsolat hibája (nem a robot egyedi „nem tudom” válasza) sorozatban: leállunk,
            # különben a mérés a vészlapot (a legkisebbet) mérné a robot helyett
            # és ha a robot még egyszer sem adott szabályos választ (pl. rossz szerver, rossz
            # kérésformátum), az első öt hiba után is
            szamlalo["hiba_sorozat"] += 1
            kapcsolat = isinstance(e, urllib.error.URLError) and not isinstance(e, urllib.error.HTTPError)
            if szamlalo["hiba_sorozat"] >= MAX_HIBA_SOROZAT and (kapcsolat or not szamlalo["siker"]):
                raise KulsoHiba(f"A külső robot {MAX_HIBA_SOROZAT}-ször egymás után hibát adott "
                                f"({vegpont}): {szoveg}")
            return lap, {"kulso": {"hiba": szoveg}}
    return fv
