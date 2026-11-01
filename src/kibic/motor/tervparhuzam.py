"""
Az elemzések gyűlő tára és párhuzamos számítása (2026-11-01, Felvevő tervjáték).

Az egyszínű és a többszínű elemző futásai csak a lapjainktól, a céltól, az
átmenetektől és a hívás helyétől függenek — ugyanaz a kérdés más partiban is
előjön. Ezért:

  - **gyűlő tár**: minden kiszámolt elemzés lemezre kerül (alapból
    `~/.cache/kibic/elemzes`; `KIBIC_ELEMZES_TAR=könyvtár` felülírja,
    `KIBIC_ELEMZES_TAR=ki` kikapcsolja; a régi `KIBIC_SZK_TAR` is jó);
  - **gyűjtő mód**: a tervező értékelés közben nem számol, hanem jelzi a
    hiányzó elemzést (`HianyzoElemzes`); a hiányzókat egyszerre, külön
    folyamatokban számoljuk (`szamol_mind`), aztán az értékelés újrafut.

A folyamatok száma: `KIBIC_SZALAK`, alapból a gép logikai processzorainak
száma (de legfeljebb a feladatok száma). Egy többszínű elemzés 1–2 GB
memóriát is használhat: sok szálon a memória a korlát.
"""
from __future__ import annotations

import dataclasses
import hashlib
import os
import pickle
import tempfile
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
import multiprocessing as mp


# --- gyűlő tár ----------------------------------------------------------------------

def _konyvtar() -> str | None:
    kvt = os.environ.get("KIBIC_ELEMZES_TAR") or os.environ.get("KIBIC_SZK_TAR")
    if kvt in ("ki", "0", "nem"):
        return None
    return kvt or os.path.join(os.path.expanduser("~"), ".cache", "kibic", "elemzes")


def _kanon(x):
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return (type(x).__module__ + "." + type(x).__name__,
                tuple((f.name, _kanon(getattr(x, f.name))) for f in dataclasses.fields(x)))
    if isinstance(x, (frozenset, set)):
        return ("halmaz", tuple(sorted(_kanon(e) for e in x)))
    if isinstance(x, (tuple, list)):
        return tuple(_kanon(e) for e in x)
    if isinstance(x, dict):
        return ("szotar", tuple(sorted((_kanon(k), _kanon(v)) for k, v in x.items())))
    return x


_VERZIO: str | None = None


def verzio() -> str:
    """Az elemzők forrásának ujjlenyomata: ha az elemző változik, a régi tár
    eredményei nem érvényesek (új alkönyvtár)."""
    global _VERZIO
    if _VERZIO is None:
        h = hashlib.sha1()
        kvt = os.path.dirname(os.path.abspath(__file__))
        for nev in ("tervszinkezeles.py", "tervtobbszin.py"):
            with open(os.path.join(kvt, nev), "rb") as f:
                h.update(f.read())
        _VERZIO = h.hexdigest()[:12]
    return _VERZIO


def _ut(kulcs) -> str | None:
    kvt = _konyvtar()
    if not kvt:
        return None
    return os.path.join(kvt, verzio(),
                        hashlib.sha1(repr(_kanon(kulcs)).encode()).hexdigest() + ".pkl")


MEMORIA: dict = {}            # a folyamat saját tára (a lemez előtt)


def tarbol(kulcs):
    if kulcs in MEMORIA:
        return MEMORIA[kulcs]
    ut = _ut(kulcs)
    if ut and os.path.exists(ut):
        try:
            with open(ut, "rb") as f:
                ertek = pickle.load(f)
        except Exception:          # félbemaradt / régi fájl: újraszámoljuk
            return None
        MEMORIA[kulcs] = ertek
        return ertek
    return None


def tarba(kulcs, ertek):
    MEMORIA[kulcs] = ertek
    ut = _ut(kulcs)
    if not ut:
        return ertek
    os.makedirs(os.path.dirname(ut), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ut), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        pickle.dump(ertek, f)
    os.replace(tmp, ut)            # atomi: párhuzamos írók sem rontják el
    return ertek


