"""
Kiosztástervező — `POST /v1/kibic/kiosztas` (mohabridzs-deal-design/1.1).

A MohaBridzs ezen a végponton kér kiosztássort a kibictől: célzott
gyakorláshoz (licithelyzet, lejátszási vagy ellenjátéki feladat), egy
verseny kiosztásaiból (PBN), vagy kész kiosztások ellenőrzésére és
annotálására. A teljes szerződés: doc/mohabridzs-deal-design-1.1.md.

A FELADAT HÁROM RÉTEGE
----------------------
1. FORRÁS (`source`): honnan jönnek a jelölt kiosztások —
   `generate` (véletlen, seeddel újrajátszható), `pbn` (verseny-PBN),
   `deals` (kész kiosztások, pl. az MB tárából).
2. CÉL (`target`): mit kell tudnia a kiosztásnak —
   `hands`   kézfeltételek ülésenként vagy szerepenként (gyors szűrő),
   `auction` a KIBIC licitje a megadott rendszerekkel ezen a menet-
             előtagon megy végig (a rendszer dönt, nem egy kézlista),
   `play`    kontraktus és lejátszási / ellenjátéki feltétel (DD).
3. ÉRTELMEZÉS: a válasz `interpretation` mezője visszaadja, amit a kibic
   a kérésből értett (preset feloldva, ülésekre fordítva) — ez kell a
   szabad szöveges kéréshez is, hogy az ember jóváhagyhassa.

A licit- és a DD-motor befecskendezhető (`betolto`, `dd`), így a
szolgáltatás tesztelhető adatbázis és DDS nélkül is.
"""
from __future__ import annotations

import hashlib
import random
import re
import time
from pathlib import Path
from typing import Callable

PROTOKOLL = "mohabridzs-deal-design/1.1"
ELFOGADOTT_PROTOKOLLOK = ("mohabridzs-deal-design/1.1",)

ULESEK = "NESW"
SZINEK = "SHDC"
RANGOK = "AKQJT98765432"
LAPOK = [sz + r for sz in SZINEK for r in RANGOK]
FIGURAPONT = {"A": 4, "K": 3, "Q": 2, "J": 1}
SZEREPEK = {"dealer": 0, "lho": 1, "partner": 2, "rho": 3}
BELIK = ("none", "ns", "ew", "both")
# a szabványos 16-os ciklus: 1. tábla senki, 2. ÉD, 3. KNy, 4. mind ...
_BELI_CIKLUS = ["none", "ns", "ew", "both", "ns", "ew", "both", "none",
                "ew", "both", "none", "ns", "both", "none", "ns", "ew"]

KORLAT = {"count_max": 64, "count_max_import": 128, "time_budget_ms": 20000,
          "time_budget_ms_max": 120000, "auction_calls_max": 48}
ALAP_RENDSZER = "KIBIC_STAND"

HELYZETEK_UT = (Path(__file__).resolve().parents[3] / "rendszerek" / "kiosztas"
                / "helyzetek.yaml")

# Szabad szöveg -> strukturált `target`. Ha nincs beállítva (pl. a Hermes
# pipeline-on át egy Qwen-modell), a kibic a szöveget nem vállalja.
SZOVEG_FORDITO: Callable[[str, dict], dict] | None = None

TECHNIKAK = {
    # kód: (állapot, magyar név, mit jelent a kibicnek)
    "finesse": ("supported", "impassz",
                "a kontraktus DD szerint teljesül, de egy védőfigura áthelyezésével "
                "(a másik védőhöz) bukik — és a felvevő oldalnak van e figuránál "
                "magasabb lapja ebben a színben (villa)"),
    "expassz": ("supported", "expassz",
                "mint az impassz, de a felvevő oldalnak NINCS a kulcsfiguránál "
                "magasabb lapja: a figura felé kell játszani (pl. Kx a hiányzó ász ellen)"),
    "sure_tricks_short": ("experimental", "kevés biztos ütés",
                          "a kontraktus DD szerint teljesül, de a felső biztos ütések "
                          "száma kevesebb a szükségesnél (valamit ki kell dolgozni)"),
    "dummy_reversal": ("planned", "asztalfordítás", ""),
    "crossruff": ("planned", "keresztlopás", ""),
    "elimination": ("planned", "eliminálás, bedobás", ""),
    "squeeze": ("planned", "beszorítás (squeeze)", ""),
    "trump_coup": ("planned", "adupuccs", ""),
    "hold_up": ("planned", "tartás (hold-up)", ""),
    "safety_play": ("planned", "biztonsági játék", ""),
}
INDULASOK = {
    "single_suit": "csak egy színből induló lap buktat (és van nem buktató indulás)",
    "any_beating": "van buktató indulás (de nem mind az)",
}


class KiosztasHiba(ValueError):
    """Kérés-hiba: `kod` a szerződés hibakódja, `http` a javasolt státusz."""

    def __init__(self, kod: str, uzenet: str, http: int = 400):
        super().__init__(uzenet)
        self.kod, self.http = kod, http


# --- lapok, kezek --------------------------------------------------------

def _lap(x) -> str:
    s = str(x).strip().upper()
    if len(s) == 3 and s[1:] == "10":
        s = s[0] + "T"
    if len(s) == 2 and s[0] not in SZINEK and s[1] in SZINEK:
        s = s[1] + s[0]
    if s not in LAPOK:
        raise KiosztasHiba("invalid_deal", f"érvénytelen lap: {x!r}")
    return s


def _rang(lap: str) -> int:
    return RANGOK.index(lap[1])            # 0 = ász


def _rendez(lapok) -> list[str]:
    return sorted(lapok, key=lambda c: (SZINEK.index(c[0]), _rang(c)))


def kezek_ellenoriz(hands) -> dict[str, list[str]]:
    """{N,E,S,W: 13 lap} — pontosan 52 különböző, szabályos lap."""
    if not isinstance(hands, dict):
        raise KiosztasHiba("invalid_deal", "a `hands` objektum legyen")
    ki, latott = {}, set()
    for u in ULESEK:
        lapok = [_lap(x) for x in (hands.get(u) or [])]
        if len(lapok) != 13:
            raise KiosztasHiba("invalid_deal", f"a(z) {u} kéz {len(lapok)} lapos, nem 13")
        for lap in lapok:
            if lap in latott:
                raise KiosztasHiba("invalid_deal", f"kétszer szereplő lap: {lap}")
            latott.add(lap)
        ki[u] = _rendez(lapok)
    return ki


