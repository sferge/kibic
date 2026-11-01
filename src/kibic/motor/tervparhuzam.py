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


def _elso_lepes(el, e: Elemzes, egyszinu: bool):
    """A kezelés első lépése (az élő játékhoz): (hívó "X"/"Y", lap, {a 2. kéz
    lapja: a 3. kéz lapja}). Egyszínűnél a lapok rangok, többszínűnél kódok."""
    try:
        if egyszinu:
            idx, ures, *_ = el._kezdo()
            kulcs = (el.legjobb_allapot, idx, ures, ures, e.k, e.m)
        else:
            idx, ures, allapot = el._kezdo()
            kulcs = (allapot, idx, ures, ures, e.k, e.m)
        akc = el.dontes.get(kulcs)
        if akc is None:
            return None
        harmadik = {l2: c3 for (kk, h, cc, l2), c3 in el.harmadik.items()
                    if kk == kulcs and (h, cc) == akc}
        return (akc[0], akc[1], harmadik if egyszinu else {})
    except Exception:          # noqa: BLE001 — az első lépés csak kiegészítő adat
        return None


def kiszamol(e: Elemzes):
    """Egy elemzés (a folyamatban is ez fut)."""
    if e.fajta == "egy":
        from .tervszinkezeles import Elemzo
        el = Elemzo(e.feladat)
        ertek = (el.tart, el.kimenetek(e.k, e.m), _elso_lepes(el, e, True))
    elif e.fajta == "tobb":
        from . import tervtobbszin as tt
        el = tt.Elemzo(e.feladat)
        ertek = (el.tart, el.kimenetek(e.k, e.m), _elso_lepes(el, e, False))
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


def _rss_gb() -> float:
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2**30
    except Exception:
        return 0.0


def _gyorsitotarak_uritese() -> None:
    from . import tervszinkezeles as ts
    from . import tervtobbszin as tt
    for f in (ts.dd_cel, ts._cel_rek, ts.dd, ts._dd_rek):
        f.cache_clear()
    tt.tarak_uritese()
    import gc
    gc.collect()


def _munkas(e: Elemzes):
    """A folyamatban: számol, lemezre ír, és a nagy gyorsítótárakat üríti (a
    folyamat memóriája ne nőjön feladatról feladatra)."""
    ertek = kiszamol(e)
    ut = _ut(e.kulcs)
    if ut:
        MEMORIA.pop(e.kulcs, None)
        tarba(e.kulcs, ertek)
        MEMORIA.pop(e.kulcs, None)
    if e.fajta == "tobb" or _rss_gb() > 1.0:
        _gyorsitotarak_uritese()
    return e.kulcs, ertek


def mp_kontextus():
    """A folyamatok indítása: `KIBIC_MP` (alap: fork; a szolgáltatásban forkserver,
    mert a többszálú folyamat forkja zárakat örökölhet)."""
    return mp.get_context(os.environ.get("KIBIC_MP", "fork"))


def szalak_szama() -> int:
    n = os.environ.get("KIBIC_SZALAK")
    return max(1, int(n)) if n else (os.cpu_count() or 1)


def szabad_memoria_gb() -> float:
    """A felhasználható memória: a gép szabad memóriája, és ha a folyamatcsoportnak
    (konténer) kisebb a kerete, az."""
    szabad = None
    try:
        with open("/proc/meminfo") as f:
            for sor in f:
                if sor.startswith("MemAvailable:"):
                    szabad = int(sor.split()[1]) / 2**20
    except Exception:
        pass
    try:
        with open("/sys/fs/cgroup/memory.max") as f:
            mx = f.read().strip()
        with open("/sys/fs/cgroup/memory.current") as f:
            cur = int(f.read().strip())
        if mx != "max":
            cg = (int(mx) - cur) / 2**30
            szabad = cg if szabad is None else min(szabad, cg)
    except Exception:
        pass
    return szabad if szabad is not None else 8.0


# egy többszínű elemzés legfeljebb ennyi memóriát használ (GB; a 4Q01 #12-n ~4)
TOBB_MEMORIA_GB = float(os.environ.get("KIBIC_TOBB_MEMORIA_GB", "4.5"))


def tobb_szalak_szama() -> int:
    """Egyszerre ennyi többszínű elemzés: a szálak, de a memória is korlátoz
    (KIBIC_SZALAK_TOBB felülírja)."""
    n = os.environ.get("KIBIC_SZALAK_TOBB")
    if n:
        return max(1, int(n))
    return max(1, min(szalak_szama(), int(szabad_memoria_gb() // TOBB_MEMORIA_GB)))


STATISZTIKA = {"szamolt": 0, "korok": 0}


def szamol_mind(elemzesek) -> None:
    """A hiányzó elemzések kiszámolása külön folyamatokban (a fő folyamat
    memóriája így nem nő): a többszínűek a memória szerinti számú folyamatban,
    a többi a szálak számának megfelelőben, egyszerre."""
    egyedi = {e.kulcs: e for e in elemzesek if tarbol(e.kulcs) is None}
    if not egyedi:
        return
    STATISZTIKA["korok"] += 1
    STATISZTIKA["szamolt"] += len(egyedi)
    tobb = [e for e in egyedi.values() if e.fajta == "tobb"]
    egy = [e for e in egyedi.values() if e.fajta != "tobb"]
    ctx = mp_kontextus()
    poolok, jovok = [], []
    try:
        if tobb:
            p = ProcessPoolExecutor(max_workers=min(tobb_szalak_szama(), len(tobb)), mp_context=ctx)
            poolok.append(p)
            jovok += [p.submit(_munkas, e) for e in tobb]
        if egy:
            p = ProcessPoolExecutor(max_workers=min(szalak_szama(), len(egy)), mp_context=ctx)
            poolok.append(p)
            jovok += [p.submit(_munkas, e) for e in egy]
        for j in jovok:
            kulcs, ertek = j.result()
            MEMORIA[kulcs] = ertek
    finally:
        for p in poolok:
            p.shutdown(wait=True, cancel_futures=True)


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
