"""
KONVENCIÓKÁRTYA generálása (HTML, A4 fekvő, WBF-szerkezet).

    # YAML-ból, adatbázis nélkül:
    python -m kibic.cli.kartya rendszerek/yaml --rendszer KIBIC_STAND --ki kartya.html

    # az adatbázisból (a motor által ténylegesen használt szabályokkal):
    python -m kibic.cli.kartya --rendszer KIBIC_STAND --db [--teszt] --ki kartya.html

    # a nyers adatszerkezet (JSON):
    python -m kibic.cli.kartya rendszerek/yaml --rendszer KIBIC_STAND --json

A HTML böngészőben megnyitható, és onnan PDF-be nyomtatható (A4 fekvő).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from ..motor.kartya import kartya_db, kartya_html, kartya_yamlbol


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Konvenciókártya generálása")
    ap.add_argument("utak", nargs="*", help="YAML-fájlok vagy könyvtárak")
    ap.add_argument("--rendszer", required=True)
    ap.add_argument("--db", action="store_true", help="Az adatbázisból")
    ap.add_argument("--teszt", action="store_true",
                    help="--db mellett: a JAVASOLT szabályokkal is")
    ap.add_argument("--ki", help="A HTML kimeneti fájl (alap: a szabványos kimenet)")
    ap.add_argument("--json", action="store_true", help="HTML helyett JSON")
    ap.add_argument("--jelzesek", nargs="*",
                    help="YAML mellett: a jelzéscsomagok könyvtára (alap: rendszerek/jelzesek)")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    if a.db:
        import pymysql
        conn = pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                               database=a.adatbazis, charset="utf8mb4")
        try:
            adat = kartya_db(conn, a.rendszer, a.teszt)
        finally:
            conn.close()
    else:
        if not a.utak:
            ap.error("adj meg YAML-könyvtárat, vagy használd a --db-t")
        from ..impex.rendszer_yaml import betolt
        adat = kartya_yamlbol(betolt(a.utak), a.rendszer, jelzes_utak=a.jelzesek)

    kimenet = json.dumps(adat, ensure_ascii=False, indent=2) if a.json \
        else kartya_html(adat)
    if a.ki:
        with open(a.ki, "w", encoding="utf-8") as f:
            f.write(kimenet)
        print(f"Kész: {a.ki}")
    else:
        sys.stdout.write(kimenet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