def pbn_deal(kezek: dict[str, list[str]], elso: str = "N") -> str:
    reszek, i = [], ULESEK.index(elso)
    for k in range(4):
        u = ULESEK[(i + k) % 4]
        reszek.append(".".join("".join(c[1] for c in kezek[u] if c[0] == sz)
                               for sz in SZINEK))
    return f"{elso}:" + " ".join(reszek)


def pbn_kezek(deal: str) -> dict[str, list[str]]:
    deal = deal.strip()
    if len(deal) < 3 or deal[1] != ":" or deal[0].upper() not in ULESEK:
        raise KiosztasHiba("pbn_parse_error", f"hibás Deal-tag: {deal[:30]!r}")
    darabok = deal[2:].split()
    if len(darabok) != 4:
        raise KiosztasHiba("pbn_parse_error", f"hibás Deal-tag (nem 4 kéz): {deal[:30]!r}")
    i = ULESEK.index(deal[0].upper())
    kezek = {}
    for k, d in enumerate(darabok):
        szinek = d.split(".")
        if len(szinek) != 4:
            raise KiosztasHiba("pbn_parse_error", f"hibás kéz a Deal-tagben: {d!r}")
        kezek[ULESEK[(i + k) % 4]] = [sz + r for sz, s in zip(SZINEK, szinek)
                                      for r in s.upper().replace("10", "T")]
    return kezek_ellenoriz(kezek)


class KezInfo:
    """Egy kéz gyors jellemzői (a szűrők ezt használják)."""
    __slots__ = ("lapok", "hossz", "hcp", "alak")

    def __init__(self, lapok):
        self.lapok = set(lapok)
        self.hossz = {sz: 0 for sz in SZINEK}
        self.hcp = 0
        for c in lapok:
            self.hossz[c[0]] += 1
            self.hcp += FIGURAPONT.get(c[1], 0)
        self.alak = "".join(str(x) for x in sorted(self.hossz.values(), reverse=True))


# --- sávok és kézfeltételek ---------------------------------------------

def _sav(v, hely: str, felso: int = 40) -> tuple[int, int]:
    """[lo, hi] | "15-17" | "8+" | "-10" | 5  ->  (lo, hi)"""
    if isinstance(v, (list, tuple)) and len(v) == 2:
        lo = 0 if v[0] is None else int(v[0])
        hi = felso if v[1] is None else int(v[1])
    elif isinstance(v, int):
        lo = hi = v
    elif isinstance(v, str):
        s = v.replace(" ", "")
        m = re.fullmatch(r"(\d+)?-(\d+)?|(\d+)\+|(\d+)", s)
        if not m:
            raise KiosztasHiba("invalid_request", f"{hely}: hibás sáv {v!r}")
        if m.group(3):
            lo, hi = int(m.group(3)), felso
        elif m.group(4):
            lo = hi = int(m.group(4))
        else:
            lo = int(m.group(1) or 0)
            hi = int(m.group(2)) if m.group(2) else felso
    else:
        raise KiosztasHiba("invalid_request", f"{hely}: hibás sáv {v!r}")
    if lo > hi:
        raise KiosztasHiba("invalid_request", f"{hely}: üres sáv {v!r}")
    return lo, hi


ALAKOK = {
    "balanced": {"4333", "4432", "5332"},
    "semi_balanced": {"4333", "4432", "5332", "5422", "6322"},
}


def kezfeltetel(spec: dict, hely: str) -> tuple[Callable[[KezInfo], bool], dict]:
    """
    A protokoll kézfeltétele -> (szűrő, normalizált alak).
        hcp       sáv
        suits     {S: sáv, ...}
        shape     balanced | semi_balanced | unbalanced | ["4432", "5-4-3-1", ...]
                  (kötőjel nélkül: rendezett alak; kötőjellel: pontos S-H-D-C)
        cards     ["SA", ...]   — ezek nála vannak
        no_cards  ["SK", ...]   — ezek nincsenek nála
        any_of    [kézfeltétel, ...] — legalább egy teljesül
    """
    if not isinstance(spec, dict):
        raise KiosztasHiba("invalid_request", f"{hely}: a kézfeltétel objektum legyen")
    ismert = {"hcp", "suits", "shape", "cards", "no_cards", "any_of"}
    rossz = set(spec) - ismert
    if rossz:
        raise KiosztasHiba("invalid_request", f"{hely}: ismeretlen kulcs: {sorted(rossz)}")
    proba: list[Callable[[KezInfo], bool]] = []
    norm: dict = {}
    if "hcp" in spec:
        lo, hi = _sav(spec["hcp"], f"{hely}.hcp", 37)
        norm["hcp"] = [lo, hi]
        proba.append(lambda k, lo=lo, hi=hi: lo <= k.hcp <= hi)
    if "suits" in spec:
        if not isinstance(spec["suits"], dict):
            raise KiosztasHiba("invalid_request", f"{hely}.suits: objektum legyen")
        norm["suits"] = {}
        for sz, v in spec["suits"].items():
            sz = str(sz).upper()
            if sz not in SZINEK:
                raise KiosztasHiba("invalid_request", f"{hely}.suits: ismeretlen szín {sz!r}")
            lo, hi = _sav(v, f"{hely}.suits.{sz}", 13)
            norm["suits"][sz] = [lo, hi]
            proba.append(lambda k, sz=sz, lo=lo, hi=hi: lo <= k.hossz[sz] <= hi)
    if "shape" in spec:
        a = spec["shape"]
        if a in ALAKOK:
            halmaz = ALAKOK[a]
            proba.append(lambda k, h=halmaz: k.alak in h)
        elif a == "unbalanced":
            proba.append(lambda k: k.alak not in ALAKOK["balanced"])
        elif isinstance(a, list) and a:
            rendezett, pontos = set(), set()
            for x in a:
                s = str(x).replace(" ", "")
                if re.fullmatch(r"\d-\d-\d-\d", s) and sum(map(int, s.split("-"))) == 13:
                    pontos.add(tuple(map(int, s.split("-"))))
                elif re.fullmatch(r"\d{4}", s) and sum(map(int, s)) == 13:
                    rendezett.add("".join(sorted(s, reverse=True)))
                else:
                    raise KiosztasHiba("invalid_request", f"{hely}.shape: hibás alak {x!r}")
            proba.append(lambda k, r=rendezett, p=pontos:
                         k.alak in r or tuple(k.hossz[sz] for sz in SZINEK) in p)
        else:
            raise KiosztasHiba("invalid_request", f"{hely}.shape: balanced / semi_balanced / "
                                                  f"unbalanced vagy alaklista")
        norm["shape"] = a
    for kulcs, kell in (("cards", True), ("no_cards", False)):
        if kulcs in spec:
            lapok = [_lap(x) for x in spec[kulcs]]
            norm[kulcs] = lapok
            proba.append(lambda k, l=tuple(lapok), kell=kell:
                         all((c in k.lapok) == kell for c in l))
    if "any_of" in spec:
        agak = [kezfeltetel(x, f"{hely}.any_of[{i}]") for i, x in enumerate(spec["any_of"])]
        if not agak:
            raise KiosztasHiba("invalid_request", f"{hely}.any_of: üres")
        norm["any_of"] = [n for _, n in agak]
        proba.append(lambda k, a=tuple(f for f, _ in agak): any(f(k) for f in a))
    return (lambda k: all(p(k) for p in proba)), norm


