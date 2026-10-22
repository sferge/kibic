"""
Alert-bányász — a licitrendszer-tudásbázis nyersanyaga.

A 2885 alertelt licit szó szerint azt írja le, mit JELENTETT egy licit
annál a párnál. Ez a tudásbázis és az ágensprofil legértékesebb forrása,
és mellékesen jött, az importálással.

Használat:
    python -m kibic.cli.alertek                    # leggyakoribb licit+magyarázat
    python -m kibic.cli.alertek --nyitas           # csak nyitó licitek
    python -m kibic.cli.alertek --licit 1NT        # egy konkrét licit
    python -m kibic.cli.alertek --konvenciok       # konvenciónevek gyakorisága
    python -m kibic.cli.alertek --pontok 1NT       # a tényleges HCP-eloszlás
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

from ..domain import Leosztas, ULESEK

# Ismert konvenció- és rendszernevek felismerése a magyarázatokból
KONVENCIOK = [
    "stayman", "transfer", "jacoby", "texas", "blackwood", "gerber",
    "michaels", "unusual", "drury", "bergen", "smolen", "lebensohl",
    "negative double", "takeout", "cue", "splinter", "control", "keycard",
    "rkc", "precision", "sayc", "2/1", "acol", "polish", "weak two",
    "namyats", "flannery", "puppet", "minorwood", "dopi", "roman",
]

RENDSZEREK = ["sayc", "2/1", "acol", "precision", "polish", "standard american"]


def _kapcsolat(a):
    try:
        import pymysql
    except ImportError:
        print("A pymysql csomag nem érhető el.", file=sys.stderr)
        sys.exit(2)
    return pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4")


def _alertek(conn, csak_nyitas: bool, csak_licit: str | None):
    """
    Végigmegy a játszmákon, és kiadja az alertelt liciteket a licitáló
    kezével együtt. Python-oldalon szűr, hogy MySQL 5.7-en is fusson
    (nincs JSON_TABLE).
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT j.id, j.licit, l.kezek_pbn, l.oszto, l.beliallas"
        "  FROM jatszma j JOIN leosztas l ON l.id = j.leosztas_id"
        " WHERE j.licit IS NOT NULL")
    for jid, licit_j, kezek_pbn, oszto, beli in cur.fetchall():
        try:
            licitek = json.loads(licit_j)
        except (TypeError, ValueError):
            continue
        leosztas = None
        for i, b in enumerate(licitek):
            if not b.get("alert") or not b.get("magyarazat"):
                continue
            if csak_nyitas and any(x.get("licit") not in (None, "PASS")
                                   for x in licitek[:i]):
                continue
            if csak_licit and b.get("licit") != csak_licit.upper():
                continue
            if leosztas is None:
                try:
                    leosztas = Leosztas.pbn_bol(kezek_pbn, oszto, beli)
                except ValueError:
                    leosztas = False
            yield jid, i, b, (leosztas or None)


def _normalizal(szoveg: str) -> str:
    """A magyarázatok egységesítése a csoportosításhoz."""
    s = szoveg.lower().strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[.;!]+$", "", s)
    return s


def gyakorisag(conn, a) -> None:
    parok: Counter = Counter()
    licitek: Counter = Counter()
    osszes = 0
    for _, _, b, _ in _alertek(conn, a.nyitas, a.licit):
        osszes += 1
        licitek[b["licit"]] += 1
        parok[(b["licit"], _normalizal(b["magyarazat"]))] += 1

    print("=" * 70)
    print(f"  Alertelt licit: {osszes}"
          + ("  (csak nyitó licitek)" if a.nyitas else ""))
    print("-" * 70)
    print("  LEGGYAKORIBB LICITEK:")
    for licit, db in licitek.most_common(15):
        print(f"    {licit:<6} {db:>5}")
    print("-" * 70)
    print("  LEGGYAKORIBB LICIT + MAGYARÁZAT PÁROK:")
    for (licit, mag), db in parok.most_common(a.darab):
        print(f"    {db:>4}x  {licit:<6} {mag[:56]}")
    print("=" * 70)


def konvenciok(conn, a) -> None:
    talalat: Counter = Counter()
    rendszer: Counter = Counter()
    osszes = 0
    for _, _, b, _ in _alertek(conn, False, None):
        osszes += 1
        s = _normalizal(b["magyarazat"])
        for k in KONVENCIOK:
            if k in s:
                talalat[k] += 1
        for r in RENDSZEREK:
            if r in s:
                rendszer[r] += 1

    print("=" * 70)
    print(f"  Alertelt licit: {osszes}")
    print("-" * 70)
    print("  FELISMERT KONVENCIÓK:")
    for k, db in talalat.most_common(30):
        print(f"    {db:>5}x  {k}")
    if rendszer:
        print("-" * 70)
        print("  EMLÍTETT RENDSZEREK:")
        for r, db in rendszer.most_common():
            print(f"    {db:>5}x  {r}")
    print("=" * 70)


def pontok(conn, a) -> None:
    """
    A tényleges kézértékek eloszlása egy adott licitnél.
    Ez adja meg empirikusan a paraméterek valódi értékét — vagyis a
    NYITAS_MIN / 1NT_MIN nem elméleti szám lesz, hanem MÉRT.
    """
    from ..domain import ERTEKELOK

    hcpk: list[float] = []
    alakok: Counter = Counter()
    for _, i, b, leosztas in _alertek(conn, a.nyitas, a.licit):
        if leosztas is None:
            continue
        ules = b.get("ules")
        if ules not in ULESEK:
            continue
        kez = leosztas.kezek[ules]
        hcpk.append(ERTEKELOK["HCP"](kez))
        alakok[kez.rendezett_alak] += 1

    if not hcpk:
        print("Nincs adat ehhez a licithez.")
        return

    hcpk.sort()
    n = len(hcpk)
    def pct(p): return hcpk[min(n - 1, int(n * p))]

    print("=" * 70)
    print(f"  Licit: {a.licit or '(mind)'}   |   megfigyelés: {n}")
    print("-" * 70)
    print(f"  HCP:  min={hcpk[0]:g}  5%={pct(.05):g}  25%={pct(.25):g}  "
          f"medián={pct(.5):g}  75%={pct(.75):g}  95%={pct(.95):g}  "
          f"max={hcpk[-1]:g}")
    print(f"  átlag={sum(hcpk)/n:.2f}")
    print("-" * 70)
    print("  ELOSZTÁSOK:")
    for alak, db in alakok.most_common(10):
        print(f"    {alak:<10} {db:>5}  ({100*db/n:.1f}%)")
    print("-" * 70)
    print("  Javasolt paraméterérték (5. percentilis, hogy a megfigyelt")
    print(f"  licitek 95%-a beleférjen):  {pct(.05):g}")
    print("=" * 70)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Alertelt licitek kimutatása")
    ap.add_argument("--nyitas", action="store_true",
                    help="Csak nyitó licitek (passzok után is)")
    ap.add_argument("--licit", default=None, help="Egy konkrét licit, pl. 1NT")
    ap.add_argument("--konvenciok", action="store_true",
                    help="Konvenciónevek gyakorisága")
    ap.add_argument("--pontok", action="store_true",
                    help="A licit mögötti tényleges kézértékek eloszlása")
    ap.add_argument("--darab", type=int, default=40)
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host",   default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user",   default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    conn = _kapcsolat(a)
    try:
        if a.konvenciok:
            konvenciok(conn, a)
        elif a.pontok:
            pontok(conn, a)
        else:
            gyakorisag(conn, a)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
