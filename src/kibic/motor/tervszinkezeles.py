"""
Egyszínű elemző — a színkezelés taktikai szintje (2026-10-31, Felvevő tervjáték).

Egy színben a két kezünk lapjai és a kint lévő lapok alapján minden k-ra
kiszámolja: melyik kezelés hozza a legnagyobb eséllyel legalább k ütést, és
mennyi ez az esély; a választott kezelés mellett a védők minden lehetséges
lapjára az ütések számát (ebből látszik a próba / kockázat, és a terv `siker`
feltétele).

A modell (a szokásos egyszínű elemzés):
  - a felvevő oldal minden ütés elején bármelyik kezéből hívhat (korlátlan
    átmenet — az átmeneteket a tervező külön könyveli);
  - a felvevő döntései CSAK a látott lapokon múlnak: a lehetséges védőlapok
    halmazán (információs halmaz) választ, a megfigyelt lapok szerint ágazva;
  - a védők DD szerint játszanak ebben a színben (mindent látnak; egyenlőségnél
    a legkisebb lappal);
  - a védők lapjainak súlya a szabad helyekből (alapból: 13–13 szabad hely, a
    priori elosztás); a súlyozásról a tervező SZABAD_HELYEK szabálya dönt.

A lapok rangszámok (A=14 … 2=2); egy kéz színhiánya üres halmaz.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations
from math import comb

RANG = {c: 14 - i for i, c in enumerate("AKQJT98765432")}
JEL = {v: k for k, v in RANG.items()}


def rangok(s: str) -> frozenset[int]:
    return frozenset(RANG[c] for c in s.upper() if c in RANG)


def jel(lapok) -> str:
    return "".join(JEL[r] for r in sorted(lapok, reverse=True)) or "–"


# --- 1. A szín DD-értéke (a védők döntéseihez) --------------------------------------
#
# Ülésrend: X (felvevő), V1 (X bal keze), Y (asztal), V2 (Y bal keze).
# Ha X hív: X, V1, Y, V2; ha Y hív: Y, V2, X, V1.

def _gyoztes(utes: list[tuple[str, int | None]]) -> str:
    """A legnagyobb lap ülése (a színhiányos kéz lapja None)."""
    return max((u for u in utes if u[1] is not None), key=lambda u: u[1])[0]


@lru_cache(maxsize=None)
def dd(X: frozenset, Y: frozenset, V1: frozenset, V2: frozenset) -> int:
    """A felvevő oldal ütései ebben a színben, ha mindenki mindent lát
    (ütés elején a felvevő választja a hívó kezet)."""
    if not X and not Y:
        return 0
    if not V1 and not V2:
        return max(len(X), len(Y))
    legjobb = 0
    for hivo in ("X", "Y"):
        h = X if hivo == "X" else Y
        for c in _kepviselok(h, V1 | V2):
            legjobb = max(legjobb, _utes_dd(X, Y, V1, V2, hivo, c))
    return legjobb


def _utes_dd(X, Y, V1, V2, hivo, c) -> int:
    """Egy ütés (a hívó lapja c) DD-értéke és a folytatás."""
    sorrend = ["X", "V1", "Y", "V2"] if hivo == "X" else ["Y", "V2", "X", "V1"]
    kezek = {"X": X, "Y": Y, "V1": V1, "V2": V2}
    return _dd_rek(kezek, sorrend, [(hivo, c)])


def _dd_rek(kezek: dict, sorrend: list, utes: list) -> int:
    return _dd_rek_t(kezek["X"], kezek["Y"], kezek["V1"], kezek["V2"], tuple(sorrend), tuple(utes))


@lru_cache(maxsize=None)
def _dd_rek_t(X, Y, V1, V2, sorrend: tuple, utes: tuple) -> int:
    kezek = {"X": X, "Y": Y, "V1": V1, "V2": V2}
    utes = list(utes)
    i = len(utes)
    if i == 4:
        uj = {k: v - {l for u, l in utes if u == k and l is not None} for k, v in kezek.items()}
        nyert = 1 if _gyoztes(utes) in ("X", "Y") else 0
        return nyert + dd(uj["X"], uj["Y"], uj["V1"], uj["V2"])
    u = sorrend[i]
    lapok = kezek[u]
    if not lapok:
        return _dd_rek_t(X, Y, V1, V2, sorrend, tuple(utes + [(u, None)]))
    vals = [_dd_rek_t(X, Y, V1, V2, sorrend, tuple(utes + [(u, c)]))
            for c in _kepviselok(lapok, _kint(kezek, u))]
    return max(vals) if u in ("X", "Y") else min(vals)


def _kint(kezek: dict, u: str) -> frozenset:
    """A másik oldal lapjai (az egyenértékűséghez)."""
    if u in ("X", "Y"):
        return kezek["V1"] | kezek["V2"]
    return kezek["X"] | kezek["Y"]


def _kepviselok(lapok: frozenset, ellen: frozenset) -> list[int]:
    """Egyenértékű lapok közül egy (a legkisebb): két lap egyenértékű, ha az
    ellenfél egyetlen lapja sincs köztük."""
    ki, elozo = [], None
    for r in sorted(lapok):
        if elozo is not None and not any(elozo < e < r for e in ellen):
            elozo = r
            continue
        ki.append(r)
        elozo = r
    return ki


@lru_cache(maxsize=None)
def dd_cel(X: frozenset, Y: frozenset, V1: frozenset, V2: frozenset, k: int, m: int) -> int:
    """1, ha a mindent látó felvevő legalább k ütést visz, legfeljebb m vesztett
    ütéssel (a cél elérése után a színt nem kell tovább játszani)."""
    if m < 0:
        return 0
    if k <= 0:
        return 1
    if max(len(X), len(Y)) < k:
        return 0
    if not V1 and not V2:
        return 1
    for hivo in ("X", "Y"):
        h = X if hivo == "X" else Y
        for c in _kepviselok(h, V1 | V2):
            sorrend = ("X", "V1", "Y", "V2") if hivo == "X" else ("Y", "V2", "X", "V1")
            if _cel_rek(X, Y, V1, V2, sorrend, ((hivo, c),), k, m):
                return 1
    return 0


@lru_cache(maxsize=None)
def _cel_rek(X, Y, V1, V2, sorrend: tuple, utes: tuple, k: int, m: int) -> int:
    kezek = {"X": X, "Y": Y, "V1": V1, "V2": V2}
    i = len(utes)
    if i == 4:
        uj = {kk: v - {l for u, l in utes if u == kk and l is not None} for kk, v in kezek.items()}
        nyert = _gyoztes(list(utes)) in ("X", "Y")
        return dd_cel(uj["X"], uj["Y"], uj["V1"], uj["V2"], k - (1 if nyert else 0), m - (0 if nyert else 1))
    u = sorrend[i]
    lapok = kezek[u]
    if not lapok:
        return _cel_rek(X, Y, V1, V2, sorrend, utes + ((u, None),), k, m)
    vals = [_cel_rek(X, Y, V1, V2, sorrend, utes + ((u, c),), k, m)
            for c in _kepviselok(lapok, _kint(kezek, u))]
    return max(vals) if u in ("X", "Y") else min(vals)


def vedo_lap(kezek: dict, sorrend: list, utes: list, k: int = 99, m: int = 99) -> int | None:
    """A soron lévő védő lapja: a felvevő célját (k ütés, legfeljebb m vesztés)
    akadályozza a mindent látó felvevő ellen; ha mindegy, a felvevő DD-ütéseit
    csökkenti; ha az is mindegy, a legkisebb lapot teszi."""
    u = sorrend[len(utes)]
    lapok = kezek[u]
    if not lapok:
        return None
    X, Y, V1, V2 = kezek["X"], kezek["Y"], kezek["V1"], kezek["V2"]
    legjobb, lap = None, None
    for c in sorted(lapok):
        uj = tuple(utes) + ((u, c),)
        v = (_cel_rek(X, Y, V1, V2, tuple(sorrend), uj, k, m),
             _dd_rek_t(X, Y, V1, V2, tuple(sorrend), uj))
        if legjobb is None or v < legjobb:
            legjobb, lap = v, c
    return lap


# --- 2. A felvevő: döntés a látott lapokon (információs halmaz) ----------------------

@dataclass(frozen=True)
class Feladat:
    X: frozenset            # a felvevő (vagy az egyik kezünk) lapjai
    Y: frozenset            # a másik kezünk lapjai
    kint: frozenset         # a kint lévő lapok
    ures1: int = 13         # V1 (X bal keze) szabad helyei
    ures2: int = 13         # V2 (Y bal keze) szabad helyei

    def tartasok(self) -> list[tuple[frozenset, frozenset, int]]:
        """(V1 lapjai, V2 lapjai, súly) minden lehetséges elosztásra."""
        n = len(self.kint)
        egyeb = self.ures1 + self.ures2 - n
        ki = []
        for k in range(n + 1):
            w = comb(egyeb, self.ures1 - k) if 0 <= self.ures1 - k <= egyeb else 0
            if not w:
                continue
            for v1 in combinations(sorted(self.kint), k):
                v1 = frozenset(v1)
                ki.append((v1, self.kint - v1, w))
        return ki


class Elemzo:
    def __init__(self, f: Feladat):
        self.f = f
        self.tart = f.tartasok()
        self.W = sum(w for _, _, w in self.tart)
        self._memo: dict = {}
        self.dontes: dict = {}
        self.harmadik: dict = {}

    def esely(self, k: int, m: int = 99) -> tuple[float, str]:
        """P(legalább k ütés, legfeljebb m vesztett ütéssel a színben) a legjobb
        kezeléssel, és az első lépés leírása."""
        idx = tuple(range(len(self.tart)))
        ures = tuple(frozenset() for _ in idx)
        v = self._ertek(self.f.X, self.f.Y, idx, ures, ures, k, m)
        kulcs = (self.f.X, self.f.Y, idx, ures, ures, k, m)
        akc = self.dontes.get(kulcs)
        if akc is not None:
            # a 3. kéz terve, ha a 2. kéz a legkisebb lehetséges lapját teszi
            jel2 = [(l2, c3) for (kk, h, c, l2), c3 in self.harmadik.items()
                    if kk == kulcs and (h, c) == akc]
            if jel2:
                l2, c3 = min(jel2, key=lambda x: (x[0] is None, x[0] or 0))
                return v / self.W, self._leiras(akc) + (f", ha a 2. kéz kicsit tesz: {JEL[c3]}" if c3 else "")
        return v / self.W, self._leiras(akc)

    def _leiras(self, akc) -> str:
        if akc is None:
            return "—"
        hivo, c = akc
        return f"{'felvevő' if hivo == 'X' else 'asztal'} hív: {JEL[c]}"

    def _ertek(self, X, Y, idx: tuple, lej1: tuple, lej2: tuple, k: int, m: int = 99) -> float:
        """Az információs halmaz (idx: a még lehetséges tartások; lej1/lej2: a
        védők eddig LEJÁTSZOTT lapjai tartásonként) értéke: a súlyok összege,
        ahol a legjobb folytatással meglesz a k ütés."""
        if m < 0:
            return 0.0
        if k <= 0:
            return float(sum(self.tart[i][2] for i in idx))
        if max(len(X), len(Y)) < k:
            return 0.0
        kulcs = (X, Y, idx, lej1, lej2, k, m)
        if kulcs in self._memo:
            return self._memo[kulcs]
        maradek = [(self.tart[i][0] - lej1[j], self.tart[i][1] - lej2[j]) for j, i in enumerate(idx)]
        if all(not a and not b for a, b in maradek):
            v = float(sum(self.tart[i][2] for i in idx)) if max(len(X), len(Y)) >= k else 0.0
            self._memo[kulcs] = v
            return v
        kint_most = frozenset().union(*[a | b for a, b in maradek]) if maradek else frozenset()
        legjobb, akc = -1.0, None
        for hivo in ("X", "Y"):
            h = X if hivo == "X" else Y
            for c in _kepviselok(h, kint_most):
                v = self._utes(X, Y, idx, lej1, lej2, k, m, hivo, c, maradek, kulcs)
                if v > legjobb:
                    legjobb, akc = v, (hivo, c)
        self._memo[kulcs] = legjobb
        self.dontes[kulcs] = akc
        return legjobb

    def _utes(self, X, Y, idx, lej1, lej2, k, m, hivo, c, maradek, kulcs=None) -> float:
        sorrend = ["X", "V1", "Y", "V2"] if hivo == "X" else ["Y", "V2", "X", "V1"]
        # 2. kéz (védő): tartásonként a DD-lapja; csoportosítás a lap szerint
        csop2: dict = {}
        for j, i in enumerate(idx):
            v1, v2 = maradek[j]
            kezek = {"X": X, "Y": Y, "V1": v1, "V2": v2}
            l2 = vedo_lap(kezek, sorrend, [(hivo, c)], k, m)
            csop2.setdefault(l2, []).append(j)
        ossz = 0.0
        harmadik = sorrend[2]
        h3 = X if harmadik == "X" else Y
        for l2, js in csop2.items():
            kint_most = frozenset().union(*[maradek[j][0] | maradek[j][1] for j in js])
            valaszt = _kepviselok(h3, kint_most) if h3 else [None]
            legjobb, c3_best = 0.0, None
            for c3 in valaszt:
                # 4. kéz (védő)
                csop4: dict = {}
                for j in js:
                    v1, v2 = maradek[j]
                    kezek = {"X": X, "Y": Y, "V1": v1, "V2": v2}
                    l4 = vedo_lap(kezek, sorrend, [(hivo, c), (sorrend[1], l2), (harmadik, c3)], k, m)
                    csop4.setdefault(l4, []).append(j)
                v = 0.0
                for l4, js4 in csop4.items():
                    utes = [(hivo, c), (sorrend[1], l2), (harmadik, c3), (sorrend[3], l4)]
                    nyert = _gyoztes(utes) in ("X", "Y")
                    uX = X - {l for u, l in utes if u == "X" and l is not None}
                    uY = Y - {l for u, l in utes if u == "Y" and l is not None}
                    idx2 = tuple(idx[j] for j in js4)
                    l1 = tuple(lej1[j] | ({l for u, l in utes if u == "V1" and l is not None}) for j in js4)
                    l2_ = tuple(lej2[j] | ({l for u, l in utes if u == "V2" and l is not None}) for j in js4)
                    v += self._ertek(uX, uY, idx2, l1, l2_, k - (1 if nyert else 0), m - (0 if nyert else 1))
                if v > legjobb or c3_best is None:
                    legjobb, c3_best = v, c3
            if kulcs is not None:
                self.harmadik[(kulcs, hivo, c, l2)] = c3_best
            ossz += legjobb
        return ossz


@dataclass
class Kinalat:
    """A szín kezelési kínálata: k → (esély, az első lépés)."""
    feladat: Feladat
    eselyek: dict = field(default_factory=dict)

    @property
    def biztos(self) -> int:
        return max((k for k, (p, _) in self.eselyek.items() if p >= 1 - 1e-12), default=0)


def kinalat(f: Feladat, m: int = 99) -> Kinalat:
    """k → (P, első lépés), legfeljebb m vesztett ütéssel a színben."""
    e = Elemzo(f)
    ki = Kinalat(f)
    for k in range(1, max(len(f.X), len(f.Y)) + 1):
        p, leiras = e.esely(k, m)
        ki.eselyek[k] = (p, leiras)
        if p <= 0:
            break
    return ki