# --- tábla, osztó, beliállás, forgatás --------------------------------

def tabla_oszto(n: int) -> str:
    return ULESEK[(n - 1) % 4]


def tabla_beli(n: int) -> str:
    return _BELI_CIKLUS[(n - 1) % 16]


def forgat(kezek: dict, oszto: str, beli: str, lepes: int):
    """Az egész asztal elforgatása `lepes` üléssel az óramutató szerint."""
    if lepes % 4 == 0:
        return kezek, oszto, beli
    uj = {ULESEK[(ULESEK.index(u) + lepes) % 4]: kezek[u] for u in ULESEK}
    o = ULESEK[(ULESEK.index(oszto) + lepes) % 4]
    if lepes % 2 and beli in ("ns", "ew"):
        beli = "ew" if beli == "ns" else "ns"
    return uj, o, beli


def vonal(u: str) -> str:
    return "NS" if u in "NS" else "EW"


# --- licit: előtag-illesztés, szimuláció, kontraktus ---------------------

def _hivas_drot(h: str | None) -> str | None:
    if not h:
        return None
    h = str(h).upper()
    return h[:-2] + "N" if h.endswith("NT") else h


def _token_illik(token: str, hivas: str) -> bool:
    """'1N' | '2D|2H' | '*' (bármi) | 'BID' (szintes licit) | '!P' (nem passz)."""
    for t in str(token).upper().replace("NT", "N").split("|"):
        t = t.strip()
        if t == "*" or t == hivas:
            return True
        if t == "BID" and hivas[0].isdigit():
            return True
        if t == "!P" and hivas != "P":
            return True
    return False


def elotag_illik(menet: list[dict], elotag: list) -> bool:
    """Igaz, ha a (részleges) menet eddig összhangban van az előtaggal."""
    for m, t in zip(menet, elotag):
        tok = "|".join(t) if isinstance(t, list) else t
        if not _token_illik(tok, m["call"]):
            return False
    return True


def kontraktus(menet: list[dict]) -> dict | None:
    """A menet végső kontraktusa: {level, strain, multiplier, declarer} vagy None."""
    utolso = None
    szorzo = 1
    for i, m in enumerate(menet):
        c = m["call"]
        if c[0].isdigit():
            utolso, szorzo = i, 1
        elif c == "X":
            szorzo = 2
        elif c == "XX":
            szorzo = 4
    if utolso is None:
        return None
    c = menet[utolso]["call"]
    szint, szin = int(c[0]), c[1:]
    oldal = vonal(menet[utolso]["seat"])
    felvevo = next(m["seat"] for m in menet
                   if m["call"][1:] == szin and m["call"][0].isdigit()
                   and vonal(m["seat"]) == oldal)
    return {"level": szint, "strain": szin, "multiplier": szorzo, "declarer": felvevo}


def ag(menet: list[dict], tanulo: str) -> str | None:
    """uncontested / competitive / defensive — a tanuló vonala szemszögéből."""
    elso_mi = elso_ok = None
    for i, m in enumerate(menet):
        if m["call"] == "P":
            continue
        if vonal(m["seat"]) == vonal(tanulo):
            elso_mi = i if elso_mi is None else elso_mi
        else:
            elso_ok = i if elso_ok is None else elso_ok
    if elso_mi is None and elso_ok is None:
        return None
    if elso_mi is not None and (elso_ok is None or elso_mi < elso_ok):
        return "uncontested" if elso_ok is None else "competitive"
    return "defensive"


class Licitszimulator:
    """A kibic licitál mind a négy ülésen (vonalanként a saját rendszerével)."""

    def __init__(self, betolto, rendszerek: dict[str, str],
                 csaladok: dict | None = None, teszt: bool | None = None):
        self.betolto, self.rendszerek = betolto, rendszerek
        self.csaladok, self.teszt = csaladok or {}, teszt

    def menet(self, kezek, oszto: str, beli: str, elotag: list | None = None,
              teljes: bool = True) -> tuple[list[dict], bool]:
        """(menet, illik-e az előtagra). Az előtag elbukásakor azonnal megáll."""
        from .licit import licit_elemzes
        menet: list[dict] = []
        u, passz, volt = oszto, 0, False
        while len(menet) < KORLAT["auction_calls_max"]:
            masik = "EW" if vonal(u) == "NS" else "NS"
            v = licit_elemzes({
                "hand": list(kezek[u]), "seat": u, "dealer": oszto,
                "vulnerability": beli,
                "auction": [{"seat": m["seat"], "call": m["call"]} for m in menet],
                "system": self.rendszerek[vonal(u)],
                "opponent_system": self.rendszerek[masik],
                "families": self.csaladok, "inference": False, "simulate": False,
                "test_mode": self.teszt}, self.betolto)
            hivas = _hivas_drot(v.get("call"))
            elem = {"seat": u, "call": hivas or "P"}
            if hivas is None:
                elem["fallback"] = True        # nincs szabály: passz (mint a gateway)
            elif v.get("source") == "HEZAG":
                elem["gap"] = True             # nincs szabály: a hézag-elv döntött
            elif (v.get("alert") or {}).get("text"):
                elem["alert"] = v["alert"]["text"]
            menet.append(elem)
            if elotag and len(menet) <= len(elotag) and not elotag_illik(menet, elotag):
                return menet, False
            if elotag and not teljes and len(menet) >= len(elotag):
                return menet, True
            if elem["call"] == "P":
                passz += 1
            else:
                passz, volt = 0, True
            if (volt and passz == 3) or (not volt and passz == 4):
                break
            u = ULESEK[(ULESEK.index(u) + 1) % 4]
        return menet, (not elotag or (len(menet) >= len(elotag)
                                      and elotag_illik(menet, elotag)))


