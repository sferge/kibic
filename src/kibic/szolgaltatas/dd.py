"""
Double dummy állás-elemző szolgáltatás.

Egy konkrét játékállásból megmondja a soron lévő játékos MINDEN
játszható lapjára, mi lenne a végeredmény tökéletes folytatás mellett
(`-2`, `-1`, `=`, `+1`...), és mennyit veszít a legjobb laphoz képest.

VISZONY A MOHABRIDZS AI GATEWAY PROTOKOLLHOZ
--------------------------------------------
Ez NEM része a `mohabridzs-ai/1.0` szerződésnek, és nem is lehet: az
döntéshozatalról szól (`deadline_ms`, `legal_actions`, "pontosan egy
Action"), ez pedig UTÓLAGOS ELEMZÉS emberi fogyasztásra. Saját
névtérben él: `POST /v1/kibic/dd`.

A JELÖLÉSEK viszont szándékosan azonosak, hogy a hívó appnak ne kelljen
kétféle konvenciót kezelnie: égtáj `N E S W`, szín `C D H S`, szan `N`,
lap `SA` / `DT`, beliállás `none ns ew both`.

BEMENET
-------
    {
      "request_id": "opcionális, változatlanul visszaadjuk",
      "hands": {"N": ["SA","SK",...], "E": [...], "S": [...], "W": [...]},
      "contract": {"level": 4, "strain": "H", "multiplier": 1},
      "declarer": "S",
      "vulnerability": "ns",
      "play": [{"seat":"W","card":"D2"}, ...]
    }

A `hands` lehet a TELJES kiosztás (52 lap) vagy a MÉG KÉZBEN LÉVŐ lapok
— utóbbi esetben a szolgáltatás a `play` alapján visszaállítja az
eredetit. A `contract` megadható `"4H"` alakú szövegként is, a `play`
pedig lapok sima listájaként (`["D2","D6",...]`), ha a hívónak úgy
kényelmesebb.

FONTOS KORLÁT
-------------
Double dummy elemzés: NYÍLT LAPOKKAL számol. Azt mondja meg, mi lett
volna a legjobb teljes információ birtokában. Emberi hiba megítélésére
FELSŐ KORLÁT — egy gyengébbnek jelölt lap teljesen ésszerű lehetett az
akkori tudás alapján. A válasz `warning` mezője ezt mindig tartalmazza;
érdemes a felhasználónak is megmutatni.
"""
from __future__ import annotations

from ..domain import (Kez, Kontraktus, Lap, Leosztas, SZINEK, ULESEK,
                      kovetkezo_ules, pontszam_ns, vonal)

FIGYELMEZTETES = (
    "Double dummy elemzés: nyílt lapokkal számol, tehát azt mutatja, mi "
    "lett volna a legjobb teljes információ birtokában. A valódi játékban "
    "nem látható minden lap, ezért az itt gyengébbnek jelölt választás is "
    "lehetett teljesen ésszerű."
)

BELI_TERKEP = {"NONE": "NONE", "NS": "NS", "EW": "EW", "BOTH": "ALL",
               "ALL": "ALL", "": "NONE"}


class DdHiba(ValueError):
    """Hibás bemenet. A hívó HTTP 400-zal fordíthatja le."""


# --- Bemenet értelmezése ---------------------------------------------

def _lap(jeloles: str) -> Lap:
    try:
        return Lap.parse(str(jeloles))
    except ValueError as e:
        raise DdHiba(f"Érvénytelen lapjelölés: {jeloles!r}") from e


def _kontraktus(ertek, felvevo: str) -> Kontraktus:
    if isinstance(ertek, dict):
        szint = ertek.get("level")
        szin = str(ertek.get("strain", "")).upper()
        szorzo = int(ertek.get("multiplier", 1) or 1)
        if szin == "N":
            szin = "NT"
        kontra = {1: "", 2: "X", 4: "XX"}.get(szorzo, "")
        if not szint or szin not in ("C", "D", "H", "S", "NT"):
            raise DdHiba(f"Érvénytelen kontraktus: {ertek!r}")
        return Kontraktus(int(szint), szin, kontra, felvevo)
    s = str(ertek or "").upper().replace(" ", "")
    if len(s) >= 2 and s[1] == "N" and (len(s) == 2 or s[2] != "T"):
        s = s[0] + "NT" + s[2:]          # "4N" -> "4NT", "4NX" -> "4NTX"
    k = Kontraktus.parse(s, felvevo)
    if k is None:
        raise DdHiba("Passzolt lapot nem lehet elemezni")
    return k


def _lejatszas(play) -> list[tuple[str | None, Lap]]:
    """A kijátszott lapok időrendben: [(ülés vagy None, Lap), ...]"""
    ki: list[tuple[str | None, Lap]] = []
    for x in play or []:
        if isinstance(x, dict):
            ules = str(x.get("seat", "")).upper()[:1] or None
            if ules and ules not in ULESEK:
                raise DdHiba(f"Érvénytelen égtáj: {x.get('seat')!r}")
            ki.append((ules, _lap(x.get("card"))))
        else:
            ki.append((None, _lap(x)))
    return ki


