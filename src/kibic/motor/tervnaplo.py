"""
A tervnapló (2026-11-01, Felvevő tervjáték): a kibic partinként megjegyzi a
tervét, és ha a lapok illeszkednek, újratervezés nélkül folytatja.

Az MB-nek ebből semmit nem kell tudnia: a napló a kibic saját munkamemóriája,
fájlban (`KIBIC_TERVNAPLO`, alap `~/.cache/kibic/tervnaplo`; `ki`: kikapcsolva),
a játszma kulcsa szerint (meccs, asztal, leosztás, felvevő) — így újraindítás
és több szolgáltatás-folyamat esetén is megmarad.

A napló tartalma: az állás, ahol a terv készült, a terv (technikák, kiaduzás,
a megfigyelésen múló döntései), a tudás (színhiányok) és a lejátszás hossza
akkor.

Folytatás (`kovetkezo_lap`): a terv útját (a köreit) újra lejátsszuk minden
olyan elosztás-osztályon, amely összefér azzal, ami azóta látszott (a védők
lapjai, színhiányai). Ahol a mi lapjaink eddig pontosan a terv köreit követték,
az osztály a terv egy ágán van; ha minden ilyen osztályon ugyanaz a következő
lap, az a terv lapja — tervezés nélkül. Különben (eltérés, a terv vége, egy
elemzős lépés belseje) None: újratervezés.
"""
from __future__ import annotations

import hashlib
import os
import pickle
import tempfile
from dataclasses import dataclass, field

from ..domain import Lap, kovetkezo_ules, vonal


@dataclass
class Naplo:
    allas: object               # tervsema.Allas — a terv készítésekor
    korlatok: list
    terv: object                # tervezo.TervErtek
    lapok_szama: int            # a lejátszott lapok száma a terv készítésekor
    relevans: set = field(default_factory=set)


def _konyvtar() -> str | None:
    kvt = os.environ.get("KIBIC_TERVNAPLO")
    if kvt in ("ki", "0", "nem"):
        return None
    return kvt or os.path.join(os.path.expanduser("~"), ".cache", "kibic", "tervnaplo")


def _ut(kulcs: str) -> str | None:
    kvt = _konyvtar()
    if not kvt:
        return None
    return os.path.join(kvt, hashlib.sha1(kulcs.encode()).hexdigest() + ".pkl")


def betolt(kulcs: str) -> Naplo | None:
    ut = _ut(kulcs)
    if not ut or not os.path.exists(ut):
        return None
    try:
        with open(ut, "rb") as f:
            return pickle.load(f)
    except Exception:              # noqa: BLE001 — sérült / régi napló: újratervezünk
        return None


def ment(kulcs: str, naplo: Naplo) -> None:
    ut = _ut(kulcs)
    if not ut:
        return
    os.makedirs(os.path.dirname(ut), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(ut), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        pickle.dump(naplo, f)
    os.replace(tmp, ut)


# --- a terv folytatása ---------------------------------------------------------------

def _osszefer(o, vedok, uj: list) -> bool:
    """Az osztály összefér-e azzal, ami a terv óta látszott (a védők lapjai)."""
    db: dict = {}
    for i in range(0, len(uj), 4):
        utes = uj[i:i + 4]
        hivott = utes[0][1].szin
        for u, l in utes:
            if u not in vedok:
                continue
            db[(u, l.szin)] = db.get((u, l.szin), 0) + 1
            if l in o.birtokos and o.birtokos[l] != u:
                return False
            if l.szin != hivott and o.kezhossz(u, hivott) != db.get((u, hivott), 0):
                return False                       # színhiány: pontosan ennyi volt nála
    return all(o.kezhossz(u, sz) >= n for (u, sz), n in db.items())


def _terv_korei(naplo: Naplo, o):
    """A terv útja egy osztályon: [("kor", hívó, {ülés: lap}) | ("elemzo", p, elemzés)
    | ("vege",)]."""
    from .tervezo import Eset, Ertekelo, helyzetelemzes, kezdo_allapot
    h = helyzetelemzes(naplo.allas)
    v = naplo.terv
    e = Ertekelo(h, v.terv, kockazat=True)
    e.politika_rogzitett = v.politika
    e.ut = []
    st = e.kiaduzas(kezdo_allapot(naplo.allas), "mind" if v.terv.kiaduzas >= 13 else v.terv.kiaduzas)
    e.futtat([Eset(o, 1, h.tartalek, h.hiany)], 0, 0, st)
    ki = []
    for x in e.ut:
        if x[0] in ("adu", "kor"):
            ki.append(("kor", x[1], dict(x[2])))
        elif x[0] == "elemzo":
            ki.append(("elemzo", x[1], x[2]))
            break                                  # az elemzős lépés belsejét nem látjuk
        elif x[0] in ("kudarc", "siker"):
            break
    return ki


def kovetkezo_lap(naplo: Naplo, lejatszott: list, ules: str, max_osztaly: int = 300):
    """A terv következő lapja az `ules` kéznek (a mi hívásunk, vagy a mi hívásunk
    után a 3. kéz), ha a játék eddig a terv szerint ment: (lap, kör) vagy None."""
    from .tervszamolo import osztalyok
    a = naplo.allas
    mi = (a.felvevo, a.asztal)
    vedok = a.vedok
    uj = list(lejatszott[naplo.lapok_szama:])
    teljes = uj[:len(uj) - len(uj) % 4]
    akt = uj[len(uj) - len(uj) % 4:]
    # a mi hívásaink körei (a védői hívások ütései a terven kívül esnek: a terv
    # „elvesztett ütés után ugyanonnan folytatjuk” feltevéssel él)
    sajat = [teljes[i:i + 4] for i in range(0, len(teljes), 4) if teljes[i][0] in mi]
    oszt = osztalyok(a.kint, {v: a.hatra for v in vedok}, naplo.relevans,
                     [k for k in naplo.korlatok if k.tudas == "megfigyelt"])
    oszt = sorted((o for o in oszt if _osszefer(o, vedok, uj)), key=lambda o: -o.suly)[:max_osztaly]
    javaslat = set()
    kor_ki = None
    for o in oszt:
        korok = _terv_korei(naplo, o)
        rendben = True
        for i, utes in enumerate(sajat):
            if i >= len(korok) or korok[i][0] != "kor":
                rendben = False
                break
            _, hivo, lapok = korok[i]
            if utes[0][0] != hivo or any(lapok.get(u) != l for u, l in utes if u in mi):
                rendben = False
                break
        if not rendben:
            continue
        i = len(sajat)
        if i >= len(korok) or korok[i][0] != "kor":
            return None                            # a terv vége / elemzős lépés: újratervezés
        _, hivo, lapok = korok[i]
        if not akt:
            if hivo != ules:
                return None
        elif akt[0][0] != hivo or akt[0][1] != lapok.get(hivo):
            continue                               # ezen az ágon más lett volna a hívás
        lap = lapok.get(ules)
        if lap is None:
            return None
        javaslat.add(lap)
        kor_ki = lapok
    if len(javaslat) != 1:
        return None
    return javaslat.pop(), kor_ki