# --- DD-motor -----------------------------------------------------------

class DdMotor:
    """A DDS-solver burkolata. Tesztben helyettesíthető (ugyanez a felület)."""

    elerheto = True

    def tablak(self, kezek_lista: list[dict]) -> list[dict[str, dict[str, int]]]:
        from ..solver.dds import dd_tablak
        return dd_tablak([self._leosztas(k) for k in kezek_lista])

    def indulasok(self, kezek: dict, k: dict) -> list[tuple[str, int]]:
        """[(induló lap, a felvevő ütései DD szerint)] — a kijátszó minden lapjára."""
        from ..domain import Kontraktus
        from ..solver.dds import lap_elemzes
        szin = "NT" if k["strain"] == "N" else k["strain"]
        kon = Kontraktus(k["level"], szin, {1: "", 2: "X", 4: "XX"}[k["multiplier"]],
                         k["declarer"])
        return [(e.lap, e.felvevo_osszesen)
                for e in lap_elemzes(self._leosztas(kezek), [], kon)]

    @staticmethod
    def _leosztas(kezek):
        from ..domain import Leosztas
        return Leosztas.pbn_bol(pbn_deal(kezek))


def dd_elerheto() -> bool:
    try:
        from ..solver.dds import _betolt
        _betolt()
        return True
    except ImportError:
        return False


def _strain(k: dict) -> str:
    return "NT" if k["strain"] == "N" else k["strain"]


def _csere(kezek, a: str, b: str, lap_a: str, lap_b: str) -> dict:
    uj = {u: list(v) for u, v in kezek.items()}
    uj[a].remove(lap_a), uj[b].remove(lap_b)
    uj[a].append(lap_b), uj[b].append(lap_a)
    return {u: _rendez(v) for u, v in uj.items()}


def kulcsfigurak(kezek, k: dict, dd: DdMotor) -> list[dict]:
    """
    Impassz / expassz csere-teszttel. Ha a kontraktus DD szerint teljesül,
    minden védőfigurát (A K Q J) megpróbálunk a MÁSIK védőhöz tenni (a
    legkisebb lapjával cserélve ugyanabban a színben — a hosszak nem
    változnak). Ahol így bukik, ott a kontraktus a figura helyén múlik.
    """
    f = k["declarer"]
    asztal = ULESEK[(ULESEK.index(f) + 2) % 4]
    vedok = (ULESEK[(ULESEK.index(f) + 1) % 4], ULESEK[(ULESEK.index(f) + 3) % 4])
    kell = k["level"] + 6
    jeloltek: list[tuple[dict, dict]] = []
    for sz in SZINEK:
        for d, masik in (vedok, vedok[::-1]):
            kicsik = sorted((c for c in kezek[masik] if c[0] == sz), key=_rang, reverse=True)
            for h in (c for c in kezek[d] if c[0] == sz and c[1] in "AKQJ"):
                if not kicsik or _rang(kicsik[0]) <= _rang(h):
                    continue                    # nincs nála kisebb lap a másiknál
                sajat = [c for c in kezek[f] + kezek[asztal] if c[0] == sz]
                if not sajat:
                    continue
                tipus = "finesse" if any(_rang(c) < _rang(h) for c in sajat) else "expassz"
                jeloltek.append(({"suit": sz, "card": h, "seat": d, "type": tipus},
                                 _csere(kezek, d, masik, h, kicsik[0])))
    if not jeloltek:
        return []
    tablak = dd.tablak([kezek] + [j[1] for j in jeloltek])
    if tablak[0][f][_strain(k)] < kell:
        return []
    return [j[0] for j, t in zip(jeloltek, tablak[1:]) if t[f][_strain(k)] < kell]


def biztos_utesek(kezek, felvevo: str) -> int:
    """Felső biztos ütések (A, AK, AKQ... a két kéz együtt, a hosszabb kéz hosszáig)."""
    asztal = ULESEK[(ULESEK.index(felvevo) + 2) % 4]
    ossz = 0
    for sz in SZINEK:
        a = [c for c in kezek[felvevo] if c[0] == sz]
        b = [c for c in kezek[asztal] if c[0] == sz]
        rangok = {c[1] for c in a + b}
        felso = 0
        for r in RANGOK:
            if r not in rangok:
                break
            felso += 1
        ossz += min(felso, max(len(a), len(b)))
    return ossz


# --- a helyzetkatalógus -------------------------------------------------

_HELYZETEK: dict | None = None


def helyzetek() -> dict[str, dict]:
    global _HELYZETEK
    if _HELYZETEK is None:
        import yaml
        adat = yaml.safe_load(HELYZETEK_UT.read_text(encoding="utf-8")) or {}
        _HELYZETEK = {h["code"]: h for h in adat.get("presets", [])}
    return _HELYZETEK


