"""
Az egyszínű elemző mint végrehajtható színkezelés (2026-11-18, Felvevő tervjáték).

Az elemző (`tervszinkezeles.Elemzo`) egy színben a látott lapokon dönt: minden
információs halmazra (a még lehetséges elosztások és a védők eddigi lapjai) tárolja,
melyik kezünkből melyik lapot hívjuk, és a második kéz lapjára mit tegyen a harmadik.
Ez a modul ezen a döntési fán lépked a valódi lejátszás szerint:

  * `dontes()` — a következő hívás: ("X"/"Y", rang), vagy None, ha a színnek vége
    (a cél teljesült, vagy már egyetlen lehetséges elosztáson sem érhető el);
  * `harmadik(akcio, l2)` — a harmadik kéz lapja a második kéz lapjára;
  * `lep(utes)` — egy lement ütés a színben (bárki hívta): az új információs halmaz
    a megfigyelt lapokkal összeférő elosztásokból. Ha a védő olyan lapot tett, amire az
    elemző nem számított, ugyanazzal az elemzővel onnan számol tovább (a tár megmarad).

Szerepek: X = a felvevő, Y = az asztal, V1 = a felvevő bal keze, V2 = az asztal bal keze.
Az elemzők gyorsítótárban vannak (a feladat szerint): a sorsolt világok sokszor
ugyanazt a színállást adják.
"""
from __future__ import annotations

from . import tervszinkezeles as ts

_TAR: dict = {}


TAR_MAX = 150                 # az elemzők memóriája nagy: legfeljebb ennyit tartunk


def urites() -> None:
    """A gyorsítótárak ürítése (partik között; a mindent látó segédfüggvényeké is)."""
    _TAR.clear()
    for fv in (ts.dd, ts._dd_rek, ts.dd_cel, ts._cel_rek):
        fv.cache_clear()


def elemzo(f: ts.Feladat) -> ts.Elemzo:
    e = _TAR.get(f)
    if e is None:
        if len(_TAR) >= TAR_MAX:
            urites()
        e = ts.Elemzo(f)
        _TAR[f] = e
    return e


class SzinPolitika:
    def __init__(self, X: frozenset, Y: frozenset, kint: frozenset, ures1: int, ures2: int,
                 k: int, m: int, adu: bool = False):
        self.f = ts.Feladat(frozenset(X), frozenset(Y), frozenset(kint), max(ures1, 0), max(ures2, 0),
                            0, 0, None, None, None, adu)
        self.el = elemzo(self.f)
        self.p, _, _ = self.el.megold(k, m)
        allapot = self.el.legjobb_allapot
        idx, ures, *_ = self.el._kezdo()
        self.node = (allapot, idx, ures, ures, k, m)

    @property
    def k(self) -> int:
        return self.node[4]

    @property
    def m(self) -> int:
        return self.node[5]

    def lapjaink(self) -> tuple[frozenset, frozenset]:
        return self.node[0][0], self.node[0][1]

    def dontes(self):
        allapot, idx, l1, l2, k, m = self.node
        if k <= 0 or m < 0 or not idx:
            return None
        self.el._ertek(allapot, idx, l1, l2, k, m)
        return self.el.dontes.get(self.node)

    def harmadik(self, akcio, l2):
        """A harmadik kéz lapja a ténylegesen látott második lapra: minden tartáson,
        amelyből a védő tehette (nem csak a védőmodell szerintieken)."""
        try:
            return self.el.harmadik_megfigyelt(self.node, akcio[0], akcio[1], l2)
        except Exception:                                   # noqa: BLE001
            return self.el.harmadik.get((self.node, akcio[0], akcio[1], l2))

    def lep(self, utes) -> None:
        """`utes`: ((szerep, rang | None | LOP), …) a játék sorrendjében; None: nem
        adott színt (dobott), LOP: lopott."""
        allapot, idx, l1, l2, k, m = self.node
        X, Y, rx, ry, bx, by, hol = allapot
        lop = {"X": rx, "Y": ry, "V1": 99, "V2": 99}
        uj, ul, mienk, szin = ts._utes_vege({"X": X, "Y": Y, "V1": frozenset(), "V2": frozenset()},
                                            lop, utes)
        v = {s: {c for u, c in utes if u == s and c not in (None, ts.LOP)} for s in ("V1", "V2")}
        ki = {s: any(u == s and c in (None, ts.LOP) for u, c in utes) for s in ("V1", "V2")}
        tart = []
        for j, i in enumerate(idx):
            a = self.el.tart[i][0] - l1[j]
            b = self.el.tart[i][1] - l2[j]
            if not (v["V1"] <= a and v["V2"] <= b):
                continue
            if ki["V1"] and a - v["V1"]:
                continue
            if ki["V2"] and b - v["V2"]:
                continue
            tart.append(j)
        idx2 = tuple(idx[j] for j in tart)
        l1n = tuple(l1[j] | frozenset(v["V1"]) for j in tart)
        l2n = tuple(l2[j] | frozenset(v["V2"]) for j in tart)
        k2 = k - (1 if szin else 0)
        m2 = m - (0 if mienk else 1)
        self.node = ((uj["X"], uj["Y"], ul["X"], ul["Y"], bx, by, None), idx2, l1n, l2n, k2, m2)
