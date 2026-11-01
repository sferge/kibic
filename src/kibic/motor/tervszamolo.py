"""
A tervező valószínűség-számolója (2026-10-31, Felvevő tervjáték).

A kint lévő lapok minden lehetséges elosztását nem egyenként vesszük sorra,
hanem OSZTÁLYOKBAN: egy osztály színenként megadja a két védő hosszát és a
releváns lapok (a sémák `siker` feltételében szereplő figurák) birtokosát. Az
osztály súlya azoknak a konkrét elosztásoknak a száma, amelyek ebbe esnek
(minden konkrét elosztás egyformán valószínű a tudásállapot mellett). A
rejtett predikátumok (`birtokos`, `figura_hossz`, a védők hossza) az osztályon
pontosan értékelhetők.

A tudásállapot: a megfigyelt lapok (a kint lévő halmaz), a védők üres helyei,
a megfigyelt színhiányok, és a feltevések (pl. „Kelet legalább 5 pikk” a
licitből) — ezek a hosszakra adott kemény korlátok.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from math import comb

from ..domain import SZINEK, Lap, kovetkezo_ules

VEDOK = ("E", "W")


@dataclass(frozen=True)
class Korlat:
    """Egy védő hossza egy színben a KINT LÉVŐ lapok között (min..max)."""
    kez: str
    szin: str
    min: int = 0
    max: int = 13
    tudas: str = "megfigyelt"     # megfigyelt / bizonyitott / feltetelezett (pl. a licitből)


@dataclass
class Osztaly:
    hossz: dict            # (kez, szin) -> a kint lévő lapjai a színben
    birtokos: dict         # releváns Lap -> kéz
    suly: int
    azon: int = 0

    def kezhossz(self, kez: str, sz: str) -> int:
        return self.hossz[(kez, sz)]


def osztalyok(kint: set[Lap], ures: dict[str, int], relevans: set[Lap],
              korlatok: list[Korlat] = ()) -> list[Osztaly]:
    """Az elosztás-osztályok. `ures`: a két védő kint lévő lapjainak száma."""
    vedok = sorted(ures)
    a, b = vedok
    szin_opciok = []
    for sz in SZINEK:
        lapok = [l for l in kint if l.szin == sz]
        rel = sorted((l for l in lapok if l in relevans), key=str)
        egyeb = len(lapok) - len(rel)
        lo = {v: 0 for v in vedok}
        hi = {v: len(lapok) for v in vedok}
        for k in korlatok:
            if k.szin == sz and k.kez in hi:
                lo[k.kez] = max(lo[k.kez], k.min)
                hi[k.kez] = min(hi[k.kez], k.max)
        opciok = []
        for n_a in range(len(lapok) + 1):
            n_b = len(lapok) - n_a
            if not (lo[a] <= n_a <= hi[a] and lo[b] <= n_b <= hi[b]):
                continue
            for r in range(len(rel) + 1):
                for nala in combinations(rel, r):
                    if r > n_a or n_a - r > egyeb:
                        continue
                    db = comb(egyeb, n_a - r)
                    opciok.append((n_a, n_b, frozenset(nala), tuple(rel), db))
        szin_opciok.append((sz, opciok))

    ki: list[Osztaly] = []

    def rek(i: int, maradt_a: int, hossz: dict, birt: dict, suly: int):
        if i == len(szin_opciok):
            if maradt_a == 0:
                ki.append(Osztaly(dict(hossz), dict(birt), suly, len(ki)))
            return
        sz, opciok = szin_opciok[i]
        for n_a, n_b, nala, rel, db in opciok:
            if n_a > maradt_a:
                continue
            hossz[(a, sz)], hossz[(b, sz)] = n_a, n_b
            for l in rel:
                birt[l] = a if l in nala else b
            rek(i + 1, maradt_a - n_a, hossz, birt, suly * db)

    rek(0, ures[a], {}, {}, 1)
    return ki


def rejtett_fogalmak(o: Osztaly) -> dict:
    """A `siker` feltétel nyelve egy osztályon (csak a számoló használja)."""
    def birtokos(l):
        return o.birtokos.get(l)

    def figura_hossz(l):
        k = o.birtokos.get(l)
        return o.hossz[(k, l.szin)] if k else 99

    return {
        "birtokos": birtokos,
        "figura_hossz": figura_hossz,
        "vedo_hossz": lambda k, sz: o.hossz[(k, sz)],
        "bal": lambda k: kovetkezo_ules(k, 1),
        "jobb": lambda k: kovetkezo_ules(k, 3),
        "partner": lambda k: kovetkezo_ules(k, 2),
        "hossz": lambda x: len(x) if x is not None else 0,
    }