# --- a feladatok ----------------------------------------------------------------------

@dataclass(frozen=True)
class Elemzes:
    """Egy elemzés: fajta „egy” (egyszínű, kimenetek), „tobb” (többszínű,
    kimenetek) vagy „celok” (egyszínű: minden (k, m) cél esélye és kimenet-
    összegzése a példányok kiválasztásához)."""
    fajta: str
    feladat: object
    k: int = 0
    m: int = 0
    celok: tuple = ()

    @property
    def kulcs(self):
        return (self.fajta, self.feladat, self.k, self.m, self.celok)


class HianyzoElemzes(Exception):
    def __init__(self, elemzes: Elemzes):
        super().__init__(elemzes.fajta)
        self.elemzes = elemzes


def kiszamol(e: Elemzes):
    """Egy elemzés (a folyamatban is ez fut)."""
    if e.fajta == "egy":
        from .tervszinkezeles import Elemzo
        el = Elemzo(e.feladat)
        ertek = (el.tart, el.kimenetek(e.k, e.m))
    elif e.fajta == "tobb":
        from . import tervtobbszin as tt
        el = tt.Elemzo(e.feladat)
        ertek = (el.tart, el.kimenetek(e.k, e.m))
        tt.tarak_uritese()
    elif e.fajta == "celok":
        from collections import Counter
        from .tervszinkezeles import Elemzo
        el = Elemzo(e.feladat)
        ertek = {}
        for k, m in e.celok:
            p = el.megold(k, m)[0]
            if p <= 0:
                ertek[(k, m)] = (p, None)
                continue
            kim = el.kimenetek(k, m)
            ertek[(k, m)] = (p, tuple(sorted(Counter((x.utes, x.vesztes, x.lopas)
                                                     for x in kim.values()).items())))
    else:
        raise ValueError(e.fajta)
    return ertek


def _munkas(e: Elemzes):
    return e.kulcs, tarba(e.kulcs, kiszamol(e))


def szalak_szama() -> int:
    n = os.environ.get("KIBIC_SZALAK")
    return max(1, int(n)) if n else (os.cpu_count() or 1)


STATISZTIKA = {"szamolt": 0, "korok": 0}


def szamol_mind(elemzesek) -> None:
    """A hiányzó elemzések kiszámolása (párhuzamosan, ha több van és több szál)."""
    egyedi = {e.kulcs: e for e in elemzesek if tarbol(e.kulcs) is None}
    if not egyedi:
        return
    STATISZTIKA["korok"] += 1
    STATISZTIKA["szamolt"] += len(egyedi)
    n = min(szalak_szama(), len(egyedi))
    # a drágábbak előre (a többszínű elemzés percekig tarthat)
    sor = sorted(egyedi.values(), key=lambda e: e.fajta != "tobb")
    if n <= 1:
        for e in sor:
            _munkas(e)
        return
    with ProcessPoolExecutor(max_workers=n, mp_context=mp.get_context("fork")) as pool:
        for kulcs, ertek in pool.map(_munkas, sor):
            MEMORIA[kulcs] = ertek


def gyujtve(fv, *args, **kw):
    """fv(...) gyűjtő módban: amíg hiányzó elemzésre fut, kiszámoljuk (egyszerre
    az összes addig ismertté váltat) és újrafuttatjuk."""
    while True:
        try:
            return fv(*args, **kw)
        except HianyzoElemzes as h:
            szamol_mind([h.elemzes])


def ertekel_mind(feladatok: list, fv) -> list:
    """Sok független értékelés (pl. tervek): körönként mindegyik addig fut, amíg
    elemzés hiányzik; a kör hiányzó elemzéseit egyszerre, párhuzamosan számoljuk."""
    ki = [None] * len(feladatok)
    hatra = list(range(len(feladatok)))
    while hatra:
        hiany, maradt = [], []
        for i in hatra:
            try:
                ki[i] = fv(feladatok[i])
            except HianyzoElemzes as h:
                hiany.append(h.elemzes)
                maradt.append(i)
        if hiany:
            szamol_mind(hiany)
        hatra = maradt
    return ki
