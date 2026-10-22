"""
LICIT-MAGYARÁZAT — két, szándékosan eltérő tartalmú szolgáltatás.

1. `POST /v1/bridge/explain` — ÉLES, a MohaBridzs szerződés része
   (mohabridzs-ai/1.1). Bárki kérdezheti az asztalnál, az ellenfél is.
   A válasz KIZÁRÓLAG a MEGÁLLAPODÁS: mit jelent a licit a pár
   rendszerében. Kezet nem kap és nem is használ — így szerkezetileg
   képtelen elárulni a lapot. Ha a kérésben mégis jönne `visible_hands`,
   figyelmen kívül hagyjuk.

2. `POST /v1/kibic/magyaraz` — MŰHELY, csak a tanításhoz. Megkapja a
   licitáló kezét is, és elmondja: mit jelent a licit a rendszerben, mit
   licitálna ott a kibic, és MIÉRT (a teljes "miért ez, miért nem az"
   nyommal). Ellenfélnek soha nem szabad kiadni.

A kettő közös magja a `licit_jelentese()`: a jelentés-propagálás, ami a
licitmenetből kényszertárat épít — itt egyetlen licitre, a szabállyal
együtt (alert, szöveg, melyik konvencióból jön).
"""
from __future__ import annotations

import time

from ..domain import ULESEK, vonal
from .licit import LicitHiba, _igeret_json, _menet, _ules, licit_elemzes

NINCS_MEGALLAPODAS = "Nincs rá kifejezett megállapodásunk."


# --- A közös mag -------------------------------------------------------

def licit_jelentese(sorok, paramtar, licitek: list[dict], index: int,
                    oszto: str, prop=None) -> dict:
    """
    Az `index`-edik licit jelentése a rendszerben — KÉZ NÉLKÜL.

    A korábbi licitekből felépített kényszertár kell hozzá (a fésű-kötések
    abból jönnek), de az is csak a licitekből: mindenki látja őket.
    """
    from ..motor.propagal import Propagalo, egyesit

    if not 0 <= index < len(licitek):
        raise LicitHiba(f"Nincs {index}. licit a menetben "
                        f"(0..{len(licitek) - 1})")
    elem = licitek[index]
    u, hivas = elem["ules"], elem["licit"]
    ki: dict = {"index": index, "seat": u, "call": hivas}

    if prop is None:
        prop = Propagalo(sorok, paramtar)
    elotte = licitek[:index]
    tar = prop.kenyszertar(elotte, oszto=oszto).kenyszertar if elotte else None
    parok = prop.motor_ules(u).jelentes_sorokkal(elotte, u, hivas, tar, oszto)

    if hivas == "P" and not parok:
        ki.update({"agreed": True, "alert": False, "text": "Passz",
                   "text_en": "Pass", "shows": None, "forcing": None,
                   "conventions": []})
        return ki
    if not parok:
        ki.update({"agreed": False, "alert": False,
                   "text": NINCS_MEGALLAPODAS,
                   "text_en": "No specific agreement.",
                   "shows": None, "forcing": None, "conventions": []})
        return ki

    szovegek: list[str] = []
    angol: list[str] = []
    for sor, _ in parok:
        t = sor.magyarazat or sor.feltetel_szoveg or ""
        if t and t not in szovegek:
            szovegek.append(t)
        e = getattr(sor, "magyarazat_en", None)
        if e and e not in angol:
            angol.append(e)
    ig = egyesit([ig for _, ig in parok])
    mutat = _igeret_json(ig)
    if mutat and mutat.get("described") == "semmi":
        mutat = None                  # a licit nem szűkít (pl. mesterséges kérdés)
    ki.update({
        "agreed": True,
        "alert": any(getattr(sor, "alert", False) for sor, _ in parok),
        "text": " VAGY ".join(szovegek),
        "text_en": " OR ".join(angol) or None,
        "shows": mutat,
        "forcing": ig.forsz if ig.forsz and ig.forsz != "NEM" else None,
        "conventions": sorted({sor.rendszer_kod for sor, _ in parok}),
        "principle": all(getattr(sor, "szabaly_fajta", "") == "ELV"
                         for sor, _ in parok),
    })
    if len(parok) > 1:
        ki["alternatives"] = len(parok)
    return ki


# --- 1. ÉLES: /v1/bridge/explain --------------------------------------

class MagyarazatHiba(ValueError):
    """Hibás kérés. A hívó HTTP 400-zal fordíthatja le."""