def kepessegek() -> dict:
    """GET /v1/kibic/kiosztas/kepessegek — mit vállal a kibic."""
    return {
        "protocol": PROTOKOLL,
        "protocols": list(ELFOGADOTT_PROTOKOLLOK),
        "endpoint": "/v1/kibic/kiosztas",
        "sources": ["generate", "pbn", "deals"],
        "targets": {
            "hands": ["hcp", "suits", "shape", "cards", "no_cards", "any_of"],
            "hands_keys": list(ULESEK) + list(SZEREPEK),
            "auction": ["prefix", "student_role", "branch", "final", "fallback"],
            "auction_tokens": ["1N", "2D|2H", "*", "BID", "!P"],
            "play": {
                "student": ["declarer", "leader"],
                "contract": ["auto", "4S"],
                "result": ["makes", "fails", "exact"],
                "techniques": [{"code": k, "status": v[0], "name_hu": v[1],
                                "definition": v[2] or None, "requires": "dds"}
                               for k, v in TECHNIKAK.items()],
                "lead": [{"code": k, "definition": v, "requires": "dds"}
                         for k, v in INDULASOK.items()],
            },
        },
        "presets": [{"code": h["code"], "name": h.get("name"), "practice": h.get("practice"),
                     "description": h.get("description")} for h in helyzetek().values()],
        "text": {"supported": SZOVEG_FORDITO is not None,
                 "note": "szabad szöveg csak beállított fordítóval (LLM -> target); "
                         "a válasz `interpretation` mezője mindig visszaadja az értelmezést"},
        "dds": dd_elerheto(),
        "limits": dict(KORLAT),
        "default_systems": {"NS": ALAP_RENDSZER, "EW": ALAP_RENDSZER},
    }


# --- a kérés értelmezése ---------------------------------------------------

def _ules(x, hely: str) -> str:
    s = str(x or "").upper()
    if s in ("0", "1", "2", "3"):
        return ULESEK[int(s)]
    if s not in ULESEK:
        raise KiosztasHiba("invalid_request", f"{hely}: N/E/S/W vagy 0..3 legyen")
    return s


def _beli(x, hely: str) -> str:
    s = str(x or "").lower()
    s = {"all": "both", "-": "none", "love": "none"}.get(s, s)
    if s not in BELIK:
        raise KiosztasHiba("invalid_request", f"{hely}: none / ns / ew / both legyen")
    return s


def _egyesit(alap: dict, felul: dict) -> dict:
    """A preset célja + a kérés célja (a kérés felülír, a kezeket kulcsonként)."""
    ki = {k: v for k, v in alap.items()}
    for k, v in (felul or {}).items():
        if isinstance(v, dict) and isinstance(ki.get(k), dict):
            ki[k] = {**ki[k], **v}
        else:
            ki[k] = v
    return ki


