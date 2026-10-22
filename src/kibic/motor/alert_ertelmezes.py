"""
AZ ALERT SZÖVEGÉNEK ÉRTELMEZÉSE (2026-10-02).

Ha az ellenfél egy licitjét sem az ő rendszerük (családjuk), sem a mienk
nem írja le, de a MohaBridzs elküldte az asztalnál kapott magyarázatot
(`history.auction[].alert`), abból a szövegből építünk ígéretet — annyit,
amennyi biztosan kiolvasható:

  * pontsáv:   "16+", "11-15", "12–14 pont", "0-7 HCP", "max 10"
  * színhossz: "5+ kőr", "4-es pikk", "6+ ♦", "hosszú treff", "5+ hearts"
  * egyenletes / balanced
  * gyenge / blokk / preempt (pontsáv nélkül: legfeljebb 10)
  * erős treff / strong club (pontsáv nélkül: 16+)
  * természetes / natural: a licitált szín 4+ (szan: egyenletes)

Ami VAGY-ot tartalmaz ("káró vagy mindkét nemes"), abból csak a pont
olvasható ki biztosan: a színeket ilyenkor nem írjuk be (mindegyik ág
lehet igaz). Ami nem olvasható ki, az nyitott marad — a kényszertár a
"mi LEHET" tára, inkább kevesebbet tudjunk, mint rosszat.

A modul magyar és angol szöveget ért; a szótára szándékosan kicsi.
"""
from __future__ import annotations

import re

from .helyzet import Igeret

_SZIN_SZAVAK = {
    "C": ("♣", "treff", "treffek", "clubs", "club"),
    "D": ("♦", "káró", "karo", "diamonds", "diamond"),
    "H": ("♥", "kőr", "kor", "hearts", "heart"),
    "S": ("♠", "pikk", "spades", "spade"),
}
_SZIN_MINTA = "|".join(sorted((re.escape(w) for ws in _SZIN_SZAVAK.values() for w in ws),
                              key=len, reverse=True))
_SZO_SZIN = {w: k for k, ws in _SZIN_SZAVAK.items() for w in ws}
_NEMESEK_SZO = r"(?:nemes(?:ek)?|majors?|M(?=\b))"
_MINOROK_SZO = r"(?:minor(?:ok|s)?|m(?=\b))"

_PONT_SZO = r"(?:pont|p\b|fp|hcp|pts|points?|figurapont)"
_SAV = re.compile(r"(?<![\d+])(\d{1,2})\s*[-–—]\s*(\d{1,2})(?![\d])\s*(" + _PONT_SZO + r")?",
                  re.I)
_PLUSZ = re.compile(r"(?<![\d-])(\d{1,2})\s*\+\s*(" + _PONT_SZO + r")?", re.I)
_MAX = re.compile(r"(?:max(?:imum)?\.?|legfeljebb|at most)\s*(\d{1,2})", re.I)
_HOSSZ = re.compile(
    r"(?<![\d-])(\d{1,2})(\+?)\s*(?:-?(?:es|as|os|ös|ös|lapos|lap|cards?|card)\b)?\s*(?:in\s+)?("
    + _SZIN_MINTA + r")", re.I)
_HOSSZU = re.compile(r"(?:hosszú|long)\s+(" + _SZIN_MINTA + r")", re.I)


def alert_szoveg(alert) -> str | None:
    """Az auction[].alert lehet szöveg vagy {"text": ...} — a szöveg."""
    if isinstance(alert, dict):
        alert = alert.get("text") or alert.get("explanation")
    if alert is None or alert is True or alert is False:
        return None
    return str(alert)


def _szin(szo: str) -> str | None:
    return _SZO_SZIN.get(szo.lower()) or _SZO_SZIN.get(szo)