def _leosztas(hands, lejatszas, oszto: str, beli: str) -> Leosztas:
    """
    A TELJES kiosztás összeállítása. A `hands` lehet a teljes 52 lap,
    vagy a még kézben lévők — utóbbi esetben a kijátszott lapokat
    visszaadjuk a megfelelő kezeknek.
    """
    if isinstance(hands, str):
        return Leosztas.pbn_bol(hands, oszto, beli)
    if not isinstance(hands, dict):
        raise DdHiba("A `hands` mező objektum vagy PBN-szöveg legyen")

    kezek: dict[str, set[Lap]] = {}
    for u in ULESEK:
        if u not in hands:
            raise DdHiba(f"Hiányzik a(z) {u} kéz. A double dummy elemzéshez "
                         f"MIND A NÉGY kéz kell.")
        kezek[u] = {_lap(x) for x in hands[u]}

    ossz = sum(len(v) for v in kezek.values())
    if ossz < 52:
        # A még kézben lévők jöttek: a kijátszott lapokat visszatesszük
        for ules, lap in lejatszas:
            if ules is None:
                raise DdHiba(
                    "Hiányos kezek esetén a `play` elemeinél kell a `seat` "
                    "mező, hogy visszaállítható legyen az eredeti kiosztás")
            kezek[ules].add(lap)
        ossz = sum(len(v) for v in kezek.values())
    if ossz != 52:
        raise DdHiba(f"A kiosztás {ossz} lapot tartalmaz 52 helyett")

    return Leosztas({u: Kez(frozenset(kezek[u])) for u in ULESEK},
                    oszto, beli)


def _eredmeny_jel(utesek: int, kell: int) -> str:
    k = utesek - kell
    return "=" if k == 0 else (f"+{k}" if k > 0 else str(k))


# --- A szolgáltatás ---------------------------------------------------

def dd_elemzes(keres: dict) -> dict:
    """Egy játékállás laponkénti double dummy kiértékelése."""
    from ..solver.dds import lap_elemzes      # lusta import: endplay kell hozzá

    if not isinstance(keres, dict):
        raise DdHiba("A kérés JSON-objektum legyen")

    felvevo = str(keres.get("declarer", "")).upper()[:1]
    if felvevo not in ULESEK:
        raise DdHiba("Hiányzó vagy érvénytelen `declarer`")

    beli = BELI_TERKEP.get(str(keres.get("vulnerability", "none")).upper())
    if beli is None:
        raise DdHiba("A `vulnerability` none / ns / ew / both lehet")

    kontraktus = _kontraktus(keres.get("contract"), felvevo)
    lejatszas = _lejatszas(keres.get("play"))
    leosztas = _leosztas(keres.get("hands"), lejatszas, felvevo, beli)

    if len(lejatszas) >= 52:
        raise DdHiba("A lejátszás már befejeződött")

    # A soron lévő ülés és az eddigi ütések a saját logikánkból
    soron = kovetkezo_ules(kontraktus.felvevo)
    adu = None if kontraktus.szin == "NT" else kontraktus.szin
    aktualis: list[tuple[str, Lap]] = []
    lement = felvevo_eddig = 0
    for i, (ules, lap) in enumerate(lejatszas):
        if ules and ules != soron:
            raise DdHiba(
                f"A {i+1}. lapnál {soron} következne, a kérés szerint {ules}. "
                f"Ellenőrizd a kijátszás sorrendjét.")
        aktualis.append((soron, lap))
        soron = kovetkezo_ules(soron)
        if len(aktualis) == 4:
            lement += 1
            gy = _utes_gyoztes(aktualis, adu)
            if vonal(gy) == vonal(kontraktus.felvevo):
                felvevo_eddig += 1
            soron = gy
            aktualis = []

    ertekelesek = lap_elemzes(leosztas, [str(l) for _, l in lejatszas],
                              kontraktus)
    if not ertekelesek:
        raise DdHiba("Ebből az állásból nincs játszható lap")

    kell = kontraktus.kell_utes
    lapok = [{
        "card": e.lap,
        "declarer_total": e.felvevo_osszesen,
        "result": _eredmeny_jel(e.felvevo_osszesen, kell),
        "score_ns": pontszam_ns(kontraktus, e.felvevo_osszesen, beli),
        "best": e.legjobb,
        "loss": e.veszteseg,
    } for e in ertekelesek]

    return {
        "request_id": keres.get("request_id"),
        "seat": soron,
        "contract": str(kontraktus),
        "declarer": kontraktus.felvevo,
        "vulnerability": keres.get("vulnerability", "none"),
        "needed_tricks": kell,
        "tricks": {
            "completed": lement,
            "declarer_won": felvevo_eddig,
            "defenders_won": lement - felvevo_eddig,
            "remaining": 13 - lement,
            "cards_in_current_trick": len(aktualis),
        },
        "best_cards": [x["card"] for x in lapok if x["best"]],
        "cards": lapok,
        "warning": FIGYELMEZTETES,
    }


def _utes_gyoztes(lapok: list[tuple[str, Lap]], adu: str | None) -> str:
    gyoztes, legjobb = lapok[0]
    for ules, lap in lapok[1:]:
        if lap.szin == legjobb.szin:
            if lap.rang > legjobb.rang:
                gyoztes, legjobb = ules, lap
        elif adu and lap.szin == adu and legjobb.szin != adu:
            gyoztes, legjobb = ules, lap
    return gyoztes
