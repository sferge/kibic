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


OSSZ_MEMO_MAX = 600_000       # az elemzők együttes memóriakerete (állapot)
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
                 k: int, m: int, adu: bool = False, lop_x: int = 0, lop_y: int = 0,
                 atm_x: int | None = None, atm_y: int | None = None, hivas: str | None = None):
        self.f = ts.Feladat(frozenset(X), frozenset(Y), frozenset(kint), max(ures1, 0), max(ures2, 0),
                            max(lop_x, 0), max(lop_y, 0), atm_x, atm_y, hivas, adu)
        self.el = elemzo(self.f)
        self.p, self.sikeres, _ = self.el.megold(k, m)
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
            X, Y = self.node[0][0], self.node[0][1]
            return self.el.harmadik.get((self.node, akcio[0], akcio[1], ts.osztaly(l2, X | Y)))

    def lep(self, utes) -> None:
        """`utes`: ((szerep, rang | None | LOP), …) a játék sorrendjében; None: nem
        adott színt (dobott), LOP: lopott."""
        allapot, idx, l1, l2, k, m = self.node
        X, Y, rx, ry, bx, by, hol = allapot
        lop = {"X": rx, "Y": ry, "V1": 99, "V2": 99}
        uj, ul, mienk, szin = ts._utes_vege({"X": X, "Y": Y, "V1": frozenset(), "V2": frozenset()},
                                            lop, utes)
        v = {s: [c for u, c in utes if u == s and c not in (None, ts.LOP)] for s in ("V1", "V2")}
        ki = {s: any(u == s and c in (None, ts.LOP) for u, c in utes) for s in ("V1", "V2")}
        mi = X | Y

        def megfeleltet(kez: frozenset, latott: list):
            """A látott lapok a tartás lapjaira: a pontos lap, vagy (RELEVANS_LAPOK)
            ugyanannak az osztálynak egy lapja; None, ha nem fér össze."""
            szabad = set(kez)
            ki_ = set()
            for c in latott:
                if c in szabad:
                    t = c
                else:
                    q = ts.osztaly(c, mi)
                    tars = sorted(l for l in szabad if ts.RELEVANS_LAPOK and ts.osztaly(l, mi) == q)
                    if not tars:
                        return None
                    t = tars[0]
                szabad.discard(t)
                ki_.add(t)
            return frozenset(ki_)

        tart, f1, f2 = [], [], []
        for j, i in enumerate(idx):
            a = self.el.tart[i][0] - l1[j]
            b = self.el.tart[i][1] - l2[j]
            ma, mb = megfeleltet(a, v["V1"]), megfeleltet(b, v["V2"])
            if ma is None or mb is None:
                continue
            if ki["V1"] and a - ma:
                continue
            if ki["V2"] and b - mb:
                continue
            tart.append(j)
            f1.append(ma)
            f2.append(mb)
        if ts.HALOTT_TARTAS and getattr(self, "sikeres", None):
            # HALOTT_TARTAS: a terv a gyökérben sikeresnek tervezett tartásokon játszik — a
            # többin (a védők valamely játéka ellen úgyis bukik) a döntés nem áldozhat élő
            # tartást (MB 49: a második kőrimpassz, nem a K lehívása); ha egyik sem maradt,
            # minden még lehetséges tartás számít (a régi viselkedés)
            tervezett = [n for n, j in enumerate(tart) if idx[j] in self.sikeres]
            if tervezett:
                tart = [tart[n] for n in tervezett]
                f1 = [f1[n] for n in tervezett]
                f2 = [f2[n] for n in tervezett]
        idx2 = tuple(idx[j] for j in tart)
        l1n = tuple(l1[j] | f1[n] for n, j in enumerate(tart))
        l2n = tuple(l2[j] | f2[n] for n, j in enumerate(tart))
        k2 = k - (1 if szin else 0)
        m2 = m - (0 if mienk else 1)
        uj_hol = None
        if hol is not None:
            # átmenetkorlát mellett: a hívás másik kézből egy átmenetet vitt; utána a
            # nyerő kéz hív (a védő nyerése után: „-”, bármelyik kezünk egy átmenettel)
            hivo = utes[0][0]
            if hivo in ("X", "Y") and hol != hivo:
                bx, by = (bx - 1, by) if hivo == "X" else (bx, by - 1)
            gy = ts._gyoztes(utes)
            uj_hol = gy if gy in ("X", "Y") else "-"
        self.node = ((uj["X"], uj["Y"], ul["X"], ul["Y"], bx, by, uj_hol), idx2, l1n, l2n, k2, m2)

    def esely_atmenettel(self, atm_x: int, atm_y: int, hivas: str) -> float:
        """A hátralévő kezelés esélye, ha a színen kívül ennyi átmenet marad, és ez a kéz
        hív (a terv által igényelt átmenetek mérlegeléséhez)."""
        allapot, idx, l1, l2, k, m = self.node
        if not self.el.korlatos or not idx:
            return self.p
        X, Y, rx, ry, *_ = allapot
        w, _ = self.el._ertek((X, Y, rx, ry, atm_x, atm_y, hivas), idx, l1, l2, k, m)
        return w / sum(self.el.tart[i][2] for i in idx)

    def frissit(self, atm_x: int | None, atm_y: int | None, hivas: str | None) -> None:
        """A színen kívüli állapot (átmenetek, ki hív) a valódi játékból: a végrehajtó a
        szín ütései között más színeket is játszik."""
        if atm_x is None or not self.el.korlatos:
            return
        allapot, *rest = self.node
        X, Y, rx, ry, bx, by, hol = allapot
        self.node = ((X, Y, rx, ry, atm_x, atm_y, hivas), *rest)
        if ts.HALOTT_TARTAS and (bx, by, hol) != (atm_x, atm_y, hivas) and rest[0]:
            # a tervezett (sikeres) tartások az új átmenetekkel / hívó kézzel (HALOTT_TARTAS)
            _, sik = self.el._ertek(*self.node)
            self.sikeres = sik