def explain_valasz(keres: dict, betolto) -> dict:
    """
    `POST /v1/bridge/explain` (mohabridzs-ai/1.1).

    Kérés: game.vulnerability, state.dealer, history.auction,
    actor.seat (a MAGYARÁZÓ AI ülése), question.call_index (a kérdezett
    licit sorszáma a history.auction-ben, 0-tól). A kérdezett licitnek a
    magyarázó VONALÁN kell elhangzania: a saját vonalunk megállapodását
    mondjuk el, az ellenfélét nem.
    """
    from .atjaro import _rendszer, drotra

    start = time.time()
    if not isinstance(keres, dict):
        raise MagyarazatHiba("A kérés JSON-objektum legyen")
    allapot = keres.get("state") or {}
    szereplo = keres.get("actor") or {}
    kerdes = keres.get("question") or {}
    ules = str(szereplo.get("seat") or "").upper()
    if ules not in ULESEK:
        raise MagyarazatHiba("Az 'actor.seat' hiányzik vagy hibás")
    try:
        index = int(kerdes.get("call_index"))
    except (TypeError, ValueError) as e:
        raise MagyarazatHiba("A 'question.call_index' egész szám legyen") from e

    menet = (keres.get("history") or {}).get("auction") or []
    try:
        oszto = _ules(allapot.get("dealer"), "state.dealer")
        licitek = _menet(menet, oszto)
    except LicitHiba as e:
        raise MagyarazatHiba(str(e)) from e
    if not 0 <= index < len(licitek):
        raise MagyarazatHiba(f"A 'question.call_index' kívül esik a "
                             f"licitmeneten (0..{len(licitek) - 1})")
    if vonal(licitek[index]["ules"]) != vonal(ules):
        raise MagyarazatHiba(
            "A kérdezett licit nem a magyarázó vonalán hangzott el: az "
            "ellenfél licitjét a saját párja magyarázza")

    from .licit import vonalas_propagalo
    from .profil import vonal_feloldas
    rendszer, par = _rendszer(keres, ules)
    vf = vonal_feloldas(keres, ules)
    # A TESZT MÓD itt csak azt dönti el, mely szabályok élnek (ugyanazok,
    # amikkel a kibic licitált) — kezet ettől sem kap a magyarázat.
    sorok, paramtar = betolto(rendszer, par)
    # az előtte elhangzott ellenfél-licitek az ő rendszerük szerint
    prop = vonalas_propagalo(sorok, paramtar, betolto, ules,
                             vf.get("opponents_system"), vf.get("families"))
    j = licit_jelentese(sorok, paramtar, licitek, index, oszto, prop=prop)
    j["call"] = drotra(j["call"])
    return {
        "request_id": keres.get("request_id"),
        "explanation": j,
        "meta": {"source": "model", "pipeline": "kibic_explain",
                 "elapsed_ms": int((time.time() - start) * 1000),
                 "system": rendszer},
    }


# --- 2. MŰHELY: /v1/kibic/magyaraz ------------------------------------

def magyaraz_muhely(keres: dict, betolto) -> dict:
    """
    `POST /v1/kibic/magyaraz` — a tanításhoz.

    Bemenet: mint a /v1/kibic/licit (hand, seat, dealer, vulnerability,
    auction, system), plusz `call_index`: melyik elhangzott licitet
    vizsgáljuk. A `hand` a licitáló keze (opcionális: nélküle csak a
    jelentés és a megértés jön vissza).

    Kimenet:
      meaning      — ugyanaz, mint a bridge/explain (a megállapodás)
      would_bid    — mit licitált volna ott a kibic ezzel a kézzel, és
                     miért (teljes tanító nyom: considered / why_not)
      matches      — egyezik-e az elhangzott licittel
    """
    if not isinstance(keres, dict):
        raise LicitHiba("A kérés JSON-objektum legyen")
    rendszer = keres.get("system")
    if not rendszer:
        raise LicitHiba("A 'system' mező kötelező")
    oszto = _ules(keres.get("dealer"), "dealer")
    licitek = _menet(keres.get("auction"), oszto)
    try:
        index = int(keres.get("call_index"))
    except (TypeError, ValueError) as e:
        raise LicitHiba("A 'call_index' egész szám legyen") from e
    teszt = keres.get("test_mode")
    if teszt is None:
        sorok, paramtar = betolto(rendszer, keres.get("pair"))
    else:
        sorok, paramtar = betolto(rendszer, keres.get("pair"), bool(teszt))

    ki: dict = {"request_id": keres.get("request_id"), "system": rendszer,
                "meaning": licit_jelentese(sorok, paramtar, licitek, index,
                                           oszto)}
    if keres.get("hand"):
        elhangzott = licitek[index]
        belso = {"hand": keres["hand"], "seat": elhangzott["ules"],
                 "dealer": oszto,
                 "vulnerability": keres.get("vulnerability", "none"),
                 "auction": [{"seat": e["ules"], "call": e["licit"]}
                             for e in licitek[:index]],
                 "system": rendszer, "pair": keres.get("pair"),
                 "debug": True}
        if teszt is not None:
            belso["test_mode"] = teszt
        e = licit_elemzes(belso, betolto)
        ki["would_bid"] = {
            "call": e.get("call"), "source": e.get("source"),
            "explanation": e.get("explanation"), "alert": e.get("alert"),
            "debug": e.get("debug"),
            "constraints": e.get("constraints"),
            "auction_understanding": e.get("auction_understanding"),
        }
        ki["matches"] = (e["call"] == elhangzott["licit"]) \
            if e.get("call") else None
    return ki


