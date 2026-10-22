"""
PROFILOK — melyik rendszerben licitál egy AI-játékos.

A PROFIL a MohaBridzs fogalma: az AI-játékos beállítása, amit minden
kérésben elküld (`actor.profile_code`). A kibic ebből dönti el, melyik
rendszer szemüvegén át licitál, magyaráz és melyik kártyát mutatja.

A kibic NEM tárol asztali állapotot: hogy egy játékosnak éppen mi a
profilja, azt a MohaBridzs tartja nyilván, és a kéréssel küldi. A
profilváltás tehát a MohaBridzsben történik; a kibic a következő
kéréstől az új profillal dolgozik. Így sok asztal, sok AI-játékos
párhuzamosan is kiszolgálható egyetlen kibic-példánnyal.

A feloldás sorrendje (`profil_feloldas`):
  1. nincs profilkód                → az alaprendszer (KIBIC_RENDSZER)
  2. a KIBIC_PROFILOK leképzés       → az ott megadott rendszer (és pár)
     (`kod=RENDSZER:pár;kod2=...`)
  3. a kód egy KÍNÁLT rendszer neve  → az a rendszer (kis-nagybetű mindegy:
     (`kibic_stand` → KIBIC_STAND)    a kínált rendszerek listája a
                                       capabilities válaszában van)
  4. egyébként                       → szó nélkül az alaprendszer
     (1.1-ben a MohaBridzs a MODELL nevét küldi, pl. "kibic" — ez nem
     rendszer, hanem azt jelenti: "a saját rendszereddel játssz")

Az 1.1-es működés tehát: egy kibic-példány = egy rendszer (KIBIC_RENDSZER).
A rendszerlista és a rendszer szerinti kártya az 1.2-es tervezethez
készült (doc/mohabridzs-ai-1.2-tervezet.md).

KÍNÁLT rendszer: aktív ALAPRENDSZER vagy RENDSZER, AMELYNEK VAN
KONVENCIÓKÁRTYÁJA (a `rendszer.kartya` ki van töltve). Csak olyan
rendszert kínálunk fel, amit a partner és az ellenfél meg is nézhet.
"""
from __future__ import annotations

import os
from typing import Callable

ALAP_RENDSZER = os.getenv("KIBIC_RENDSZER", "LICREN_STAND")
ALAP_PAR = os.getenv("KIBIC_PAR") or None

# Az ISMERT rendszerek és rendszercsaládok forrása: {KÓD: {"kind", "family"}}
# (ALAPRENDSZER / RENDSZER / RENDSZERCSALAD, kártya nélkül is). A HTTP-réteg
# állítja be; tesztben kézzel.
ISMERT_FORRAS: Callable[[], dict[str, dict]] | None = None

# A rendszercsaládok kódjai (a `rendszer.csalad` értékei).
CSALADOK = ("NATURAL", "STRONG_CLUB", "ACOL", "PRECISION", "POLISH", "EGYEB")
# A Precision nem család, hanem az erős treff család rendszere (2026-10-02):
# ha a MohaBridzs családként küldi, STRONG_CLUB-ként értjük.
CSALAD_ALIAS = {"PRECISION": "STRONG_CLUB"}

# A kínált rendszerek forrása: [{"system", "name", ...}] listát ad.
# A HTTP-réteg állítja be (adatbázisból, gyorsítótárazva); tesztben
# kézzel. Ha nincs beállítva, a 3. lépés kimarad.
KINALT_FORRAS: Callable[[], list[dict]] | None = None


def _lekepzes() -> list[tuple[str, str, str | None]]:
    """A KIBIC_PROFILOK: [(profilkód, rendszer, pár)] — minden híváskor
    frissen olvasva, hogy a tesztek és az újraindítás nélküli
    beállítás is működjön."""
    ki = []
    for tetel in os.getenv("KIBIC_PROFILOK", "").split(";"):
        if "=" not in tetel:
            continue
        p, ertek = tetel.split("=", 1)
        rendszer, _, par = ertek.partition(":")
        if p.strip() and rendszer.strip():
            ki.append((p.strip(), rendszer.strip(), par.strip() or None))
    return ki


