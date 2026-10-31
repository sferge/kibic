"""
Egyszínű elemző — a színkezelés taktikai szintje (2026-10-31, Felvevő tervjáték).

Egy színben a két kezünk lapjai és a kint lévő lapok alapján minden k-ra
kiszámolja: melyik kezelés hozza a legnagyobb eséllyel legalább k ütést (a szín
lapjaival), legfeljebb m vesztett ütéssel és legfeljebb R lopással; és a
választott kezelés mellett, hogy a védők mely lehetséges lapjaival sikerül (ez a
tervező `siker` feltétele, osztályonként arányos súllyal).

A modell (a szokásos egyszínű elemzés):
  - a felvevő oldal minden ütés elején bármelyik kezéből hívhat, amelyikben van
    lap a színből (korlátlan átmenet — az átmeneteket a tervező könyveli);
  - a színhiányos kezünk lophat (ha van még lopása): a lopott ütés nem a szín
    ütése és nem vesztés (pl. a lopásos kimagasítás köre); a védők nem lopnak
    (az ELLOPÁS a tervező általános szabálya);
  - a felvevő döntései CSAK a látott lapokon múlnak: a lehetséges védőlapok
    halmazán (információs halmaz) választ, a megfigyelt lapok szerint ágazva;
  - a védők a felvevő célja ellen játszanak, mindent látva (egyenlőségnél a
    felvevő DD-ütéseit csökkentik, aztán a legkisebb lapot teszik);
  - a védők lapjainak súlya a szabad helyekből (alapból 13–13, a priori).

A lapok rangszámok (A=14 … 2=2); a lopás lapja LOP.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from itertools import combinations
from math import comb

RANG = {c: 14 - i for i, c in enumerate("AKQJT98765432")}
JEL = {v: k for k, v in RANG.items()}
LOP = 100                     # a lopás „lapja”: minden színlapot üt
MI = ("X", "Y")


def rangok(s: str) -> frozenset[int]:
    return frozenset(RANG[c] for c in s.upper() if c in RANG)


def jel(lapok) -> str:
    return "".join(JEL[r] for r in sorted(lapok, reverse=True)) or "–"


def _lapjel(c) -> str:
    return "lop" if c == LOP else ("–" if c is None else JEL[c])


# Ülésrend: X, V1 (X bal keze), Y, V2 (Y bal keze).
SORREND = {"X": ("X", "V1", "Y", "V2"), "Y": ("Y", "V2", "X", "V1")}


def _gyoztes(utes) -> str:
    return max((u for u in utes if u[1] is not None), key=lambda u: u[1])[0]


def _kepviselok(lapok, ellen) -> list[int]:
    """Egyenértékű lapok közül a legkisebb (két lap egyenértékű, ha az ellenfél
    egyetlen lapja sincs köztük)."""
    ki, elozo = [], None
    for r in sorted(lapok):
        if elozo is not None and not any(elozo < e < r for e in ellen):
            elozo = r
            continue
        ki.append(r)
        elozo = r
    return ki


def _lehetosegek(kezek: dict, u: str, lop: dict, hivo_szin: bool = True) -> list:
    """A soron lévő kéz választható lapjai (követés; a mi színhiányos kezünk lophat)."""
    lapok = kezek[u]
    if lapok:
        ellen = (kezek["V1"] | kezek["V2"]) if u in MI else (kezek["X"] | kezek["Y"])
        return _kepviselok(lapok, ellen)
    if u in MI and lop.get(u, 0) > 0:
        return [None, LOP]
    return [None]


def _utes_vege(kezek: dict, lop: dict, utes) -> tuple[dict, dict, bool, bool]:
    """(új kezek, új lopások, a mi ütésünk-e, szín-ütés-e)."""
    uj = {k: v - {l for u, l in utes if u == k and l not in (None, LOP)} for k, v in kezek.items()}
    uj_lop = dict(lop)
    for u, l in utes:
        if l == LOP:
            uj_lop[u] -= 1
    gy = _gyoztes(utes)
    mienk = gy in MI
    lopott = any(l == LOP for _, l in utes)
    return uj, uj_lop, mienk, mienk and not lopott


# --- 1. A mindent látó játék (a védők döntéseihez) -----------------------------------

@lru_cache(maxsize=None)
def dd_cel(X, Y, V1, V2, rx: int, ry: int, k: int, m: int) -> int:
    """1, ha a mindent látó felvevő legalább k szín-ütést visz legfeljebb m
    vesztéssel (a cél elérése után a színt nem kell tovább játszani)."""
    if m < 0:
        return 0
    if k <= 0:
        return 1
    if max(len(X), len(Y)) < k:
        return 0
    if not V1 and not V2:
        return 1
    for hivo in MI:
        if not (X if hivo == "X" else Y):
            continue
        for c in _kepviselok(X if hivo == "X" else Y, V1 | V2):
            if _cel_rek(X, Y, V1, V2, rx, ry, SORREND[hivo], ((hivo, c),), k, m):
                return 1
    return 0


@lru_cache(maxsize=None)
def _cel_rek(X, Y, V1, V2, rx, ry, sorrend, utes, k, m) -> int:
    kezek = {"X": X, "Y": Y, "V1": V1, "V2": V2}
    lop = {"X": rx, "Y": ry}
    if len(utes) == 4:
        uj, ul, mienk, szin = _utes_vege(kezek, lop, utes)
        return dd_cel(uj["X"], uj["Y"], uj["V1"], uj["V2"], ul["X"], ul["Y"],
                      k - (1 if szin else 0), m - (0 if mienk else 1))
    u = sorrend[len(utes)]
    vals = [_cel_rek(X, Y, V1, V2, rx, ry, sorrend, utes + ((u, c),), k, m)
            for c in _lehetosegek(kezek, u, lop)]
    return max(vals) if u in MI else min(vals)


@lru_cache(maxsize=None)
def dd(X, Y, V1, V2, rx: int, ry: int) -> int:
    """A mindent látó felvevő szín-ütései (a védők döntéseinek másodlagos mércéje)."""
    if not X and not Y:
        return 0
    if not V1 and not V2:
        return max(len(X), len(Y))
    legjobb = 0
    for hivo in MI:
        h = X if hivo == "X" else Y
        for c in (_kepviselok(h, V1 | V2) if h else []):
            legjobb = max(legjobb, _dd_rek(X, Y, V1, V2, rx, ry, SORREND[hivo], ((hivo, c),)))
    return legjobb


@lru_cache(maxsize=None)
def _dd_rek(X, Y, V1, V2, rx, ry, sorrend, utes) -> int:
    kezek = {"X": X, "Y": Y, "V1": V1, "V2": V2}
    lop = {"X": rx, "Y": ry}
    if len(utes) == 4:
        uj, ul, mienk, szin = _utes_vege(kezek, lop, utes)
        return (1 if szin else 0) + dd(uj["X"], uj["Y"], uj["V1"], uj["V2"], ul["X"], ul["Y"])
    u = sorrend[len(utes)]
    vals = [_dd_rek(X, Y, V1, V2, rx, ry, sorrend, utes + ((u, c),))
            for c in _lehetosegek(kezek, u, lop)]
    return max(vals) if u in MI else min(vals)


def vedo_lap(kezek: dict, lop: dict, sorrend, utes, k: int, m: int):
    """A soron lévő védő lapja: a felvevő célja ellen; egyenlőségnél a DD-ütés
    ellen; aztán a legkisebb lap."""
    u = sorrend[len(utes)]
    if not kezek[u]:
        return None
    X, Y, V1, V2 = kezek["X"], kezek["Y"], kezek["V1"], kezek["V2"]
    legjobb, lap = None, None
    for c in sorted(kezek[u]):
        uj = tuple(utes) + ((u, c),)
        v = (_cel_rek(X, Y, V1, V2, lop["X"], lop["Y"], tuple(sorrend), uj, k, m),
             _dd_rek(X, Y, V1, V2, lop["X"], lop["Y"], tuple(sorrend), uj))
        if legjobb is None or v < legjobb:
            legjobb, lap = v, c
    return lap


# --- 2. A felvevő a látott lapokon (információs halmaz) ------------------------------

@dataclass(frozen=True)
class Feladat:
    X: frozenset            # az egyik kezünk (a felvevő) lapjai a színben
    Y: frozenset            # a másik kezünk (az asztal) lapjai
    kint: frozenset         # a kint lévő lapok
    ures1: int = 13         # V1 (X bal keze) szabad helyei
    ures2: int = 13         # V2 (Y bal keze) szabad helyei
    lop_x: int = 0          # ennyiszer lophat X (ha színhiányos)
    lop_y: int = 0
    atm_x: int | None = None   # átmenetek X-be más színekben (None: korlátlan)
    atm_y: int | None = None
    hivas: str | None = None   # ki van hívásban az elején ("X"/"Y"; None: mindegy)
    adu: bool = False          # aduszín: a maradékot végigjátsszuk (a kis adu is üt)

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


@dataclass(frozen=True)
class Kimenet:
    """Egy tartásra a választott kezelés eredménye (a szín végéig)."""
    utes: int               # szín-ütések
    vesztes: int            # vesztett ütések
    lopas: int              # felhasznált lopások
    atm_x: int              # felhasznált átmenetek X-be
    atm_y: int


class Elemzo:
    """Az információs halmazokon számoló felvevő. Állapot: a két kezünk lapjai,
    a lopások, az átmenetek, ki van hívásban; a még lehetséges tartások és a
    védők eddig lejátszott lapjai. Átmenetkorlát mellett ha a védő viszi az
    ütést, a legrosszabb kezünkbe hív (ő választja, hova jön vissza a hívás)."""

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
        ures = tuple(frozenset() for _ in idx)
        bx = self.f.atm_x if self.f.atm_x is not None else 99
        by = self.f.atm_y if self.f.atm_y is not None else 99
        return idx, ures, bx, by, (self.f.hivas if self.korlatos else None)

    def megold(self, k: int, m: int = 99) -> tuple[float, frozenset, str]:
        """(P(legalább k szín-ütés, legfeljebb m vesztés), a sikeres tartások
        indexei, az első lépés leírása)."""
        idx, ures, bx, by, h0 = self._kezdo()
        legjobb = None
        # a felvevő kevesebb lopással is beérheti (a védők modellje a lopásszámtól
        # függ, ezért az eredmény nem magától monoton): a legjobb lopásszám
        for rx in range(self.f.lop_x + 1):
            for ry in range(self.f.lop_y + 1):
                allapot = (self.f.X, self.f.Y, rx, ry, bx, by, h0)
                w, sikeres = self._ertek(allapot, idx, ures, ures, k, m)
                if legjobb is None or w > legjobb[0] + 1e-9:
                    legjobb = (w, sikeres, allapot)
        w, sikeres, allapot = legjobb
        self.legjobb_allapot = allapot
        kulcs = (allapot, idx, ures, ures, k, m)
        leiras = self._leiras(kulcs) + (f" (lopás: {allapot[2] + allapot[3]})" if allapot[2] + allapot[3] else "")
        return w / self.W, sikeres, leiras

    def esely(self, k: int, m: int = 99) -> tuple[float, str]:
        p, _, l = self.megold(k, m)
        return p, l

    def _leiras(self, kulcs) -> str:
        akc = self.dontes.get(kulcs)
        if akc is None:
            return "—"
        hivo, c = akc
        s = f"{'felvevő' if hivo == 'X' else 'asztal'} hív: {_lapjel(c)}"
        jel2 = [(l2, c3) for (kk, h, cc, l2), c3 in self.harmadik.items() if kk == kulcs and (h, cc) == akc]
        if jel2:
            l2, c3 = min(jel2, key=lambda x: (x[0] is None, x[0] or 0))
            if c3 is not None:
                s += f", ha a 2. kéz kicsit tesz: {_lapjel(c3)}"
        return s

    # -- a lehetséges hívások egy állapotban --
    def _hivasok(self, allapot, kint_most):
        X, Y, rx, ry, bx, by, hol = allapot
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
            for c in _kepviselok(h, kint_most):
                ki.append((hivo, c, nbx, nby))
        return ki

    def _ertek(self, allapot, idx, lej1, lej2, k, m) -> tuple[float, frozenset]:
        X, Y = allapot[0], allapot[1]
        if m < 0:
            return 0.0, frozenset()
        if k <= 0:
            return float(sum(self.tart[i][2] for i in idx)), frozenset(idx)
        if max(len(X), len(Y)) < k:
            return 0.0, frozenset()
        kulcs = (allapot, idx, lej1, lej2, k, m)
        if kulcs in self._memo:
            return self._memo[kulcs]
        maradek = [(self.tart[i][0] - lej1[j], self.tart[i][1] - lej2[j]) for j, i in enumerate(idx)]
        if all(not a and not b for a, b in maradek):
            v = (float(sum(self.tart[i][2] for i in idx)), frozenset(idx))
            self._memo[kulcs] = v
            return v
        kint_most = frozenset().union(*[a | b for a, b in maradek])
        legjobb, akc = (-1.0, frozenset()), None
        for hivo, c, nbx, nby in self._hivasok(allapot, kint_most):
            v = self._utes(allapot, nbx, nby, idx, lej1, lej2, k, m, hivo, c, maradek, kulcs)
            if v[0] > legjobb[0]:
                legjobb, akc = v, (hivo, c)
        if akc is None:
            legjobb = (0.0, frozenset())
        self._memo[kulcs] = legjobb
        self.dontes[kulcs] = akc
        return legjobb

    def _utes_lapjai(self, allapot, idx, maradek, hivo, c, k, m):
        """A 2. kéz lapja tartásonként → csoportok."""
        X, Y, rx, ry = allapot[:4]
        sorrend = SORREND[hivo]
        lop = {"X": rx, "Y": ry}
        csop2: dict = {}
        for j, i in enumerate(idx):
            v1, v2 = maradek[j]
            kezek = {"X": X, "Y": Y, "V1": v1, "V2": v2}
            csop2.setdefault(vedo_lap(kezek, lop, sorrend, [(hivo, c)], k, m), []).append(j)
        return csop2

    def _utes(self, allapot, nbx, nby, idx, lej1, lej2, k, m, hivo, c, maradek, kulcs):
        X, Y, rx, ry, bx, by, hol = allapot
        sorrend = SORREND[hivo]
        lop = {"X": rx, "Y": ry}
        harmadik = sorrend[2]
        ossz_w, ossz_s = 0.0, frozenset()
        for l2, js in self._utes_lapjai(allapot, idx, maradek, hivo, c, k, m).items():
            kezek0 = {"X": X, "Y": Y,
                      "V1": frozenset().union(*[maradek[j][0] for j in js]),
                      "V2": frozenset().union(*[maradek[j][1] for j in js])}
            legjobb, c3_best = (0.0, frozenset()), None
            for c3 in _lehetosegek(kezek0, harmadik, lop):
                csop4: dict = {}
                for j in js:
                    v1, v2 = maradek[j]
                    kezek = {"X": X, "Y": Y, "V1": v1, "V2": v2}
                    l4 = vedo_lap(kezek, lop, sorrend, [(hivo, c), (sorrend[1], l2), (harmadik, c3)], k, m)
                    csop4.setdefault(l4, []).append(j)
                w, s = 0.0, frozenset()
                for l4, js4 in csop4.items():
                    utes = ((hivo, c), (sorrend[1], l2), (harmadik, c3), (sorrend[3], l4))
                    uj, ul, mienk, szin = _utes_vege({"X": X, "Y": Y, "V1": frozenset(), "V2": frozenset()},
                                                     lop, utes)
                    idx2 = tuple(idx[j] for j in js4)
                    l1 = tuple(lej1[j] | {l for u, l in utes if u == "V1" and l is not None} for j in js4)
                    l2_ = tuple(lej2[j] | {l for u, l in utes if u == "V2" and l is not None} for j in js4)
                    k2, m2 = k - (1 if szin else 0), m - (0 if mienk else 1)
                    if mienk or hol is None:
                        uj_hol = _gyoztes(utes) if hol is not None else None
                        vw, vs = self._ertek((uj["X"], uj["Y"], ul["X"], ul["Y"], nbx, nby, uj_hol),
                                             idx2, l1, l2_, k2, m2)
                    else:
                        # a védő viszi: ő választja, melyik kezünkbe hív vissza
                        vw, vs = min((self._ertek((uj["X"], uj["Y"], ul["X"], ul["Y"], nbx, nby, h),
                                                  idx2, l1, l2_, k2, m2) for h in MI), key=lambda x: x[0])
                    w += vw
                    s |= vs
                if w > legjobb[0] or c3_best is None:
                    legjobb, c3_best = (w, s), c3
            self.harmadik[(kulcs, hivo, c, l2)] = c3_best
            ossz_w += legjobb[0]
            ossz_s |= legjobb[1]
        return ossz_w, ossz_s

    # -- a választott kezelés tartásonként (a szín végéig) --
    def kimenetek(self, k: int, m: int = 99) -> dict[int, Kimenet]:
        """Minden tartásra: a (k, m) célra választott kezelés eredménye. A cél
        elérése (vagy kudarca) után a maradékot a mindent látó játék adja (ez már
        csak lehívás); a felhasznált átmenetek a hívások számából."""
        self.megold(k, m)
        allapot = self.legjobb_allapot
        idx, ures, *_ = self._kezdo()
        ki: dict[int, Kimenet] = {}
        self._lejatszik(allapot, idx, ures, ures, k, m, (0, 0, 0, 0, 0), ki)
        return ki

    def _lejatszik(self, allapot, idx, lej1, lej2, k, m, szamlalo, ki):
        X, Y, rx, ry, bx, by, hol = allapot
        kulcs = (allapot, idx, lej1, lej2, k, m)
        akc = self.dontes.get(kulcs)
        if akc is None:
            # vége (vagy cél elérve / elbukott): a maradék a mindent látó játékkal
            # a cél után (vagy ha elbukott): a maradékból csak a biztos nyerők számítanak
            # (a többi kis lap eldobható, lopható — nem kell vesztésre hívni)
            ut, ve, lo, ax, ay = szamlalo
            for j, i in enumerate(idx):
                v1, v2 = self.tart[i][0] - lej1[j], self.tart[i][1] - lej2[j]
                if not (v1 or v2):
                    ki[i] = Kimenet(ut + max(len(X), len(Y)), ve, lo, ax, ay)
                elif self.f.adu:
                    # aduban végigjátsszuk: a mindent látó folytatás ütései és vesztései
                    plusz = dd(X, Y, v1, v2, rx, ry)
                    ki[i] = Kimenet(ut + plusz, ve + max(0, max(len(X), len(Y)) - plusz), lo, ax, ay)
                else:
                    vedo_max = max(v1 | v2)
                    felso = sum(1 for l in X | Y if l > vedo_max)
                    ki[i] = Kimenet(ut + min(felso, max(len(X), len(Y))), ve, lo, ax, ay)
            return
        hivo, c = akc
        maradek = [(self.tart[i][0] - lej1[j], self.tart[i][1] - lej2[j]) for j, i in enumerate(idx)]
        nbx, nby = bx, by
        ut, ve, lo, ax, ay = szamlalo
        if hol is not None and hol != hivo:
            if hivo == "X":
                nbx -= 1
                ax += 1
            else:
                nby -= 1
                ay += 1
        sorrend = SORREND[hivo]
        lop = {"X": rx, "Y": ry}
        harmadik = sorrend[2]
        for l2, js in self._utes_lapjai(allapot, idx, maradek, hivo, c, k, m).items():
            c3 = self.harmadik.get((kulcs, hivo, c, l2))
            csop4: dict = {}
            for j in js:
                v1, v2 = maradek[j]
                kezek = {"X": X, "Y": Y, "V1": v1, "V2": v2}
                l4 = vedo_lap(kezek, lop, sorrend, [(hivo, c), (sorrend[1], l2), (harmadik, c3)], k, m)
                csop4.setdefault(l4, []).append(j)
            for l4, js4 in csop4.items():
                utes = ((hivo, c), (sorrend[1], l2), (harmadik, c3), (sorrend[3], l4))
                uj, ul, mienk, szin = _utes_vege({"X": X, "Y": Y, "V1": frozenset(), "V2": frozenset()},
                                                 lop, utes)
                idx2 = tuple(idx[j] for j in js4)
                l1 = tuple(lej1[j] | {l for u, l in utes if u == "V1" and l is not None} for j in js4)
                l2_ = tuple(lej2[j] | {l for u, l in utes if u == "V2" and l is not None} for j in js4)
                k2, m2 = k - (1 if szin else 0), m - (0 if mienk else 1)
                lopott = sum(1 for _, l in utes if l == LOP)
                sz2 = (ut + (1 if szin else 0), ve + (0 if mienk else 1), lo + lopott, ax, ay)
                if mienk or hol is None:
                    uj_hol = _gyoztes(utes) if hol is not None else None
                    self._lejatszik((uj["X"], uj["Y"], ul["X"], ul["Y"], nbx, nby, uj_hol),
                                    idx2, l1, l2_, k2, m2, sz2, ki)
                else:
                    h = min(MI, key=lambda h: self._ertek((uj["X"], uj["Y"], ul["X"], ul["Y"], nbx, nby, h),
                                                           idx2, l1, l2_, k2, m2)[0])
                    self._lejatszik((uj["X"], uj["Y"], ul["X"], ul["Y"], nbx, nby, h),
                                    idx2, l1, l2_, k2, m2, sz2, ki)


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
