"""
MOHABRIDZS AI GATEWAY ADAPTER — `mohabridzs-ai/1.0`.

Ez a réteg **ráülteti** a kibicet a MohaBridzs külső AI-játékos
szerződésére. Két végpontot szolgál ki:

    POST /v1/bridge/bid
    POST /v1/bridge/play

és nem tartalmaz bridzslogikát: fordító. A licitdöntés a
`licit_elemzes()`-ből jön, a lejátszás egyelőre kényszerű lap vagy
tartalék.

MIÉRT KELL KÜLÖN RÉTEG
----------------------
A két szerződés mást akar:

    /v1/kibic/licit          /v1/bridge/bid
    ------------------       -----------------------------------
    MAGYARÁZAT a fő tartalom pontosan EGY Action a fő tartalom
    `call` lehet null        a `call` kötelező és legális kell legyen
    ráér                     `deadline_ms` a mérvadó
    tetszőleges méret        legfeljebb 64 KiB
    `1NT`                    `1N`  (a dróton `N` a szan)

A kibic ma a kompetitív ágakon gyakran néma (`call: null`). A gateway
viszont nem fogad el nemleges választ: ilyenkor **tartalékot** adunk
(`meta.source = "fallback"`), és a `fallback_reason`-ben megmondjuk,
miért. Így a MohaBridzs admin AI-naplója magától mérni fogja, hány
döntés jött valódi szabályból és hány a tartalékból — ez pontosan az a
lefedettségi szám, amit amúgy is mérni akarunk, csak élesben.

AMI A SZERZŐDÉSBŐL KÖTELEZŐ, ÉS ITT HOL VAN
--------------------------------------------
    két végpont         `bid_dontes` / `play_dontes` (api.py köti be)
    közös titok         api.py `_jogosultsag`
    request_id          `_valasz()` változtatás nélkül visszaadja
    szabályos akció     `_valaszt()` — mindig a legal_actions-ből
    idempotencia        `Idempotenciatar`, ütközésre 409
    ülésenkénti állapot `munkamenet_kulcs()` (ma tárolatlan: nincs mit)
    előre kompatibilitás ismeretlen mezőt nem nézünk, nem is hibázunk
    határidő            `deadline_ms` szabja a szimuláció engedélyét
    válaszformátum      sima dict; a `meta.kibic` szándékosan rövid

A `meta.kibic` diagnosztika, nem gondolatmenet: ág, forrás, lefedettség
és a nem értett licitek listája. A teljes elemzés a naplóba megy (ha kérik),
a dróton nem.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict

from . import licit as _licit_mod
from .licit import LicitHiba, licit_elemzes

PROTOKOLL = "mohabridzs-ai/1.0"

# A gateway a rövid `N` jelölést használja a szanra, a kibic belül `NT`-t.
SZAN_DROT = "N"
SZAN_BELSO = "NT"

LAP_RANG = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8,
            "9": 9, "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
SZIN_SORREND = {"C": 0, "D": 1, "H": 2, "S": 3}
HIVAS_SORREND = {"P": -3, "X": -2, "XX": -1}
FELVETEL_SZIN = {"C": 0, "D": 1, "H": 2, "S": 3, SZAN_DROT: 4}

# Alapértelmezett rendszer, ha a profil nem mond mást (lásd profil.py).
from .profil import (ALAP_PAR, ALAP_RENDSZER, profil_feloldas,  # noqa: E402,F401
                     vonal_feloldas, vonal_rendszerek)

# SZIMULÁCIÓ (2026-10-20, a szerkesztő): a mérlegelő helyzetekben ALAPMŰKÖDÉS.
# KIBIC_ATJARO_SZIMULACIO=0 kikapcsolja (alap: 1). KIBIC_ATJARO_SZIM_MS az
# időkerete (alap: 10 000 ms — a stop-kártya 12 mp-e alatt, „emberi”
# gondolkodási idő); ha a MohaBridzs határideje (deadline_ms) szorosabb, a
# keret ahhoz igazodik (SZIM_TARTALEK_MS marad a licit többi részére). Ha a
# keret letelik, az addig kiszámolt mintán dönt (elég minta esetén), különben
# a szabály-alapú becslés.
SZIMULACIO_ENGEDVE = os.getenv("KIBIC_ATJARO_SZIMULACIO", "1").strip().lower() \
    not in ("0", "nem", "no", "false", "ki")
SZIMULACIO_MS = int(os.getenv("KIBIC_ATJARO_SZIM_MS", "10000"))
SZIM_TARTALEK_MS = int(os.getenv("KIBIC_ATJARO_SZIM_TARTALEK_MS", "1500"))
SZIM_MIN_KERET_MS = 1000

NAPLO_UT = os.getenv("KIBIC_ATJARO_NAPLO") or None
# a döntés napló-sorába a teljes kérés is (a saját kéz és az asztal!) — csak
# elemzéshez: python -m kibic.cli.jatekelemzes
NAPLO_KERES = os.getenv("KIBIC_ATJARO_NAPLO_KERES", "") in ("1", "igen", "true")

MAX_MAGYARAZAT = 500          # a szerződés korlátja
# Információkérés (mohabridzs-ai 1.1): ha az ellenvonal licitjét nem értjük,
# a végleges licit előtt magyarázatot kérünk. Kikapcsolható: KIBIC_INFO_KERES=0.
INFO_KERES = os.getenv("KIBIC_INFO_KERES", "1") not in ("0", "nem", "")


class AtjaroHiba(ValueError):
    """Hibás gateway-kérés. A hívó HTTP 400-zal fordíthatja le."""


class Utkozes(ValueError):
    """Ugyanaz az idempotenciakulcs más kéréstörzzsel — HTTP 409."""


# --- Jelölésváltás ----------------------------------------------------

def drotra(hivas: str | None) -> str | None:
    """A kibic belső alakjából a publikus jelölésbe: `1NT` -> `1N`."""
    if not hivas:
        return None
    if hivas.endswith(SZAN_BELSO):
        return hivas[:-2] + SZAN_DROT
    return hivas


def _hivas_rang(h: str) -> tuple:
    """Rendezéshez: P < X < XX < 1C < ... < 7N."""
    if h in HIVAS_SORREND:
        return (HIVAS_SORREND[h], 0)
    return (int(h[0]), FELVETEL_SZIN.get(h[1:], 9))


# --- A kérés olvasása --------------------------------------------------

def _szotar(keres, mezo: str, kotelezo: bool = True) -> dict:
    ertek = keres.get(mezo)
    if isinstance(ertek, dict):
        return ertek
    if kotelezo:
        raise AtjaroHiba(f"Hiányzó vagy hibás '{mezo}' objektum")
    return {}


def _legalis(keres: dict, mezo: str) -> list[str]:
    la = _szotar(keres, "legal_actions")
    lista = la.get(mezo)
    if not isinstance(lista, list) or not lista:
        raise AtjaroHiba(f"A 'legal_actions.{mezo}' üres vagy hiányzik")
    return [str(x) for x in lista]


def munkamenet_kulcs(keres: dict) -> str:
    """
    A szerződés által ajánlott ülésenkénti kulcs.

    Ma nincs mit tárolni mögé (a kibic minden döntést a menetből számol
    újra), de a naplóba beírjuk: gyakorlásban ugyanaz a profil több
    helyen is ülhet, és így különválasztható, melyik szék mit döntött.
    """
    g = keres.get("game") or {}
    a = keres.get("actor") or {}
    return "bridge:{}:{}:{}:{}".format(
        g.get("match_id", "?"), g.get("table_index", 0),
        g.get("board_number", 0), a.get("seat", "?"))


def _rendszer(keres: dict, ules: str | None = None) -> tuple[str, str | None]:
    """
    Melyik rendszer szemüvegén át licitáljon / magyarázzon ez az AI?
    1.2: a saját vonal rendszere a `game.systems`-ből; ha nincs (régi
    kliens), az `actor.profile_code`-ból (profil.py).
    """
    p = profil_feloldas(keres)
    if ules:
        v = vonal_feloldas(keres, ules)
        if v["own_source"] == "systems":
            return v["own"], None
    return p["system"], p["pair"]


def _vonal_meta(v: dict) -> dict:
    """A vonalak rendszere a naplónak (meta.kibic.systems)."""
    ki = {"own": v.get("own"), "own_source": v.get("own_source"),
          "own_sent": v.get("own_sent"),
          "opponents": v.get("opponents"),
          "opponents_family": v.get("opponents_family"),
          "opponents_system": v.get("opponents_system"),
          "opponents_known": v.get("opponents_known")}
    if v.get("own_mismatch"):
        ki["own_mismatch"] = True
    if not v.get("sent"):
        ki["warning"] = "a kérés nem hozott game.systems-t: a saját rendszer a profilból jön, az ellenfélé ismeretlen"
    return {k: x for k, x in ki.items() if x is not None}


# --- A válasz építése --------------------------------------------------

def _valasz(keres: dict, tipus: str, akcio: dict, magyarazat: str,
            bizonyossag: float | None, meta: dict) -> dict:
    ki = {"request_id": keres.get("request_id"),
          "action": dict(akcio, type=tipus),
          "explanation": (magyarazat or "")[:MAX_MAGYARAZAT],
          "meta": meta}
    if bizonyossag is not None:
        ki["confidence"] = round(max(0.0, min(1.0, bizonyossag)), 2)
    return ki


def _valaszt(javasolt: str | None, legalis: list[str],
             alap: str) -> tuple[str, str | None]:
    """
    A szerződés MUST-ja: a válasz a legal_actions egyik eleme.

    Visszaad: (választott akció, tartalék oka vagy None).
    A tartaléklétra: a kibic javaslata -> az `alap` (passz / legkisebb
    lap) -> a felsorolás első eleme. Sosem találunk ki akciót.
    """
    if javasolt and javasolt in legalis:
        return javasolt, None
    if javasolt:
        return ((alap if alap in legalis else legalis[0]),
                f"a javasolt {javasolt} nem szerepelt a legal_actions között")
    if alap in legalis:
        return alap, "a kibicnek nincs szabálya erre a helyzetre"
    return legalis[0], "a kibicnek nincs szabálya erre a helyzetre"


def _magyarazat(elemzes: dict, tartalek_ok: str | None) -> str:
    """Rövid, emberi indoklás — gondolatmenet nélkül."""
    if tartalek_ok:
        nem_ertett = (elemzes.get("coverage") or {}).get("unknown_calls") or []
        reszek = [f"Tartalék: {tartalek_ok}."]
        if nem_ertett:
            reszek.append("Nem értett licit: " + ", ".join(nem_ertett[:4]) + ".")
        return " ".join(reszek)
    szoveg = (elemzes.get("explanation") or "").strip()
    jeloltek = elemzes.get("candidates") or []
    if not szoveg and jeloltek:
        szoveg = jeloltek[0].get("why") or ""
    forras = elemzes.get("source")
    if forras == "ELV" and elemzes.get("situational_agreement"):
        szoveg = (f"Helyzeti megállapodás ({elemzes['situational_agreement']}) szerint. "
                  + szoveg).strip()
    elif forras == "ELV":
        szoveg = ("Nincs rá megállapodás; általános elv alapján. " + szoveg).strip()
    elif forras == "MERLEGELES":
        szoveg = ("Szimulációs mérlegelés. " + szoveg).strip()
    elif forras == "HEZAG":
        szoveg = ("Nincs rá megállapodás; " + szoveg).strip()
    return szoveg or "Szabály szerinti licit."


def _bizonyossag(elemzes: dict) -> float:
    """
    Nem valószínűség, hanem őszinteség: mennyire állt mögötte tudás.

    Egy szabály, ért menet -> magas; több jelölt, néma helyek -> alacsony.
    A gateway csak naplózza, de a felhasználónak sokat mond.
    """
    forras = elemzes.get("source")
    alap = {"SZABALY": 0.8, "SPIRAL": 0.8, "MERLEGELES": 0.7, "ELV": 0.5,
            "HEZAG": 0.35}.get(forras, 0.2)
    if forras == "ELV" and elemzes.get("situational_agreement"):
        alap = 0.8                         # konvenció helyzeti alakja: megállapodás
    if elemzes.get("uncertain"):
        alap -= 0.15
    lefedettseg = (elemzes.get("coverage") or {}).get("ratio")
    if lefedettseg is not None:
        alap -= 0.2 * (1.0 - float(lefedettseg))
    return max(0.05, min(0.95, alap))


def _meta_kibic(elemzes: dict, keres: dict) -> dict:
    """
    Rövid diagnosztika a dróton. NEM gondolatmenet és nem kéztartalom.

    Az ismeretlen mezőket a MohaBridzs figyelmen kívül hagyja, tehát ez
    nem sérti a szerződést — viszont az admin naplóból így is látszik,
    hol néma a rendszer.
    """
    fedes = elemzes.get("coverage") or {}
    ki = {"branch": elemzes.get("branch"),
          "rule_source": elemzes.get("source"),
          "understood": fedes.get("understood"),
          "unknown": fedes.get("unknown")}
    nem_ertett = fedes.get("unknown_calls") or []
    if nem_ertett:
        ki["unknown_calls"] = nem_ertett[:8]
    if fedes.get("from_alert"):
        ki["understood_from_alert"] = fedes["from_alert"][:8]
    if elemzes.get("explain_requests"):
        # 1.2: a kibic magyarázatot kér ezekre (auction[index].alert-ben jöhet)
        ki["explain_requests"] = elemzes["explain_requests"][:8]
    jeloltek = elemzes.get("candidates") or []
    if len(jeloltek) > 1:
        ki["candidates"] = [j.get("call") for j in jeloltek[:6]]
    if elemzes.get("undecidable_rules"):
        ki["undecidable_rules"] = elemzes["undecidable_rules"]
    if elemzes.get("test_mode"):
        # Jóvá nem hagyott szabályokkal is licitál: a naplóban látszódjon.
        ki["test_mode"] = True
    if elemzes.get("implicit_pass"):
        # A passz a hallgatólagos "nincs nyitóerő" szabályból jött, nem
        # konkrét sorból — a lefedettség-méréshez külön kell látszania.
        ki["implicit_pass"] = True
    return ki


# --- Idempotencia ------------------------------------------------------

class Idempotenciatar:
    """
    Kulcsonként a kérés lenyomata és a kész válasz.

    Ugyanaz a kulcs + ugyanaz a törzs -> ugyanaz a válasz (nem számolunk
    újra). Ugyanaz a kulcs + más törzs -> `Utkozes` (HTTP 409).
    Korlátos méret, mert egy parti sok döntést ad.
    """

    def __init__(self, meret: int = 512):
        self.meret = meret
        self._tar: OrderedDict[str, tuple[str, dict]] = OrderedDict()
        self._zar = threading.Lock()

    @staticmethod
    def lenyomat(keres: dict) -> str:
        nyers = json.dumps(keres, sort_keys=True, ensure_ascii=False,
                           default=str)
        return hashlib.sha256(nyers.encode("utf-8")).hexdigest()

    def olvas(self, kulcs: str | None, keres: dict) -> dict | None:
        if not kulcs:
            return None
        uj = self.lenyomat(keres)
        with self._zar:
            tetel = self._tar.get(kulcs)
        if tetel is None:
            return None
        regi, valasz = tetel
        if regi != uj:
            raise Utkozes(
                f"Az Idempotency-Key ({kulcs}) már más kéréstörzshöz tartozik")
        return valasz

    def ir(self, kulcs: str | None, keres: dict, valasz: dict) -> None:
        if not kulcs:
            return
        with self._zar:
            self._tar[kulcs] = (self.lenyomat(keres), valasz)
            while len(self._tar) > self.meret:
                self._tar.popitem(last=False)

    def urit(self) -> int:
        with self._zar:
            db = len(self._tar)
            self._tar.clear()
        return db

    def kesz_valasz(self, kulcs: str | None) -> dict | None:
        """A kulcshoz tárolt kész válasz törzs-ellenőrzés nélkül (az életjelnek)."""
        if not kulcs:
            return None
        with self._zar:
            tetel = self._tar.get(kulcs)
        return tetel[1] if tetel else None


TAR = Idempotenciatar()


# --- Napló -------------------------------------------------------------

def _meta_debug_nelkul(meta: dict | None) -> dict | None:
    """A tanító nyom a kéz értékeit is tartalmazza: a naplóba nem kerül."""
    if not meta or "debug" not in (meta.get("kibic") or {}):
        return meta
    m = dict(meta)
    m["kibic"] = {k: v for k, v in meta["kibic"].items() if k != "debug"}
    return m


def naploz(keres: dict, elemzes: dict | None, valasz: dict) -> None:
    """
    A TELJES elemzés a naplóba, a dróton csak a rövid meta megy.

    A szerződés 12. pontja tiltja a kéz és a nyers prompt naplózását: a
    `hand` és a `visible_hands` ezért ide sem kerül be — a kényszertár és
    a lefedettség viszont igen, mert épp az a hasznos.
    """
    if not NAPLO_UT:
        return
    sor = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "request_id": keres.get("request_id"),
        "session": munkamenet_kulcs(keres),
        "decision": keres.get("decision"),
        "deadline_ms": keres.get("deadline_ms"),
        "action": valasz.get("action"),
        "meta": _meta_debug_nelkul(valasz.get("meta")),
        "explanation": valasz.get("explanation"),
        "alert": valasz.get("alert"),
    }
    if NAPLO_KERES and keres.get("decision") == "play":
        sor["request"] = keres          # KIBIC_ATJARO_NAPLO_KERES=1: a visszajátszáshoz
    if elemzes and elemzes.get("shadow"):
        sor["shadow"] = elemzes["shadow"]       # árnyék mód: az új döntéshozók (nem a dróton)
    if elemzes:
        sor["kibic"] = {k: elemzes.get(k) for k in
                        ("branch", "call", "source", "candidates",
                         "to_deliberate", "auction_understanding",
                         "constraints", "coverage", "deliberation")}
    try:
        with open(NAPLO_UT, "a", encoding="utf-8") as f:
            f.write(json.dumps(sor, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass          # a napló sosem állíthatja meg a partit


# --- LICIT -------------------------------------------------------------

def info_keres_indexek(keres: dict, elemzes: dict) -> list[int]:
    """
    Mely ellenvonali licitekre kérjünk magyarázatot (`history.auction`
    0-alapú indexei). Csak 1.1-es protokollnál (az 1.0-s MB nem ismeri),
    csak még meg nem kérdezett licitre.
    """
    if not INFO_KERES:
        return []
    prot = str(keres.get("protocol") or "")
    if not prot.startswith("mohabridzs-ai/") or prot.endswith("/1.0"):
        return []
    menet = (keres.get("history") or {}).get("auction") or []
    ki = []
    for r in elemzes.get("explain_requests") or []:
        i = r.get("index")
        if not isinstance(i, int) or i >= len(menet):
            continue
        elem = menet[i]
        if isinstance(elem, dict) and elem.get("information"):
            continue
        ki.append(i)
    return sorted(set(ki))


def bid_dontes(keres: dict, betolto) -> dict:
    """`POST /v1/bridge/bid` — pontosan egy szabályos licit."""
    start = time.time()
    hivasok = _legalis(keres, "calls")
    allapot = _szotar(keres, "state", kotelezo=False)
    szereplo = _szotar(keres, "actor")
    jatek = _szotar(keres, "game", kotelezo=False)

    ules = str(szereplo.get("acting_for_seat")
               or szereplo.get("seat") or "").upper()
    if ules not in ("N", "E", "S", "W"):
        raise AtjaroHiba("Az 'actor.acting_for_seat' hiányzik vagy hibás")

    lathato = allapot.get("visible_hands") or {}
    kez = lathato.get(ules)
    if not kez:
        raise AtjaroHiba(
            f"A 'state.visible_hands' nem tartalmazza a(z) {ules} kezet")

    vf = vonal_feloldas(keres, ules)
    rendszer, par = _rendszer(keres, ules)
    hatarido = int(keres.get("deadline_ms") or 0)
    szim_keret = SZIMULACIO_MS if not hatarido else \
        min(SZIMULACIO_MS, hatarido - SZIM_TARTALEK_MS)
    szimulal = SZIMULACIO_ENGEDVE and szim_keret >= SZIM_MIN_KERET_MS

    belso = {
        "request_id": keres.get("request_id"),
        "hand": list(kez),
        "seat": ules,
        "dealer": allapot.get("dealer") or ules,
        "vulnerability": jatek.get("vulnerability") or "none",
        "auction": ((keres.get("history") or {}).get("auction") or []),
        "system": rendszer,
        "pair": par,
        "opponent_system": vf.get("opponents_system"),
        "families": vf.get("families"),
        "legal_actions": hivasok,
        "simulate": szimulal,
        "simulate_ms": szim_keret,
        # versenyforma (MP / BAM / IMP), ha az MB küldi — a 6M vagy 6NT döntéshez
        "scoring": jatek.get("scoring") or jatek.get("scoring_type"),
        # kizárásos következtetés: a határidő negyede, legfeljebb a beállított keret
        "inference_ms": min(_licit_mod.KOVETKEZTETES_MS, hatarido // 4) if hatarido else
                        _licit_mod.KOVETKEZTETES_MS,
    }

    elemzes: dict | None = None
    hiba_ok = None
    try:
        elemzes = licit_elemzes(belso, betolto)
    except LicitHiba as e:
        hiba_ok = f"a kibic nem tudta értelmezni a helyzetet: {e}"
    except Exception as e:                       # noqa: BLE001
        # A parti nem állhat meg egy belső hiba miatt. Passzolunk, és
        # megmondjuk, hogy tartalék volt.
        hiba_ok = f"belső hiba: {type(e).__name__}"

    if elemzes is None:
        akcio, ok = _valaszt(None, hivasok, "P")
        valasz = _valasz(keres, "bid", {"call": akcio},
                         f"Tartalék: {hiba_ok}.", 0.05,
                         {"source": "fallback", "pipeline": "kibic_bid",
                          "elapsed_ms": int((time.time() - start) * 1000),
                          "fallback_reason": hiba_ok})
        naploz(keres, None, valasz)
        return valasz

    # INFORMÁCIÓKÉRÉS (1.1): az ellenvonal nem értett / szöveg nélkül
    # alertált licitjeire, a végleges licit ELŐTT. Az MB begyűjti a
    # magyarázatokat, és ugyanebben a helyzetben újra hív; a már
    # megkérdezett licitet (bármi lett a válasz) többször nem kérjük.
    kerdes = info_keres_indexek(keres, elemzes)
    if kerdes:
        meta = {"source": "model", "pipeline": "kibic_bid",
                "elapsed_ms": int((time.time() - start) * 1000),
                "fallback_reason": None,
                "kibic": _meta_kibic(elemzes, keres)}
        meta["kibic"]["system"] = rendszer
        hivasok_szoveg = ", ".join(
            f"{r['seat']}:{drotra(r['call'])}" for r in elemzes["explain_requests"]
            if r["index"] in kerdes)
        valasz = _valasz(keres, "request_information", {"bid_indices": kerdes},
                         f"Magyarázatot kérek az ellenvonal licitjére: {hivasok_szoveg}.",
                         None, meta)
        naploz(keres, elemzes, valasz)
        return valasz

    akcio, ok = _valaszt(drotra(elemzes.get("call")), hivasok, "P")
    meta = {
        "source": "fallback" if ok else "model",
        "pipeline": "kibic_bid",
        "elapsed_ms": int((time.time() - start) * 1000),
        "fallback_reason": ok,
        "kibic": _meta_kibic(elemzes, keres),
    }
    # Melyik rendszerben döntött, és mit tudott az ellenfélről.
    meta["kibic"]["system"] = rendszer
    meta["kibic"]["systems"] = _vonal_meta(vf)
    valasz = _valasz(keres, "bid", {"call": akcio},
                     _magyarazat(elemzes, ok),
                     0.05 if ok else _bizonyossag(elemzes), meta)
    # ALERT (mohabridzs-ai 1.1 bővítés): ha a választott licit a rendszer
    # szerint alertálandó, a MEGÁLLAPODÁS szövege a licittel együtt megy.
    # Tartalék licitnél nincs alert: arra nincs megállapodás.
    if not ok and elemzes.get("alert"):
        a = elemzes["alert"]
        valasz["alert"] = {"text": a.get("text") or "",
                           "text_en": a.get("text_en")}
    # TANÍTÓ NYOM: csak teszt módban (a kéz adatait is tartalmazza).
    if elemzes.get("debug") and elemzes.get("test_mode"):
        meta["kibic"]["debug"] = elemzes["debug"]
    naploz(keres, elemzes, valasz)
    return valasz


# --- LEJÁTSZÁS ---------------------------------------------------------

def _legkisebb(lapok: list[str]) -> str:
    """A MohaBridzs tartalékával azonos: legkisebb rang, C D H S döntetlenre."""
    def kulcs(x: str):
        s = x.strip().upper()
        szin, rang = (s[0], s[1]) if s[0] in SZIN_SORREND else (s[1], s[0])
        return (LAP_RANG.get(rang, 99), SZIN_SORREND.get(szin, 9))
    return min(lapok, key=kulcs)


# A lejátszó réteg időkerete: a határidő ennyied része, legfeljebb ennyi ms.
LEJATSZAS_MS = int(os.getenv("KIBIC_LEJATSZAS_MS", "10000"))
LEJATSZAS_ARANY = 0.4
# legfeljebb ennyi minta. Hogy ténylegesen mennyit néz meg, azt a döntés
# biztossága dönti el (2026-10-23): kötegenként sorsol, és megáll, ha a legjobb
# lap már biztosan jobb (vagy biztosan alig különbözik) — különben az időkeret
# végéig gondolkodik. A végjátékban — ha kevés a lehetséges elosztás — MINDET
# megnézi (kimerítő elemzés). Legalább: KIBIC_LEJATSZAS_MIN_MINTA (60).
LEJATSZAS_MINTA = int(os.getenv("KIBIC_LEJATSZAS_MINTA", "3000"))
# a licit kizárásos következtetésének időkerete a lejátszásban (a határidő 30%-áig);
# leosztásonként egyszer fizetjük meg, utána gyorsítótárból jön
LEJATSZAS_KOVETKEZTETES_MS = int(os.getenv("KIBIC_LEJATSZAS_KOVETKEZTETES_MS", "15000"))


def licit_tudas(k: dict, betolto, kovetkeztetes_ms: int = 0) -> tuple[dict, dict]:
    """
    A licitmenetből a lejátszásnak: (kényszertár, kizárásos következtetés).
    A kényszertár: amit a licitek KIMONDTAK (mint a licit.kenyszertar_menetbol);
    a következtetés: amit KIZÁRTAK (a licit-szál kovetkeztetes.py-ja: a
    licitmotor szimulálja a licitálót — pl. a passz 1♥-re „0-5 pont”).
    Az ellenfél licitjeit az ő rendszerük szerint, ha ismeretlen: a miénk szerint.
    `k`: seat, dealer, vulnerability, auction, system, pair, opponent_system,
    families, test_mode.
    """
    L = _licit_mod
    oszto = L._ules(k.get("dealer", k.get("seat")), "dealer")
    ules = L._ules(k.get("seat"), "seat")
    beli = L.BELI_TERKEP.get(str(k.get("vulnerability", "none")).upper(), "NONE")
    licitek = L._menet(k.get("auction"), oszto)
    teszt = k.get("test_mode")
    sorok, paramtar = (betolto(k["system"], k.get("pair")) if teszt is None
                       else betolto(k["system"], k.get("pair"), bool(teszt)))
    prop = L.vonalas_propagalo(sorok, paramtar, betolto, ules,
                               k.get("opponent_system") or k["system"],
                               k.get("families") or {}, teszt)
    er = prop.kenyszertar(licitek, oszto=oszto, beliallas=beli,
                          kovetkeztet_ulesek={u for u in "NESW" if u != ules}
                          if kovetkeztetes_ms > 0 else None,
                          kovetkeztetes_ms=max(0, int(kovetkeztetes_ms)))
    return er.kenyszertar, dict(getattr(er, "kovetkeztetett", None) or {})


def _tartalek_play(keres: dict, lapok: list[str], ok: str, start: float) -> dict:
    return _valasz(
        keres, "play", {"card": _legkisebb(lapok)}, f"Tartalék: {ok}.", 0.05,
        {"source": "fallback", "pipeline": "kibic_play",
         "elapsed_ms": int((time.time() - start) * 1000), "fallback_reason": ok})


# Gondolkodási idő (2026-10-24): a kijátszásra adott válasz legalább ennyi ms
# (egyenletes véletlen a tartományból) — a kényszerű / szingli lapra adott
# azonnali válasz elárulná, hogy nem volt választás. Ha a döntés tovább tartott,
# nincs várakozás; legfeljebb a határidő (deadline_ms) 30%-a; az utolsó ütésben
# (mindenkinek egy lapja van) nincs. "0" kikapcsolja. Formátum: "1500-3000" vagy "2000".
GONDOLKODAS_MS = os.getenv("KIBIC_GONDOLKODAS_MS", "1500-3000")
GONDOLKODAS_HATARIDO_ARANY = 0.3


def _gondolkodas_tartomany(ertek: str) -> tuple[int, int]:
    try:
        a, _, b = str(ertek).strip().partition("-")
        lo = max(0, int(a))
        hi = max(lo, int(b)) if b else lo
        return lo, hi
    except ValueError:
        return 0, 0


def _utolso_utes(keres: dict) -> bool:
    st = keres.get("state") or {}
    hist = (keres.get("history") or {}).get("play")
    if hist is None:
        hist = [c for t in (st.get("completed_tricks") or []) for c in (t.get("cards") or [])]
    return len(hist or []) >= 48


def gondolkodasi_ido(keres: dict, start: float, rng=None) -> int:
    """
    A válaszig hátralévő várakozás ms-ban (0, ha nem kell). `start`: a kérés
    feldolgozásának kezdete (time.time()).
    """
    import random
    lo, hi = _gondolkodas_tartomany(GONDOLKODAS_MS)
    if hi <= 0 or _utolso_utes(keres):
        return 0
    cel = (rng or random).randint(lo, hi)
    hatarido = int(keres.get("deadline_ms") or 0)
    if hatarido > 0:
        cel = min(cel, int(hatarido * GONDOLKODAS_HATARIDO_ARANY))
    return max(0, cel - int((time.time() - start) * 1000))


def play_dontes(keres: dict, betolto=None, jelzes_fv=None, dd_zar=None,
                feladat=None) -> dict:
    """
    `POST /v1/bridge/play` — a döntés (`_play_dontes`) és a gondolkodási idő.

    `feladat` (surgetes.Feladat): az életjel-nyilvántartás bejegyzése. A döntés
    ide jelenti az előrehaladást, sürgetésre (`feladat.siess`) a mintavétel
    megáll; a kész döntés a gondolkodási idő ELŐTT bekerül, így a sürgetés
    azonnal megkapja, és a várakozás is megszakad.
    """
    start = time.time()
    try:
        valasz = _play_dontes(keres, betolto, jelzes_fv, dd_zar, feladat)
    except Exception as e:                       # noqa: BLE001 — az életjel lássa
        if feladat is not None:
            feladat.hibas(type(e).__name__)
        raise
    if feladat is not None:
        feladat.kesz(valasz)
    var_ms = gondolkodasi_ido(keres, start)
    if var_ms > 0:
        if feladat is not None:
            feladat.siess.wait(var_ms / 1000)
        else:
            time.sleep(var_ms / 1000)
    return valasz


def _terv_play(keres: dict, allas, start: float, feladat, figyelem: list) -> dict | None:
    """A felvevő tervező lapja (motor/tervdontes.py), ha be van kapcsolva és ad
    lapot; különben None (a régi lejátszó dönt). A sürgetés a tervezés lépcsői
    között megállítja: az addigi legjobb megy, ha már van."""
    from ..motor import tervdontes as td
    if allas.vedo or not td.bekapcsolva(keres):
        return None
    # a többszálú szolgáltatásban a folyamatok forkserverrel indulnak
    os.environ.setdefault("KIBIC_MP", "forkserver")
    if feladat is not None:
        feladat.szakaszba("tervezes")
    try:
        d = td.dontes(allas, munkamenet_kulcs(keres),
                      megallito=feladat.megallito if feladat is not None else None)
    except Exception as e:                       # noqa: BLE001 — a régi lejátszó a tartalék
        figyelem.append(f"tervező: {type(e).__name__}: {e}"[:200])
        return None
    if d is None or d.lap not in allas.legalis:
        figyelem.append("tervező: nincs lapja ebben a helyzetben (a régi lejátszó dönt)")
        return None
    meta = {"source": "model", "pipeline": "kibic_terv",
            "elapsed_ms": int((time.time() - start) * 1000),
            "fallback_reason": None, "kibic": {"planner": d.meta}}
    if figyelem:
        meta["kibic"]["warnings"] = list(figyelem)
    valasz = _valasz(keres, "play", {"card": allas.legalis[d.lap]}, d.magyarazat,
                     d.bizonyossag, meta)
    naploz(keres, None, valasz)
    return valasz


def _play_dontes(keres: dict, betolto=None, jelzes_fv=None, dd_zar=None,
                 feladat=None) -> dict:
    """
    `POST /v1/bridge/play` — a lejátszó réteg (motor/lejatszas.py):

      1. tények -> minta a rejtett kezekből (a licit kényszertárával),
      2. DD-szűrő: jó / talán / biztosan rossz lapok,
      3. a megállapodás (jelzésrendszer) a jó lapok közül választ,
      4. a mérlegelő elvek (még csak szövegként a jelzésrendszerben).

    `betolto`: a licitrendszer betöltője (a kényszertárhoz); `jelzes_fv(kód)`:
    a licitrendszer jelzésrendszere; `dd_zar`: a DDS nem szálbiztos. Ha
    bármelyik hiányzik vagy hibázik, a döntés kevesebb tudással, de megszületik;
    csak értelmezhetetlen kérésnél van tartalék (legkisebb lap).
    """
    from ..motor import lejatszas as lj
    start = time.time()
    lapok = _legalis(keres, "cards")
    szereplo = keres.get("actor") or {}
    ules = str(szereplo.get("acting_for_seat") or szereplo.get("seat") or "").upper()
    if len(lapok) == 1:
        valasz = _valasz(
            keres, "play", {"card": lapok[0]}, "Kényszerű lap.", 1.0,
            {"source": "model", "pipeline": "kibic_play_kenyszer",
             "elapsed_ms": int((time.time() - start) * 1000),
             "fallback_reason": None})
        naploz(keres, None, valasz)
        return valasz
    try:
        allas = lj.allas_keresbol(keres)
    except lj.LejatszasHiba as e:
        valasz = _tartalek_play(keres, lapok, f"a kibic nem értette a játékállást: {e}", start)
        naploz(keres, None, valasz)
        return valasz

    figyelem: list[str] = []
    # a kibic nem néz bele abba, amit a játékos nem láthat (pl. tanári nézet)
    eldobott = lj.lathato_szures(allas, str(szereplo.get("seat") or "").upper() or None)
    if eldobott:
        figyelem.append(f"nem látható kezek figyelmen kívül: {','.join(eldobott)}")

    # a sémákból dolgozó felvevő tervező (KIBIC_TERVEZO / KIBIC_TERVEZO_PROFILOK)
    terv_valasz = _terv_play(keres, allas, start, feladat, figyelem)
    if terv_valasz is not None:
        return terv_valasz
    rendszer = par = None
    vf: dict = {}
    try:
        vf = vonal_feloldas(keres, ules)
        rendszer, par = _rendszer(keres, ules)
    except Exception as e:                       # noqa: BLE001
        figyelem.append(f"rendszer: {type(e).__name__}")

    jelz = None
    if jelzes_fv and rendszer:
        try:
            jelz = jelzes_fv(rendszer)
        except Exception as e:                   # noqa: BLE001
            figyelem.append(f"jelzésrendszer: {type(e).__name__}")

    tar, valoszinu = None, {}
    hatarido = int(keres.get("deadline_ms") or 20000)
    if feladat is not None:
        feladat.szakaszba("kovetkeztetes")
    if betolto and rendszer:
        try:
            st = keres.get("state") or {}
            # a kizárásos következtetés a parti ELSŐ döntésénél drága (a licitmotor
            # szimulálja a licitálót), utána gyorsítótárból jön
            kov_ms = min(LEJATSZAS_KOVETKEZTETES_MS, int(hatarido * 0.3))
            tar, valoszinu = licit_tudas({
                "seat": ules, "dealer": st.get("dealer") or ules,
                "vulnerability": (keres.get("game") or {}).get("vulnerability") or "none",
                "auction": (keres.get("history") or {}).get("auction") or [],
                "system": rendszer, "pair": par,
                "opponent_system": vf.get("opponents_system"),
                "families": vf.get("families")}, betolto, kov_ms)
        except Exception as e:                   # noqa: BLE001
            figyelem.append(f"kényszertár: {type(e).__name__}")

    def dd_fv(lo, jatszott, k):
        from ..solver import dds
        if dd_zar is None or dds.parhuzamos():
            # nincs zár, vagy a DDS külön folyamatokban fut (KIBIC_DDS_FOLYAMATOK)
            ered = dds.lap_elemzes(lo, jatszott, k)
            if feladat is not None:
                feladat.dd_eredmeny(ered, 0.0, szamit=k is allas.kontraktus)
            return ered
        t0 = time.time()
        if feladat is not None and not dd_zar.acquire(blocking=False):
            feladat.szakaszba("dds_var")     # más asztal számol: sorban állunk
            dd_zar.acquire()
            feladat.szakaszba("mintavetel")
        elif feladat is None:
            dd_zar.acquire()
        var = time.time() - t0
        try:
            ered = dds.lap_elemzes(lo, jatszott, k)
        finally:
            dd_zar.release()
        if feladat is not None:
            feladat.dd_eredmeny(ered, var, szamit=k is allas.kontraktus)
        return ered

    keret_s = min(LEJATSZAS_MS, max(1000, int(hatarido * LEJATSZAS_ARANY))) / 1000
    keret_s = max(1.0, keret_s - (time.time() - start))     # a következtetés ideje levonva
    if feladat is not None:
        feladat.keret(keret_s, LEJATSZAS_MINTA)
    try:
        e = lj.jatek_dontes(allas, jelz, tar, dd_fv, ido_keret_s=keret_s, db=LEJATSZAS_MINTA,
                            valoszinu=valoszinu,
                            megallito=feladat.megallito if feladat is not None else None)
    except Exception as ex:                      # noqa: BLE001 — a parti nem állhat meg
        valasz = _tartalek_play(keres, lapok, f"belső hiba: {type(ex).__name__}", start)
        naploz(keres, None, valasz)
        return valasz

    if feladat is not None:
        feladat.szakaszba("dontes")
    lap = allas.legalis[e.dontes.lap]
    if e.stat:
        s = e.stat.get(e.dontes.lap)
        bizonyossag = 0.5 + 0.45 * (s.legjobb if s else 0.0)
    else:
        bizonyossag = 0.3
    if e.terites is not None and e.terites.mind:
        bizonyossag = 1.0               # terítés: minden elosztás ellen biztos
    kibic = lj.meta(e)
    kibic["system"] = rendszer
    kibic["signals"] = jelz.rendszer.kod if jelz and jelz.rendszer else None
    kibic["constraints_used"] = tar is not None
    if figyelem:
        kibic["warnings"] = figyelem
    teszt = bool(getattr(betolto, "teszt_alap", False))
    if teszt and e.stat:
        # laponként a DD-osztályok — a kéz lapjai, ezért csak teszt módban, és a naplóba sem
        kibic["debug"] = {"cards": lj.meta(e, reszletes=True).get("cards")}
    meta = {"source": "model", "pipeline": "kibic_play",
            "elapsed_ms": int((time.time() - start) * 1000),
            "fallback_reason": None, "kibic": kibic}
    if ules in ("N", "E", "S", "W") and vf:
        meta["kibic"]["systems"] = _vonal_meta(vf)
    valasz = _valasz(keres, "play", {"card": lap}, lj.magyarazat(e), bizonyossag, meta)
    naploz(keres, None, valasz)
    return valasz


# =====================================================================
# Terítés elbírálása — POST /v1/bridge/claim (MB AI-terítés 1.0)
# =====================================================================
# Az MB a terítő ellenfeleit kérdezi (mindkettőt külön); a válasz
# `action: {type: claim_response, accept: true|false}`. A döntés a
# motor/terites.py `elbiral` függvénye. A magyarázat KÉZ NÉLKÜLI és nem
# árulja el, hogy a terítés a valódi állásban kijönne-e (az a terítőnek
# információ volna) — a részletes ok csak teszt módban megy ki.

CLAIM_IDO_MS = int(os.getenv("KIBIC_CLAIM_MS", "20000"))

_CLAIM_SZOVEG = {
    "BIZTOS": "Elfogadom: a bejelentett ütések a lapok bármely elhelyezkedése mellett megvannak.",
    "MINDEN_ELOSZTAS": "Elfogadom: a bejelentett ütések a lapok minden lehetséges elhelyezkedése mellett megvannak.",
}
_CLAIM_ELUTASIT = "Nem fogadom el: nem látom biztosnak — játsszuk le."


def claim_dontes(keres: dict, dd_zar=None) -> dict:
    """`POST /v1/bridge/claim` — elfogadjuk-e az ellenfél (vagy az ellenvonal) terítését."""
    from ..motor import lejatszas as lj
    from ..domain import vonal
    from ..motor.terites import elbiral
    start = time.time()
    if not isinstance(keres, dict):
        raise AtjaroHiba("A kérés JSON-objektum legyen")
    if keres.get("decision") not in (None, "claim_response"):
        raise AtjaroHiba("A 'decision' értéke 'claim_response' legyen")
    c = keres.get("claim")
    if not isinstance(c, dict):
        raise AtjaroHiba("A 'claim' objektum hiányzik")
    terito = str(c.get("claimant") or "").upper()
    if terito not in ("N", "E", "S", "W"):
        raise AtjaroHiba("A 'claim.claimant' hiányzik vagy hibás")
    utesek = c.get("tricks")
    if isinstance(utesek, bool) or not isinstance(utesek, int):
        raise AtjaroHiba("A 'claim.tricks' egész szám legyen")

    def valasz(elfogad: bool, szoveg: str, kibic: dict, forras: str = "model",
               ok: str | None = None) -> dict:
        meta = {"source": forras, "pipeline": "kibic_claim",
                "elapsed_ms": int((time.time() - start) * 1000),
                "fallback_reason": ok if forras == "fallback" else None, "kibic": kibic}
        v = _valasz(keres, "claim_response", {"accept": elfogad}, szoveg,
                    1.0 if elfogad else None, meta)
        naploz(keres, None, v)
        return v

    # a szabályos kijátszási kérés alakja kell a játékállás olvasásához
    szereplo = keres.get("actor") or {}
    ules = str(szereplo.get("acting_for_seat") or szereplo.get("seat") or "").upper()
    sajat = ((keres.get("state") or {}).get("visible_hands") or {}).get(ules) or []
    try:
        allas = lj.allas_keresbol(dict(keres, legal_actions={"cards": list(sajat[:1]) or ["C2"]}))
    except lj.LejatszasHiba as e:
        return valasz(False, _CLAIM_ELUTASIT, {}, "fallback", f"a játékállás nem értelmezhető: {e}")
    if vonal(allas.ules) == vonal(terito):
        return valasz(False, _CLAIM_ELUTASIT, {}, "fallback", "a saját vonal terítéséről nem dönt")

    def dd_fv(lo, jatszott, k):
        from ..solver.dds import lap_elemzes
        if dd_zar is None:
            return lap_elemzes(lo, jatszott, k)
        with dd_zar:
            return lap_elemzes(lo, jatszott, k)

    hatarido = int(keres.get("deadline_ms") or 60000)
    ido_s = max(1.0, min(CLAIM_IDO_MS, hatarido * 0.5) / 1000)
    try:
        e = elbiral(allas, terito, utesek, dd_fv, ido_s)
    except ImportError:
        return valasz(False, _CLAIM_ELUTASIT, {}, "fallback", "nincs DDS")
    except Exception as ex:                      # noqa: BLE001
        return valasz(False, _CLAIM_ELUTASIT, {}, "fallback", f"belső hiba: {type(ex).__name__}")
    kibic = {"worlds_checked": e.vilagok, "exhaustive": e.kimerito}
    if keres.get("test_mode"):
        kibic["debug"] = {"reason": e.ok, "declarer_tricks_claimed": e.cel,
                          "declarer_tricks_dd": e.dd, "worlds_total": e.osszes_vilag}
    return valasz(e.elfogad, _CLAIM_SZOVEG.get(e.ok, "Elfogadom.") if e.elfogad else _CLAIM_ELUTASIT,
                  kibic)
