"""
GATEWAY-PRÓBA — a MohaBridzs nélkül is megmondja, jó-e a szolgáltatás.

A `mohabridzs-ai/1.0` szerződés 14. pontja ad egy átadás előtti
ellenőrzőlistát. Ez a CLI végigméri, pontról pontra, egy FUTÓ kibic
szolgáltatáson. Így nem a webapp-pal kell debugolni: mire a MohaBridzs
először hív, már tudjuk, hogy a szerződés teljesül.

    # a szolgáltatás egy másik ablakban:
    uvicorn kibic.szolgaltatas.api:app --host 0.0.0.0 --port 9050

    # ellenőrzőlista:
    python -m kibic.cli.atjaroproba --cim http://localhost:9050

    # egyetlen kézzel írt helyzet, teljes válasszal:
    python -m kibic.cli.atjaroproba --cim http://localhost:9050 \\
        --kez "SK S7 S4 HA HQ H6 H3 D9 D5 D2 C8 C6 C3" \\
        --menet "1S P" --ules S --oszto N --beli ns

    # ugyanez hálózat nélkül, közvetlen importtal (adatbázis kell):
    python -m kibic.cli.atjaroproba --helyben --menet "1S P" ...

A `--titok` ugyanaz, mint a MohaBridzs `AI_SHARED_SECRET` mezője.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
import urllib.error
import urllib.request

PROTOKOLL = "mohabridzs-ai/1.0"
ULESEK = ("N", "E", "S", "W")
SZINEK = "SHDC"
LAPOK = "AKQJT98765432"


# --- Hívófél ----------------------------------------------------------

class Kliens:
    """Pont azt küldi, amit a MohaBridzs küldene — fejlécestül."""

    def __init__(self, cim: str, titok: str | None = None,
                 idozites_ms: int = 20000):
        self.cim = cim.rstrip("/")
        self.titok = titok
        self.hatarido = idozites_ms

    def hiv(self, utvonal: str, torzs: dict, idem: str | None = None,
            titok: str | None = "=alap") -> tuple[int, dict | str, float]:
        adat = json.dumps(torzs, ensure_ascii=False).encode("utf-8")
        kr = urllib.request.Request(self.cim + utvonal, data=adat,
                                    method="POST")
        kr.add_header("Accept", "application/json")
        kr.add_header("Content-Type", "application/json; charset=utf-8")
        kr.add_header("X-MohaBridzs-Protocol", "1.0")
        kr.add_header("Idempotency-Key", idem or torzs.get("request_id", ""))
        t = self.titok if titok == "=alap" else titok
        if t:
            kr.add_header("Authorization", f"Bearer {t}")
        start = time.time()
        try:
            with urllib.request.urlopen(kr, timeout=60) as v:
                nyers = v.read()
                kod = v.status
        except urllib.error.HTTPError as e:
            nyers, kod = e.read(), e.code
        except urllib.error.URLError as e:
            return 0, f"nem elérhető: {e.reason}", time.time() - start
        ido = time.time() - start
        try:
            return kod, json.loads(nyers.decode("utf-8")), ido
        except (ValueError, UnicodeDecodeError):
            return kod, nyers.decode("utf-8", "replace"), ido


class HelyiKliens(Kliens):
    """Hálózat nélkül, közvetlen importtal — a szállítóréteget kihagyva."""

    def __init__(self, **kw):
        super().__init__("közvetlen", **kw)

    def hiv(self, utvonal, torzs, idem=None, titok="=alap"):
        from ..szolgaltatas.api import _rendszer_betolto
        from ..szolgaltatas.atjaro import AtjaroHiba, bid_dontes, play_dontes
        start = time.time()
        try:
            if utvonal.endswith("/bid"):
                v = bid_dontes(torzs, _rendszer_betolto)
            else:
                v = play_dontes(torzs)
        except AtjaroHiba as e:
            return 400, {"detail": str(e)}, time.time() - start
        return 200, v, time.time() - start


# --- Kérésgyártás -----------------------------------------------------

def veletlen_kez(rng: random.Random) -> list[str]:
    pakli = [s + l for s in SZINEK for l in LAPOK]
    rng.shuffle(pakli)
    return pakli[:13]


def _kovetkezo(u: str) -> str:
    return ULESEK[(ULESEK.index(u) + 1) % 4]


def szabalyos_hivasok(menet: list[dict]) -> list[str]:
    """
    A pillanatnyilag szabályos licitek — nagyjából. A MohaBridzs adja
    élesben; itt csak azért kell, hogy legyen mihez mérni a választ.
    """
    magassag = None
    for e in menet:
        h = e["call"]
        if h not in ("P", "X", "XX"):
            magassag = h
    ki = ["P"]
    rang = {"C": 0, "D": 1, "H": 2, "S": 3, "N": 4}
    kezd = (0, 0) if magassag is None else (
        int(magassag[0]), rang[magassag[1:]])
    # kontra / rekontra
    utolso_felvetel_ules = None
    u = None
    for e in menet:
        if e["call"] not in ("P", "X", "XX"):
            utolso_felvetel_ules = e["seat"]
    if utolso_felvetel_ules:
        ki.append("X")
    for szint in range(1, 8):
        for sz in "CDHSN":
            if (szint, rang[sz]) > kezd:
                ki.append(f"{szint}{sz}")
    return ki


def bid_keres(kez: list[str], menet: list[dict], ules: str, oszto: str,
              beli: str, azonosito: str, hatarido: int = 20000,
              profil: str = "kibic", asztal: int = 0,
              leosztas: int = 1) -> dict:
    return {
        "protocol": PROTOKOLL,
        "request_id": azonosito,
        "decision": "bid",
        "deadline_ms": hatarido,
        "game": {"match_id": "proba-0001", "state_version": len(menet) + 1,
                 "round_number": 1, "board_number": leosztas,
                 "table_index": asztal, "vulnerability": beli},
        "actor": {"player_index": ULESEK.index(ules), "seat": ules,
                  "acting_for_seat": ules, "is_declarer": False,
                  "controls_dummy": False, "profile_code": profil},
        "state": {"phase": "bidding", "dealer": oszto, "current_seat": ules,
                  "contract": None, "declarer": None, "dummy": None,
                  "visible_hands": {ules: kez},
                  "current_trick": [], "completed_tricks": [], "ns_tricks": 0},
        "history": {"auction": menet, "play": []},
        "legal_actions": {"calls": szabalyos_hivasok(menet)},
    }


def menet_ertelmez(szoveg: str, oszto: str) -> list[dict]:
    ki, u = [], oszto
    for darab in (szoveg or "").replace(",", " ").split():
        h = darab.strip().upper()
        if h in ("PASS", "-"):
            h = "P"
        ki.append({"seat": u, "call": h})
        u = _kovetkezo(u)
    return ki


# --- Ellenőrzőlista ---------------------------------------------------

class Lista:
    def __init__(self):
        self.tetelek: list[tuple[str, bool | None, str]] = []

    def be(self, nev: str, rendben: bool | None, megjegyzes: str = ""):
        self.tetelek.append((nev, rendben, megjegyzes))
        jel = {True: "  OK  ", False: " HIBA ", None: " kihagy"}[rendben]
        print(f"[{jel}] {nev}" + (f"  — {megjegyzes}" if megjegyzes else ""))

    @property
    def hibas(self) -> int:
        return sum(1 for _, r, _ in self.tetelek if r is False)


def ellenorzolista(k: Kliens, rng: random.Random, titok: str | None) -> Lista:
    L = Lista()
    kez = veletlen_kez(rng)
    menet = menet_ertelmez("1S P", "N")
    keres = bid_keres(kez, menet, "S", "N", "ns", "proba:1:0:1:bid:2")

    # 1. Mindkét végpont elérhető
    kod, v, ido = k.hiv("/v1/bridge/bid", keres)
    L.be("1a. POST /v1/bridge/bid elérhető", kod == 200, f"HTTP {kod}")
    if kod != 200:
        print(f"      válasz: {v}")
        return L
    lapok = {"cards": [x for x in kez[:1]]}
    play = {"protocol": PROTOKOLL, "request_id": "proba:1:0:1:play:1",
            "decision": "play", "deadline_ms": 20000,
            "game": keres["game"], "actor": keres["actor"],
            "state": dict(keres["state"], phase="play"),
            "history": {"auction": menet, "play": []},
            "legal_actions": lapok}
    kod2, v2, _ = k.hiv("/v1/bridge/play", play)
    L.be("1b. POST /v1/bridge/play elérhető", kod2 == 200, f"HTTP {kod2}")

    # 2. Hibás titokkal nincs döntés
    if titok:
        kod3, _, _ = k.hiv("/v1/bridge/bid", keres, titok="rossz-titok")
        L.be("2. hibás titokkal nem dönt", kod3 in (401, 403), f"HTTP {kod3}")
    else:
        L.be("2. hibás titokkal nem dönt", None,
             "nincs beállítva titok (--titok)")

    # 3. request_id változatlanul
    L.be("3. a request_id változatlanul visszamegy",
         v.get("request_id") == keres["request_id"], str(v.get("request_id")))

    # 4. Csak a legal_actions-ből választ
    akcio = v.get("action") or {}
    L.be("4a. action.type = bid", akcio.get("type") == "bid",
         str(akcio.get("type")))
    L.be("4b. a licit a calls tömbből való",
         akcio.get("call") in keres["legal_actions"]["calls"],
         str(akcio.get("call")))
    a2 = (v2 or {}).get("action") or {}
    L.be("4c. a lap a cards tömbből való",
         a2.get("card") in lapok["cards"], str(a2.get("card")))

    # 5. Idempotencia
    kod4, v4, _ = k.hiv("/v1/bridge/bid", keres)
    L.be("5a. ugyanaz a kulcs ugyanazt adja",
         v4.get("action") == v.get("action"), str(v4.get("action")))
    mas = dict(keres, deadline_ms=5000)
    kod5, _, _ = k.hiv("/v1/bridge/bid", mas, idem=keres["request_id"])
    L.be("5b. ugyanaz a kulcs más törzzsel ütközés", kod5 == 409,
         f"HTTP {kod5} (409 az ajánlott)")

    # 6. Külön ülés, külön állapot
    kez_e = veletlen_kez(rng)
    keres_e = bid_keres(kez_e, menet, "E", "N", "ns", "proba:1:0:1:bid:3")
    kod6, v6, _ = k.hiv("/v1/bridge/bid", keres_e)
    kulon = (kod6 == 200
             and (v6.get("meta") or {}).get("kibic") is not None or kod6 == 200)
    L.be("6. külön ülés külön döntést kap", kod6 == 200 and
         v6.get("request_id") == keres_e["request_id"], f"HTTP {kod6}")

    # 7. Ismeretlen jövőbeli mező
    jovo = dict(keres, request_id="proba:1:0:1:bid:4",
                jovobeli_mezo={"x": 1}, protocol_extension="2.0")
    jovo["actor"] = dict(keres["actor"], uj_mezo=True)
    kod7, _, _ = k.hiv("/v1/bridge/bid", jovo)
    L.be("7. ismeretlen mező nem okoz 4xx/5xx", kod7 == 200, f"HTTP {kod7}")

    # 8. Egy, kettő vagy három látható kéz
    harom = dict(keres, request_id="proba:1:0:1:play:5", decision="play")
    harom["state"] = dict(keres["state"], phase="play", visible_hands={
        "S": kez[:8], "N": veletlen_kez(rng)[:8], "E": veletlen_kez(rng)[:8]})
    harom["legal_actions"] = {"cards": kez[:2]}
    kod8, v8, _ = k.hiv("/v1/bridge/play", harom)
    L.be("8. három látható kezet is elfogad", kod8 == 200, f"HTTP {kod8}")

    # 9. Határidő és méret
    meret = len(json.dumps(v, ensure_ascii=False).encode("utf-8"))
    L.be("9a. a válasz a deadline_ms alatt érkezett",
         ido * 1000 < keres["deadline_ms"],
         f"{int(ido * 1000)} ms / {keres['deadline_ms']} ms")
    L.be("9b. a válasz 64 KiB alatt", meret < 64 * 1024, f"{meret} bájt")

    # 10. Jelölések
    hivas = str(akcio.get("call") or "")
    L.be("10a. a licit nagybetűs", hivas == hivas.upper(), hivas)
    L.be("10b. nincs 'NT' és nincs 'PASS' a dróton",
         "NT" not in hivas and hivas != "PASS", hivas)

    # 11. Diagnosztika: nincs benne kéz
    szoveg = json.dumps(v, ensure_ascii=False)
    szivargas = [l for l in kez if f'"{l}"' in szoveg]
    L.be("11. a válasz nem szivárogtat kéztartalmat", not szivargas,
         ", ".join(szivargas))

    # Ráadás: mennyi jött valódi szabályból?
    meta = v.get("meta") or {}
    L.be("+ a döntés forrása", None,
         f"{meta.get('source')} / {(meta.get('kibic') or {}).get('rule_source')}"
         f" — {v.get('explanation')}")
    return L


# --- Egyetlen helyzet -------------------------------------------------

def egy_helyzet(k: Kliens, args) -> int:
    kez = args.kez.replace(",", " ").split() if args.kez else veletlen_kez(
        random.Random(args.mag))
    if len(kez) != 13:
        print(f"13 lap kell, {len(kez)} érkezett", file=sys.stderr)
        return 2
    menet = menet_ertelmez(args.menet, args.oszto)
    keres = bid_keres(kez, menet, args.ules, args.oszto, args.beli,
                      args.azonosito, hatarido=args.hatarido,
                      profil=args.profil)
    print("--- KÉRÉS " + "-" * 60)
    print(json.dumps(keres, ensure_ascii=False, indent=2))
    kod, v, ido = k.hiv("/v1/bridge/bid", keres)
    print(f"--- VÁLASZ (HTTP {kod}, {int(ido * 1000)} ms) " + "-" * 40)
    print(json.dumps(v, ensure_ascii=False, indent=2))
    if kod == 200 and isinstance(v, dict):
        akcio = (v.get("action") or {}).get("call")
        if akcio not in keres["legal_actions"]["calls"]:
            print("\nFIGYELEM: a válasz nem a legal_actions eleme!",
                  file=sys.stderr)
            return 1
    return 0 if kod == 200 else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="A kibic gateway-adapterének próbája a MohaBridzs nélkül")
    p.add_argument("--cim", default="http://localhost:9050",
                   help="a szolgáltatás alapcíme")
    p.add_argument("--helyben", action="store_true",
                   help="hálózat nélkül, közvetlen importtal")
    p.add_argument("--titok", default=None,
                   help="a közös titok (KIBIC_SHARED_SECRET)")
    p.add_argument("--kez", default=None, help='pl. "SK S7 S4 HA ..."')
    p.add_argument("--menet", default="1S P", help='pl. "1S P 2H X"')
    p.add_argument("--ules", default="S", choices=list(ULESEK))
    p.add_argument("--oszto", default="N", choices=list(ULESEK))
    p.add_argument("--beli", default="none",
                   choices=["none", "ns", "ew", "both"])
    p.add_argument("--profil", default="kibic")
    p.add_argument("--hatarido", type=int, default=20000)
    p.add_argument("--azonosito", default="proba:1:0:1:bid:9")
    p.add_argument("--mag", type=int, default=None, help="véletlenmag")
    p.add_argument("--lista", action="store_true",
                   help="az átadás előtti ellenőrzőlista futtatása")
    args = p.parse_args(argv)

    k = (HelyiKliens(titok=args.titok) if args.helyben
         else Kliens(args.cim, args.titok))

    if args.lista or (args.kez is None and args.menet == "1S P"):
        print(f"Ellenőrzőlista — {args.cim if not args.helyben else 'helyben'}"
              f"  ({PROTOKOLL})\n")
        L = ellenorzolista(k, random.Random(args.mag), args.titok)
        print(f"\n{len(L.tetelek)} tétel, {L.hibas} hibás.")
        return 1 if L.hibas else 0
    return egy_helyzet(k, args)


if __name__ == "__main__":
    raise SystemExit(main())
