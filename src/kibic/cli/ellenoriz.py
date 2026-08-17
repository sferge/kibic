"""
Visszajátszó CLI — a 0. fázis kilépési feltételének második fele.

Használat:
    python -m kibic.cli.ellenoriz "tanpartik/**/*.pbn"     # fájlokból
    python -m kibic.cli.ellenoriz --db                     # adatbázisból
    python -m kibic.cli.ellenoriz --db --hibak 20          # több hibarészlet
    python -m kibic.cli.ellenoriz --db --parti 1234        # egyetlen parti naplója
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field

from ..domain import Leosztas, Kontraktus
from ..impex import pbn
from ..motor.visszajatszo import visszajatszik, Eredmeny


@dataclass
class Osszesites:
    partik: int = 0
    licit_ellenorzott: int = 0
    licit_hibas: int = 0
    lejatszas_teljes: int = 0
    lejatszas_claim: int = 0
    lejatszas_nincs: int = 0
    utes_egyezik: int = 0
    utes_elter: int = 0
    claim_rendben: int = 0
    claim_ellentmondas: int = 0
    hibas_partik: int = 0
    hibatipusok: Counter = field(default_factory=Counter)
    peldak: list[str] = field(default_factory=list)

    def kiir(self, hibak_szama: int) -> None:
        p = print
        p("=" * 64)
        p(f"  Visszajátszott parti:        {self.partik}")
        p(f"  Hibátlan:                    {self.partik - self.hibas_partik}"
          f"   (hibás: {self.hibas_partik})")
        p("-" * 64)
        p("  LICIT")
        p(f"    Kontraktus+felvevő levezetve és egyezik: "
          f"{self.licit_ellenorzott - self.licit_hibas}")
        p(f"    Eltérés vagy szabálytalanság:           {self.licit_hibas}")
        p("-" * 64)
        p("  LEJÁTSZÁS")
        p(f"    Teljes (13 ütés):     {self.lejatszas_teljes}")
        p(f"      ebből ütésszám egyezik: {self.utes_egyezik}"
          f"   (eltér: {self.utes_elter})")
        p(f"    Terítéssel megszakadt: {self.lejatszas_claim}")
        p(f"      konzisztens: {self.claim_rendben}"
          f"   (ellentmondásos: {self.claim_ellentmondas})")
        p(f"    Nincs lejátszás:      {self.lejatszas_nincs}")
        if self.hibatipusok:
            p("-" * 64)
            p("  HIBATÍPUSOK:")
            for tipus, db in self.hibatipusok.most_common(10):
                p(f"    {db:>5}x  {tipus}")
        if self.peldak:
            p("-" * 64)
            p(f"  PÉLDÁK (első {min(hibak_szama, len(self.peldak))}):")
            for e in self.peldak[:hibak_szama]:
                p(f"    ! {e}")
        p("=" * 64)


def _hibatipus(uzenet: str) -> str:
    """A hibaüzenet általánosítása csoportosításhoz."""
    for minta in ("nincs a kezében", "nem vallotta meg", "Ütésszám eltér",
                  "Kontraktus eltér", "Felvevő eltér", "Terítés ellentmondásos",
                  "nem magasabb az előzőnél", "következne, de",
                  "kontra felvétel nélkül", "rekontra kontra nélkül",
                  "saját felvétel kontrázása", "Kiosztás"):
        if minta in uzenet:
            return minta
    return uzenet[:60]


def _feldolgoz(o: Osszesites, er: Eredmeny, azonosito: str,
               volt_lejatszas: bool) -> None:
    o.partik += 1
    if er.licit_ellenorzott:
        o.licit_ellenorzott += 1
    if any("Licit" in h or "Kontraktus eltér" in h or "Felvevő eltér" in h
           for h in er.hibak):
        o.licit_hibas += 1

    if not volt_lejatszas:
        o.lejatszas_nincs += 1
    elif er.lejatszas_teljes:
        o.lejatszas_teljes += 1
        if any("Ütésszám eltér" in h for h in er.hibak):
            o.utes_elter += 1
        else:
            o.utes_egyezik += 1
    else:
        o.lejatszas_claim += 1
        if any("Terítés ellentmondásos" in h for h in er.hibak):
            o.claim_ellentmondas += 1
        else:
            o.claim_rendben += 1

    if er.hibak:
        o.hibas_partik += 1
        for h in er.hibak:
            o.hibatipusok[_hibatipus(h)] += 1
            if len(o.peldak) < 200:
                o.peldak.append(f"{azonosito}: {h}")


# --- Fájl alapú futás -------------------------------------------------

def fajlokbol(utak: list[str], o: Osszesites, reszletes: bool) -> None:
    for ut in utak:
        with open(ut, encoding="utf-8-sig", errors="replace") as f:
            jatszmak = pbn.olvas(f.read())
        nev = ut.rsplit("/", 1)[-1]
        for j in jatszmak:
            if j.leosztas is None:
                continue
            er = visszajatszik(
                j.leosztas, j.licit, j.lapok,
                jk_kontraktus=j.kontraktus, jk_felvevo=j.felvevo,
                jk_utesek=j.eredmeny_utes, claim_utes=j.claim_utes)
            _feldolgoz(o, er, f"{nev}#{j.tabla_szam}", bool(j.lapok))
            if reszletes and er.utesek:
                for u in er.utesek:
                    print(u)


# --- Adatbázis alapú futás -------------------------------------------

def adatbazisbol(o: Osszesites, db: str, host: str, user: str, jelszo: str,
                 parti_id: int | None, reszletes: bool) -> None:
    try:
        import pymysql
    except ImportError:
        print("A pymysql csomag nem érhető el.", file=sys.stderr)
        sys.exit(2)

    conn = pymysql.connect(host=host, user=user, password=jelszo,
                           database=db, charset="utf8mb4")
    cur = conn.cursor()
    felt = "WHERE j.id = %s" if parti_id else ""
    cur.execute(
        "SELECT j.id, l.kezek_pbn, l.oszto, l.beliallas, l.tabla_szam,"
        "       j.licit, j.lejatszas, j.felvevo, j.kontraktus, j.eredmeny_utes"
        "  FROM jatszma j JOIN leosztas l ON l.id = j.leosztas_id "
        + felt, (parti_id,) if parti_id else ())

    for (jid, kezek, oszto, beli, tabla, licit_j, lejatszas_j,
         felvevo, kontraktus_s, utesek) in cur.fetchall():
        try:
            leosztas = Leosztas.pbn_bol(kezek, oszto, beli, tabla)
        except ValueError as e:
            o.partik += 1
            o.hibas_partik += 1
            o.hibatipusok["Kiosztás"] += 1
            o.peldak.append(f"#{jid}: {e}")
            continue

        licitek = json.loads(licit_j) if licit_j else None
        lejatszas = json.loads(lejatszas_j) if lejatszas_j else {}
        lapok = lejatszas.get("lapok")
        try:
            kontraktus = Kontraktus.parse(kontraktus_s or "", felvevo or "N")
        except ValueError:
            kontraktus = None

        er = visszajatszik(leosztas, licitek, lapok,
                           jk_kontraktus=kontraktus, jk_felvevo=felvevo,
                           jk_utesek=utesek,
                           claim_utes=lejatszas.get("claim_utes"))
        _feldolgoz(o, er, f"#{jid}", bool(lapok))
        if reszletes:
            print(f"--- játszma #{jid}: {kontraktus_s} {felvevo} "
                  f"({utesek} ütés a jegyzőkönyv szerint) ---")
            for u in er.utesek:
                print(" ", u)
            if er.felvevo_utesek is not None:
                print(f"  Visszajátszva: {er.felvevo_utesek} felvevő-ütés")
            for h in er.hibak:
                print(f"  ! {h}")
    conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Parti-visszajátszó és ellenőrző")
    ap.add_argument("utak", nargs="*", help="PBN-fájlok (glob is)")
    ap.add_argument("--db", action="store_true",
                    help="Adatbázisból olvas fájlok helyett")
    ap.add_argument("--parti", type=int, default=None,
                    help="Egyetlen játszma azonosítója (--db mellett)")
    ap.add_argument("--reszletes", action="store_true",
                    help="Ütésenkénti napló kiírása")
    ap.add_argument("--hibak", type=int, default=10,
                    help="Hány hibapéldát írjon ki")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host",   default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user",   default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    o = Osszesites()
    if a.db:
        adatbazisbol(o, a.adatbazis, a.host, a.user, a.jelszo,
                     a.parti, a.reszletes)
    else:
        if not a.utak:
            ap.error("Adj meg fájlokat, vagy használd a --db kapcsolót")
        utak: list[str] = []
        for m in a.utak:
            utak.extend(sorted(glob.glob(m, recursive=True)) or [m])
        fajlokbol(utak, o, a.reszletes)

    o.kiir(a.hibak)
    return 1 if o.hibas_partik else 0


if __name__ == "__main__":
    raise SystemExit(main())
