"""
Importáló: jegyzőkönyv-fájl -> adatbázis.

Használat:
    python -m bridzs.importalo fajl.pbn --dry-run          # csak elemzés + statisztika
    python -m bridzs.importalo fajl.pbn --db bridzs        # tényleges betöltés
    python -m bridzs.importalo minta/*.pbn --db bridzs --cimke arany_keszlet

Tervezési elv: a domain-mag (domain.py) és az olvasók (pbn.py) semmit nem
tudnak az adatbázisról. Ez a modul a leképező réteg — a motor sosem
olvas közvetlenül a DB-ből, hanem ezen keresztül kap Leosztas/Jatszma
objektumokat. Így a tárolás lecserélhető anélkül, hogy a motor változna.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass, field

from . import pbn
from ..domain import ERTEKELOK, ULESEK, ertekeld
from ..domain import pontszam_ns


# --- Statisztika ------------------------------------------------------

@dataclass
class Statisztika:
    fajlok: int = 0
    rekordok: int = 0
    ervenyes_leosztas: int = 0
    hibas_leosztas: int = 0
    egyedi_leosztas: int = 0
    van_licit: int = 0
    van_lejatszas: int = 0
    teljes_lejatszas: int = 0
    claim: int = 0
    pont_egyezik: int = 0
    pont_elter: int = 0
    pont_nincs: int = 0
    alertes_licit: int = 0
    hianyos_cimkek: Counter = field(default_factory=Counter)
    jatekosok: Counter = field(default_factory=Counter)
    figyelmeztetesek: list[str] = field(default_factory=list)
    elteresek: list[str] = field(default_factory=list)

    def kiir(self) -> None:
        p = print
        p("=" * 62)
        p(f"  Feldolgozott fájl:        {self.fajlok}")
        p(f"  PBN-rekord:               {self.rekordok}")
        p(f"  Érvényes kiosztás:        {self.ervenyes_leosztas}"
          f"   (hibás: {self.hibas_leosztas})")
        p(f"  Egyedi leosztás:          {self.egyedi_leosztas}")
        p(f"  Van licitmenet:           {self.van_licit}"
          f"   (alertelt licit: {self.alertes_licit})")
        p(f"  Van lejátszás:            {self.van_lejatszas}"
          f"   (teljes: {self.teljes_lejatszas}, claim: {self.claim})")
        p("-" * 62)
        p("  PONTSZÁM-ELLENŐRZÉS (a saját motorunk vs. a jegyzőkönyv)")
        p(f"    egyezik:  {self.pont_egyezik}")
        p(f"    eltér:    {self.pont_elter}")
        p(f"    nincs adat: {self.pont_nincs}")
        if self.elteresek:
            p("  Eltérések:")
            for e in self.elteresek[:15]:
                p(f"    ! {e}")
        p("-" * 62)
        p(f"  Játékosok ({len(self.jatekosok)}):")
        for nev, db in self.jatekosok.most_common(12):
            p(f"    {nev:<24} {db:>4} játszma")
        if self.hianyos_cimkek:
            p("-" * 62)
            p("  KIOSZTÁS NÉLKÜLI REKORDOK címkemintái (parser-diagnosztika):")
            for minta, db in self.hianyos_cimkek.most_common(8):
                p(f"    {db:>5}x  [{minta}]")
        if self.figyelmeztetesek:
            p("-" * 62)
            p(f"  Figyelmeztetés ({len(self.figyelmeztetesek)}):")
            for f in self.figyelmeztetesek[:8]:
                p(f"    ~ {f}")
        p("=" * 62)


# --- Elemzés (DB nélkül) ---------------------------------------------

def elemez(utak: list[str]) -> tuple[Statisztika, list[pbn.PbnJatszma]]:
    st = Statisztika()
    minden: list[pbn.PbnJatszma] = []
    hashek: set[str] = set()

    for ut in utak:
        st.fajlok += 1
        with open(ut, encoding="utf-8-sig", errors="replace") as f:
            szoveg = f.read()
        jatszmak = pbn.olvas(szoveg)
        st.rekordok += len(jatszmak)

        for j in jatszmak:
            cimke = f"{ut.rsplit('/', 1)[-1]}#{j.tabla_szam}"
            for w in j.figyelmeztetesek:
                st.figyelmeztetesek.append(f"{cimke}: {w}")

            if j.leosztas is None:
                st.hibas_leosztas += 1
                # Diagnosztika: MILYEN címkéi vannak a hiányos rekordnak?
                st.hianyos_cimkek[",".join(sorted(j.cimkek)[:6]) or "(nincs címke)"] += 1
                continue
            st.ervenyes_leosztas += 1
            st.alertes_licit += sum(1 for b in j.licit if b.get("alert"))
            if j.leosztas.hash not in hashek:
                hashek.add(j.leosztas.hash)
                st.egyedi_leosztas += 1

            if j.licit:
                st.van_licit += 1
            if j.lapok:
                st.van_lejatszas += 1
                if len(j.lapok) == 52:
                    st.teljes_lejatszas += 1
            if j.claim_utes:
                st.claim += 1

            for u, nev in j.jatekosok().items():
                if nev:
                    st.jatekosok[nev.strip().lower()] += 1

            # Pontszám-ellenőrzés: ez a 0. fázis kilépési feltételének fele
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
                        f"{cimke}: {j.kontraktus} {j.felvevo} {j.eredmeny_utes} ütés "
                        f"{j.leosztas.beliallas} -> saját {szamitott}, "
                        f"jegyzőkönyv {j.pontszam_ns}")
            minden.append(j)
    return st, minden


# --- Adatbázis-réteg --------------------------------------------------

DDL_HIBA = ("A pymysql csomag nem érhető el. Telepítés: pip install pymysql\n"
            "Dry-run módban (--dry-run) adatbázis nélkül is fut.")


class Betolto:
    """A leképező réteg: PbnJatszma -> adatbázissorok."""

    def __init__(self, conn):
        self.conn = conn
        self.cur = conn.cursor()
        self._jatekos_cache: dict[str, int] = {}
        self._ertekelo_cache: dict[str, int] = {}
        self._esemeny_cache: dict[tuple, int] = {}
        self._tolts_ertekelok()

    def _tolts_ertekelok(self):
        self.cur.execute("SELECT kod, id FROM ertekelo")
        self._ertekelo_cache = {k: i for k, i in self.cur.fetchall()}

    # -- segédek --

    def jatekos_id(self, nev: str) -> int | None:
        nev = (nev or "").strip()
        if not nev:
            return None
        kulcs = nev.lower()
        if kulcs in self._jatekos_cache:
            return self._jatekos_cache[kulcs]
        self.cur.execute("SELECT id FROM jatekos WHERE azonosito=%s", (kulcs,))
        r = self.cur.fetchone()
        if r:
            self._jatekos_cache[kulcs] = r[0]
            return r[0]
        self.cur.execute(
            "INSERT INTO jatekos (azonosito, megjelenit) VALUES (%s,%s)",
            (kulcs, nev))
        self._jatekos_cache[kulcs] = self.cur.lastrowid
        return self.cur.lastrowid

    def esemeny_id(self, cimkek: dict) -> int | None:
        nev = (cimkek.get("Event") or "").strip()
        if not nev:
            return None
        helyszin = (cimkek.get("Site") or "").strip() or None
        datum = (cimkek.get("Date") or "").replace(".", "-").strip() or None
        if datum and ("?" in datum or len(datum) < 8):
            datum = None
        szamolas = (cimkek.get("Scoring") or "").strip().upper()
        szamolas = szamolas if szamolas in ("MP", "IMP", "BAM", "RUBBER") else "ISMERETLEN"
        kulcs = (nev, datum, helyszin)
        if kulcs in self._esemeny_cache:
            return self._esemeny_cache[kulcs]
        self.cur.execute(
            "SELECT id FROM esemeny WHERE nev=%s AND datum<=>%s AND helyszin<=>%s",
            (nev, datum, helyszin))
        r = self.cur.fetchone()
        if r:
            self._esemeny_cache[kulcs] = r[0]
            return r[0]
        self.cur.execute(
            "INSERT INTO esemeny (nev, helyszin, datum, szamolas) VALUES (%s,%s,%s,%s)",
            (nev, helyszin, datum, szamolas))
        self._esemeny_cache[kulcs] = self.cur.lastrowid
        return self.cur.lastrowid

    def forras_fajl_id(self, ut: str, tartalom: str, formatum: str,
                       nyerset_ments: bool) -> int:
        h = hashlib.sha256(tartalom.encode()).hexdigest()
        self.cur.execute("SELECT id FROM forras_fajl WHERE fajl_hash=%s", (h,))
        r = self.cur.fetchone()
        if r:
            return r[0]
        self.cur.execute(
            "INSERT INTO forras_fajl (fajlnev, formatum, fajl_hash, meret_bajt,"
            " nyers_tartalom) VALUES (%s,%s,%s,%s,%s)",
            (ut.rsplit("/", 1)[-1], formatum, h, len(tartalom.encode()),
             tartalom if nyerset_ments else None))
        return self.cur.lastrowid

    def leosztas_id(self, leosztas) -> int:
        h = leosztas.hash
        self.cur.execute("SELECT id FROM leosztas WHERE leosztas_hash=%s", (h,))
        r = self.cur.fetchone()
        if r:
            return r[0]
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

        # Kézértékek: MINDEN regisztrált metrika, párhuzamosan.
        sorok = []
        for u in ULESEK:
            for kod, ertek in ertekeld(k[u]).items():
                eid = self._ertekelo_cache.get(kod)
                if eid:
                    sorok.append((lid, u, eid, ertek))
        if sorok:
            self.cur.executemany(
                "INSERT INTO kez_ertek (leosztas_id, ules, ertekelo_id, ertek)"
                " VALUES (%s,%s,%s,%s)", sorok)
        return lid

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

        szamitott = None
        allapot = "NEM_ELLENORIZVE"
        if j.eredmeny_utes is not None and j.leosztas:
            szamitott = pontszam_ns(j.kontraktus, j.eredmeny_utes,
                                    j.leosztas.beliallas)
            if j.pontszam_ns is not None:
                allapot = "EGYEZIK" if szamitott == j.pontszam_ns else "ELTER"

        cimkek = [c for c in [cimke, "claim" if j.claim_utes else None] if c]

        self.cur.execute(
            "INSERT INTO jatszma (leosztas_id, esemeny_id, forras_fajl_id,"
            " n_jatekos_id, e_jatekos_id, s_jatekos_id, w_jatekos_id,"
            " licit, lejatszas, felvevo, kontraktus, eredmeny_utes,"
            " pontszam_ns, mp_szazalek_ns, pontszam_ellenorzott,"
            " pontszam_szamitott, cimkek)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (leosztas_id, esemeny_id, forras_id,
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
           cimke: str | None, nyerset_ments: bool) -> Statisztika:
    try:
        import pymysql
    except ImportError:
        print(DDL_HIBA, file=sys.stderr)
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
            fid = b.forras_fajl_id(ut, szoveg, "PBN", nyerset_ments)
            for j in pbn.olvas(szoveg):
                st.rekordok += 1
                if j.leosztas is None:
                    st.hibas_leosztas += 1
                    continue
                st.ervenyes_leosztas += 1
                lid = b.leosztas_id(j.leosztas)
                eid = b.esemeny_id(j.cimkek)
                b.jatszma_beszur(j, lid, eid, fid, cimke)
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
    ap.add_argument("--db", default="bridzs")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--user", default="root")
    ap.add_argument("--jelszo", default="")
    ap.add_argument("--cimke", default=None,
                    help="Címke a beszúrt játszmákra, pl. arany_keszlet")
    ap.add_argument("--nyerset-ments", action="store_true",
                    help="A teljes eredeti fájl eltárolása a forras_fajl táblában")
    a = ap.parse_args(argv)

    utak: list[str] = []
    for m in a.utak:
        utak.extend(sorted(glob.glob(m)) or [m])

    if a.dry_run:
        st, _ = elemez(utak)
    else:
        st = betolt(utak, a.db, a.host, a.user, a.jelszo,
                    a.cimke, a.nyerset_ments)
    st.kiir()
    return 1 if st.pont_elter or st.hibas_leosztas else 0


if __name__ == "__main__":
    raise SystemExit(main())