def ertelmez(keres: dict) -> dict:
    """A kérés normalizálása + ellenőrzése. Visszaad: a belső terv (dict)."""
    if not isinstance(keres, dict):
        raise KiosztasHiba("invalid_request", "a kérés JSON-objektum legyen")
    prot = keres.get("protocol") or PROTOKOLL
    if prot not in ELFOGADOTT_PROTOKOLLOK:
        raise KiosztasHiba("unsupported_protocol",
                           f"ismeretlen protokoll: {prot!r} (ismert: {list(ELFOGADOTT_PROTOKOLLOK)})")
    forras = keres.get("source") or {"type": "generate"}
    if isinstance(forras, str):
        forras = {"type": forras}
    ft = forras.get("type", "generate")
    if ft not in ("generate", "pbn", "deals"):
        raise KiosztasHiba("invalid_request", f"source.type: generate / pbn / deals, nem {ft!r}")

    target = dict(keres.get("target") or {})
    megjegyzes = []
    szoveg = (keres.get("text") or "").strip()
    if szoveg and not target:
        if SZOVEG_FORDITO is None:
            raise KiosztasHiba("text_unsupported",
                               "szabad szöveges kérést ez a kibic nem vállal (nincs fordító "
                               "beállítva); küldj `target`-et vagy `target.preset`-et",
                               422)
        target = dict(SZOVEG_FORDITO(szoveg, kepessegek()) or {})
        megjegyzes.append("a `target` a szabad szövegből készült — ellenőrizendő")
    elif szoveg:
        megjegyzes.append("a `text` mellett strukturált `target` is jött: az számít")

    preset = None
    if target.get("preset"):
        preset = helyzetek().get(str(target["preset"]).upper())
        if preset is None:
            raise KiosztasHiba("unknown_preset", f"ismeretlen helyzet: {target['preset']!r} "
                                                 f"(ismert: {sorted(helyzetek())})", 422)
        target = _egyesit(preset.get("target") or {},
                          {k: v for k, v in target.items() if k != "preset"})

    ismert_cel = {"hands", "auction", "play"}
    rossz = set(target) - ismert_cel
    if rossz:
        raise KiosztasHiba("invalid_request", f"target: ismeretlen kulcs: {sorted(rossz)}")

    import_ = ft != "generate"
    db_max = KORLAT["count_max_import"] if import_ else KORLAT["count_max"]
    db = keres.get("count")
    db = (db_max if import_ else 8) if db is None else int(db)
    if not 1 <= db <= db_max:
        raise KiosztasHiba("invalid_request", f"count: 1..{db_max}")
    ido = int(keres.get("time_budget_ms") or KORLAT["time_budget_ms"])
    ido = max(500, min(ido, KORLAT["time_budget_ms_max"]))

    tanulo = _ules((keres.get("student") or {}).get("seat") or "S", "student.seat")
    rendszerek = {"NS": ALAP_RENDSZER, "EW": ALAP_RENDSZER}
    for k, v in (keres.get("systems") or {}).items():
        if str(k).upper() not in rendszerek:
            raise KiosztasHiba("invalid_request", "systems: NS / EW kulcsok")
        rendszerek[str(k).upper()] = str(v).upper()

    auction = dict(target.get("auction") or {})
    if auction:
        bad = set(auction) - {"prefix", "student_role", "branch", "final", "fallback"}
        if bad:
            raise KiosztasHiba("invalid_request", f"target.auction: ismeretlen kulcs {sorted(bad)}")
        if auction.get("student_role") and auction["student_role"] not in SZEREPEK:
            raise KiosztasHiba("invalid_request", "target.auction.student_role: "
                                                  "dealer / lho / partner / rho")
        if auction.get("branch") and auction["branch"] not in ("uncontested", "competitive",
                                                               "defensive"):
            raise KiosztasHiba("invalid_request", "target.auction.branch: uncontested / "
                                                  "competitive / defensive")
        if auction.get("fallback") not in (None, "allow", "exclude", "only"):
            raise KiosztasHiba("invalid_request", "target.auction.fallback: allow / exclude / only")
        if "final" in auction:
            fin = auction["final"] or {}
            bad = set(fin) - {"min_level", "contract", "side"}
            if bad:
                raise KiosztasHiba("invalid_request", f"target.auction.final: ismeretlen kulcs {sorted(bad)}")
            if "min_level" in fin:
                fin["min_level"] = int(fin["min_level"])
            if fin.get("side") not in (None, "student", "opponents"):
                raise KiosztasHiba("invalid_request", "target.auction.final.side: student / opponents")
            auction["final"] = fin

    play = dict(target.get("play") or {})
    if play:
        bad = set(play) - {"student", "contract", "declarer", "result", "technique", "lead",
                           "min_level"}
        if bad:
            raise KiosztasHiba("invalid_request", f"target.play: ismeretlen kulcs {sorted(bad)}")
        play.setdefault("contract", "auto")
        play.setdefault("student", "declarer")
        if play["student"] not in ("declarer", "leader"):
            raise KiosztasHiba("invalid_request", "target.play.student: declarer / leader")
        if play["contract"] != "auto":
            m = re.fullmatch(r"([1-7])(NT|N|S|H|D|C)(X{0,2})", str(play["contract"]).upper())
            if not m:
                raise KiosztasHiba("invalid_request", f"target.play.contract: {play['contract']!r}")
            play["_kontraktus"] = {"level": int(m.group(1)),
                                   "strain": "N" if m.group(2) in ("N", "NT") else m.group(2),
                                   "multiplier": {"": 1, "X": 2, "XX": 4}[m.group(3)],
                                   "declarer": _ules(play.get("declarer") or tanulo,
                                                     "target.play.declarer")}
        tech = play.get("technique")
        if tech:
            lista = tech if isinstance(tech, list) else [tech]
            for t in lista:
                if t not in TECHNIKAK:
                    raise KiosztasHiba("unsupported_target", f"ismeretlen technika: {t!r}", 422)
                if TECHNIKAK[t][0] == "planned":
                    raise KiosztasHiba(
                        "unsupported_target",
                        f"a(z) {t!r} ({TECHNIKAK[t][1]}) technikát a kibic még nem tudja "
                        f"felismerni (tervezett); most támogatott: "
                        f"{[k for k, v in TECHNIKAK.items() if v[0] != 'planned']}", 422)
            play["technique"] = lista
        if play.get("lead") and play["lead"] not in INDULASOK:
            raise KiosztasHiba("unsupported_target", f"ismeretlen indulásfeltétel: {play['lead']!r}",
                               422)
        if play.get("result") and play["result"] not in ("makes", "fails", "exact"):
            raise KiosztasHiba("invalid_request", "target.play.result: makes / fails / exact")
        if play["student"] == "leader" and not play.get("lead"):
            play.setdefault("result", "fails")

    hands_spec = target.get("hands") or {}
    if not isinstance(hands_spec, dict):
        raise KiosztasHiba("invalid_request", "target.hands objektum legyen")
    for k in hands_spec:
        if str(k).upper() not in ULESEK and str(k) not in SZEREPEK:
            raise KiosztasHiba("invalid_request",
                               f"target.hands: kulcs N/E/S/W vagy {list(SZEREPEK)}, nem {k!r}")
    for k, v in hands_spec.items():
        kezfeltetel(v, f"target.hands.{k}")             # korai ellenőrzés

    oszto = keres.get("dealer")
    beli = keres.get("vulnerability")
    seed = keres.get("seed")
    if seed is None:
        seed = format(random.SystemRandom().getrandbits(48), "x")
    return {
        "request_id": keres.get("request_id"), "title": keres.get("title")
        or (preset or {}).get("name"),
        "source": forras, "count": db, "time_ms": ido, "seed": str(seed),
        "first_board": int(keres.get("first_board") or 1),
        "dealer": None if oszto in (None, "by_board") else _ules(oszto, "dealer"),
        "vulnerability": None if beli in (None, "by_board") else _beli(beli, "vulnerability"),
        "student": tanulo, "systems": rendszerek, "test_mode": keres.get("test_mode"),
        "preset": (preset or {}).get("code"), "tags": list((preset or {}).get("tags") or []),
        "hands": hands_spec, "auction": auction, "play": play,
        "include": set(keres.get("include") or ["auction"]),
        "dry_run": bool(keres.get("dry_run")), "notes": megjegyzes,
    }


def _ertelmezes_ki(terv: dict) -> dict:
    """A válasz `interpretation` mezője — amit a kibic értett."""
    play = {k: v for k, v in terv["play"].items() if not k.startswith("_")}
    return {k: v for k, v in {
        "preset": terv["preset"], "source": terv["source"].get("type"),
        "count": terv["count"], "seed": terv["seed"], "student_seat": terv["student"],
        "systems": terv["systems"], "dealer": terv["dealer"] or "by_board",
        "vulnerability": terv["vulnerability"] or "by_board",
        "hands": {k: kezfeltetel(v, k)[1] for k, v in terv["hands"].items()} or None,
        "auction": terv["auction"] or None, "play": play or None,
        "notes": terv["notes"] or None,
    }.items() if v is not None}


# --- a kiszolgálás ------------------------------------------------------

def _oszto_beli(terv: dict, tabla: int) -> tuple[str, str]:
    oszto = terv["dealer"] or tabla_oszto(tabla)
    szerep = terv["auction"].get("student_role")
    if szerep:
        # a tanuló ülése a menetben a `szerep` helyén legyen
        oszto = ULESEK[(ULESEK.index(terv["student"]) - SZEREPEK[szerep]) % 4]
    return oszto, terv["vulnerability"] or tabla_beli(tabla)


def _kezszurok(terv: dict, oszto: str) -> dict[str, Callable]:
    ki = {}
    for k, v in terv["hands"].items():
        u = str(k).upper() if str(k).upper() in ULESEK else \
            ULESEK[(ULESEK.index(oszto) + SZEREPEK[k]) % 4]
        f, _ = kezfeltetel(v, f"target.hands.{k}")
        if u in ki:
            elozo = ki[u]
            ki[u] = lambda h, a=elozo, b=f: a(h) and b(h)
        else:
            ki[u] = f
    return ki


