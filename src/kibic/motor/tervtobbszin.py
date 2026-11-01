"""
Többszínű elemző — az adu és egy (vagy több) mellékszín együtt (2026-11-01,
Felvevő tervjáték).

Az egyszínű elemző általánosítása: a vizsgált színek lapjai valódi lapok, az
egyik lehet adu. Így az elemző maga kezeli:
  - a lopást (mi és a védők is), a felüllopást;
  - az adu köreit átmenetként (pl. ♥K most, ♥A később az asztalba) és a
    kiaduzás idejét;
  - a kimagasított lap lehívását a kiaduzás után.
A többi szín átmenetei kezenkénti keretként jönnek be (ennyiszer lehet a
másik kézbe jutni egy nem vizsgált színben); a nem vizsgált színekre dobni
lehet (None).

A cél: legalább k ütés a vizsgált színekben, legfeljebb m vesztéssel, és ha
aduszín is vizsgált, a védőknél ne maradjon adu (különben a többi nyerőnket
ellophatják).

Modell (mint az egyszínű elemzőnél): a felvevő a látott lapokon dönt
(információs halmaz); a védők mindent látnak, a cél ellen játszanak (egyenlőség
esetén a felvevőt minél több vesztésre kényszerítik, a negyedik kéz elviszi az
ütését, aztán a legkisebb lap). A lapok kódja: szín·16 + rang.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations, product
from math import comb

MI = ("X", "Y")
SORREND = {"X": ("X", "V1", "Y", "V2"), "Y": ("Y", "V2", "X", "V1")}
SZINJEL = "SHDC"
LAPJEL = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}


def kod(szin: int, rang: int) -> int:
    """Valódi lap kódja. (Az összevont kis lapok „jelzői” ugyanebben a
    rendszerben: a sáv legnagyobb lapjának rangja, + a védő és a sorszám.)"""
    return (szin * 16 + rang) << 6


def jelzo(szin: int, rang: int, vedo: int, sorszam: int) -> int:
    return ((szin * 16 + rang) << 6) | (vedo << 5) | (sorszam + 1)


def szine(l: int) -> int:
    return l >> 10


def rangja(l: int) -> int:
    return (l >> 6) & 15


def lapjel(l) -> str:
    if l is None:
        return "dob"
    r = rangja(l)
    return "♠♥♦♣"[szine(l)] + LAPJEL.get(r, str(r))


# --- a játék szabályai -----------------------------------------------------------------

def _kepviselok(lapok, ellen, sz: int) -> list[int]:
    """Egy szín lapjai közül az egyenértékűek egyike (a legkisebb)."""
    ki, elozo = [], None
    for l in sorted(x for x in lapok if szine(x) == sz):
        if elozo is not None and not any(szine(e) == sz and elozo < e < l for e in ellen):
            elozo = l
            continue
        ki.append(l)
        elozo = l
    return ki


def _gyoztes(utes, adu: int | None) -> str:
    hivott = szine(utes[0][1])
    lopott = [(u, l) for u, l in utes if l is not None and adu is not None and szine(l) == adu
              and hivott != adu]
    if lopott:
        return max(lopott, key=lambda x: x[1])[0]
    return max(((u, l) for u, l in utes if l is not None and szine(l) == hivott), key=lambda x: x[1])[0]


def _lehetosegek(kezek: dict, u: str, utes, adu, szinek) -> list:
    """A soron lévő kéz választható lapjai (képviselők): színre szín; színhiánynál
    lopás (adu), dobás egy vizsgált színből, vagy dobás kívülről (None)."""
    lapok = kezek[u]
    ellen = (kezek["V1"] | kezek["V2"]) if u in MI else (kezek["X"] | kezek["Y"])
    if not utes:
        return [c for sz in szinek for c in _kepviselok(lapok, ellen, sz)]
    hivott = szine(utes[0][1])
    sajat = _kepviselok(lapok, ellen, hivott)
    if sajat:
        return sajat
    ki = [None]
    for sz in szinek:
        ki += _kepviselok(lapok, ellen, sz)
    return ki


def _vege(kezek, utes, adu):
    uj = {k: v - {l for u, l in utes if u == k and l is not None} for k, v in kezek.items()}
    return uj, _gyoztes(utes, adu)


@lru_cache(maxsize=600_000)
def dd_cel(X, Y, V1, V2, adu, szinek, k: int, m: int) -> int:
    """1, ha a mindent látó felvevő (szabad hívással) legalább k ütést visz
    legfeljebb m vesztéssel, és a végén a védőknél nincs adu."""
    if m < 0:
        return 0
    vedo_adu = adu is not None and any(szine(l) == adu for l in V1 | V2)
    if k <= 0 and not vedo_adu:
        return 1
    if not X and not Y:
        return 0
    for hivo in MI:
        h = X if hivo == "X" else Y
        for c in _lehetosegek({"X": X, "Y": Y, "V1": V1, "V2": V2}, hivo, (), adu, szinek):
            if _cel_rek(X, Y, V1, V2, adu, szinek, SORREND[hivo], ((hivo, c),), k, m):
                return 1
    return 0


@lru_cache(maxsize=600_000)
def _cel_rek(X, Y, V1, V2, adu, szinek, sorrend, utes, k, m) -> int:
    kezek = {"X": X, "Y": Y, "V1": V1, "V2": V2}
    if len(utes) == 4:
        uj, gy = _vege(kezek, utes, adu)
        mienk = gy in MI
        return dd_cel(uj["X"], uj["Y"], uj["V1"], uj["V2"], adu, szinek,
                      k - (1 if mienk else 0), m - (0 if mienk else 1))
    u = sorrend[len(utes)]
    mi = u in MI
    for c in _lehetosegek(kezek, u, utes, adu, szinek):
        v = _cel_rek(X, Y, V1, V2, adu, szinek, sorrend, utes + ((u, c),), k, m)
        if mi and v:
            return 1
        if not mi and not v:
            return 0
    return 0 if mi else 1


def vedo_lap(kezek: dict, sorrend, utes, adu, szinek, k: int, m: int):
    """A védő lapja: a cél ellen; egyenlőségnél a mindent látó felvevőt minél több
    vesztésre kényszeríti; a negyedik kéz elviszi az ütését; aztán dobás / a
    legkisebb lap."""
    return _vedo_lap(kezek["X"], kezek["Y"], kezek["V1"], kezek["V2"], tuple(sorrend), tuple(utes),
                     adu, szinek, k, m)


@lru_cache(maxsize=300_000)
def _vedo_lap(X, Y, V1, V2, sorrend, utes, adu, szinek, k, m):
    kezek = {"X": X, "Y": Y, "V1": V1, "V2": V2}
    u = sorrend[len(utes)]
    opc = _lehetosegek(kezek, u, utes, adu, szinek)
    if len(opc) == 1:
        return opc[0]
    so = tuple(sorrend)
    cel = {c: _cel_rek(X, Y, V1, V2, adu, szinek, so, tuple(utes) + ((u, c),), k, m) for c in opc}
    legk = min(cel.values())
    jelolt = [c for c in opc if cel[c] == legk]
    if len(jelolt) > 1 and legk == 1:
        def min_veszt(c):
            uj = tuple(utes) + ((u, c),)
            return next((mm for mm in range(0, min(m, 13) + 1)
                         if _cel_rek(X, Y, V1, V2, adu, szinek, so, uj, k, mm)), 99)
        mv = {c: min_veszt(c) for c in jelolt}
        legn = max(mv.values())
        jelolt = [c for c in jelolt if mv[c] == legn]
    if len(jelolt) > 1 and len(utes) == 3:
        nyer = [c for c in jelolt if _gyoztes(tuple(utes) + ((u, c),), adu) not in MI]
        if nyer:
            jelolt = nyer
    return min(jelolt, key=lambda c: (c is not None, rangja(c) if c is not None else 0))


# --- a felvevő a látott lapokon ----------------------------------------------------------

@dataclass(frozen=True)
class Feladat:
    X: frozenset                 # a felvevő lapjai a vizsgált színekben (kódok)
    Y: frozenset                 # az asztal lapjai
    kint: frozenset              # a kint lévő lapok a vizsgált színekben
    szinek: tuple                # a vizsgált színek (indexek: 0=♠ … 3=♣)
    adu: int | None = None       # az aduszín, ha vizsgált
    ures1: int = 13              # V1 (X bal keze) kint lévő lapjainak száma (összesen)
    ures2: int = 13
    atm_x: int | None = None     # átmenetek X-be a NEM vizsgált színekben (None: korlátlan)
    atm_y: int | None = None
    hivas: str | None = None     # ki van hívásban ("X"/"Y")
    hossz_korlat: tuple = ()     # ((védő 1/2, szín, min, max), …) — megfigyelt hosszak

    def tartasok(self) -> list[tuple[frozenset, frozenset, int]]:
        """(V1 lapjai, V2 lapjai, súly). Összevonás: a kint lévő lapok, amelyek a mi
        két szomszédos lapunk közé esnek, a mi lapjainkkal szemben egyenértékűek —
        ezekből csak a darabszám számít; a védő ilyen lapjai „jelzők” (a sáv
        rangjával, védőnként sorszámozva), így a megfigyelés sem árul el többet,
        mint a darabszámot. A súly a binomiális együtthatók szorzata. Az egylapos
        sáv lapja valódi lap marad."""
        szinenkent = []
        mi = self.X | self.Y
        for sz in self.szinek:
            lapok = sorted((l for l in self.kint if szine(l) == sz), reverse=True)
            # sávok: a mi lapjaink között
            savok: list[list[int]] = []
            sajat = sorted((l for l in mi if szine(l) == sz), reverse=True)
            for l in lapok:
                hely = sum(1 for x in sajat if x > l)
                while len(savok) <= hely:
                    savok.append([])
                savok[hely].append(l)
            savok = [sv for sv in savok if sv]
            opc = []
            for darabok in product(*[range(len(sv) + 1) for sv in savok]):
                v1, v2 = set(), set()
                for sv, d in zip(savok, darabok):
                    if len(sv) == 1:
                        (v1 if d else v2).add(sv[0])
                        continue
                    top = rangja(sv[0])
                    v1 |= {jelzo(sz, top, 0, i) for i in range(d)}
                    v2 |= {jelzo(sz, top, 1, i) for i in range(len(sv) - d)}
                v1, v2_ = frozenset(v1), frozenset(v2)
                w = 1
                for sv, d in zip(savok, darabok):
                    w *= comb(len(sv), d)
                jo = True
                for ved, ksz, lo, hi in self.hossz_korlat:
                    if ksz == sz:
                        h = len(v1) if ved == 1 else len(lapok) - len(v1)
                        jo = jo and lo <= h <= hi
                if jo:
                    opc.append((v1, v2_, w))
            szinenkent.append(opc)
        n_kint = len(self.kint)
        egyeb = self.ures1 + self.ures2 - n_kint
        ki = []
        for kombo in product(*szinenkent):
            v1 = frozenset().union(*[a for a, _, _ in kombo])
            v2 = frozenset().union(*[b for _, b, _ in kombo])
            w = comb(egyeb, self.ures1 - len(v1)) if 0 <= self.ures1 - len(v1) <= egyeb else 0
            for _, _, d in kombo:
                w *= d
            if w:
                ki.append((v1, v2, w))
        return ki


@dataclass(frozen=True)
class Kimenet:
    utes: int
    vesztes: int
    atm_x: int
    atm_y: int
    siker: bool


class Elemzo:
    def __init__(self, f: Feladat):
        self.f = f
        self.tart = f.tartasok()
        self.W = sum(w for _, _, w in self.tart)
        self._memo: dict = {}
        self.dontes: dict = {}
        self.harmadik: dict = {}
        self.korlatos = f.atm_x is not None or f.atm_y is not None

    def _kezdo(self):
        idx = tuple(range(len(self.tart)))
        ures = frozenset()
        bx = self.f.atm_x if self.f.atm_x is not None else 99
        by = self.f.atm_y if self.f.atm_y is not None else 99
        return idx, ures, (self.f.X, self.f.Y, bx, by, self.f.hivas if self.korlatos else None)

    def W_(self, halmaz) -> float:
        return float(sum(self.tart[i][2] for i in halmaz))

    def megold(self, k: int, m: int = 99) -> tuple[float, frozenset, str]:
        """(P(cél), a sikeres tartások, az első lépés). A kezelés lexikografikus:
        elsősorban a k ütés, másodsorban (ha az nem megy) a k−1 ütés esélye —
        így a kudarc is a lehető legtöbb ütéssel ér véget (a tervező erre építi
        a folytatást)."""
        idx, ures, allapot = self._kezdo()
        s1, s2 = self._ertek(allapot, idx, ures, ures, k, m)
        kulcs = (allapot, idx, ures, ures, k, m)
        akc = self.dontes.get(kulcs)
        leiras = "—" if akc is None else \
            f"{'felvevő' if akc[0] == 'X' else 'asztal'} hív: {lapjel(akc[1])}"
        return self.W_(s1) / self.W, s1, leiras

    def _hivasok(self, allapot, kint_most):
        X, Y, bx, by, hol = allapot
        ki = []
        for hivo in MI:
            h = X if hivo == "X" else Y
            if not h:
                continue
            nbx, nby = bx, by
            if hol is not None and hol != hivo:
                if hivo == "X":
                    if bx <= 0:
                        continue
                    nbx -= 1
                else:
                    if by <= 0:
                        continue
                    nby -= 1
            for sz in self.f.szinek:
                for c in _kepviselok(h, kint_most, sz):
                    ki.append((hivo, c, nbx, nby))
        return ki

    def _kesz(self, i, lej1, lej2, k) -> bool:
        """Elérte-e a célt ez a tartás: k ≤ 0 és a védőknél nincs adu."""
        if k > 0:
            return False
        if self.f.adu is None:
            return True
        v = (self.tart[i][0] - lej1) | (self.tart[i][1] - lej2)
        return not any(szine(l) == self.f.adu for l in v)

    def _ertek(self, allapot, idx, lej1, lej2, k, m):
        """(a k ütést elérő tartások, a k−1 ütést elérő tartások) a legjobb
        folytatással (lexikografikus: előbb a k, aztán a k−1)."""
        X, Y = allapot[0], allapot[1]
        ures = frozenset()
        if m < 0 or not idx:
            return ures, ures
        kesz1 = frozenset(i for i in idx if self._kesz(i, lej1, lej2, k))
        kesz2 = frozenset(i for i in idx if i not in kesz1 and self._kesz(i, lej1, lej2, k - 1))
        maradt = tuple(i for i in idx if i not in kesz1)
        if not maradt:
            return kesz1, kesz1
        if not X and not Y:
            return kesz1, kesz1 | kesz2
        kulcs = (allapot, maradt, lej1, lej2, k, m)
        if kulcs in self._memo:
            r1, r2 = self._memo[kulcs]
        else:
            maradek = [(self.tart[i][0] - lej1, self.tart[i][1] - lej2) for i in maradt]
            kint_most = frozenset().union(*[a | b for a, b in maradek])
            legjobb, akc = None, None
            for hivo, c, nbx, nby in self._hivasok(allapot, kint_most):
                v = self._utes(allapot, nbx, nby, maradt, lej1, lej2, k, m, hivo, c, maradek, kulcs)
                if legjobb is None or (self.W_(v[0]), self.W_(v[1])) > (self.W_(legjobb[0]), self.W_(legjobb[1])):
                    legjobb, akc = v, (hivo, c)
            r1, r2 = legjobb if legjobb else (ures, ures)
            self._memo[kulcs] = (r1, r2)
            self.dontes[kulcs] = akc
        return kesz1 | r1, kesz1 | kesz2 | r2

    def _csoport(self, X, Y, maradek, js, sorrend, utes, k, m):
        cs: dict = {}
        for j in js:
            v1, v2 = maradek[j]
            kezek = {"X": X, "Y": Y, "V1": v1, "V2": v2}
            cs.setdefault(vedo_lap(kezek, sorrend, utes, self.f.adu, self.f.szinek, k, m), []).append(j)
        return cs

    def _utes(self, allapot, nbx, nby, idx, lej1, lej2, k, m, hivo, c, maradek, kulcs, kimenet=None):
        X, Y, bx, by, hol = allapot
        sorrend = SORREND[hivo]
        harmadik = sorrend[2]
        o1, o2 = frozenset(), frozenset()
        for l2, js in self._csoport(X, Y, maradek, range(len(idx)), sorrend, ((hivo, c),), k, m).items():
            kezek0 = {"X": X, "Y": Y,
                      "V1": frozenset().union(*[maradek[j][0] for j in js]),
                      "V2": frozenset().union(*[maradek[j][1] for j in js])}
            utes2 = ((hivo, c), (sorrend[1], l2))
            valaszt = _lehetosegek(kezek0, harmadik, utes2, self.f.adu, self.f.szinek)
            if kimenet is not None:
                valaszt = [self.harmadik.get((kulcs, hivo, c, l2), valaszt[0])]
            legjobb, c3_best = None, None
            for c3 in valaszt:
                utes3 = utes2 + ((harmadik, c3),)
                a1, a2 = frozenset(), frozenset()
                for l4, js4 in self._csoport(X, Y, maradek, js, sorrend, utes3, k, m).items():
                    utes = utes3 + ((sorrend[3], l4),)
                    uj, gy = _vege({"X": X, "Y": Y, "V1": frozenset(), "V2": frozenset()}, utes, self.f.adu)
                    mienk = gy in MI
                    idx2 = tuple(idx[j] for j in js4)
                    l1 = lej1 | {l for u, l in utes if u == "V1" and l is not None}
                    l2_ = lej2 | {l for u, l in utes if u == "V2" and l is not None}
                    k2, m2 = k - (1 if mienk else 0), m - (0 if mienk else 1)
                    uj_hol = (gy if mienk else "-") if hol is not None else None
                    uj_all = (uj["X"], uj["Y"], nbx, nby, uj_hol)
                    if kimenet is not None:
                        ut, ve, ax, ay = kimenet
                        self._lejatszik(uj_all, idx2, l1, l2_, k2, m2,
                                        (ut + (1 if mienk else 0), ve + (0 if mienk else 1),
                                         ax + (bx - nbx), ay + (by - nby)))
                        continue
                    v1, v2 = self._ertek(uj_all, idx2, l1, l2_, k2, m2)
                    a1 |= v1
                    a2 |= v2
                if kimenet is None and (legjobb is None or
                                        (self.W_(a1), self.W_(a2)) > (self.W_(legjobb[0]), self.W_(legjobb[1]))):
                    legjobb, c3_best = (a1, a2), c3
            if kimenet is None:
                self.harmadik[(kulcs, hivo, c, l2)] = c3_best
                o1 |= legjobb[0]
                o2 |= legjobb[1]
        return o1, o2

    # -- a választott kezelés tartásonként --
    def kimenetek(self, k: int, m: int = 99) -> dict[int, Kimenet]:
        self.megold(k, m)
        idx, ures, allapot = self._kezdo()
        self._ki: dict[int, Kimenet] = {}
        self._siker_k = k
        self._lejatszik(allapot, idx, ures, ures, k, m, (0, 0, 0, 0))
        tarak_uritese()
        self._memo.clear()
        return self._ki


    def _lejatszik(self, allapot, idx, lej1, lej2, k, m, szamlalo):
        X, Y = allapot[0], allapot[1]
        ut, ve, ax, ay = szamlalo
        if m < 0:
            for i in idx:
                self._ki.setdefault(i, Kimenet(ut, ve, ax, ay, False))
            return
        for i in idx:
            if self._kesz(i, lej1, lej2, k):
                self._ki[i] = Kimenet(ut, ve, ax, ay, True)             # a cél megvan
            elif self._kesz(i, lej1, lej2, k - 1):
                self._ki[i] = Kimenet(ut, ve, ax, ay, False)            # a k−1 megvan (ideiglenesen)
        idx = tuple(i for i in idx if not self._kesz(i, lej1, lej2, k))
        if not idx:
            return
        kulcs = (allapot, idx, lej1, lej2, k, m)
        akc = self.dontes.get(kulcs)
        if akc is None or (not X and not Y):
            for i in idx:
                self._ki.setdefault(i, Kimenet(ut, ve, ax, ay, False))
            return
        hivo, c = akc
        maradek = [(self.tart[i][0] - lej1, self.tart[i][1] - lej2) for i in idx]
        bx, by, hol = allapot[2], allapot[3], allapot[4]
        nbx, nby = bx, by
        if hol is not None and hol != hivo:
            if hivo == "X":
                nbx -= 1
            else:
                nby -= 1
        self._utes(allapot, nbx, nby, idx, lej1, lej2, k, m, hivo, c, maradek, kulcs,
                   kimenet=(ut, ve, ax, ay))

def tarak_uritese() -> None:
    """A mindent látó játék gyorsítótárai (sok memória; futásonként ürítjük)."""
    dd_cel.cache_clear()
    _cel_rek.cache_clear()
    _vedo_lap.cache_clear()