def alert_igeret(szoveg: str | None, licit: str | None = None) -> Igeret | None:
    """
    Az alert szövegéből kiolvasható ígéret, vagy None, ha semmi biztos nem
    olvasható ki belőle. A `licit` ("1C", "2NT", "X") a "természetes"
    szóhoz kell.
    """
    if not szoveg or not str(szoveg).strip():
        return None
    t = " " + str(szoveg).strip() + " "
    kis = t.lower()
    ig = Igeret(nyilatkozott=True)
    talalt = False
    vagylagos = bool(re.search(r"\b(vagy|or)\b", kis)) or "/" in kis

    # --- pont ---
    pont_lo = pont_hi = None
    for m in _SAV.finditer(t):
        lo, hi, szo = int(m.group(1)), int(m.group(2)), m.group(3)
        if lo > hi or hi > 40:
            continue
        # "5-4" alakú elosztás ne legyen pont: pontnak vesszük, ha a
        # pont szó követi, vagy a felső határ 8+, vagy 0-tól indul
        if szo or hi >= 8 or lo == 0:
            pont_lo, pont_hi = lo, hi
            break
    if pont_lo is None:
        for m in _PLUSZ.finditer(t):
            utana = t[m.end():m.end() + 12]
            if re.match(r"\s*(?:-?(?:es|as|os|ös|lapos|lap|cards?)\b)?\s*(?:in\s+)?(?:"
                        + _SZIN_MINTA + ")", utana, re.I):
                continue                      # "5+ kőr": hossz, nem pont
            v = int(m.group(1))
            if m.group(2) or v >= 8:
                pont_lo = v
                break
    m = _MAX.search(t)
    if m and pont_hi is None:
        pont_hi = int(m.group(1))
    if pont_lo is None and pont_hi is None:
        if re.search(r"erős treff|strong club|precision", kis):
            pont_lo = 16
        elif re.search(r"\b(gyenge|weak|blokk|preempt|kizáró|kizárás)", kis):
            pont_hi = 10
    if pont_lo is not None or pont_hi is not None:
        ig.szukit_pont(pont_lo, pont_hi)
        talalt = True

    # --- színhossz (csak ha nem vagylagos) ---
    if not vagylagos:
        for m in _HOSSZ.finditer(t):
            db, plusz, szo = int(m.group(1)), m.group(2), m.group(3)
            sz = _szin(szo)
            if sz is None or not 1 <= db <= 13:
                continue
            # a pontsávban szereplő szám ne legyen hossz ("11-15 ... kőr")
            if db > 9:
                continue
            ig.hossz_min[sz] = max(ig.hossz_min.get(sz, 0), db)
            if not plusz and re.search(r"pontosan|exactly", kis):
                ig.hossz_max[sz] = min(ig.hossz_max.get(sz, 13), db)
            talalt = True
        for m in _HOSSZU.finditer(t):
            sz = _szin(m.group(1))
            if sz:
                ig.hossz_min[sz] = max(ig.hossz_min.get(sz, 0), 6)
                talalt = True
        if re.search(r"mindkét\s+" + _NEMESEK_SZO + r"|both\s+majors", t, re.I):
            for sz in ("H", "S"):
                ig.hossz_min[sz] = max(ig.hossz_min.get(sz, 0), 4)
            talalt = True
        if re.search(r"mindkét\s+" + _MINOROK_SZO + r"|both\s+minors", t, re.I):
            for sz in ("C", "D"):
                ig.hossz_min[sz] = max(ig.hossz_min.get(sz, 0), 4)
            talalt = True

    if re.search(r"egyenletes|balanced|kiegyensúlyozott", kis):
        for sz in ("C", "D", "H", "S"):
            ig.hossz_min[sz] = max(ig.hossz_min.get(sz, 0), 2)
            ig.hossz_max[sz] = min(ig.hossz_max.get(sz, 13), 5)
        talalt = True

    if (re.search(r"természetes|natural", kis)
            and not re.search(r"nem természetes|not natural|mesterséges|artificial", kis)
            and licit and len(licit) >= 2 and licit[0].isdigit()):
        sz = licit[1:]
        if sz in ("C", "D", "H", "S") and not vagylagos:
            ig.hossz_min[sz] = max(ig.hossz_min.get(sz, 0), 4)
            talalt = True

    return ig if talalt else None
