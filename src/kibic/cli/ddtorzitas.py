"""
A DOUBLE DUMMY TORZÍTÁSÁNAK MÉRÉSE.

MIÉRT. A DD tökéletes lejátszást ÉS tökéletes védekezést feltételez. A
valóságban EGYIK SEM igaz — és ez fontos: nem csak a védelem hibázik, a
felvevő is. A mért eltérés tehát nem "a védelem hibája", hanem a KÉT
HIBA EGYENLEGE:

    a felvevő hibázott  ->  kevesebb ütés a DD-nél  (negatív eltérés)
    a védelem hibázott  ->  több ütés a DD-nél      (pozitív eltérés)

Ez csak akkor mozdítja el a becslést, ha a két oldal nem egyforma
gyakran téved. Hogy így van-e, azt nem feltételezni kell, hanem mérni:
több ezer játszmánk van ismert eredménnyel ÉS DD-táblával.

MÓDSZER
-------
Minden olyan játszmára, ahol van kontraktus, eredmény és DD-tábla:

    eltérés = valódi ütés - DD-ütés     (a felvevő szemszögéből)

Az ELOSZLÁS a lényeg, nem csak az átlag: abból látszik, melyik oldal
hibázott gyakrabban, és mennyivel.

MIT MÉRTÜNK (6440 játszmás gyűjtemény, 2026-09)
-----------------------------------------------
    sima szín        +0.033   szórás 0.85   n=3551    2.3 szigma
    sima SZAN        +0.297   szórás 1.27   n=1549    9.2 szigma
    kontrázott szín  +0.159   szórás 0.84   n= 422    3.9 szigma
    kontrázott szan  +0.270   szórás 1.43   n=  37    1.2 szigma

Fő hatások a "sima szín" alaphoz képest:
    SZAN    +0.264 ütés (7.5 szigma)   <- a DOMINÁNS torzító
    KONTRA  +0.126 ütés (2.9 szigma)

A KÉT HIBA EGYENLEGE, az eloszlásból:

                    felvevő rosszabb   pontosan DD   védelem rosszabb   nettó
    sima szín            21% (-0.25)       56%           24% (+0.28)   +0.03
    sima SZAN            20% (-0.28)       43%           37% (+0.57)   +0.30
    kontrázott szín      16% (-0.18)       57%           27% (+0.34)   +0.16

SZÍNBEN a két hiba majdnem kioltja egymást — a felvevőnek is sok nehéz
döntése van (aduosztás, lopási terv, elszámolás), és körülbelül olyan
gyakran téved, mint a védelem. SZANBAN nem: ott a védelem feladata a
nehezebb (a vak kijátszás dönt, a színfelszabadítás időzítése kritikus,
és nincs adu, ami mentene), a felvevőé pedig inkább számolás. Ezért
marad szanban +0.30 ütés a nettó egyenleg.

Szanban a szórás is másfélszer nagyobb, tehát ott nemcsak elfogultabb,
hanem bizonytalanabb is a becslés.

A kontrázott szan cellája 37 játszmából áll: ±0.24 standard hibával az
"eredménye" zaj. A mérlegelő ezért összevonja (motor.merlegel.MIN_MINTA).

MIT OLVASS KI BELŐLE
--------------------
* A SZIGMA dönt, nem az átlag. Kis mintán a legszebb átlag is zaj.
* A SZÓRÁS legalább olyan fontos: 0.85 szórás mellett az egy-ütéses
  tévedés a szokásos eset, nem a kivétel. Ezért ment az ELOSZLÁS is a
  mentett fájlba — az átlagkorrekciót a kerekítés elnyelné.
* A DD-ütésszám szerinti bontás (--reszletes) a regresszióra figyel: a
  széleken (0 vagy 13 ütés) az eltérés csak egy irányba mehet.

HASZNÁLAT
---------
    source .env
    python -m kibic.cli.ddtorzitas --reszletes
    python -m kibic.cli.ddtorzitas --mentes kalibracio.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict

from ..domain import Kontraktus, vonal


def _kapcsolat(a):
    try:
        import pymysql
    except ImportError:
        print("A pymysql csomag nem érhető el.", file=sys.stderr)
        sys.exit(2)
    return pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4",
                           autocommit=False)


SQL = """
SELECT j.kontraktus, j.felvevo, j.eredmeny_utes, l.dds_utesek, l.beliallas
  FROM jatszma j
  JOIN leosztas l ON l.id = j.leosztas_id
 WHERE j.kontraktus IS NOT NULL
   AND j.kontraktus NOT IN ('PASS','')
   AND j.eredmeny_utes IS NOT NULL
   AND j.felvevo IS NOT NULL
   AND l.dds_utesek IS NOT NULL
