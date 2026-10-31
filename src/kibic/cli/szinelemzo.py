"""
Egyszínű elemző (2026-10-31, Felvevő tervjáték): egy szín kezelési kínálata.

    PYTHONPATH=src python -m kibic.cli.szinelemzo --felvevo K98654 --asztal A32 [--vesztes 1]

A felvevő és az asztal lapjai a színben (A K Q J T 9 … 2); a kint lévő lapok
alapból a többi. Kimenet: k-ként a legalább k ütés legjobb esélye (legfeljebb
`--vesztes` vesztett ütéssel a színben) és a legjobb kezelés első lépése.
"""
from __future__ import annotations

import argparse
import sys

from ..motor.tervszinkezeles import Feladat, jel, kinalat, rangok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Egyszínű elemző")
    ap.add_argument("--felvevo", required=True, help="a felvevő lapjai a színben, pl. K98654 (üres: -)")
    ap.add_argument("--asztal", required=True, help="az asztal lapjai a színben")
    ap.add_argument("--kint", help="a kint lévő lapok (alapból a többi)")
    ap.add_argument("--vesztes", type=int, default=99, help="legfeljebb ennyi vesztett ütés a színben")
    ap.add_argument("--ures", type=int, nargs=2, default=(13, 13),
                    help="a felvevő bal és jobb keze szabad helyei (alap: 13 13)")
    a = ap.parse_args(argv)
    X, Y = rangok(a.felvevo.replace("-", "")), rangok(a.asztal.replace("-", ""))
    kint = rangok(a.kint) if a.kint else frozenset(range(2, 15)) - X - Y
    f = Feladat(X, Y, kint, a.ures[0], a.ures[1])
    k = kinalat(f, a.vesztes)
    print(f"felvevő {jel(X)} · asztal {jel(Y)} · kint {jel(kint)}"
          + (f" · legfeljebb {a.vesztes} vesztés" if a.vesztes < 99 else ""))
    for kk, (p, l) in k.eselyek.items():
        print(f"  ≥{kk} ütés: {p:6.1%}   {l}")
    print(f"biztos: {k.biztos}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
