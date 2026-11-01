"""
A tervező az élő játékban — próba a valódi lejátszás mentén (2026-11-01).

    PYTHONPATH=src python -m kibic.cli.tervjatek --pbn tanpartik/Pavlicek_felvevo/4Q01.pbn --tabla 4

A partit a PBN valódi lejátszása szerint játssza végig; a felvevő oldalának
minden döntésénél megkérdezi a tervezőt (ugyanaz a függvény, amit a /play hív:
motor/tervdontes.py), és kiírja a valódi lapot, a tervező lapját és az időt. A
„—” azt jelenti, hogy a tervező nem ad lapot (élesben a régi lejátszó dönt).
"""
from __future__ import annotations

import argparse
import sys
import time

from ..domain import Lap, kovetkezo_ules, vonal
from ..motor import tervdontes as td
from ..motor import tervjatszo as tj
from ..motor.lejatszas import JatekAllas
from .jatekmeres import fajlok_kibontasa, partik_fajlbol
from .tervjatszo import tabla_szam


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A tervező döntései a valódi lejátszás mentén")
    ap.add_argument("--pbn", default="tanpartik/Pavlicek_felvevo/4Q01.pbn")
    ap.add_argument("--tabla", type=int, required=True)
    a = ap.parse_args(argv)
    partik = [p for p in partik_fajlbol(fajlok_kibontasa([a.pbn], ".pbn"), "IMP", 1)
              if tabla_szam(p.azonosito) == a.tabla]
    if not partik:
        print("nincs ilyen tábla", file=sys.stderr)
        return 1
    p = partik[0]
    k = p.kontraktus
    adu = None if k.szin == "NT" else k.szin
    felv, aszt = k.felvevo, kovetkezo_ules(k.felvevo, 2)
    g = tj.Jatek({u: set(p.leosztas.kezek[u].lapok) for u in "NESW"}, felv, adu, [], tj.Terv(()))
    jatszott, egyezik, dontes, ossz = [], 0, 0, 0.0
    print(p.azonosito, k)
    for i, c in enumerate(Lap.parse(str(x)) for x in p.lapok):
        u = kovetkezo_ules(felv, 1) if i == 0 else g.soron()
        if vonal(u) == vonal(felv) and i > 0:
            kez = g.kezek[u]
            akt = jatszott[len(jatszott) - len(jatszott) % 4:]
            leg = ([l for l in kez if l.szin == akt[0][1].szin] or list(kez)) if akt else list(kez)
            ja = JatekAllas(ules=u, kontraktus=k, asztal=aszt,
                            lathato={felv: list(g.kezek[felv]), aszt: list(g.kezek[aszt])},
                            lejatszott=list(jatszott), legalis={l: str(l) for l in leg})
            t = time.time()
            r = td.dontes(ja, f"tervjatek:{p.azonosito}")
            dt = time.time() - t
            ossz += dt
            if r is not None:
                dontes += 1
                egyezik += r.lap == c
            print(f"{len(jatszott) // 4 + 1:2d}. ütés {u}: valódi {c}  tervező {r.lap if r else '—'} "
                  f"{'=' if r and r.lap == c else ' '} {dt:6.1f} s  {r.magyarazat if r else ''}", flush=True)
        g.tesz(u, c)
        jatszott.append((u, c))
    print(f"\na tervező {dontes} döntést hozott, ebből {egyezik} egyezik a valódival; összes idő {ossz:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
