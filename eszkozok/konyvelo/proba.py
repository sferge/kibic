"""
A tervkönyvelő próbája egy partin, az első ütéstől (2026-11-18).

    PYTHONPATH=src python3 eszkozok/konyvelo/proba.py tanpartik/Pavlicek_felvevo/4Q01.pbn 1 \
        [--vilag 40] [--legjobb 3 --vilag2 150] [--naplo]

A jelölt tervek (az egy- és kételemű esélysorok a technikákból) sorsolt
világokon, DD-védők ellen; a legjobbak még egyszer több világon. `--naplo`: a
legjobb terv végrehajtása a valódi leosztáson, ütésenként.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from kibic.cli.jatekmeres import _pbn_olvas          # noqa: E402
from kibic.domain import Lap, kovetkezo_ules           # noqa: E402
from kibic.motor import tervjatszo as tj               # noqa: E402
from kibic.motor.tervellenorzo import vilagok          # noqa: E402
from kibic.motor.tervkonyvelo import KTerv, ertekel, lejatszik, tervjeloltek  # noqa: E402
from kibic.motor.tervsema import Allas, technikak_betoltese  # noqa: E402
from kibic.solver.dds import lap_elemzes               # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("pbn")
    ap.add_argument("tabla", type=int)
    ap.add_argument("--vilag", type=int, default=40)
    ap.add_argument("--legjobb", type=int, default=3)
    ap.add_argument("--vilag2", type=int, default=150)
    ap.add_argument("--naplo", action="store_true")
    ap.add_argument("--mag", type=int, default=1)
    a = ap.parse_args(argv)

    j = next(x for x in _pbn_olvas(a.pbn) if x.tabla_szam == a.tabla)
    k, F = j.kontraktus, j.felvevo
    import dataclasses
    k = dataclasses.replace(k, felvevo=F)
    adu = None if k.szin == "NT" else k.szin
    A = kovetkezo_ules(F, 2)
    kijatszo = kovetkezo_ules(F, 1)
    indulas = (kijatszo, Lap.parse(j.lapok[0]))
    lo = j.leosztas
    kezek = {u: set(lo.kezek[u].lapok) for u in (F, A)}
    vedok = (kovetkezo_ules(F, 1), kovetkezo_ules(F, 3))
    kint = {l for u in vedok for l in lo.kezek[u].lapok} - {indulas[1]}
    allas = Allas(felvevo=F, adu=adu, kezek=kezek, kint=kint, cel=6 + k.szint, hatra=13,
                  soron=kovetkezo_ules(kijatszo, 1))
    print(f"{Path(a.pbn).name} #{a.tabla}: {k.szint}{k.szin} {F}, indulás {indulas[1]}")

    tervek = tervjeloltek(allas, technikak_betoltese())
    print(f"{len(tervek)} jelölt terv")
    vl = vilagok(lo, [indulas], kint, a.vilag, mag=a.mag, vedok=tuple(sorted(vedok)))
    tar = tj.DDTar(lap_elemzes, k)
    t0 = time.time()
    er = ertekel(tervek, vl, F, k, [indulas], tar)
    er.sort(key=lambda r: (-r.esely, -r.utesek))
    print(f"{a.vilag} világ, {time.time() - t0:.0f} s, {tar.hivas} DD-hívás")
    for r in er:
        print(f"  {100 * r.esely:5.1f}%  {r.utesek / r.n:5.2f} ütés  {r.terv.nev}")

    if a.legjobb and a.vilag2:
        vl2 = vilagok(lo, [indulas], kint, a.vilag2, mag=a.mag + 1, vedok=tuple(sorted(vedok)))
        tar2 = tj.DDTar(lap_elemzes, k)
        t0 = time.time()
        er2 = ertekel([r.terv for r in er[:a.legjobb]], vl2, F, k, [indulas], tar2)
        er2.sort(key=lambda r: -r.esely)
        print(f"\nA legjobbak {a.vilag2} új világon ({time.time() - t0:.0f} s):")
        for r in er2:
            print(f"  {100 * r.esely:5.1f}%  {r.utesek / r.n:5.2f} ütés  {r.terv.nev}")

    if a.naplo:
        legjobb = er[0].terv
        naplo: list[str] = []

        def dd_vedo(jj):
            return tj._vedo_lap(lap_elemzes(lo, [str(l) for _, l in jj.lapok], k))
        n = lejatszik(legjobb, lo, F, adu, [indulas], dd_vedo, naplo, cel=6 + k.szint)
        print(f"\nA valódi leosztáson ({legjobb.nev}): {n} ütés (kell {6 + k.szint})")
        for s in naplo:
            print("  " + s)


if __name__ == "__main__":
    main()
