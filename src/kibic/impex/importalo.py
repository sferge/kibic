"""
Importáló: jegyzőkönyv-fájl -> adatbázis.

Használat:
    python -m kibic.impex.importalo "tanpartik/**/*.pbn" --dry-run
    python -m kibic.impex.importalo "tanpartik/**/*.pbn"
    python -m kibic.impex.importalo "arany/*.pbn" --cimke arany_keszlet

Kapcsolati adatok környezeti változóból (a jelszó ne kerüljön a
shell-előzményekbe):  KIBIC_DB, KIBIC_HOST, KIBIC_USER, KIBIC_PASS

Tervezési elv: a domain-mag és az olvasók semmit nem tudnak az
adatbázisról. Ez a modul a leképező réteg — a motor sosem olvas
közvetlenül a DB-ből, hanem ezen keresztül kap domain-objektumokat.

Az importálás IDEMPOTENS: a már betöltött fájlokat (fájl-hash alapján)
kihagyja, hacsak a --ujra kapcsolót nem adod meg.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field

from . import lin, pbn
from ..domain import ULESEK, ertekeld, pontszam_ns


def _olvaso(ut: str):
    """A kiterjesztés alapján választ olvasót. Mindkettő PbnJatszma-t ad."""
    return lin if ut.lower().endswith(".lin") else pbn


def jatszma_hash(j) -> str | None:
    """
    Duplikáció-védelem: a leosztásból, a négy játékosból és a
    licitmenetből. A LIN-ben nincs parti-azonosító, ezért kell.
    """
    if j.leosztas is None:
        return None
    jat = j.jatekosok()
    resz = [j.leosztas.hash,
            "|".join((jat.get(u) or "").strip().lower() for u in ULESEK),
            "|".join(f"{b.get('ules')}{b.get('licit')}" for b in (j.licit or []))]
    return hashlib.sha256("~".join(resz).encode()).hexdigest()


# --- Statisztika ------------------------------------------------------

@dataclass
class Statisztika:
    fajlok: int = 0
    kihagyott_fajl: int = 0
    duplikalt_jatszma: int = 0
    rekordok: int = 0
    ervenyes_leosztas: int = 0
    hibas_leosztas: int = 0
    egyedi_leosztas: int = 0
    van_licit: int = 0
    alertes_licit: int = 0
    van_lejatszas: int = 0
    teljes_lejatszas: int = 0
    claim: int = 0
    pont_egyezik: int = 0
    pont_elter: int = 0
    pont_nincs: int = 0
    max_alak_hossz: int = 0
    max_alak_pelda: str = ""
    hianyos_cimkek: Counter = field(default_factory=Counter)
    jatekosok: Counter = field(default_factory=Counter)
    figyelmeztetesek: list[str] = field(default_factory=list)
    elteresek: list[str] = field(default_factory=list)

    def kiir(self, betoltes: bool) -> None:
        p = print
        p("=" * 62)
        p(f"  Mód:                      {'BETÖLTÉS' if betoltes else 'DRY-RUN'}")
        p(f"  Feldolgozott fájl:        {self.fajlok}"
          f"   (kihagyva, mert már bent volt: {self.kihagyott_fajl})")
        p(f"  Rekord:                   {self.rekordok}"
          f"   (duplikált játszma: {self.duplikalt_jatszma})")
        p(f"  Érvényes kiosztás:        {self.ervenyes_leosztas}"
          f"   (hibás: {self.hibas_leosztas})")
        p(f"  Egyedi leosztás:          {self.egyedi_leosztas}")
        p(f"  Van licitmenet:           {self.van_licit}"
          f"   (alertelt licit: {self.alertes_licit})")
        p(f"  Van lejátszás:            {self.van_lejatszas}"
          f"   (teljes: {self.teljes_lejatszas}, claim: {self.claim})")
        p(f"  Leghosszabb alak-string:  {self.max_alak_hossz} karakter"
          f"   ({self.max_alak_pelda})")
        p("-" * 62)
        p("  PONTSZÁM-ELLENŐRZÉS (a saját motorunk vs. a jegyzőkönyv)")
        p(f"    egyezik:    {self.pont_egyezik}")
        p(f"    eltér:      {self.pont_elter}")
        p(f"    nincs adat: {self.pont_nincs}")
        if self.elteresek:
            p("  Eltérések:")
            for e in self.elteresek[:15]:
                p(f"    ! {e}")
        if self.hianyos_cimkek:
            p("-" * 62)
            p("  KIOSZTÁS NÉLKÜLI REKORDOK címkemintái (parser-diagnosztika):")
            for minta, db in self.hianyos_cimkek.most_common(8):
                p(f"    {db:>5}x  [{minta}]")
        p("-" * 62)
        p(f"  Játékosok ({len(self.jatekosok)}):")
        for nev, db in self.jatekosok.most_common(12):
            p(f"    {nev:<24} {db:>5} játszma")
        if self.figyelmeztetesek:
            p("-" * 62)
            p(f"  Figyelmeztetés ({len(self.figyelmeztetesek)}):")
            for f in self.figyelmeztetesek[:8]:
                p(f"    ~ {f}")
        p("=" * 62)


def _statisztikaz(st: Statisztika, j: pbn.PbnJatszma, cimke_dg: str) -> bool:
    """
    Egy rekord felvétele a statisztikába. Ugyanazt csinálja dry-run és
    betöltés módban, hogy a két kimutatás összehasonlítható legyen.
    Visszaad: feldolgozható-e a rekord (van-e kiosztása).
    """
    for w in j.figyelmeztetesek:
        st.figyelmeztetesek.append(f"{cimke_dg}: {w}")

    if j.leosztas is None:
        st.hibas_leosztas += 1
        st.hianyos_cimkek[",".join(sorted(j.cimkek)[:6]) or "(nincs címke)"] += 1
        return False

    st.ervenyes_leosztas += 1
    if j.licit:
        st.van_licit += 1
    st.alertes_licit += sum(1 for b in j.licit if b.get("alert"))
    if j.lapok:
        st.van_lejatszas += 1
        if len(j.lapok) == 52:
            st.teljes_lejatszas += 1
    if j.claim_utes:
        st.claim += 1

    # Séma-ellenőrzés: elfér-e az alak-string az oszlopban?
    for u in ULESEK:
        a = j.leosztas.kezek[u].alak
        if len(a) > st.max_alak_hossz:
            st.max_alak_hossz, st.max_alak_pelda = len(a), a

    for u, nev in j.jatekosok().items():
        if nev:
            st.jatekosok[nev.strip().lower()] += 1

    if j.pontszam_ns is None or j.eredmeny_utes is None:
        st.pont_nincs += 1
    else:
        szamitott = pontszam_ns(j.kontraktus, j.eredmeny_utes,
                                j.leosztas.beliallas)
        if szamitott == j.pontszam_ns:
            st.pont_egyezik += 1
        else:
            st.pont_elter += 1
            st.elteresek.append(
                f"{cimke_dg}: {j.kontraktus} {j.felvevo} {j.eredmeny_utes} ütés "
                f"{j.leosztas.beliallas} -> saját {szamitott}, "
                f"jegyzőkönyv {j.pontszam_ns}")
    return True


# --- Elemzés (adatbázis nélkül) --------------------------------------

def elemez(utak: list[str]) -> Statisztika:
    st = Statisztika()
    hashek: set[str] = set()
    for ut in utak:
        st.fajlok += 1
        with open(ut, encoding="utf-8-sig", errors="replace") as f:
            szoveg = f.read()
        for j in _olvaso(ut).olvas(szoveg):
            st.rekordok += 1
            cimke_dg = f"{ut.rsplit('/', 1)[-1]}#{j.tabla_szam}"
            if not _statisztikaz(st, j, cimke_dg):
                continue
            if j.leosztas.hash not in hashek:
                hashek.add(j.leosztas.hash)
                st.egyedi_leosztas += 1
    return st


# --- Adatbázis-réteg --------------------------------------------------

DB_HIBA = ("A pymysql csomag nem érhető el. Telepítés: pip install pymysql\n"
           "Dry-run módban (--dry-run) adatbázis nélkül is fut.")


class Betolto:
    """Leképező réteg: PbnJatszma -> adatbázissorok."""

    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()
        self._jatekos: dict[str, int] = {}
        self._esemeny: dict[tuple, int] = {}
        self.cur.execute("SELECT kod, id FROM ertekelo")
        self._ertekelo: dict[str, int] = {k: i for k, i in self.cur.fetchall()}

    # -- segédek --

    def jatekos_id(self, nev: str) -> int | None:
        nev = (nev or "").strip()
        if not nev:
            return None
        kulcs = nev.lower()
        if kulcs in self._jatekos:
            return self._jatekos[kulcs]
        self.cur.execute("SELECT id FROM jatekos WHERE azonosito=%s", (kulcs,))
        r = self.cur.fetchone()
        if not r:
            self.cur.execute(
                "INSERT INTO jatekos (azonosito, megjelenit) VALUES (%s,%s)",
                (kulcs, nev))
            uj = self.cur.lastrowid
        else:
            uj = r[0]
        self._jatekos[kulcs] = uj
        return uj

    def esemeny_id(self, cimkek: dict) -> int | None:
        nev = (cimkek.get("Event") or "").strip()
        if not nev:
            return None
        helyszin = (cimkek.get("Site") or "").strip() or None
        datum = (cimkek.get("Date") or "").replace(".", "-").strip() or None
        if datum and ("?" in datum or len(datum) < 8):
            datum = None
        szamolas = (cimkek.get("Scoring") or "").strip().upper()
        if szamolas not in ("MP", "IMP", "BAM", "RUBBER"):
            szamolas = "ISMERETLEN"
        kulcs = (nev, datum, helyszin)
        if kulcs in self._esemeny:
            return self._esemeny[kulcs]
        self.cur.execute(
            "SELECT id FROM esemeny WHERE nev=%s AND datum<=>%s AND helyszin<=>%s",
            (nev, datum, helyszin))
        r = self.cur.fetchone()
        if not r:
            self.cur.execute(
                "INSERT INTO esemeny (nev, helyszin, datum, szamolas)"
                " VALUES (%s,%s,%s,%s)", (nev, helyszin, datum, szamolas))
            uj = self.cur.lastrowid
        else:
            uj = r[0]
        self._esemeny[kulcs] = uj
        return uj

    def forras_fajl_id(self, ut: str, tartalom: str, formatum: str,
                       nyerset_ments: bool) -> tuple[int, bool]:
        """Visszaad: (id, mar_importalva)."""
        h = hashlib.sha256(tartalom.encode()).hexdigest()
        self.cur.execute("SELECT id FROM forras_fajl WHERE fajl_hash=%s", (h,))
        r = self.cur.fetchone()
        if r:
            return r[0], True
        self.cur.execute(
            "INSERT INTO forras_fajl (fajlnev, formatum, fajl_hash, meret_bajt,"
            " nyers_tartalom) VALUES (%s,%s,%s,%s,%s)",
            (ut.rsplit("/", 1)[-1], formatum, h, len(tartalom.encode()),
             tartalom if nyerset_ments else None))
        return self.cur.lastrowid, False

    def leosztas_id(self, leosztas) -> tuple[int, bool]:
        """Visszaad: (id, uj_e)."""
        h = leosztas.hash
        self.cur.execute("SELECT id FROM leosztas WHERE leosztas_hash=%s", (h,))
        r = self.cur.fetchone()
        if r:
            return r[0], False

        k = leosztas.kezek
        self.cur.execute(
            "INSERT INTO leosztas (kezek_pbn, leosztas_hash, oszto, beliallas,"
            " tabla_szam, forras, n_hcp, e_hcp, s_hcp, w_hcp,"
            " n_alak, e_alak, s_alak, w_alak,"
            " n_kiegyensulyozott, e_kiegyensulyozott,"
            " s_kiegyensulyozott, w_kiegyensulyozott)"
            " VALUES (%s,%s,%s,%s,%s,'IMPORT',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (leosztas.pbn("N"), h, leosztas.oszto, leosztas.beliallas,
             leosztas.tabla_szam,
             *[leosztas.hcp(u) for u in ULESEK],
             *[k[u].alak for u in ULESEK],
             *[int(k[u].kiegyensulyozott) for u in ULESEK]))
        lid = self.cur.lastrowid

        sorok = [(lid, u, self._ertekelo[kod], ertek)
                 for u in ULESEK
                 for kod, ertek in ertekeld(k[u]).items()
                 if kod in self._ertekelo]
        if sorok:
            self.cur.executemany(
                "INSERT INTO kez_ertek (leosztas_id, ules, ertekelo_id, ertek)"
                " VALUES (%s,%s,%s,%s)", sorok)
        return lid, True

    def jatszma_beszur(self, j: pbn.PbnJatszma, leosztas_id: int,
                       esemeny_id: int | None, forras_id: int,
                       cimke: str | None) -> int:
        jat = j.jatekosok()
        ids = {u: self.jatekos_id(jat[u]) for u in ULESEK}

        lejatszas = None
        if j.lapok:
            d = {"lapok": j.lapok}
            if j.claim_utes:
                d["claim_utes"] = j.claim_utes
                d["claim_utesszam"] = j.claim_utesszam
            lejatszas = json.dumps(d, ensure_ascii=False)

        szamitott, allapot = None, "NEM_ELLENORIZVE"
        if j.eredmeny_utes is not None and j.leosztas:
            szamitott = pontszam_ns(j.kontraktus, j.eredmeny_utes,
                                    j.leosztas.beliallas)
            if j.pontszam_ns is not None:
                allapot = "EGYEZIK" if szamitott == j.pontszam_ns else "ELTER"

        cimkek = [c for c in (cimke, "claim" if j.claim_utes else None) if c]

        jhash = jatszma_hash(j)
        if jhash:
            self.cur.execute("SELECT id FROM jatszma WHERE jatszma_hash=%s",
                             (jhash,))
            r = self.cur.fetchone()
            if r:
                return -r[0]          # negatív id = MÁR MEGVOLT

        self.cur.execute(
            "INSERT INTO jatszma (jatszma_hash, leosztas_id, esemeny_id, forras_fajl_id,"
            " n_jatekos_id, e_jatekos_id, s_jatekos_id, w_jatekos_id,"
            " licit, lejatszas, felvevo, kontraktus, eredmeny_utes,"
            " pontszam_ns, mp_szazalek_ns, pontszam_ellenorzott,"
            " pontszam_szamitott, cimkek)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (jhash, leosztas_id, esemeny_id, forras_id,
             ids["N"], ids["E"], ids["S"], ids["W"],
             json.dumps(j.licit, ensure_ascii=False) if j.licit else None,
             lejatszas, j.felvevo,
             str(j.kontraktus) if j.kontraktus else "PASS",
             j.eredmeny_utes, j.pontszam_ns, _mp(j.cimkek),
             allapot, szamitott, ",".join(cimkek) or None))
        return self.cur.lastrowid


def _mp(cimkek: dict) -> float | None:
    v = (cimkek.get("ScorePercentage") or "").strip()
    if not v:
        return None
    reszek = v.split()
    try:
        szam = float(reszek[-1])
    except ValueError:
        return None
    return szam if reszek[0].upper() != "EW" else 100.0 - szam


def betolt(utak: list[str], db: str, host: str, user: str, jelszo: str,
           cimke: str | None = None, nyerset_ments: bool = False,
           ujra: bool = False) -> Statisztika:
    try:
        import pymysql
    except ImportError:
        print(DB_HIBA, file=sys.stderr)
        sys.exit(2)

    conn = pymysql.connect(host=host, user=user, password=jelszo,
                           database=db, charset="utf8mb4", autocommit=False)
    st = Statisztika()
    b = Betolto(conn)
    try:
        for ut in utak:
            st.fajlok += 1
            with open(ut, encoding="utf-8-sig", errors="replace") as f:
                szoveg = f.read()

            formatum = "LIN" if ut.lower().endswith(".lin") else "PBN"
            fid, mar_volt = b.forras_fajl_id(ut, szoveg, formatum, nyerset_ments)
            if mar_volt and not ujra:
                st.kihagyott_fajl += 1
                continue

            for j in _olvaso(ut).olvas(szoveg):
                st.rekordok += 1
                cimke_dg = f"{ut.rsplit('/', 1)[-1]}#{j.tabla_szam}"
                if not _statisztikaz(st, j, cimke_dg):
                    continue
                lid, uj = b.leosztas_id(j.leosztas)
                if uj:
                    st.egyedi_leosztas += 1
                eid = b.esemeny_id(j.cimkek)
                if b.jatszma_beszur(j, lid, eid, fid, cimke) < 0:
                    st.duplikalt_jatszma += 1
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return st


# --- CLI --------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Bridzs jegyzőkönyv-importáló (PBN)")
    ap.add_argument("utak", nargs="+", help="PBN-fájlok (glob is)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Csak elemzés és statisztika, adatbázis nélkül")
    ap.add_argument("--db",     default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host",   default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user",   default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    ap.add_argument("--cimke", default=None,
                    help="Címke a beszúrt játszmákra, pl. arany_keszlet")
    ap.add_argument("--nyerset-ments", action="store_true",
                    help="A teljes eredeti fájl eltárolása a forras_fajl táblában")
    ap.add_argument("--ujra", action="store_true",
                    help="Már importált fájlok újbóli betöltése")
    a = ap.parse_args(argv)

    utak: list[str] = []
    for m in a.utak:
        utak.extend(sorted(glob.glob(m, recursive=True)) or [m])

    if a.dry_run:
        st = elemez(utak)
    else:
        st = betolt(utak, a.db, a.host, a.user, a.jelszo,
                    a.cimke, a.nyerset_ments, a.ujra)
    st.kiir(betoltes=not a.dry_run)
    return 1 if (st.pont_elter or st.hibas_leosztas) else 0


if __name__ == "__main__":
    raise SystemExit(main())
