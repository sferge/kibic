#!/usr/bin/env python3
"""
A hiányzó ERŐKÖVETELMÉNYEK beírása az első válaszokba.

    python eszkozok/valasz_kuszobok.py rendszerek/gfk/
    python eszkozok/valasz_kuszobok.py rendszerek/gfk/ --ir

MIÉRT KELL
----------
A `stand.lr` (és a vele közel azonos `stund.lr`) hét válaszszabályában
nincs pontküszöb. Az `1C-1S:(S>3)` mindössze négy pikket kér — a
licitmotor tehát egy két pontos lappal is `1S`-t válaszolna. A LICREN
gyakorlóprogramja máshol dönthette el, hogy a válaszoló passzoljon-e;
a fájlban ez nincs benne.

Ez NEM elgépelés, hanem a RENDSZER kiegészítése — ezért külön script,
nem a `javit_lr.py` része. A `.valaszkuszob` mentés őrzi az előző
állapotot.

AMI SZÁNDÉKOSAN NEM VÁLTOZIK
----------------------------
A `2N-3C/3D/3H/3S` szabályokban sincs erőküszöb, de ott ez HELYES: a
20-22 pontos nyitásra a Stayman és a transzferek nullával is kötelezők.

A mélyebb szintek (3., 4., 5. licit) szabályaiban sincs erőmetrika, de
ott sem hiány: az erőt a korábbi licitek már leszűkítették, a folytatás
csak az elosztásról szól.

A BEÍRT KÜSZÖBÖK
----------------
* új szín az 1-es szinten:  `(P>5)`    — 6+ pont
* 1 szan válasz:            `(F[6,10])` — 6-10 figurapont
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

KODOLASOK = ("cp852", "cp1250", "iso-8859-2")

# (helyzet, licit, a régi feltétel, az új feltétel, indoklás)
JAVITASOK = [
    ("1C", "1S", "(S>3)", "(S>3)&(P>5)",
     "Új szín az 1-es szinten: 6+ pont kell a válaszhoz."),
    ("1C", "1H", "(H>3)&((S=4)o(H>S))", "(H>3)&((S=4)o(H>S))&(P>5)",
     "Új szín az 1-es szinten: 6+ pont kell a válaszhoz."),
    ("1D", "1S", "(S>3)", "(S>3)&(P>5)",
     "Új szín az 1-es szinten: 6+ pont kell a válaszhoz."),
    ("1D", "1H", "(H>3)&((S=4)o(H>S))", "(H>3)&((S=4)o(H>S))&(P>5)",
     "Új szín az 1-es szinten: 6+ pont kell a válaszhoz."),
    ("1H", "1S", "(S>3)", "(S>3)&(P>5)",
     "Új szín az 1-es szinten: 6+ pont kell a válaszhoz."),
    ("1H", "1N", "(4>S)", "(4>S)&(F[6,10])",
     "1 szan válasz: 6-10 figurapont, négyes pikk nélkül."),
    ("1S", "1N", "(4>S)", "(4>S)&(F[6,10])",
     "1 szan válasz: 6-10 figurapont, négyes pikk nélkül."),
]

FAJLOK = ("stand.lr", "stund.lr")
SZABALY_RE = re.compile(r"^([1-7][SHDCN]):(.+)$")


def kodolas_be(ut: Path) -> tuple[str, str]:
    nyers = ut.read_bytes()
    for k in KODOLASOK:
        try:
            return nyers.decode(k), k
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"Nem dekódolható: {ut}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Erőküszöbök beírása az első válaszokba")
    ap.add_argument("mappa")
    ap.add_argument("--ir", action="store_true",
                    help="Tényleges írás (alapból csak megmutatja)")
    a = ap.parse_args(argv)

    mappa = Path(a.mappa)
    osszes = sikeres = 0

    for nev in FAJLOK:
        ut = mappa / nev
        if not ut.is_file():
            print(f"[kihagyva] {ut} nem található")
            continue
        szoveg, kod = kodolas_be(ut)
        crlf = "\r\n" in szoveg
        sorok = szoveg.replace("\r\n", "\n").split("\n")
        print(f"\n=== {nev} ({kod}{', CRLF' if crlf else ''}) ===")

        # a helyzetek követése: a '!!' utáni első nem üres sor a helyzet
        helyzet, varjuk = "START", False
        valtozott = 0
        for i, sor in enumerate(sorok):
            if sor.strip() == "!!":
                varjuk = True
                continue
            if varjuk and sor.strip():
                helyzet, varjuk = sor.strip(), False
                continue
            m = SZABALY_RE.match(sor)
            if not m:
                continue
            licit, feltetel = m.group(1), m.group(2)
            for h, l, regi, uj, ok in JAVITASOK:
                if helyzet != h or licit != l:
                    continue
                osszes += 1
                if feltetel == uj:
                    print(f"  [kész]  {i+1}. sor  {h}-{l} már javítva")
                    sikeres += 1
                elif feltetel == regi:
                    sorok[i] = f"{licit}:{uj}"
                    valtozott += 1
                    sikeres += 1
                    print(f"  {i+1}. sor  [{h}]  {l}")
                    print(f"      indok: {ok}")
                    print(f"      -      {licit}:{regi}")
                    print(f"      +      {licit}:{uj}")
                else:
                    print(f"  [HIBA]  {i+1}. sor  {h}-{l} nem illik:\n"
                          f"          van:  {feltetel}\n"
                          f"          várt: {regi}")

        if a.ir and valtozott:
            mentes = ut.with_suffix(ut.suffix + ".valaszkuszob")
            if not mentes.exists():
                shutil.copy2(ut, mentes)
                print(f"  (mentés: {mentes.name})")
            ut.write_bytes(("\r\n" if crlf else "\n").join(sorok).encode(kod))
            print(f"  KIÍRVA: {ut}  ({valtozott} sor)")

    print(f"\n{sikeres}/{osszes} javítás " +
          ("végrehajtva." if a.ir else "előkészítve (futtasd --ir kapcsolóval)."))
    return 0 if sikeres == osszes else 1


if __name__ == "__main__":
    raise SystemExit(main())