def ismert_rendszerek() -> dict[str, dict]:
    """{KÓD: {"kind", "family"}} — az adatbázis rendszerei és családjai,
    kiegészítve a kínált (kártyás) rendszerekkel."""
    ki: dict[str, dict] = {}
    if ISMERT_FORRAS is not None:
        try:
            ki = dict(ISMERT_FORRAS() or {})
        except Exception:              # noqa: BLE001
            ki = {}
    for r in kinalt_rendszerek():
        kod = str(r.get("system") or "").upper()
        if kod and kod not in ki:
            ki[kod] = {"kind": r.get("kind") or "RENDSZER", "family": r.get("family")}
    return ki


def kinalt_rendszerek() -> list[dict]:
    if KINALT_FORRAS is None:
        return []
    try:
        return list(KINALT_FORRAS() or [])
    except Exception:                  # noqa: BLE001 — adatbázis nélkül is licitálunk
        return []


def profil_feloldas(keres: dict | None) -> dict:
    """
    {"profile_code", "system", "pair", "matched", "default"} — a kérésben
    küldött profilból. `matched`: a kód rendszert jelölt-e (belső adat).
    """
    szereplo = (keres or {}).get("actor") or {}
    kod = str(szereplo.get("profile_code") or "").strip()
    if not kod:
        return {"profile_code": None, "system": ALAP_RENDSZER,
                "pair": ALAP_PAR, "matched": False, "default": True}
    for p, rendszer, par in _lekepzes():
        if p == kod:
            return {"profile_code": kod, "system": rendszer, "pair": par,
                    "matched": True, "default": False}
    nagy = kod.upper()
    if any(r.get("system") == nagy for r in kinalt_rendszerek()):
        return {"profile_code": kod, "system": nagy, "pair": None,
                "matched": True, "default": False}
    if nagy == ALAP_RENDSZER.upper():
        return {"profile_code": kod, "system": ALAP_RENDSZER,
                "pair": ALAP_PAR, "matched": True, "default": True}
    return {"profile_code": kod, "system": ALAP_RENDSZER, "pair": ALAP_PAR,
            "matched": False, "default": True}


def rendszer_lista() -> list[dict]:
    """
    A capabilities `systems` listája (1.2-tervezet): a kínált rendszerek.
    """
    alap = ALAP_RENDSZER.upper()
    return [dict({"code": r["system"]},
                 **{k: v for k, v in r.items() if k != "system"},
                 default=r["system"] == alap)
            for r in kinalt_rendszerek()]


# --- A vonalak rendszere a kérésben (1.1: game.systems) ----------------

def _rendszerkod(x) -> str | None:
    s = str(x).strip().upper() if x is not None else ""
    return s or None


def vonal_rendszerek(keres: dict | None, ules: str, sajat: str) -> dict | None:
    """
    A `game.systems` ({"NS": kód|null, "EW": kód|null}) értelmezése a
    döntő ülés szemszögéből. None, ha a MohaBridzs nem küldte.

    1. LÉPCSŐ (most): csak megállapítjuk és naplózzuk — melyik rendszer
    ellen licitálunk, ismerjük-e, és egyezik-e a saját vonal rendszere
    azzal, amit ez a példány játszik. A licitdöntést még nem befolyásolja.
    """
    from ..domain import vonal
    rendszerek = ((keres or {}).get("game") or {}).get("systems")
    if not isinstance(rendszerek, dict):
        return None
    mi = vonal(ules)
    ok = "EW" if mi == "NS" else "NS"
    sajat_kuldott = _rendszerkod(rendszerek.get(mi))
    ellen = _rendszerkod(rendszerek.get(ok))
    ismert = {r.get("system") for r in kinalt_rendszerek()}
    ki: dict = {"own": sajat_kuldott, "opponents": ellen,
                "opponents_known": (ellen in ismert) if ellen else None}
    if sajat_kuldott and sajat_kuldott != sajat.upper():
        # A pár mást játszik, mint amire ez a kibic be van állítva: a
        # partner licitjeit félre fogja érteni. Az admin lássa.
        ki["own_mismatch"] = True
    return ki


