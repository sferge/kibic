"""
Színtáblázat (2026-11-02, Felvevő tervjáték): egy szín kezelésének pontos esélyei,
egyszer kiszámolva, utána kikereséssel.

Egy szín két kezünkben (X, Y): k ütés esélye legfeljebb m vesztéssel, az egyszínű
elemzővel (a felvevő a látott lapokon dönt, a védők a cél ellen játszanak; átmenet
korlátlan, a hívás helye szabad, a játszma elején: 13-13 szabad hely). A kulcs a
13 rang tulajdonosa felülről („x”: az egyik kezünk, „y”: a másik, „.”: kint), a két
kéz felcserélhető (az esélyek nem függenek attól, melyik a felvevő).

Ha a szín nincs a táblázatban, a közelítés (`kozelites`): a színre a mindent látó
játék (single-suit double dummy) a védők minden lapjára — ez felülről becsül, mert
a tippelést mindig eltalálja (pl. kétirányú impassz).

A táblázat: `KIBIC_SZINTABLA` (alap `~/.cache/kibic/szintabla.pkl`); építése:
`python -m kibic.cli.szintabla --pbn <partik>` (párhuzamosan).
"""
from __future__ import annotations

import os
import pickle
import tempfile
from math import comb

VESZTESEK = (0, 1, 99)          # a táblázat m értékei (99: korlátlan)
MAX_KINT = 9                    # ennél több kint lévő lap (legfeljebb 3 lapunk): közelítés is elég
_TABLA: dict | None = None


def kulcs(X, Y) -> str:
    """X, Y: a két kezünk rangjai (2..14) a színben."""
    s = "".join("x" if r in X else "y" if r in Y else "." for r in range(14, 1, -1))
    t = s.translate(str.maketrans("xy", "yx"))
    return min(s, t)


def _ut() -> str:
    return os.environ.get("KIBIC_SZINTABLA") or os.path.join(
        os.path.expanduser("~"), ".cache", "kibic", "szintabla.pkl")


def tabla() -> dict:
    global _TABLA
    if _TABLA is None:
        try:
            with open(_ut(), "rb") as f:
                _TABLA = pickle.load(f)
        except Exception:          # noqa: BLE001 — nincs még táblázat
            _TABLA = {}
    return _TABLA


def ment(t: dict) -> None:
    ut = _ut()
    os.makedirs(os.path.dirname(ut), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ut), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        pickle.dump(t, f)
    os.replace(tmp, ut)


def szamol(k: str) -> dict:
    """Egy szín pontos esélyei: {m: {k: P(legalább k ütés)}}."""
    from .tervszinkezeles import Elemzo, Feladat
    X = frozenset(14 - i for i, c in enumerate(k) if c == "x")
    Y = frozenset(14 - i for i, c in enumerate(k) if c == "y")
    kint = frozenset(14 - i for i, c in enumerate(k) if c == ".")
    if not X and not Y:
        return {m: {} for m in VESZTESEK}
    if len(kint) > MAX_KINT:
        return kozelites(k)                    # 1–3 lapunk: a felső lapok és egy impassz; a DD elég
    e = Elemzo(Feladat(X, Y, kint))
    ki = {}
    for m in VESZTESEK:
        d = {}
        for kk in range(1, max(len(X), len(Y)) + 1):
            p = e.esely(kk, m)[0]
            d[kk] = p
            if p <= 0:
                break
        ki[m] = d
    from . import tervszinkezeles as ts
    for fv in (ts.dd_cel, ts._cel_rek, ts.dd, ts._dd_rek):
        fv.cache_clear()                       # a folyamat memóriája ne nőjön
    return ki


_KOZELITES: dict = {}


def kozelites(k: str) -> dict:
    """A mindent látó (single-suit DD) esélyek: {99: {k: P}} — felülről becsül."""
    if k in _KOZELITES:
        return _KOZELITES[k]
    ki = _kozelites(k)
    from . import tervszinkezeles as ts
    ts.dd.cache_clear()
    ts._dd_rek.cache_clear()
    if len(_KOZELITES) > 50_000:
        _KOZELITES.clear()
    _KOZELITES[k] = ki
    return ki


