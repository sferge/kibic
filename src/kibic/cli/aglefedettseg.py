"""
ÁGANKÉNTI LEFEDETTSÉG — hol tart valójában egy licitrendszer?

MIÉRT. Az eddigi egyetlen szám ("a stand.lr a licitpozíciók 17%-ára ad
szabályt") két dolgot kever össze. A licitálásnak három ága van, és
teljesen máshogy állnak:

    PAROS      mi kezdtünk, ők végig hallgatnak      "1NT-2C"
    KUZDELMI   mi kezdtünk, ők belelicitáltak        "1D (2C) 2H"
    VEDEKEZO   ŐK kezdtek                            "(1S) 2C"

A páros ág az, amit a klasszikus rendszerleírások részletesen kifejtenek,
és amit a LICREN-alak le tud írni. A másik kettő zömmel konvenciókból és
ELVEKBŐL áll ("védekező vonalon a kontra 4♥-ig információs"), és a
LICREN ezekre nem tud feltételt megfogalmazni, mert csak a saját lapról
tud beszélni.

Ez a mérő két kérdésre válaszol:

  1. MILYEN GYAKORI az egyes ágak? (Erre elég a gyűjtemény, rendszer nem
     kell.) Ha kiderül, hogy a páros ág a ritkább, akkor a rendszerek
     részletessége és a valódi igény között szakadék van.
  2. MENNYIT FED a rendszerünk ÁGANKÉNT? Ez az igazi állapotjelentés.

HASZNÁLAT
---------
    source .env
    python -m kibic.cli.aglefedettseg                       # csak eloszlás
    python -m kibic.cli.aglefedettseg --rendszer LICREN_STAND
    python -m kibic.cli.aglefedettseg --par "gal - korszurku"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict

from ..domain import ULESEK, vonal
from ..motor.minta import (AGAK, MintaHiba, kanonizal, menet_ag, minta_parse)


def _kapcsolat(a):
    try:
        import pymysql
    except ImportError:
        print("A pymysql csomag nem érhető el.", file=sys.stderr)
        sys.exit(2)
    return pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4",
                           autocommit=False)


# --- 1. Az ágak gyakorisága a gyűjteményben --------------------------

def ag_eloszlas(conn, limit: int | None = None, par: str | None = None):
    """
    Minden LICITPOZÍCIÓRA (ahol egy játékos döntött) kiszámoljuk, melyik
    ágban volt. A passzokat is beleszámoljuk: a passz is döntés.
    """
    cur = conn.cursor()
    # A `jatszma` a négy játékost tárolja, párt nem — a pár a két
    # játékos-id normalizált párosa (005_par.sql).
    if par:
        sql = ("SELECT j.licit,"
               "  CASE WHEN LEAST(j.n_jatekos_id,j.s_jatekos_id)=p.jatekos_a"
               "        AND GREATEST(j.n_jatekos_id,j.s_jatekos_id)=p.jatekos_b"
               "       THEN 'NS' ELSE 'EW' END AS vonal"
               " FROM jatszma j JOIN par p ON"
               "  (LEAST(j.n_jatekos_id,j.s_jatekos_id)=p.jatekos_a AND"
               "   GREATEST(j.n_jatekos_id,j.s_jatekos_id)=p.jatekos_b) OR"
               "  (LEAST(j.e_jatekos_id,j.w_jatekos_id)=p.jatekos_a AND"
               "   GREATEST(j.e_jatekos_id,j.w_jatekos_id)=p.jatekos_b)"
               " WHERE j.licit IS NOT NULL AND p.nev = %s")
    else:
        sql = "SELECT j.licit, NULL FROM jatszma j WHERE j.licit IS NOT NULL"
    if limit:
        sql += f" LIMIT {int(limit)}"
    cur.execute(sql, (par,) if par else ())

    szamlalo: Counter = Counter()
    pozicio_ag: dict[str, Counter] = defaultdict(Counter)
    partik = 0

    for licit_json, mi_vonal in cur.fetchall():
        licitek = (json.loads(licit_json) if isinstance(licit_json, str)
                   else licit_json)
        if not licitek:
            continue
        partik += 1
        for i, elem in enumerate(licitek):
            ules = elem.get("ules")
            if ules not in ULESEK:
                continue
            # Ha egy PÁRT vizsgálunk, csak az Ő döntéseik számítanak:
            # a másik vonal helyzeteit nem ők oldják meg.
            if mi_vonal and vonal(ules) != mi_vonal:
                continue
            try:
                _, tokenek = kanonizal(licitek[:i], ules) if i else ("", [])
            except Exception:          # noqa: BLE001
                continue
            ag = menet_ag(tokenek)
            szamlalo[ag] += 1
            # a licit fajtája is érdekes: a kontra aránya áganként
            l = str(elem.get("licit", "")).upper()
            fajta = ("passz" if l in ("P", "PASS")
                     else "kontra" if l in ("X", "XX", "DBL", "RDBL")
                     else "licit")
            pozicio_ag[ag][fajta] += 1

    return szamlalo, pozicio_ag, partik


# --- 2. Mennyit fed a rendszer áganként ------------------------------

def rendszer_agak(conn, rendszer_kod: str):
    """A rendszer szabályainak ág szerinti megoszlása."""
    from ..motor.feloldas import feloldas
    f = feloldas(conn, rendszer_kod)
    szamlalo: Counter = Counter()
    hibas = 0
    for s in f.sorok:
        try:
            szamlalo[minta_parse(s.minta).ag] += 1
        except MintaHiba:
            hibas += 1
    return f, szamlalo, hibas


# --- Jelentés --------------------------------------------------------

def _sav(arany: float, szeles: int = 28) -> str:
    n = int(round(arany * szeles))
    return "█" * n + "·" * (szeles - n)


def jelentes(szamlalo, pozicio_ag, partik, rendszer=None):
    ossz = sum(szamlalo.values())
    print("=" * 72)
    print("  A LICITÁLÁS HÁROM ÁGA — hány döntési helyzet esik melyikbe")
    print(f"  {partik} parti, {ossz} licitpozíció")
    print("=" * 72)
    for ag in ("PAROS", "KUZDELMI", "VEDEKEZO"):
        n = szamlalo.get(ag, 0)
        arany = n / ossz if ossz else 0
        r = pozicio_ag.get(ag, Counter())
        print(f"  {ag:10s} {_sav(arany)} {arany:5.1%}  ({n})")
        if r:
            m = sum(r.values())
            print(f"  {'':10s} ebből passz {r['passz']/m:4.0%}, "
                  f"licit {r['licit']/m:4.0%}, kontra {r['kontra']/m:4.0%}")
    print()
    paros = szamlalo.get("PAROS", 0) / ossz if ossz else 0
    if paros < 0.5:
        print(f"  A páros ág a döntések {paros:.0%}-a. A klasszikus")
        print("  rendszerleírások viszont jórészt EZT fejtik ki — a")
        print("  részletesség és a valódi igény szétválik.")

    if rendszer:
        f, sz, hibas = rendszer
        ossz_sz = sum(sz.values())
        print()
        print("=" * 72)
        print(f"  A(Z) {f.rendszer_kod} SZABÁLYAI ÁGANKÉNT ({ossz_sz} sor)")
        print("=" * 72)
        for ag in AGAK:
            n = sz.get(ag, 0)
            if not n and ag == "BARMELYIK":
                continue
            arany = n / ossz_sz if ossz_sz else 0
            print(f"  {ag:10s} {_sav(arany)} {arany:5.1%}  ({n})")
        if hibas:
            print(f"  értelmezhetetlen minta: {hibas}")
        print()
        print("  Ahol a két megoszlás eltér, ott van a hiány: ha a")
        print("  döntések fele védekező ágban van, de a szabályok 2%-a,")
        print("  akkor a rendszer ott gyakorlatilag néma.")
    print("=" * 72)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="A licitálás három ágának gyakorisága és lefedettsége")
    ap.add_argument("--rendszer", help="Rendszer kódja (pl. LICREN_STAND)")
    ap.add_argument("--par", help="Csak ennek a párnak a partijai")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host",   default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user",   default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    conn = _kapcsolat(a)
    try:
        szamlalo, pozicio_ag, partik = ag_eloszlas(conn, a.limit, a.par)
        rend = rendszer_agak(conn, a.rendszer) if a.rendszer else None
    finally:
        conn.close()

    if not szamlalo:
        print("Nincs mérhető licitmenet.", file=sys.stderr)
        return 1
    jelentes(szamlalo, pozicio_ag, partik, rend)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