# --- A vonalak rendszere (mohabridzs-ai/1.2: game.systems) -----------------

def _bejegyzes(x) -> tuple[str | None, str | None]:
    """A game.systems egy értéke: "KOD", vagy {"code": "KOD", "family": "CSALÁD"}."""
    if isinstance(x, dict):
        c = _rendszerkod(x.get("family"))
        return _rendszerkod(x.get("code")), CSALAD_ALIAS.get(c, c)
    return _rendszerkod(x), None


def vonal_feloldas(keres: dict | None, ules: str) -> dict:
    """
    Melyik rendszert játssza a két vonal — a döntő ülés szemszögéből.

    A FORRÁS a `game.systems` ({"NS": …, "EW": …}); egy érték lehet ismert
    rendszer kódja, rendszercsalád kódja (pl. "STRONG_CLUB"), vagy
    {"code": …, "family": …} (ismeretlen rendszer ismert családdal).

    * saját vonal: a `game.systems` ismert RENDSZER/ALAPRENDSZER kódja;
      ha nincs (régi kliens, ismeretlen kód, vagy csak család), a profil
      (3.2) — ezt a `own_source` jelzi;
    * ellenfél: az ismert rendszere (ezzel érti a licitjeiket), vagy csak
      a családja (a család általános rendszere, ha van ilyen az
      adatbázisban), vagy semmi (a régi működés: a saját rendszerünk
      szerint).
    """
    from ..domain import vonal
    prof = profil_feloldas(keres)
    mi = vonal(ules)
    ok = "EW" if mi == "NS" else "NS"
    rs = ((keres or {}).get("game") or {}).get("systems")
    ismert = ismert_rendszerek()

    def jatszhato(kod):
        return kod is not None and (ismert.get(kod) or {}).get("kind") in (
            "ALAPRENDSZER", "RENDSZER")

    ki: dict = {"sent": isinstance(rs, dict)}
    sajat_kod, sajat_csalad = _bejegyzes((rs or {}).get(mi)) if isinstance(rs, dict) else (None, None)
    if jatszhato(sajat_kod):
        ki.update(own=sajat_kod, own_source="systems")
    else:
        ki.update(own=prof["system"],
                  own_source="default" if prof["default"] and not prof["matched"] else "profile")
    ki["own_sent"] = sajat_kod
    if sajat_kod and sajat_kod != ki["own"].upper():
        ki["own_mismatch"] = True

    e_kod, e_csalad = _bejegyzes((rs or {}).get(ok)) if isinstance(rs, dict) else (None, None)
    e_rendszer = None
    if e_kod and e_kod not in ismert and e_kod in CSALAD_ALIAS:
        e_csalad = e_csalad or CSALAD_ALIAS[e_kod]     # "PRECISION" -> STRONG_CLUB
    elif e_kod and e_kod in ismert:
        e_rendszer = e_kod                         # ismert rendszer vagy család
        e_csalad = e_csalad or ismert[e_kod].get("family")
    elif e_kod in CSALADOK:
        e_csalad = e_kod
    if e_rendszer is None and e_csalad and e_csalad in ismert:
        e_rendszer = e_csalad                      # a család általános rendszere
    ki.update(opponents=e_kod, opponents_system=e_rendszer,
              opponents_family=e_csalad,
              opponents_known=(e_rendszer is not None) if e_kod or e_csalad else None)
    sajat_csalad = sajat_csalad or (ismert.get(ki["own"].upper()) or {}).get("family")
    ki["families"] = {mi: sajat_csalad, ok: e_csalad}
    return ki
