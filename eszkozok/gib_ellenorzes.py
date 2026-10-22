#!/usr/bin/env python3
"""
A GIB-fordítás ellenőrzése a ROBOT SAJÁT MAGYARÁZATAI ellen.

    source .env
    python eszkozok/gib_ellenorzes.py rendszerek/gib/gib.lr

MIÉRT ERŐSEBB EZ, MINT AZ EGYEZÉSI ARÁNY
-----------------------------------------
A gyűjteményben ~591 olyan alertelt licit van, ahol a magyarázatot a
GIB robot generálta. Ezek NEM emberi vélemények, hanem a robot pontos
állításai a saját lapjáról:

    "minor suit opening -- 3+ !c; 11-21 hcp; 12-22 total points"

Ez háromféle ellenőrzést enged meg:

  A) IGAZAT MOND-E A ROBOT?  A kimondott feltételt összevetjük a VALÓDI
     kézzel. Ha eltér, a magyarázat-elemzőnk hibás (a robot nem hazudik).
  B) JÓL FORDÍTOTTUNK-E?     A mi `gib.lr` szabályaink ugyanazt a licitet
     adják-e ugyanarra a kézre.
  C) HOL TÉRÜNK EL?          Az eltéréseket a robot saját feltételével
     együtt írjuk ki — azonnal látszik, melyik feltételt rontottuk el.

A (B) nem egyszerű egyezési arány: itt a hivatkozási alap egy
DETERMINISZTIKUS rendszer, nem emberek keveréke. Ha nem 100%, akkor a
fordításunk hibás — nincs "a játékos másképp gondolta" kifogás.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

SZIN_JEL = {"!c": "C", "!d": "D", "!h": "H", "!s": "S"}

# "3+ !c"  /  "2-5 !d"  /  "5+ !h"
HOSSZ_RE = re.compile(r"(\d+)\s*(?:-\s*(\d+))?\s*\+?\s*(!<?[cdhs])")
HCP_RE = re.compile(r"(\d+)\s*-\s*(\d+)\s*hcp")
TP_RE = re.compile(r"(\d+)\s*-\s*(\d+)\s*total\s*points")

GEPI_JELEK = ("total points", "hcp;", "suit opening --", "notrump opener",
              "could have")


def gepi(magyarazat: str) -> bool:
    m = magyarazat.lower()
    return any(j in m for j in GEPI_JELEK)


def allitas(magyarazat: str) -> dict:
    """A robot kimondott feltétele: {szin: (min,max)}, hcp, tp."""
    m = magyarazat.lower().replace("!<", "!")
    ki: dict = {"hossz": {}}
    for a, b, szinjel in HOSSZ_RE.findall(m):
        szin = SZIN_JEL.get(szinjel.replace("<", ""))
        if not szin:
            continue
        ki["hossz"][szin] = (int(a), int(b) if b else 13)
    h = HCP_RE.search(m)
    if h:
        ki["hcp"] = (int(h.group(1)), int(h.group(2)))
    t = TP_RE.search(m)
    if t:
        ki["tp"] = (int(t.group(1)), int(t.group(2)))
    return ki


def allitas_teljesul(a: dict, kez, ERTEKELOK) -> list[str]:
    """Mi NEM teljesül a robot állításából a valódi kézre?"""
    sertes = []
    for szin, (mn, mx) in a.get("hossz", {}).items():
        h = kez.hossz(szin)
        if not (mn <= h <= mx):
            sertes.append(f"{szin} hossz {h} nem {mn}-{mx}")
    if "hcp" in a:
        mn, mx = a["hcp"]
        f = ERTEKELOK["HCP"](kez)
        if not (mn <= f <= mx):
            sertes.append(f"HCP {f:g} nem {mn}-{mx}")
    if "tp" in a:
        mn, mx = a["tp"]
        p = ERTEKELOK["AP_321"](kez)
        if not (mn <= p <= mx):
            sertes.append(f"total points {p:g} nem {mn}-{mx}")
    return sertes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="GIB-fordítás ellenőrzése")
    ap.add_argument("lr", help="A gib.lr fájl")
    ap.add_argument("--metrika", default="P_AP321",
                    help="A @PONT feloldása (a GIB 'total points'-ja AP_321)")
    ap.add_argument("--peldak", type=int, default=12)
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    import pymysql
    from kibic.domain import ERTEKELOK, Leosztas, ULESEK
    from kibic.impex.licren import fordit, olvas
    from kibic.motor.kifejezes import Kontextus, kiertekel

    r = olvas(a.lr)
    szabalyok = [(i, sz.licit, fordit(sz.ast))
                 for i, sz in enumerate(r.inditasok.szabalyok) if sz.ast]
    print(f"{len(szabalyok)} nyitási szabály a(z) {a.lr} fájlból")
    print(f"A @PONT feloldása: {a.metrika}\n")

    conn = pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4")
    cur = conn.cursor()
    cur.execute("SELECT j.id, j.licit, l.kezek_pbn, l.oszto, l.beliallas"
                "  FROM jatszma j JOIN leosztas l ON l.id=j.leosztas_id"
                " WHERE j.licit IS NOT NULL")

    talalt = hazug = egyezik = elter = 0
    ertelmezhetetlen = 0
    tevesztes: Counter = Counter()
    peldak: list[str] = []
    hazugsagok: list[str] = []

    for jid, licit_j, kezek_pbn, oszto, beli in cur.fetchall():
        try:
            licitek = json.loads(licit_j)
            leosztas = Leosztas.pbn_bol(kezek_pbn, oszto, beli)
        except Exception:                      # noqa: BLE001
            continue
        for i, b in enumerate(licitek):
            L = (b.get("licit") or "").upper()
            if L in ("PASS", "P"):
                continue
            # csak NYITÁS: előtte csak passzok
            if any((x.get("licit") or "").upper() not in ("PASS", "P")
                   for x in licitek[:i]):
                break
            mag = b.get("magyarazat") or ""
            ules = b.get("ules")
            if not b.get("alert") or not gepi(mag) or ules not in ULESEK:
                break
            talalt += 1
            kez = leosztas.kezek[ules]

            # (A) igazat mond-e a robot?
            all_ = allitas(mag)
            if not all_.get("hossz") and "hcp" not in all_:
                ertelmezhetetlen += 1
            else:
                sertes = allitas_teljesul(all_, kez, ERTEKELOK)
                if sertes:
                    hazug += 1
                    if len(hazugsagok) < 6:
                        hazugsagok.append(
                            f"#{jid} {L} ({kez.pbn()}): {'; '.join(sertes)}"
                            f"\n      robot: {mag[:80]}")

            # (B) jól fordítottunk-e?
            ktx = Kontextus(ules=ules, beliallas=beli,
                            metrika={"PONT": a.metrika,
                                     "JATEKUTES": "J_KLASSZIKUS"})
            jeloltek = [(i2, lic) for i2, lic, fa in szabalyok
                        if kiertekel(fa, kez, ktx) is True]
            mienk = jeloltek[-1][1] if jeloltek else "PASS"
            if mienk == "N" or (len(mienk) == 2 and mienk[1] == "N"):
                mienk = mienk[0] + "NT"
            valodi = L if L != "1N" else "1NT"
            if mienk == valodi:
                egyezik += 1
            else:
                elter += 1
                tevesztes[f"{valodi} -> {mienk}"] += 1
                if len(peldak) < a.peldak:
                    peldak.append(
                        f"{valodi} -> {mienk}  ({kez.pbn()}, "
                        f"HCP={ERTEKELOK['HCP'](kez):g}, "
                        f"TP={ERTEKELOK['AP_321'](kez):g})"
                        f"\n      robot: {mag[:90]}")
            break

    print("=" * 70)
    print(f"  Gépi magyarázatú NYITÁS: {talalt}")
    print("-" * 70)
    print("  (A) IGAZAT MOND-E A ROBOT? — a kimondott feltétel vs. a valódi kéz")
    print(f"      teljesül:          {talalt - hazug - ertelmezhetetlen}")
    print(f"      NEM teljesül:      {hazug}   <- ha >0, a mi elemzőnk hibás")
    print(f"      értelmezhetetlen:  {ertelmezhetetlen}")
    for h in hazugsagok:
        print(f"      ! {h}")
    print("-" * 70)
    arany = 100 * egyezik / talalt if talalt else 0
    print(f"  (B) JÓL FORDÍTOTTUNK-E? — a gib.lr vs. a robot valódi licitje")
    print(f"      egyezik: {egyezik}  ({arany:.1f}%)")
    print(f"      eltér:   {elter}")
    print("-" * 70)
    print("  (C) ELTÉRÉSEK")
    for minta, db in tevesztes.most_common(10):
        print(f"      {db:>4}x  {minta}")
    if peldak:
        print("\n  Példák:")
        for p in peldak:
            print(f"      {p}")
    print("=" * 70)
    print("\n  A (B) arány itt SZIGORÚBB mérce, mint az emberi partikon:")
    print("  a GIB determinisztikus, tehát minden eltérés a MI hibánk.")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
