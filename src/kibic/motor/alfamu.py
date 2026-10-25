"""
„Ugyanaz a lap minden világban” — egy szintnyi előrelátás a felvevőnek
(αμ, Cazenave–Ventos; itt M = 1, 2026-10-25).

A gond: a DD minden sorsolt világban látja a lapokat, ezért a felvevő KÖVETKEZŐ
döntését is minden világban jól találja el (stratégiai összeolvadás) — egy
impassz vagy lehúzás így minden világban „biztos”. Itt a jelölt lap után a
védők DD szerint (tökéletesen) folytatnak, de a felvevő következő döntésénél
UGYANAZT a lapot kell tennie azokban a világokban, amelyeket a látott lapokból
nem tud megkülönböztetni (a védők addig letett lapjai azonosak). A további
döntések már DD szerint mennek.

A Pavlicek felvevő-partik diagnózisán (85 eredményrontó döntés): 18-at javít;
60 helyes döntésből 1-et ront el.
"""
from __future__ import annotations

import time
from collections import defaultdict

from ..domain import Lap, kovetkezo_ules, vonal
from ..domain.pontozas import imp, pontszam


def _nyero(utes: list[tuple[str, Lap]], adu: str | None) -> str:
    hivott = utes[0][1].szin

    def kulcs(x):
        l = x[1]
        return (2 if adu and l.szin == adu else 1 if l.szin == hivott else 0, l.rang)
    return max(utes, key=kulcs)[0]


def _soron(ul: list[tuple[str, Lap]], kijatszo: str, adu: str | None) -> str:
    n = len(ul)
    if n == 0:
        return kijatszo
    if n % 4 == 0:
        return _nyero(ul[n - 4:], adu)
    return kovetkezo_ules(ul[-1][0])


def _felvevo_utesei(ul: list[tuple[str, Lap]], adu: str | None, oldal: str) -> int:
    return sum(1 for i in range(0, len(ul) - len(ul) % 4, 4)
               if vonal(_nyero(ul[i:i + 4], adu)) == oldal)


def _lap(jel: str) -> Lap:
    return Lap.parse(jel)


def folytatas(allas, lo, c: Lap, dd_fv) -> tuple[tuple, dict[str, int]]:
    """
    Egy világban: a `c` lap után a védők DD szerint (egyenlőségnél a legkisebb
    lappal) a felvevő oldal következő döntéséig. Vissza: (a védők közben letett
    lapjai — ez különbözteti meg a világokat a felvevő szemében, {lap: a felvevő
    végső ütésszáma, ha a következő döntésnél ezt a lapot teszi}).
    """
    k = allas.kontraktus
    adu = allas.adu
    oldal = vonal(allas.felvevo)
    kijatszo = kovetkezo_ules(allas.felvevo)
    ul = list(allas.lejatszott) + [(allas.ules, c)]
    kulcs: list[str] = []
    while len(ul) < 52:
        kov = _soron(ul, kijatszo, adu)
        ered = dd_fv(lo, [str(l) for _, l in ul], k)
        if not ered:
            break
        if vonal(kov) == oldal:
            return tuple(kulcs), {e.lap: e.felvevo_osszesen for e in ered}
        legj = max(e.utesek for e in ered)
        lap = min((_lap(e.lap) for e in ered if e.utesek == legj), key=lambda l: (l.rang, l.szin))
        ul.append((kov, lap))
        kulcs.append(str(lap))
    return tuple(kulcs), {"-": _felvevo_utesei(ul, adu, oldal)}


def ertekeles(allas, vilagok, sulyok, jeloltek: list[Lap], dd_fv,
              hatarido: float | None = None, min_vilag: int = 10) -> tuple[dict[Lap, float], int] | None:
    """
    Jelöltenként a várható érték (IMP-ben a világonkénti legjobbhoz mérve; MP-ben
    a legjobb elérésének aránya), és a ténylegesen megnézett világok száma.
    None, ha az időkeretbe kevesebb mint `min_vilag` világ fért.
    """
    k = allas.kontraktus
    fo = vonal(allas.ules) == vonal(allas.felvevo)
    mp = (getattr(allas, "pontozas", "IMP") or "IMP").upper() == "MP"
    adat: list[tuple[float, dict[Lap, tuple[tuple, dict[str, int]]]]] = []
    for lo, w in zip(vilagok, sulyok):
        if hatarido is not None and time.time() > hatarido:
            break
        if w <= 0:
            continue
        adat.append((w, {c: folytatas(allas, lo, c, dd_fv) for c in jeloltek}))
    if len(adat) < min_vilag:
        return None

    def pont(utes: int) -> int:
        p = pontszam(k, utes, allas.beliallas)
        return p if fo else -p

    # világonként a csúcs: bármely jelölt, bármely folytatás
    csucs = [max(pont(u) for c in jeloltek for u in d[c][1].values()) for _, d in adat]

    def ertek(i: int, utes: int) -> float:
        if mp:
            return 1.0 if pont(utes) >= csucs[i] else 0.0
        return -imp(csucs[i] - pont(utes))

    ki: dict[Lap, float] = {}
    W = sum(w for w, _ in adat)
    for c in jeloltek:
        csop: dict[tuple, list[int]] = defaultdict(list)
        for i, (_, d) in enumerate(adat):
            csop[d[c][0]].append(i)
        ossz = 0.0
        for idx in csop.values():
            lapok = set.intersection(*(set(adat[i][1][c][1]) for i in idx)) or set(adat[idx[0]][1][c][1])

            def v(lap: str) -> float:
                tot = 0.0
                for i in idx:
                    t = adat[i][1][c][1]
                    tot += adat[i][0] * ertek(i, t.get(lap, min(t.values())))
                return tot
            ossz += max(v(l) for l in lapok)
        ki[c] = ossz / W if W else 0.0
    return ki, len(adat)