def _general(terv: dict, index: int, oszto: str) -> dict[str, list[str]]:
    """A `seed` és az `index` egyértelműen meghatározza a kiosztást."""
    rnd = random.Random(f"{terv['seed']}:{index}")
    pakli = list(LAPOK)
    rnd.shuffle(pakli)
    return {u: _rendez(pakli[13 * i:13 * i + 13]) for i, u in enumerate(ULESEK)}


def pbn_beolvas(szoveg: str) -> list[dict]:
    """PBN -> [{board, dealer, vulnerability, hands, event, played}] (a Deal-tagek alapján)."""
    tetelek, aktualis = [], {}
    for sor in szoveg.splitlines():
        m = re.match(r'\s*\[(\w+)\s+"(.*)"\]', sor)
        if not m:
            continue
        tag, ertek = m.group(1), m.group(2)
        if tag == "Event" and aktualis.get("Deal"):
            tetelek.append(aktualis)
            aktualis = {}
        if tag == "Board" and aktualis.get("Deal"):
            tetelek.append(aktualis)
            aktualis = {k: v for k, v in aktualis.items() if k == "Event"}
        aktualis[tag] = ertek
    if aktualis.get("Deal"):
        tetelek.append(aktualis)
    if not tetelek:
        raise KiosztasHiba("pbn_parse_error", "a PBN-ben nincs egyetlen [Deal] tag sem")
    ki, utolso_event = [], None
    for i, t in enumerate(tetelek, start=1):
        utolso_event = t.get("Event") or utolso_event
        try:
            tabla = int(t.get("Board") or i)
        except ValueError:
            tabla = i
        d = (t.get("Dealer") or "").upper()[:1]
        v = (t.get("Vulnerable") or "").lower()
        v = {"none": "none", "love": "none", "-": "none", "ns": "ns", "ew": "ew",
             "all": "both", "both": "both"}.get(v)
        played = {k.lower(): t[k] for k in ("Contract", "Declarer", "Result") if t.get(k)}
        ki.append({"board": tabla, "dealer": d if d in ULESEK else tabla_oszto(tabla),
                   "vulnerability": v or tabla_beli(tabla), "hands": pbn_kezek(t["Deal"]),
                   "event": utolso_event, "played": played or None})
    return ki


def _jeloltek(terv: dict, elfogadott: list):
    """(kezek, osztó, beli, tábla, forrás-leírás) jelöltek folyama.
    Generálásnál a táblaszám a KÖVETKEZŐ elfogadott kiosztásé (osztó, beli)."""
    ft = terv["source"].get("type", "generate")
    if ft == "generate":
        i = 0
        while True:
            tabla = terv["first_board"] + len(elfogadott)
            oszto, beli = _oszto_beli(terv, tabla)
            yield _general(terv, i, oszto), oszto, beli, None, {
                "type": "generate", "seed": terv["seed"], "index": i}
            i += 1
    elif ft == "pbn":
        szoveg = terv["source"].get("pbn") or ""
        csak = set(terv["source"].get("boards") or [])
        for t in pbn_beolvas(szoveg):
            if csak and t["board"] not in csak:
                continue
            yield t["hands"], t["dealer"], t["vulnerability"], t["board"], {
                "type": "pbn", "event": t["event"], "board": t["board"],
                **({"played": t["played"]} if t["played"] else {})}
    else:
        for i, d in enumerate(terv["source"].get("deals") or []):
            tabla = int(d.get("board") or terv["first_board"] + i)
            oszto = _ules(d["dealer"], f"source.deals[{i}].dealer") if d.get("dealer") \
                else tabla_oszto(tabla)
            beli = _beli(d["vulnerability"], f"source.deals[{i}].vulnerability") \
                if d.get("vulnerability") else tabla_beli(tabla)
            yield kezek_ellenoriz(d.get("hands")), oszto, beli, tabla, {
                "type": "deals", "index": i,
                **({"title": d["title"]} if d.get("title") else {})}


