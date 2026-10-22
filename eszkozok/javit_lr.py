#!/usr/bin/env python3
"""
A LICREN `.lr` fájlok elgépeléseinek javítása.

Mind a 9 hiba azonosítva, sorszámmal és javasolt javítással. A script
BIZTONSÁGOS: alapból csak megmutatja, mit tenne (`--dry-run` az
alapértelmezés), és mentést készít, mielőtt írna.

    python javit_lr.py rendszerek/gfk/            # csak mutatja
    python javit_lr.py rendszerek/gfk/ --ir       # ténylegesen javít

A javítások indoklása a JAVITASOK listában, javításonként.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

KODOLASOK = ("cp852", "cp1250", "iso-8859-2")

# (fájlnév, sorszám, keresett részlet, csere, indoklás)
JAVITASOK = [
    # --- stand.lr és stund.lr (a kettő majdnem azonos) ---
    ("stand.lr", 123,
     "(F>[15,17])",
     "(F[15,17])",
     "Az intervallum önmagában áll, nem kell elé összehasonlító. "
     "A `>` nyilván elgépelés: a szomszédos szabályok is `F[a,b]` alakúak."),

    ("stand.lr", 277,
     "oe3163))",
     "oe3163)",
     "Egy fölösleges záró zárójel a sor végén (2 nyitó, 3 záró)."),

    ("stand.lr", 373,
     "(P[10,14])&(S=4))",
     "(P[10,14])&(S=4)",
     "Egy fölösleges záró zárójel a sor végén."),

    ("stund.lr", 122, "(F>[15,17])", "(F[15,17])", "Ugyanaz, mint a stand.lr:123."),
    ("stund.lr", 276, "oe3163))", "oe3163)", "Ugyanaz, mint a stand.lr:277."),
    ("stund.lr", 372, "(P[10,14])&(S=4))", "(P[10,14])&(S=4)",
     "Ugyanaz, mint a stand.lr:373."),

    # --- szilpre.lr ---
    ("szilpre.lr", 11,
     "(@So&O)",
     "(@So@O)",
     "A szkórhelyzet jele `@`, nem `&`. A `@So@O` = 'csak mi vagyunk "
     "beliben VAGY csak ok vannak beliben', azaz egyenlotlen beliallas."),

    ("szilpre.lr", 12,
     "((D=5)&(L2=3))))",
     "((D=5)&(L2=3)))",
     "Egy fölösleges záró zárójel (9 nyitó, 10 záró)."),

    ("szilpre.lr", 81,
     "3C:e3541o",
     "3C:e3541",
     "Befejezetlen VAGY a sor végén: a `o` után nincs semmi."),

    ("szilpre.lr", 326,
     "2>vSA+vSK+vSQ+SJ",
     "2>vSA+vSK+vSQ+vSJ",
     "Hiányzó `v` a lapjelölés elől: `SJ` helyett `vSJ` "
     "(a sor többi tagja mind `v`-vel kezdodik)."),

    ("szilpre.lr", 824,
     "&(F>13))",
     "&(F>13)",
     "Egy fölösleges záró zárójel a sor végén."),

    ("szilpre.lr", 876,
     "(S=4)&(vSA+vSK+vSQ>1))&(D=5)",
     "(S=4)&(vSA+vSK+vSQ>1)&(D=5)",
     "Egy fölösleges záró zárójel a sor közepén."),
]


def kodolas_be(ut: Path) -> tuple[str, str]:
    nyers = ut.read_bytes()
    for k in KODOLASOK:
        try:
            return nyers.decode(k), k
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Nem dekódolható: {ut}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LICREN .lr forráshiba-javító")
    ap.add_argument("mappa", help="A .lr fájlokat tartalmazó mappa")
    ap.add_argument("--ir", action="store_true",
                    help="Tényleges írás (alapból csak megmutatja)")
    a = ap.parse_args(argv)

    mappa = Path(a.mappa)
    fajlonkent: dict[str, list] = {}
    for nev, sor, keres, csere, ok in JAVITASOK:
        fajlonkent.setdefault(nev, []).append((sor, keres, csere, ok))

    osszes = sikeres = 0
    for nev, tetelek in fajlonkent.items():
        ut = mappa / nev
        if not ut.is_file():
            print(f"[kihagyva] {ut} nem található")
            continue
        szoveg, kod = kodolas_be(ut)
        crlf = "\r\n" in szoveg
        sorok = szoveg.replace("\r\n", "\n").split("\n")
        print(f"\n=== {nev} ({kod}{', CRLF' if crlf else ''}) ===")

        for sorszam, keres, csere, ok in tetelek:
            osszes += 1
            i = sorszam - 1
            if i >= len(sorok):
                print(f"  [HIBA] {sorszam}. sor nem létezik")
                continue
            eredeti = sorok[i]
            if keres not in eredeti:
                if csere in eredeti:
                    print(f"  [kész]  {sorszam}. sor már javítva")
                    sikeres += 1
                else:
                    print(f"  [HIBA]  {sorszam}. sor nem illik:\n"
                          f"          van:    {eredeti[:70]}\n"
                          f"          várt:   ...{keres}...")
                continue
            uj = eredeti.replace(keres, csere)
            print(f"  {sorszam}. sor")
            print(f"      indok: {ok}")
            print(f"      -      {eredeti[:76]}")
            print(f"      +      {uj[:76]}")
            sorok[i] = uj
            sikeres += 1

        if a.ir:
            mentes = ut.with_suffix(ut.suffix + ".eredeti")
            if not mentes.exists():
                shutil.copy2(ut, mentes)
                print(f"  (mentés: {mentes.name})")
            vissza = ("\r\n" if crlf else "\n").join(sorok)
            ut.write_bytes(vissza.encode(kod))
            print(f"  KIÍRVA: {ut}")

    print(f"\n{sikeres}/{osszes} javítás " +
          ("végrehajtva." if a.ir else "előkészítve (futtasd --ir kapcsolóval)."))
    return 0 if sikeres == osszes else 1


if __name__ == "__main__":
    raise SystemExit(main())
