"""
A-MÓDÚ MÉRÉS: a licitrendszer összevetése a valódi emberi licitekkel.

Ez az első valódi mérés a roadmap 1. fázisából. Két kérdésre válaszol:

  1. Melyik PONT-metrika (a `@PONT` feloldása) reprodukálja legjobban a
     valódi liciteket? Eddig ez tippelés lett volna — most mérés.
  2. Mennyire pontos egyáltalán a rendszer a gyűjtemény anyagán?

MÓDSZER
-------
Minden olyan licithez, ahol a játékos NYITOTT (a licitmenet első
nem-passz bemondása), megnézzük:
  * mit mond a rendszer erre a kézre (a szabályok kiértékelésével)
  * mit licitált valójában az ember

Az egyezési arány a mérőszám. FONTOS: a gyűjtemény játékosai NEM ezt a
rendszert játsszák, tehát az abszolút arány alacsony lesz. Ami számít,
az a metrikák KÖZÖTTI különbség — ugyanazon az anyagon, ugyanazzal a
szabályhalmazzal.

HASZNÁLAT
---------
    # offline, közvetlenül a .lr fájlból és PBN-ekből
    python -m kibic.cli.meres --lr rendszerek/gfk/stand.lr \\
        --partik "tanpartik/**/*.pbn" --metrikak P_HCP,P_HOSSZ,P_AP531,ZAR

    # az adatbázisból (a betöltött rendszer és a 3502 parti)
    python -m kibic.cli.meres --rendszer LICREN_STAND --db
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..domain import ERTEKELOK, Kez, Leosztas, ULESEK
from ..impex.licren import fordit, olvas
from ..motor.kifejezes import Kontextus, ismeretlen_jelzok, kiertekel

ALAP_METRIKAK = ["P_HCP", "P_HOSSZ", "P_HOSSZ5", "P_AP531", "P_AP321"]


def normalizal(licit: str) -> str:
    """
    Licitjelölés egységesítése az ÖSSZEHASONLÍTÁS előtt.

    A LICREN `N`-t ír szanra (`2N`), a PBN `NT`-t (`2NT`) — ugyanaz a
    licit. Enélkül minden szan-egyezés tévesztésnek látszana.
    """
    L = (licit or "").strip().upper()
    if L in ("P", "PASS"):
        return "PASS"
    if L in ("X", "DBL"):
        return "X"
    if L in ("XX", "RDBL"):
        return "XX"
    if len(L) == 2 and L[0] in "1234567" and L[1] == "N":
        return L[0] + "NT"
    return L


# --- Szabályok betöltése ---------------------------------------------

@dataclass
class Szabalysor:
    """Egy kiértékelhető szabály: mit licitáljunk, ha a feltétel igaz."""
    licit: str
    fa: dict
    prioritas: int
    nyers: str = ""


def szabalyok_lr(ut: str) -> list[Szabalysor]:
    """A NYITÁSI szabályok a .lr fájlból (a START blokk)."""
    r = olvas(ut)
    ki: list[Szabalysor] = []
    for i, sz in enumerate(r.inditasok.szabalyok):
        if not sz.ast:
            continue
        ki.append(Szabalysor(normalizal(sz.licit), fordit(sz.ast), (i + 1) * 10,
                             f"{sz.licit}:{sz.feltetel}"))
    return ki


def szabalyok_db(conn, rendszer_kod: str) -> list[Szabalysor]:
    """A nyitási szabályok az adatbázisból, a hivatkozási lánc feloldásával."""
    from ..db.tudastar import rendszer_lanc
    cur = conn.cursor()
    # A specifikusabb rendszer FELÜLÍRJA a szülő azonos kulcsú sorait
    latott: set[str] = set()
    ki: list[Szabalysor] = []
    for rid in rendszer_lanc(conn, rendszer_kod):
        cur.execute(
            "SELECT minta, kulcs, feltetel, prioritas, nyers_szoveg"
            "  FROM licitmenet"
            " WHERE rendszer_id=%s AND tipus='SZABALY'"
            "   AND allapot='ELFOGADOTT' AND feltetel IS NOT NULL"
            "   AND alfejezet='START'"
            " ORDER BY prioritas", (rid,))
        sajat: list[Szabalysor] = []
        for minta, kulcs, feltetel, prioritas, nyers in cur.fetchall():
            if kulcs in latott:
                continue          # a specifikusabb rendszer már felülírta
            fa = json.loads(feltetel) if isinstance(feltetel, str) else feltetel
            sajat.append(Szabalysor(normalizal(minta.split("-")[-1]), fa,
                                    prioritas or 0, nyers or ""))
        latott.update(s.licit for s in sajat)
        ki.extend(sajat)
    return sorted(ki, key=lambda s: s.prioritas)


# --- Döntés -----------------------------------------------------------

def dontes(szabalyok: list[Szabalysor], kez: Kez, ktx: Kontextus,
           mod: str = "SORREND") -> tuple[str | None, list[str], int]:
    """
    Mit licitál a rendszer erre a kézre?
    Visszaad: (döntés, a jelölthalmaz, hány szabály maradt eldönthetetlen)
    """
    jeloltek: list[tuple[int, str]] = []
    bizonytalan = 0
    for sz in szabalyok:
        e = kiertekel(sz.fa, kez, ktx)
        if e is True:
            jeloltek.append((sz.prioritas, sz.licit))
        elif e is None:
            bizonytalan += 1
    if not jeloltek:
        return None, [], bizonytalan
    if mod == "SORREND":
        # A LICREN-ben az UTOLSÓ illeszkedő nyer (növekvő prioritás)
        gyoztes = max(jeloltek, key=lambda x: x[0])[1]
    else:
        gyoztes = jeloltek[0][1]
    return gyoztes, [l for _, l in jeloltek], bizonytalan


# --- Mérés ------------------------------------------------------------

@dataclass
class Eredmeny:
    metrika: str
    vizsgalt: int = 0
    egyezik: int = 0
    passz_egyezik: int = 0
    passz_ossz: int = 0
    nyitas_egyezik: int = 0
    nyitas_ossz: int = 0
    elter: int = 0
    nincs_dontes: int = 0
    bizonytalan_szabaly: int = 0
    tobb_jelolt: int = 0
    tevesztes: Counter = field(default_factory=Counter)

    @property
    def arany(self) -> float:
        return 100.0 * self.egyezik / self.vizsgalt if self.vizsgalt else 0.0


def _nyitasi_esetek(licitek, leosztas) -> list[tuple[Kez, str, str, str]]:
    """
    Egy parti nyitási esetei: (kéz, valódi licit, ülés, beliállás).

    FONTOS: a PASSZOKAT IS gyűjtjük, a nyitás előtti üléseknél. Enélkül
    egy "mindent kinyitó" metrika hibátlannak látszana — a passzolt
    kezeknél épp az a helyes döntés, hogy NINCS nyitás.
    A nyitás után megállunk: onnantól már nem nyitási helyzet.
    """
    ki = []
    for b in licitek or []:
        licit = normalizal(b.get("licit") or "")
        ules = b.get("ules")
        if ules not in ULESEK:
            break
        if licit == "PASS":
            ki.append((leosztas.kezek[ules], "PASS", ules, leosztas.beliallas))
            continue
        ki.append((leosztas.kezek[ules], licit, ules, leosztas.beliallas))
        break
    return ki


def nyitasok_gyujtese(partik) -> list[tuple[Kez, str, str, str]]:
    ki = []
    for j in partik:
        if not j.licit or j.leosztas is None:
            continue
        ki.extend(_nyitasi_esetek(j.licit, j.leosztas))
    return ki


def mer(szabalyok: list[Szabalysor], nyitasok, metrika: str,
        jatekutes: str = "J_KLASSZIKUS") -> Eredmeny:
    er = Eredmeny(metrika)
    for kez, valodi, ules, beli in nyitasok:
        ktx = Kontextus(ules=ules, beliallas=beli,
                        metrika={"PONT": metrika, "JATEKUTES": jatekutes})
        d, jeloltek, bizonytalan = dontes(szabalyok, kez, ktx)
        er.vizsgalt += 1
        er.bizonytalan_szabaly += bizonytalan
        if len(jeloltek) > 1:
            er.tobb_jelolt += 1
        if d is None:
            d = "PASS"          # nincs illeszkedő szabály = nem nyitunk
            er.nincs_dontes += 1
        if valodi == "PASS":
            er.passz_ossz += 1
        else:
            er.nyitas_ossz += 1
        if d == valodi:
            er.egyezik += 1
            if valodi == "PASS":
                er.passz_egyezik += 1
            else:
                er.nyitas_egyezik += 1
        else:
            er.elter += 1
            er.tevesztes[f"{valodi} -> {d}"] += 1
    return er


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="A-módú mérés: metrika-választás")
    ap.add_argument("--lr", help="LICREN .lr fájl (offline mód)")
    ap.add_argument("--rendszer", help="Rendszerkód az adatbázisból")
    ap.add_argument("--partik", help="PBN-fájlok (offline mód)")
    ap.add_argument("--db", action="store_true",
                    help="A partikat az adatbázisból olvassa")
    ap.add_argument("--metrikak", default=",".join(ALAP_METRIKAK))
    ap.add_argument("--jatekutes", default="J_KLASSZIKUS")
    ap.add_argument("--tevesztes", type=int, default=8,
                    help="Hány tévesztés-mintát írjon ki")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    conn = None
    if a.rendszer or a.db:
        import pymysql
        conn = pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                               database=a.adatbazis, charset="utf8mb4")
        from ..domain.ertekelo import betolt_adatbazisbol
        betolt_adatbazisbol(conn)

    # --- szabályok ---
    if a.lr:
        szabalyok = szabalyok_lr(a.lr)
        forras = a.lr
    elif a.rendszer:
        szabalyok = szabalyok_db(conn, a.rendszer)
        forras = a.rendszer
    else:
        ap.error("Adj meg --lr vagy --rendszer paramétert")

    # --- partik ---
    if a.db:
        nyitasok = _nyitasok_db(conn)
    elif a.partik:
        from ..impex import pbn
        partik = []
        for m in sorted(glob.glob(a.partik, recursive=True)):
            with open(m, encoding="utf-8-sig", errors="replace") as f:
                partik.extend(pbn.olvas(f.read()))
        nyitasok = nyitasok_gyujtese(partik)
    else:
        ap.error("Adj meg --partik vagy --db paramétert")

    print("=" * 70)
    print(f"  Rendszer: {forras}")
    print(f"  Nyitási szabály: {len(szabalyok)}")
    print(f"  Vizsgált valódi nyitás: {len(nyitasok)}")
    print("=" * 70)

    hianyzo = [m for m in a.metrikak.split(",") if m and m not in ERTEKELOK]
    if hianyzo:
        print(f"  FIGYELEM: ismeretlen metrika: {hianyzo}")

    eredmenyek = []
    for metrika in a.metrikak.split(","):
        if not metrika or metrika in hianyzo:
            continue
        eredmenyek.append(mer(szabalyok, nyitasok, metrika, a.jatekutes))

    eredmenyek.sort(key=lambda e: -e.arany)
    print(f"\n  {'METRIKA':<12} {'ÖSSZES':>13} {'PASSZ':>13} {'NYITÁS':>13} "
          f"{'TÖBB JELÖLT':>12}")
    print("  " + "-" * 68)
    for e in eredmenyek:
        pa = 100.0 * e.passz_egyezik / e.passz_ossz if e.passz_ossz else 0
        ny = 100.0 * e.nyitas_egyezik / e.nyitas_ossz if e.nyitas_ossz else 0
        print(f"  {e.metrika:<12} {e.egyezik:>6} ({e.arany:4.1f}%) "
              f"{e.passz_egyezik:>6} ({pa:4.1f}%) "
              f"{e.nyitas_egyezik:>6} ({ny:4.1f}%) {e.tobb_jelolt:>12}")
    print("\n  A PASSZ-oszlop a fontos kontroll: egy 'mindent kinyitó'"
          "\n  metrika ott bukik el, akkor is, ha a nyitásokat eltalálja.")

    if eredmenyek and a.tevesztes:
        legjobb = eredmenyek[0]
        print(f"\n  A legjobb ({legjobb.metrika}) tipikus tévesztései:")
        for minta, db in legjobb.tevesztes.most_common(a.tevesztes):
            print(f"      {db:>4}x  {minta}")

    if conn:
        conn.close()
    return 0


def _nyitasok_db(conn):
    """A valódi nyitások az adatbázisból."""
    cur = conn.cursor()
    cur.execute(
        "SELECT l.kezek_pbn, l.oszto, l.beliallas, j.licit"
        "  FROM jatszma j JOIN leosztas l ON l.id=j.leosztas_id"
        " WHERE j.licit IS NOT NULL")
    ki = []
    for kezek_pbn, oszto, beli, licit_j in cur.fetchall():
        try:
            leosztas = Leosztas.pbn_bol(kezek_pbn, oszto, beli)
            licitek = json.loads(licit_j) if isinstance(licit_j, str) else licit_j
        except Exception:      # noqa: BLE001
            continue
        ki.extend(_nyitasi_esetek(licitek, leosztas))
    return ki


if __name__ == "__main__":
    raise SystemExit(main())