"""


def meres(conn, limit: int | None = None):
    cur = conn.cursor()
    cur.execute(SQL + (f" LIMIT {int(limit)}" if limit else ""))

    # kulcs -> eltérések listája
    durva: dict[tuple[bool, bool], list[int]] = defaultdict(list)
    szintenkent: dict[tuple[bool, int], list[int]] = defaultdict(list)
    szinenkent: dict[str, list[int]] = defaultdict(list)
    # DD-ütésszám szerint: a REGRESSZIÓ A KÖZÉPHEZ ellenőrzése. Ha a DD
    # 13 ütést mond, az eltérés csak lefelé mehet — ha ez az összevont
    # átlagot mozgatja, a durva modell félrevezet.
    dd_szerint: dict[int, list[int]] = defaultdict(list)
    hibas = 0

    for kontr_szoveg, felvevo, utes, dds, beli in cur.fetchall():
        try:
            k = Kontraktus.parse(kontr_szoveg, felvevo)
        except ValueError:
            hibas += 1
            continue
        if k is None:
            continue
        tabla = json.loads(dds) if isinstance(dds, str) else dds
        try:
            dd = int(tabla[felvevo][k.szin])
        except (KeyError, TypeError, ValueError):
            hibas += 1
            continue

        elteres = int(utes) - dd
        kontrazott = k.kontra != ""
        szan = k.szin == "NT"
        durva[(kontrazott, szan)].append(elteres)
        szintenkent[(kontrazott, k.szint)].append(elteres)
        szinenkent[k.szin].append(elteres)
        dd_szerint[dd].append(elteres)

    return durva, szintenkent, szinenkent, dd_szerint, hibas


MIN_MINTA = 200            # motor.merlegel.MIN_MINTA


def _sor(cimke: str, ertekek: list[int]) -> str:
    """
    Egy sor a jelentésben. A SZIGMA a lényeg: az átlag önmagában semmit
    nem mond, ha a minta kicsi. A `kevés` jelzés arra figyelmeztet, hogy
    ezt a cellát a mérlegelő úgyis összevonja.
    """
    if not ertekek:
        return f"{cimke:24s}  —"
    n = len(ertekek)
    atl = statistics.mean(ertekek)
    szor = statistics.pstdev(ertekek) if n > 1 else 0.0
    se = szor / (n ** 0.5) if n else 0.0
    szigma = atl / se if se else 0.0
    nulla = sum(1 for e in ertekek if e == 0) / n
    jel = "" if n >= MIN_MINTA else "  kevés!"
    return (f"{cimke:24s}  {atl:+6.3f}  ±{szor:5.2f}  {szigma:+5.1f}\u03c3   "
            f"egyezik: {nulla:4.0%}   n={n}{jel}")


def _kulonbseg(a: list[int], b: list[int], cimke: str) -> None:
    """Két cella különbsége standard hibával — ez dönti el, számít-e."""
    if len(a) < 2 or len(b) < 2:
        return
    ka = statistics.mean(a) - statistics.mean(b)
    se = ((statistics.pstdev(a) ** 2 / len(a)
           + statistics.pstdev(b) ** 2 / len(b)) ** 0.5)
    szigma = ka / se if se else 0.0
    print(f"  {cimke:36s} {ka:+.3f} \u00b1 {se:.3f}  ({szigma:+.1f}\u03c3)")


def jelentes(durva, szintenkent, szinenkent, dd_szerint, hibas,
             reszletes: bool) -> None:
    print("=" * 74)
    print("  A DOUBLE DUMMY TORZÍTÁSA — valódi ütés mínusz DD-ütés")
    print("  A KÉT HIBA EGYENLEGE: negatív = a felvevő hibázott,")
    print("  pozitív = a védelem. Csak az elmozdulás számít, nem az,")
    print("  hogy külön-külön mennyit hibáznak.")
    print("=" * 74)
    print(f"{'kontextus':24s}  {'átlag':>6s}  {'szórás':>6s}  {'szig':>6s}")
    print("-" * 74)
    for kontrazott in (False, True):
        for szan in (False, True):
            cimke = (("kontrázott " if kontrazott else "sima ")
                     + ("szan" if szan else "szín"))
            print(_sor(cimke, durva.get((kontrazott, szan), [])))

    print()
    print("  A KÉT IRÁNY KÜLÖN (az eloszlásból)")
    print(f"  {'kontextus':22s} {'felvevő rosszabb':>17s} {'pontos':>8s} "
          f"{'védelem rosszabb':>17s}")
    print("-" * 74)
    for kontrazott in (False, True):
        for szan in (False, True):
            ert = durva.get((kontrazott, szan), [])
            if not ert:
                continue
            m = len(ert)
            le = [x for x in ert if x < 0]
            fel = [x for x in ert if x > 0]
            cimke = (("kontrázott " if kontrazott else "sima ")
                     + ("szan" if szan else "szín"))
            print(f"  {cimke:22s} {len(le)/m:10.0%} ({sum(le)/m:+.2f}) "
                  f"{ert.count(0)/m:7.0%} {len(fel)/m:10.0%} "
                  f"({sum(fel)/m:+.2f})")
    print()

    sima = durva.get((False, False), []) + durva.get((False, True), [])
    kontr = durva.get((True, False), []) + durva.get((True, True), [])
    print("-" * 74)
    print(_sor("MINDEN sima", sima))
    print(_sor("MINDEN kontrázott", kontr))
    # FŐ HATÁSOK. A 2x2 cella közül a legkisebb szinte mindig gyenge
    # (kevés kontrázott szan van), ezért nem a cellákat hasonlítjuk
    # egyenként, hanem a KÉT HATÁST külön — így a nagy minták viszik a
    # becslést, és látszik, melyik számít valójában.
    ss = durva.get((False, False), [])     # sima szín: a viszonyítási alap
    print()
    print("  FŐ HATÁSOK (a 'sima szín' cellához képest)")
    print("-" * 74)
    _kulonbseg(durva.get((False, True), []), ss, "SZAN hatása")
    _kulonbseg(durva.get((True, False), []), ss, "KONTRA hatása (színben)")
    _kulonbseg(kontr, sima, "kontrázott - sima (összevontan)")
    print()
    szan_h = (statistics.mean(durva[(False, True)]) - statistics.mean(ss)
              if durva.get((False, True)) and ss else 0.0)
    kontra_h = (statistics.mean(durva[(True, False)]) - statistics.mean(ss)
                if durva.get((True, False)) and ss else 0.0)
    if abs(szan_h) > abs(kontra_h) * 1.5:
        print("  A SZAN a domináns torzító, nem a kontra. Nem azért, mert")
        print("  szanban a védelem többet hibázik ABSZOLÚT értelemben, hanem")
        print("  mert ott a felvevő KEVESEBBET: színben a két hiba nagyjából")
        print("  kioltja egymást, szanban nem.")
    elif kontra_h > 0.15:
        print("  A KONTRA a fő hatás: kontrázott kontraktus ellen a")
        print("  védelem gyakrabban hibázik, tehát a korrigálatlan")
        print("  DD-szimuláció túl gyakran kontrázna.")
    else:
        print("  Egyik hatás sem számottevő ezen az anyagon.")

    if reszletes:
        print()
        print("  SZINTENKÉNT")
        print("-" * 74)
        for (kontrazott, szint) in sorted(szintenkent):
            cimke = ("kontrázott " if kontrazott else "sima ") + f"{szint}. szint"
            print(_sor(cimke, szintenkent[(kontrazott, szint)]))
        print()
        print("  A DD-ÜTÉSSZÁM SZERINT (regresszió a középhez)")
        print("  Ha a DD 13 ütést mond, az eltérés csak lefelé mehet — a")
        print("  széleken ezért torzít. Ha a középső tartomány eltér az")
        print("  összevont átlagtól, a durva modell félrevezet.")
        print("-" * 74)
        for dd in sorted(dd_szerint):
            print(_sor(f"DD = {dd} ütés", dd_szerint[dd]))
        print()
        print("  SZÍNENKÉNT")
        print("-" * 74)
        for sz in sorted(szinenkent):
            print(_sor(sz, szinenkent[sz]))

    if hibas:
        print()
        print(f"  Feldolgozhatatlan rekord: {hibas}")
    print("=" * 74)


def kalibracio_json(durva) -> dict:
    """
    A mentett alak. Az ELOSZLÁS a lényeg, nem az átlag: az átlagot a
    kerekítés elnyeli (round(8 + 0.16) = 8), tehát átlagkorrekcióval a
    szimuláció valójában korrigálatlan marad. A mérlegelő ezért a
    hisztogramból HÚZ eltérést minden leosztáshoz.
    """
    ki = {"eltolas": {}, "szoras": {}, "minta_db": {}, "eloszlas": {}}
    for (kontrazott, szan), ertekek in durva.items():
        if not ertekek:
            continue
        kulcs = f"{int(kontrazott)}{int(szan)}"
        ki["eltolas"][kulcs] = round(statistics.mean(ertekek), 4)
        ki["szoras"][kulcs] = round(
            statistics.pstdev(ertekek) if len(ertekek) > 1 else 0.0, 4)
        ki["minta_db"][kulcs] = len(ertekek)
        hiszt: dict[str, int] = {}
        for e in ertekek:
            hiszt[str(e)] = hiszt.get(str(e), 0) + 1
        ki["eloszlas"][kulcs] = dict(sorted(hiszt.items(),
                                            key=lambda kv: int(kv[0])))
    return ki


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="A double dummy torzításának mérése a gyűjteményen")
    ap.add_argument("--reszletes", action="store_true",
                    help="Szintenkénti és színenkénti bontás is")
    ap.add_argument("--mentes", metavar="FAJL",
                    help="A kalibráció mentése JSON-ba "
                         "(motor.merlegel.Kalibracio olvassa)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host",   default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user",   default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    conn = _kapcsolat(a)
    try:
        durva, szintenkent, szinenkent, dd_szerint, hibas = meres(conn, a.limit)
    finally:
        conn.close()

    if not durva:
        print("Nincs mérhető játszma. Van már DD-tábla a leosztásokon "
              "(python -m kibic.cli.ddsfutas --tabla)?", file=sys.stderr)
        return 1

    jelentes(durva, szintenkent, szinenkent, dd_szerint, hibas, a.reszletes)

    if a.mentes:
        with open(a.mentes, "w", encoding="utf8") as f:
            json.dump(kalibracio_json(durva), f, ensure_ascii=False, indent=2)
        print(f"\nKalibráció mentve: {a.mentes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