# --- 3. KONVENCIÓKÁRTYA: /v1/bridge/card -------------------------------

class KartyaHiba(ValueError):
    """A kért kártya nem adható. `statusz`: a HTTP-kód (400 / 404)."""

    def __init__(self, uzenet: str, statusz: int = 400):
        super().__init__(uzenet)
        self.statusz = statusz


def kartya_valasz(keres: dict, kartya_fn, html_fn=None) -> dict:
    """
    `POST /v1/bridge/card` (mohabridzs-ai/1.1) — két kérdés egy végponton:

    * `system` NÉLKÜL — „partner, mutasd a kártyádat, mit játszunk?”: a
      kérdezett AI-játékos AKTUÁLIS profiljának kártyája (az
      `actor.profile_code`-ból, mint a licitnél).
    * `system`-mel (1.2-TERVEZET) — „mutasd meg ennek a rendszernek a
      kártyáját”: a kért rendszeré, az aktuálistól függetlenül. Csak a
      capabilities `systems` listájában szereplő rendszer kérhető.

    A válasz megmondja, mi a kérdezett AI aktuális rendszere
    (`current_system`), és hogy a kártya azé-e (`current`).
    """
    from .profil import kinalt_rendszerek, profil_feloldas, vonal_feloldas

    if not isinstance(keres, dict):
        raise KartyaHiba("A kérés JSON-objektum legyen")
    prof = dict(profil_feloldas(keres))
    ules = str((keres.get("actor") or {}).get("seat") or "").upper()
    if ules in ULESEK:
        # 1.2: a saját vonal rendszere a game.systems-ből
        v = vonal_feloldas(keres, ules)
        if v["own_source"] == "systems":
            prof["system"] = v["own"]
    kert = keres.get("system") or (keres.get("question") or {}).get("system")
    if kert:
        kert = str(kert).strip()
        cel = profil_feloldas({"actor": {"profile_code": kert}})
        kinalt = {r["system"] for r in kinalt_rendszerek()}
        if not cel["matched"] or cel["system"].upper() not in kinalt:
            raise KartyaHiba(f"Ismeretlen rendszer, vagy nincs kártyája: {kert}. "
                             "A kérhetők listája: GET /v1/bridge/capabilities",
                             404)
        rendszer = cel["system"]
    else:
        rendszer = prof["system"]
    adat = kartya_fn(rendszer)
    ki = {"request_id": keres.get("request_id"),
          "current_system": prof["system"],
          "system": rendszer,
          "name": adat.get("name"),
          "current": rendszer == prof["system"],
          "card": adat}
    if html_fn is not None and str(keres.get("format", "html")).lower() != "json":
        ki["html"] = html_fn(adat)
    return ki


# --- Képességek --------------------------------------------------------

def kepessegek(rendszerek: list[dict] | None = None,
               alap: str | None = None,
               csaladok: list[dict] | None = None) -> dict:
    """
    `GET /v1/bridge/capabilities` — mit tud ez az AI-szolgáltatás.
    `default_system` (1.1): ezt a rendszert játssza. `systems`
    (1.2-TERVEZET): az ismert rendszerek, amelyeknek van kártyájuk.
    """
    ki = {"protocol": "mohabridzs-ai/1.1",
          "accepts": ["mohabridzs-ai/1.0", "mohabridzs-ai/1.1"],
          "endpoints": {"bid": True, "play": True, "explain": True,
                        "card": True},
          "bid_alert": True}
    if alap is not None:
        ki["default_system"] = alap
    if rendszerek is not None:
        ki["systems"] = rendszerek
    # 1.2: a vonalak rendszere (game.systems) a döntésben is hat — a saját
    # és az ellenfél rendszere; a `families` kódjai is küldhetők.
    ki["line_systems"] = True
    # 2026-10-21: a kijátszás lejátszó réteggel — mintavétel a rejtett
    # kezekből, double dummy szűrő, a jelzésrendszer a jó lapok közül választ
    ki["play"] = {"dd_sampling": True, "signals": True, "deliberation_principles": False}
    # a teljes katalógus (család → alaprendszer → rendszer) külön végponton
    ki["endpoints"]["systems"] = True
    ki["systems_catalog"] = "/v1/bridge/systems"
    if csaladok is not None:
        ki["families"] = csaladok
    return ki