def kiosztas(keres: dict, betolto=None, dd: DdMotor | None = None,
             csaladok: dict | None = None) -> dict:
    """`POST /v1/kibic/kiosztas` — a teljes kérés kiszolgálása."""
    start = time.time()
    terv = ertelmez(keres)
    kell_licit = bool(terv["auction"]) or (terv["play"] and terv["play"]["contract"] == "auto") \
        or "auction" in terv["include"] and betolto is not None
    if (terv["auction"] or (terv["play"] and terv["play"]["contract"] == "auto")) and betolto is None:
        raise KiosztasHiba("auction_unavailable", "a licitcélhoz a rendszerek betöltése kell", 503)
    kell_dd = bool(terv["play"]) or "dd" in terv["include"]
    if kell_dd and dd is None:
        if not dd_elerheto():
            raise KiosztasHiba("dds_unavailable",
                               "a lejátszási célhoz / DD-táblához DDS kell, és nem érhető el", 503)
        dd = DdMotor()
    szim = Licitszimulator(betolto, terv["systems"], csaladok, terv["test_mode"]) \
        if betolto is not None and kell_licit else None
    hatarido = start + terv["time_ms"] / 1000.0
    db_cel = 3 if terv["dry_run"] else terv["count"]

    deals, probalt, kimerult = [], 0, False
    szuro_cache: dict[str, dict] = {}
    for kezek, oszto, beli, tabla, forras in _jeloltek(terv, deals):
        if len(deals) >= db_cel or time.time() > hatarido:
            break
        probalt += 1
        # 1. kézfeltételek (olcsó)
        if oszto not in szuro_cache:
            szuro_cache[oszto] = _kezszurok(terv, oszto)
        if not all(f(KezInfo(kezek[u])) for u, f in szuro_cache[oszto].items()):
            continue
        # 2. licit (a rendszer dönt)
        menet = None
        if szim is not None:
            elotag = terv["auction"].get("prefix")
            menet, jo = szim.menet(kezek, oszto, beli, elotag)
            if not jo:
                continue
            if terv["auction"].get("branch") and ag(menet, terv["student"]) != terv["auction"]["branch"]:
                continue
            tart = any(m.get("fallback") or m.get("gap") for m in menet)
            fb = terv["auction"].get("fallback") or "allow"
            if fb == "exclude" and tart or fb == "only" and not tart:
                continue
        kon = None
        if terv["play"]:
            kon = terv["play"].get("_kontraktus") or (kontraktus(menet) if menet else None)
            if kon is None:
                continue
            if kon["level"] < int(terv["play"].get("min_level") or 1):
                continue
        fin = terv["auction"].get("final") or {}
        if fin and menet is not None:
            kk = kontraktus(menet)
            if kk is None or kk["level"] < fin.get("min_level", 1):
                continue
            if fin.get("contract") and not _token_illik(fin["contract"],
                                                        f"{kk['level']}{kk['strain']}"):
                continue
            if fin.get("side") and (vonal(kk["declarer"]) == vonal(terv["student"])) != \
                    (fin["side"] == "student"):
                continue
        # 3. forgatás: a tanuló üljön a helyén. Csak generált kiosztásnál, azonos
        #    rendszereknél és 2 üléssel (így a beliállás és a licit is ugyanaz marad).
        if terv["play"] and kon and not terv["play"].get("_kontraktus"):
            hely = kon["declarer"] if terv["play"]["student"] == "declarer" else \
                ULESEK[(ULESEK.index(kon["declarer"]) + 1) % 4]
            lepes = (ULESEK.index(terv["student"]) - ULESEK.index(hely)) % 4
            if lepes:
                if (lepes != 2 or forras["type"] != "generate"
                        or terv["systems"]["NS"] != terv["systems"]["EW"]
                        or terv["auction"].get("student_role")
                        or any(str(k).upper() in ULESEK for k in terv["hands"])):
                    continue
                kezek, oszto, beli = forgat(kezek, oszto, beli, lepes)
                menet = [dict(m, seat=ULESEK[(ULESEK.index(m["seat"]) + lepes) % 4])
                         for m in menet] if menet else menet
                kon = dict(kon, declarer=ULESEK[(ULESEK.index(kon["declarer"]) + lepes) % 4])
        # 4. lejátszás / ellenjáték (DD)
        ellenorzes = {}
        if terv["play"]:
            ok, ellenorzes = _lejatszas_ok(kezek, kon, terv["play"], dd)
            if not ok:
                continue
        elem = {"board": tabla or terv["first_board"] + len(deals),
                "hands": kezek, "dealer": oszto, "vulnerability": beli,
                "deal_id": hashlib.sha1(pbn_deal(kezek).encode()).hexdigest()[:16],
                "tags": list(terv["tags"]), "source": forras}
        if forras["type"] == "generate":
            elem["board"] = terv["first_board"] + len(deals)
        if "pbn" in terv["include"]:
            elem["pbn"] = pbn_deal(kezek, oszto)
        if menet is not None and ("auction" in terv["include"] or terv["auction"]):
            elem["auction"] = menet
            if any(m.get("fallback") for m in menet):
                elem["auction_fallback"] = True
            if any(m.get("gap") for m in menet):
                elem["auction_gap"] = True
        if kon:
            elem["contract"] = kon
        if ellenorzes:
            elem["checks"] = ellenorzes
            for t in ellenorzes.get("techniques", []):
                elem["tags"].append(t["type"])
        if "dd" in terv["include"] and dd is not None:
            elem["dd"] = dd.tablak([kezek])[0]
        deals.append(elem)
    else:
        kimerult = True             # a forrás (PBN / kész kiosztások) elfogyott

    elapsed = int((time.time() - start) * 1000)
    statusz = "ok" if len(deals) >= db_cel or (kimerult and deals) else \
        ("partial" if deals else "empty")
    valasz = {
        "protocol": PROTOKOLL, "request_id": terv["request_id"], "status": statusz,
        "title": terv["title"], "interpretation": _ertelmezes_ki(terv),
        "stats": {"requested": terv["count"], "returned": len(deals), "tried": probalt,
                  "elapsed_ms": elapsed, "source_exhausted": kimerult},
    }
    if terv["dry_run"]:
        valasz["dry_run"] = True
        valasz["status"] = "ok" if deals else "empty"
        valasz["stats"]["estimate"] = ("feasible" if deals else
                                       "no example found within the time budget")
        valasz["examples"] = deals
        return valasz
    valasz["deals"] = deals
    if statusz != "ok":
        valasz["warnings"] = [f"{len(deals)} / {terv['count']} kiosztás készült el "
                              f"{elapsed} ms alatt ({probalt} jelölt) — bővebb időkeret "
                              f"(`time_budget_ms`) vagy lazább cél segít"]
    return valasz


def _lejatszas_ok(kezek, kon: dict, play: dict, dd: DdMotor) -> tuple[bool, dict]:
    """A lejátszási / ellenjátéki feltételek DD-vel. (megfelel-e, ellenőrzés-leírás)"""
    kell = kon["level"] + 6
    ki: dict = {"needed_tricks": kell}
    tabla = dd.tablak([kezek])[0]
    utes = tabla[kon["declarer"]][_strain(kon)]
    ki["dd_tricks"] = utes
    eredmeny = play.get("result")
    if eredmeny == "makes" and utes < kell or eredmeny == "fails" and utes >= kell \
            or eredmeny == "exact" and utes != kell:
        return False, ki
    for t in play.get("technique") or []:
        if t in ("finesse", "expassz"):
            if utes < kell:
                return False, ki
            kulcs = [x for x in kulcsfigurak(kezek, kon, dd) if x["type"] == t]
            if not kulcs:
                return False, ki
            ki.setdefault("techniques", []).extend(kulcs)
        elif t == "sure_tricks_short":
            b = biztos_utesek(kezek, kon["declarer"])
            if utes < kell or b >= kell:
                return False, ki
            ki["sure_tricks"] = b
            ki.setdefault("techniques", []).append({"type": t})
    if play.get("lead"):
        lapok = dd.indulasok(kezek, kon)
        buktato = [c for c, u in lapok if u < kell]
        if not buktato or len(buktato) == len(lapok):
            return False, ki
        if play["lead"] == "single_suit" and len({c[0] for c in buktato}) != 1:
            return False, ki
        ki["beating_leads"] = _rendez(buktato)
        ki["leader"] = ULESEK[(ULESEK.index(kon["declarer"]) + 1) % 4]
    return True, ki