def _kozelites(k: str) -> dict:
    from .tervszinkezeles import dd
    X = frozenset(14 - i for i, c in enumerate(k) if c == "x")
    Y = frozenset(14 - i for i, c in enumerate(k) if c == "y")
    kint = sorted(14 - i for i, c in enumerate(k) if c == ".")
    n = len(kint)
    if not X and not Y:
        return {99: {}}
    if n > MAX_KINT:
        # legfeljebb 3 lapunk: a felső (folytonos) lapok ütései, biztosan
        felso = 0
        for c in k:
            if c == ".":
                break
            felso += 1
        felso = min(felso, max(len(X), len(Y)))
        return {99: {kk: 1.0 for kk in range(1, felso + 1)}}
    db: dict = {}
    W = 0
    for maszk in range(1 << n):
        v1 = frozenset(kint[i] for i in range(n) if maszk >> i & 1)
        v2 = frozenset(kint) - v1
        if len(v1) > 13 or len(v2) > 13:
            continue
        w = comb(26 - n, 13 - len(v1)) if 0 <= 13 - len(v1) <= 26 - n else 0
        if not w:
            continue
        t = dd(X, Y, v1, v2, 0, 0)
        db[t] = db.get(t, 0) + w
        W += w
    ki = {}
    for kk in range(1, max(len(X), len(Y)) + 1):
        ki[kk] = sum(w for t, w in db.items() if t >= kk) / W
    return {99: ki}


def eselyek(X, Y, m: int = 99) -> tuple[dict, bool]:
    """{k: P(legalább k ütés)} és hogy pontos-e (a táblázatból) vagy közelítés."""
    k = kulcs(X, Y)
    t = tabla().get(k)
    if t is not None:
        mm = max((x for x in t if x <= m), default=99)
        return t.get(mm, t[99]), k.count(".") <= MAX_KINT
    return kozelites(k)[99], False


def eloszlas(X, Y, m: int = 99) -> tuple[dict, bool]:
    """{t: P(pontosan t ütés)} a színben."""
    p, pontos = eselyek(X, Y, m)
    ki = {}
    kmax = max(p) if p else 0
    for t in range(0, kmax + 1):
        ki[t] = (p.get(t, 1.0) if t else 1.0) - p.get(t + 1, 0.0)
    return {t: v for t, v in ki.items() if v > 1e-12}, pontos


def alapjatek_eselye(D: dict, U: dict, cel: int, m: int = 99) -> tuple[float, float]:
    """Az alapjáték gyors esélye: a négy szín ütés-eloszlása (táblázatból, ha van;
    különben közelítés) függetlennek véve, P(összesen legalább `cel` ütés).
    D, U: {szín: rangok halmaza}. → (esély, a pontos színek aránya)."""
    eloszl = {0: 1.0}
    pontos = 0
    for sz in "SHDC":
        e, ok = eloszlas(D.get(sz, set()), U.get(sz, set()), m)
        pontos += ok
        uj: dict = {}
        for t1, p1 in eloszl.items():
            for t2, p2 in e.items():
                uj[t1 + t2] = uj.get(t1 + t2, 0.0) + p1 * p2
        eloszl = uj
    return sum(p for t, p in eloszl.items() if t >= cel), pontos / 4


def alapjatek_eselye_tempoval(D: dict, U: dict, cel: int) -> tuple[float, float]:
    """Az alapjáték gyors esélye a vesztett ütésekkel együtt: színenként egy cél
    (k ütés, legfeljebb m vesztés; m ∈ {0, 1, 2+}), a színek céljai együtt legalább
    `cel` ütést adnak, és a vesztéseik összege legfeljebb a tartalék (13 − cel);
    a legjobb ilyen célkiosztás esélye (a színek függetlenek; a kombinált esélyek
    nélkül, tehát óvatos). → (esély, a pontos színek aránya)."""
    tartalek = 13 - cel
    allapot = {(0, 0): 1.0}                # (ütések, vesztések) → a legjobb esély
    pontos = 0
    for sz in "SHDC":
        X, Y = D.get(sz, set()), U.get(sz, set())
        opciok = [(0, 0, 1.0)]
        ok_db = 0
        for m, mm in ((0, 0), (1, 1), (99, 2)):
            p, ok = eselyek(X, Y, m)
            ok_db = max(ok_db, ok)
            if m != 99 and not ok:
                continue                   # a közelítésben nincs vesztés-korlátos érték
            opciok += [(k, mm, v) for k, v in p.items() if v > 0]
        pontos += ok_db
        uj: dict = {}
        for (t, l), p0 in allapot.items():
            for k, mm, p in opciok:
                kulcs = (min(cel, t + k), l + mm)
                if kulcs[1] > tartalek:
                    continue
                v = p0 * p
                if v > uj.get(kulcs, 0.0):
                    uj[kulcs] = v
        allapot = uj
    return max((p for (t, _), p in allapot.items() if t >= cel), default=0.0), pontos / 4
