"""
JELZÉSRENDSZEREK megtekintése és kipróbálása, olvasható alakban.

    # egy jelzésrendszer feloldva (amit behoz, felülír, töröl) — YAML-ból:
    python -m kibic.cli.jelzes --rendszer MOHA_STAND

    # ugyanez az adatbázisból (a jóváhagyás állapotával):
    python -m kibic.cli.jelzes --rendszer MOHA_STAND --db

    # mit hív a kibic egy lapállásból, és melyik sor miatt:
    python -m kibic.cli.jelzes --rendszer MOHA_STAND --lap KQ72 --lap "Á10 8 4"
    python -m kibic.cli.jelzes --rendszer MOHA_STAND --lap K872 --helyzet HIVAS
    python -m kibic.cli.jelzes --rendszer MOHA_STAND --lap KQ72 --szint ELES

Szintek: ELES (csak elfogadott), TESZT (javasolt is), KARTYA (alap: mint TESZT).
Indító lapnál a LEGKONKRÉTABB illeszkedő sor nyer; a --lap kiírja a többi
jelöltet is.
"""
from __future__ import annotations

import argparse
import os
import sys

from ..motor.jelzes import (SZINTEK, TERULET_NEV, jelzesek, lapok, rendszerek_betolt, sor_szoveg,
                            szep, szep_szin)
from ..motor.kartya import JELZES_KONYVTAR


def _db(a) -> dict:
    import pymysql

    from ..motor.jelzes_db import rendszerek_db
    conn = pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4")
    try:
        return rendszerek_db(conn)
    finally:
        conn.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Jelzésrendszerek megtekintése")
    ap.add_argument("--rendszer", required=True, help="A jelzésrendszer kódja, pl. MOHA_STAND")
    ap.add_argument("--utak", nargs="*", help="A YAML-könyvtár (alap: rendszerek/jelzesek)")
    ap.add_argument("--db", action="store_true", help="Az adatbázisból")
    ap.add_argument("--szint", default="KARTYA", choices=tuple(SZINTEK))
    ap.add_argument("--lap", action="append", help="Lapállás kipróbálásra, pl. KQ72 vagy 'Á10 8 4'")
    ap.add_argument("--helyzet", default="INDITAS", choices=("INDITAS", "PARTNER_SZINE", "HIVAS"))
    ap.add_argument("--kontextus", action="append", default=[], help="pl. IGERT_HAROM")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    rr = _db(a) if a.db else rendszerek_betolt(a.utak or [JELZES_KONYVTAR])
    j = jelzesek(a.rendszer, rr, a.szint)
    if j.hianyzo:
        print("HIÁNYZÓ jelzésrendszer: " + ", ".join(j.hianyzo), file=sys.stderr)
        if a.rendszer in j.hianyzo:
            return 1

    if a.lap:
        for lap in a.lap:
            ls = lapok(lap)
            for f in ("SZIN", "SZAN"):
                jeloltek = j.jeloltek(ls, f, a.helyzet, a.kontextus)
                if not jeloltek and a.helyzet == "PARTNER_SZINE":
                    jeloltek = j.jeloltek(ls, f, "INDITAS", a.kontextus)
                if not jeloltek:
                    print(f"{szep_szin(ls):<10} {f:<4} -> nincs szabály")
                    continue
                ny = jeloltek[0]
                lap_, _ = j.indito_lap(ls, f, a.helyzet, a.kontextus)
                print(f"{szep_szin(ls):<10} {f:<4} -> {szep(lap_):<3} "
                      f"[{ny.allapot}] {ny.eredet}: {ny.kulcs}  (konkrétság {ny.konkretsag})")
                for s in jeloltek[1:]:
                    print(f"{'':<19} mögötte: {s.eredet}: {s.kulcs} ({s.konkretsag})")
        return 0

    f = j.feloldas
    print("Feloldás: " + " -> ".join(f"{k}" + (f" (mélység {m})" if m else "")
                                     for k, m in f.lanc))
    fejezet = object()
    for s in f.sorok:
        if s.fejezet != fejezet:
            fejezet = s.fejezet
            print(f"\n== {fejezet or '(fejezet nélkül)'} ==")
        print(f"  [{s.allapot:<16}] {s.eredet:<13} {sor_szoveg(s)}")
        print(f"  {'':<18} kulcs: {s.kulcs} · {s.fajta.lower()}"
              + (f" · {TERULET_NEV[s.terulet]}" if s.terulet else ""))
    if f.felulirt:
        print("\nFELÜLÍRVA (a közelebbi nyert):")
        for kulcs, nyer, veszt in f.felulirt:
            print(f"  {kulcs}: {nyer} írja felül a(z) {veszt} sorát")
    if f.torolt:
        print("\nKIHAGYVA:")
        for kulcs, ki, kie in f.torolt:
            print(f"  {kulcs}: {ki} kihagyta a(z) {kie} sorát")
    if f.kizart:
        print("\nKIZÁRVA:")
        for kod, fej, ki in f.kizart:
            print(f"  {kod}" + (f" / {fej}" if fej else "") + f" (kizárta: {ki})")
    for cim, lista in (("KÖRKÖRÖS (kimaradt)", f.korkoros),
                       ("HATÁSTALAN KIZÁRÁS", [f"{a} -> {b}" + (f" / {c}" if c else "")
                                               for a, b, c in f.hatastalan_kizarasok]),
                       ("KIVÉTEL ELV NÉLKÜL", f.kivetel_elv_nelkul)):
        if lista:
            print(f"\n{cim}:")
            for x in lista:
                print(f"  {x}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
