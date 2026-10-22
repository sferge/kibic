"""
ELLENTMONDÁS-KERESŐ egy licitrendszerre.

    # import ELŐTT, közvetlenül a YAML-ból (adatbázis nélkül):
    python -m kibic.cli.rendszercheck rendszerek/yaml/ --rendszer KIBIC_STAND

    # ha a kártya a YAML-on kívüli rendszerre is hivatkozik (pl. FESU):
    python -m kibic.cli.rendszercheck rendszerek/yaml/ --rendszer KIBIC_STAND --db

    # a már betöltött, ÉLŐ rendszer (csak az ELFOGADOTT sorok; --teszt:
    # a JAVASOLT-akkal együtt, ahogy a motor teszt módban látja):
    python -m kibic.cli.rendszercheck --rendszer KIBIC_STAND --db [--teszt]

Kilépési kód: 0, ha nincs ütközés és hibás minta; 1, ha van. Így CI-ba
vagy import elé is betehető. A módszer leírása: motor/rendszercheck.py.
"""
from __future__ import annotations

import argparse
import os
import sys

from ..motor.kriterium import Parametertar
from ..motor.rendszercheck import ellenoriz, feloldas_forrasokbol


def _kapcsolat(a):
    try:
        import pymysql
    except ImportError:
        print("A pymysql csomag nem érhető el.", file=sys.stderr)
        sys.exit(2)
    return pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4",
                           autocommit=True)


def _db_kulso(conn):
    """A YAML-ban nem szereplő rendszerek az adatbázisból (csak ELFOGADOTT)."""
    from ..motor.feloldas import _hivatkozasok, _sorok
    cur = conn.cursor()
    tar: dict = {}

    def kulso(kod: str):
        if kod in tar:
            return tar[kod]
        cur.execute("SELECT id FROM rendszer WHERE kod=%s", (kod,))
        r = cur.fetchone()
        if not r:
            tar[kod] = None
            return None
        hiv = []
        for hid in _hivatkozasok(cur, r[0]):
            cur.execute("SELECT kod FROM rendszer WHERE id=%s", (hid,))
            x = cur.fetchone()
            if x:
                hiv.append(x[0])
        tar[kod] = (_sorok(cur, r[0], kod, 1), hiv)
        return tar[kod]
    return kulso


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ellentmondás-kereső")
    ap.add_argument("utak", nargs="*", help="YAML-fájlok vagy könyvtárak")
    ap.add_argument("--rendszer", required=True, help="Az ellenőrzendő rendszer kódja")
    ap.add_argument("--db", action="store_true",
                    help="Adatbázis használata (a YAML-on kívüli rendszerekhez, "
                         "vagy YAML nélkül az élő rendszerhez)")
    ap.add_argument("--csak-elfogadott", action="store_true",
                    help="YAML-módban is csak az ELFOGADOTT sorok")
    ap.add_argument("--teszt", action="store_true",
                    help="--db módban a JAVASOLT sorokat is (mint a motor teszt módja)")
    ap.add_argument("--kez", type=int, default=200, help="Kéz / helyzet (200)")
    ap.add_argument("--mag", type=int, default=1)
    ap.add_argument("--reszletes", action="store_true")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    conn = _kapcsolat(a) if a.db else None
    try:
        if a.utak:
            from ..impex.rendszer_yaml import ForrasHiba, betolt
            try:
                forrasok = betolt(a.utak)
            except ForrasHiba as e:
                print(f"HIBA: {e}", file=sys.stderr)
                return 1
            if a.rendszer not in forrasok and conn is None:
                print(f"A(z) {a.rendszer} nincs a YAML-ban (--db?)", file=sys.stderr)
                return 1
            f, hianyzo = feloldas_forrasokbol(
                forrasok, a.rendszer, a.csak_elfogadott,
                _db_kulso(conn) if conn else None)
            if hianyzo:
                print("FIGYELEM: a YAML-ban nem szereplő hivatkozott rendszer/"
                      "konvenció (adatbázisból: --db): "
                      + ", ".join(sorted(set(hianyzo))))
            if conn is not None:
                from ..motor.kriterium import parametertar_betolt
                pt = parametertar_betolt(conn, None)
                pt.rendszer_ertek = dict(forrasok[a.rendszer].parameterek) \
                    if a.rendszer in forrasok else {}
            else:
                pt = Parametertar(rendszer_ertek=dict(
                    forrasok[a.rendszer].parameterek))
        else:
            if conn is None:
                ap.error("YAML nélkül --db kell")
            from ..motor.feloldas import feloldas
            from ..motor.kriterium import parametertar_betolt
            f = feloldas(conn, a.rendszer, teszt=a.teszt)
            pt = parametertar_betolt(conn, a.rendszer)
    finally:
        if conn is not None:
            conn.close()

    print(f"{a.rendszer}: {len(f.sorok)} szabály, lánc: "
          + " -> ".join(f"{k}({m})" for k, m in f.lanc))
    for x in f.tajekoztatasok:
        print("  " + x)
    for x in f.figyelmeztetesek:
        print("FIGYELEM: " + x)
    er = ellenoriz(f.sorok, pt, kez_db=a.kez, mag=a.mag, feloldas=f)
    print(er.jelentes(a.reszletes))
    return 0 if er.rendben else 1


if __name__ == "__main__":
    sys.exit(main())
