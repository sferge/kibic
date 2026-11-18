"""
A színtáblázat építése (2026-11-02): a PBN-partik felvevő + asztal kezéből minden
színt kigyűjt, és a még hiányzókat párhuzamosan kiszámolja az egyszínű elemzővel.

    PYTHONPATH=src python -m kibic.cli.szintabla --pbn tanpartik [--szalak 32] [--max 0] [--kimenet]

--kimenet: a kezelések elosztásonkénti eredménye is (a játékmódok gyors esélyéhez;
KIBIC_SZINKIMENET, alap ~/.cache/kibic/szinkimenet.pkl) — a hiányzó színeket újraszámolja.

Folytatható: amit már kiszámolt, azt nem számolja újra (a táblázat 200 színenként
mentődik). A táblázat helye: KIBIC_SZINTABLA (alap ~/.cache/kibic/szintabla.pkl).
"""
from __future__ import annotations

import argparse
import multiprocessing as mp
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from ..domain import kovetkezo_ules
from ..motor import tervszintabla as tsz


def _szamol(k):
    return k, tsz.szamol(k), None


def _szamol_mind(k):
    e, kim = tsz.szamol_mind(k)
    return k, e, kim


def gyujt(utak: list[str]) -> dict:
    """kulcs → előfordulás (a felvevő és az asztal minden színe)."""
    from .jatekmeres import fajlok_kibontasa, partik_fajlbol
    db: dict = {}
    for p in partik_fajlbol(fajlok_kibontasa(utak, ".pbn"), "IMP", min_lapok=0):
        k = p.kontraktus
        if k is None:
            continue
        X = p.leosztas.kezek[k.felvevo].lapok
        Y = p.leosztas.kezek[kovetkezo_ules(k.felvevo, 2)].lapok
        for sz in "SHDC":
            x = {l.rang for l in X if l.szin == sz}
            y = {l.rang for l in Y if l.szin == sz}
            if x or y:
                kk = tsz.kulcs(x, y)
                db[kk] = db.get(kk, 0) + 1
    return db


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A színtáblázat építése a partik színeiből")
    ap.add_argument("--pbn", nargs="+", required=True, help="PBN-fájlok vagy könyvtárak")
    ap.add_argument("--szalak", type=int, default=os.cpu_count() or 1)
    ap.add_argument("--max", type=int, default=0, help="legfeljebb ennyi új szín (0: mind)")
    ap.add_argument("--kimenet", action="store_true", help="a kezelések elosztásonkénti eredménye is")
    a = ap.parse_args(argv)
    t0 = time.time()
    db = gyujt(a.pbn)
    tabla = dict(tsz.tabla())
    kim = dict(tsz.kimenet_tabla()) if a.kimenet else None
    hiany = sorted((k for k in db if k not in tabla or (kim is not None and k not in kim)),
                   key=lambda k: -db[k])
    if a.max:
        hiany = hiany[:a.max]
    print(f"{len(db)} különböző szín ({sum(db.values())} előfordulás); a táblázatban {len(db) - len(hiany)}; "
          f"most számolandó {len(hiany)}; szálak {a.szalak}", flush=True)
    kesz = 0
    with ProcessPoolExecutor(max_workers=max(1, a.szalak), mp_context=mp.get_context("fork")) as pool:
        fv = _szamol_mind if a.kimenet else _szamol
        for f in as_completed([pool.submit(fv, k) for k in hiany]):
            k, v, km = f.result()
            tabla[k] = v
            if kim is not None:
                kim[k] = km
            kesz += 1
            if kesz % 200 == 0 or kesz == len(hiany):
                tsz.ment(tabla)
                if kim is not None:
                    tsz.kimenet_ment(kim)
                el = time.time() - t0
                print(f"  {kesz}/{len(hiany)}  {el:.0f} s  (még kb. {el / kesz * (len(hiany) - kesz):.0f} s)",
                      flush=True)
    tsz.ment(tabla)
    if kim is not None:
        tsz.kimenet_ment(kim)
    print(f"kész: a táblázatban {len(tabla)} szín; {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
