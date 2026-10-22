"""
Önállóan játszható adu (Moha, 2026-09-30).

A szerkesztő: a gém "önállóan" akkor mondható, ha az adu a partner
SIKÉNJÉVEL szemben is játszható. Ezt itt kiszámoljuk: mekkora eséllyel
lesz legfeljebb 1 aduvesztő, ha a partnernek nincs a színből (így
impassz sincs, felülről húzzuk az adut, az ellenfél a legjobban véd).

A számítás pontos: az ellenfél lapjainak minden elosztását a tényleges
valószínűségével (hipergeometrikus) súlyozzuk, és minden elosztásban
minimax-szal számoljuk az aduvesztőt. A kis lapok SZÁMÍTANAK (a 10-es,
9-es): az AKJTxxx jóval erősebb, mint az AKJxxxx.

Néhány érték (legfeljebb 1 aduvesztő esélye):
    AKQJxx 93%   AKQTxx 71%   AKQxxx 62%
    AKQJxxx 99%  AKJTxxx 86%  AKQxxxx 84%  AKJxxxx 52%
    AKQxxxxx 96% AKJxxxxx 74% AKxxxxxx 68% AQxxxxxx 27%
"""
from __future__ import annotations

from functools import lru_cache
from itertools import combinations
from math import comb

RANGOK = "23456789TJQKA"
ALAP_KUSZOB = 2 / 3          # ~ a "8-as AK" szintje (67,8%)


@lru_cache(maxsize=None)
def _vesztok(mi: tuple, ny: tuple, kel: tuple) -> int:
    """Minimax: mi vezetünk minden körben, a két ellenfél követ."""
    if not mi or (not ny and not kel):
        return 0
    legjobb = None
    for i, c in enumerate(mi):
        maradek = mi[:i] + mi[i + 1:]
        legrosszabb = None
        for w in (ny or (None,)):
            ny2 = tuple(x for x in ny if x != w) if w is not None else ny
            for e in (kel or (None,)):
                kel2 = tuple(x for x in kel if x != e) if e is not None else kel
                magas = max([c] + [x for x in (w, e) if x is not None])
                v = (magas != c) + _vesztok(maradek, ny2, kel2)
                if legrosszabb is None or v > legrosszabb:
                    legrosszabb = v
        if legjobb is None or legrosszabb < legjobb:
            legjobb = legrosszabb
    return legjobb


@lru_cache(maxsize=None)
def legfeljebb_egy_veszto(mi: tuple) -> float:
    """`mi`: a saját lapjaink rangja (0 = kettes … 12 = ász) egy színben.
    A partnernek nincs a színből. Visszaad: P(aduvesztő <= 1)."""
    mi = tuple(sorted(mi))
    ok = [r for r in range(13) if r not in mi]
    n = len(mi)
    ossz = jo = 0.0
    for k in range(len(ok) + 1):
        suly = comb(13 + n, 13 - k) / comb(26, 13)
        for ny in combinations(ok, k):
            kel = tuple(r for r in ok if r not in ny)
            ossz += suly
            if _vesztok(mi, tuple(sorted(ny)), kel) <= 1:
                jo += suly
    return jo / ossz if ossz else 0.0


def onallo_adu(kez, szin: str, kuszob: float = ALAP_KUSZOB) -> bool:
    """Önállóan játszható-e az adu a partner sikénjével szemben is."""
    lapok = tuple(RANGOK.index(l.ertek) for l in kez.lapok if l.szin == szin)
    if len(lapok) < 6:
        return False
    return legfeljebb_egy_veszto(lapok) >= kuszob
