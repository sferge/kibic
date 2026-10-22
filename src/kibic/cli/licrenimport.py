"""
LICREN-importáló: `.lr` rendszerfájlok betöltése a tudásbázisba.

    python -m kibic.cli.licrenimport rendszerek/gfk/stand.lr \\
        --kod LICREN_STAND --nev "LICREN standard" --dry-run

    python -m kibic.cli.licrenimport rendszerek/gfk/stund.lr \\
        --kod LICREN_STUND --nev "LICREN standard (fegyelmezetlen gyenge 2)" \\
        --szulo LICREN_STAND

A `--szulo` a REKURZÍV mód: csak azokat a szabályokat viszi be, amelyek
a szülőrendszerhez képest ELTÉRNEK, plusz egy HIVATKOZAS sort a szülőre.
A `stund.lr` így 986 sor helyett 5 sorban írható le.

PRIORITÁS: a LICREN-ben az UTOLSÓ illeszkedő szabály nyer (a fájlbeli
sorrend növekvő fontosság). Ezt igazolja a precíziós 1♣: a színnyitások
UTÁN áll, és 16+ ponttal neki kell nyernie. Az importálás ezért a
`seq`-ből úgy képez `prioritas`-t, hogy a későbbi sor magasabb legyen.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field

from ..impex.licren import Rendszer, Szabaly, fordit, olvas
from ..motor.kifejezes import ismeretlen_jelzok, json_ki, leiras
from ..motor.minta import MintaHiba, kibont, minta_parse


@dataclass
class Statisztika:
    helyzetek: int = 0
    szabalyok: int = 0
    beszurva: int = 0
    kihagyva_azonos: int = 0        # a szülővel egyező (rekurzív mód)
    elemzesi_hiba: int = 0
    minta_hiba: int = 0
    eldontheto: int = 0
    index_sorok: int = 0
    ismeretlen: Counter = field(default_factory=Counter)
    hibapeldak: list[str] = field(default_factory=list)

    def kiir(self, rendszer_kod: str, betoltes: bool) -> None:
        p = print
        p("=" * 64)
        p(f"  Rendszer: {rendszer_kod}"
          f"    ({'BETÖLTÉS' if betoltes else 'DRY-RUN'})")
        p("-" * 64)
        p(f"  Licithelyzet:              {self.helyzetek}")
        p(f"  Szabály a forrásban:       {self.szabalyok}")
        p(f"  Betöltendő licitmenet-sor: {self.beszurva}")
        if self.kihagyva_azonos:
            p(f"    a szülővel azonos (kihagyva): {self.kihagyva_azonos}")
        p(f"  Kibontott index-sor:       {self.index_sorok}")
        p("-" * 64)
        arany = (100 * self.eldontheto / self.beszurva) if self.beszurva else 0
        p(f"  Teljesen kiértékelhető:    {self.eldontheto}  ({arany:.0f}%)")
        if self.ismeretlen:
            p("  Feloldásra váró hivatkozások:")
            for k, v in self.ismeretlen.most_common():
                p(f"      {k:<14} {v} szabályban")
        if self.elemzesi_hiba or self.minta_hiba:
            p("-" * 64)
            p(f"  Forráshiba: {self.elemzesi_hiba} feltétel, "
              f"{self.minta_hiba} minta")
            for h in self.hibapeldak[:8]:
                p(f"      ! {h}")
        p("=" * 64)


# --- A minta összeállítása -------------------------------------------

def _minta(helyzet_minta: str, licit: str) -> str:
    """
    A licitmenet-minta = a helyzet + a definiált licit.
    A LICREN a helyzetet adja meg (`1C-1D`), a szabály pedig a licitet
    (`1H`); nálunk a minta MINDIG a definiált licittel végződik.
    """
    if helyzet_minta.upper() in ("START", ""):
        return licit
    return f"{helyzet_minta}-{licit}"


def _sor(szabaly: Szabaly, helyzet_minta: str, fejezet: str,
         seq: int, st: Statisztika) -> dict | None:
    """Egy LICREN-szabályból egy `licitmenet` sor adatai."""
    minta_sz = _minta(helyzet_minta, szabaly.licit)
    if szabaly.hiba or not szabaly.ast:
        st.elemzesi_hiba += 1
        st.hibapeldak.append(f"{minta_sz}: {szabaly.hiba}")
        return None
    try:
        m = minta_parse(minta_sz)
    except MintaHiba as e:
        st.minta_hiba += 1
        st.hibapeldak.append(f"{minta_sz}: {e}")
        return None

    fa = fordit(szabaly.ast)
    isms = sorted(ismeretlen_jelzok(fa))
    if not isms:
        st.eldontheto += 1
    for i in isms:
        st.ismeretlen[i] += 1

    kibontas = kibont(m)
    st.index_sorok += len(kibontas)

    return {
        "minta": str(m),
        "kulcs": str(m),
        "fejezet": fejezet,
        "alfejezet": helyzet_minta,
        "seq": seq,
        "prioritas": seq,          # későbbi sor = magasabb prioritás
        "specifikussag": m.specifikussag,
        "feltetel": json_ki(fa),
        "feltetel_szoveg": leiras(fa)[:1000],
        "ismeretlen_jelzok": ",".join(isms)[:120] or None,
        "nyers_szoveg": f"{szabaly.licit}:{szabaly.feltetel}",
        "kibontas": kibontas,
    }


def sorok_gyujtese(r: Rendszer, st: Statisztika,
                   szulo_szabalyok: set[str] | None = None) -> list[dict]:
    """
    A rendszer összes szabályából `licitmenet` sorok.
    Ha `szulo_szabalyok` meg van adva (rekurzív mód), csak az ELTÉRŐKET.
    """
    ki: list[dict] = []
    seq = 0

    def blokk(helyzet_minta: str, szabalyok: list[Szabaly], fejezet: str):
        nonlocal seq
        for sz in szabalyok:
            st.szabalyok += 1
            azonosito = f"{helyzet_minta}|{sz.licit}|{sz.feltetel}"
            if szulo_szabalyok is not None and azonosito in szulo_szabalyok:
                st.kihagyva_azonos += 1
                continue
            seq += 10
            s = _sor(sz, helyzet_minta, fejezet, seq, st)
            if s:
                ki.append(s)
                st.beszurva += 1

    blokk("START", r.inditasok.szabalyok, "Nyitások")
    for h in r.helyzetek:
        st.helyzetek += 1
        blokk(h.minta, h.szabalyok, h.minta.split("-")[0])
    return ki


def szulo_azonositok(ut: str) -> set[str]:
    """A szülőrendszer szabályainak azonosítói az eltérés-szűréshez."""
    r = olvas(ut)
    ki = set()
    for sz in r.inditasok.szabalyok:
        ki.add(f"START|{sz.licit}|{sz.feltetel}")
    for h in r.helyzetek:
        for sz in h.szabalyok:
            ki.add(f"{h.minta}|{sz.licit}|{sz.feltetel}")
    return ki


# --- Adatbázisba írás -------------------------------------------------

def betolt(sorok: list[dict], kod: str, nev: str, csalad: str,
           szulo_kod: str | None, dok_kod: str | None, a) -> None:
    import pymysql
    conn = pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4",
                           autocommit=False)
    cur = conn.cursor()
    try:
        # rendszer
        cur.execute("SELECT id FROM rendszer WHERE kod=%s", (kod,))
        r = cur.fetchone()
        if r:
            rid = r[0]
            cur.execute("DELETE FROM licitmenet WHERE rendszer_id=%s", (rid,))
        else:
            cur.execute(
                "INSERT INTO rendszer (kod, nev, fajta, csalad, leiras)"
                " VALUES (%s,%s,'ALAPRENDSZER',%s,%s)",
                (kod, nev, csalad, f"LICREN import: {a.fajl}"))
            rid = cur.lastrowid

        dok_id = None
        if dok_kod:
            cur.execute("SELECT id FROM forras_dokumentum WHERE kod=%s",
                        (dok_kod,))
            d = cur.fetchone()
            dok_id = d[0] if d else None
            if dok_id:
                cur.execute(
                    "INSERT IGNORE INTO rendszer_dokumentum"
                    " (rendszer_id, dokumentum_id) VALUES (%s,%s)",
                    (rid, dok_id))

        # HIVATKOZAS a szülőre (rekurzív mód)
        if szulo_kod:
            cur.execute("SELECT id FROM rendszer WHERE kod=%s", (szulo_kod,))
            sz = cur.fetchone()
            if not sz:
                raise SystemExit(f"A szülőrendszer nincs betöltve: {szulo_kod}")
            cur.execute(
                "INSERT INTO licitmenet (rendszer_id, fejezet, seq, tipus,"
                " hivatkozott_id, allapot, nyers_szoveg)"
                " VALUES (%s,'Alaprendszer',0,'HIVATKOZAS',%s,'ELFOGADOTT',%s)",
                (rid, sz[0], f"Az egesz {szulo_kod} rendszer beemelese"))

        for s in sorok:
            cur.execute(
                "INSERT INTO licitmenet (rendszer_id, fejezet, alfejezet, seq,"
                " tipus, minta, kulcs, specifikussag, prioritas, feltetel,"
                " feltetel_szoveg, ismeretlen_jelzok, nyers_szoveg,"
                " dokumentum_id, allapot, dontesi_mod)"
                " VALUES (%s,%s,%s,%s,'SZABALY',%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                " 'ELFOGADOTT','SORREND')",
                (rid, s["fejezet"], s["alfejezet"], s["seq"], s["minta"],
                 s["kulcs"], s["specifikussag"], s["prioritas"],
                 s["feltetel"], s["feltetel_szoveg"], s["ismeretlen_jelzok"],
                 s["nyers_szoveg"], dok_id))
            lm_id = cur.lastrowid
            if s["kibontas"]:
                cur.executemany(
                    "INSERT IGNORE INTO licitmenet_index"
                    " (licitmenet_id, szekvencia, kotesek) VALUES (%s,%s,%s)",
                    [(lm_id, szekv, kot) for szekv, kot in s["kibontas"]])
        conn.commit()
        print(f"Betöltve: rendszer #{rid} ({kod}), {len(sorok)} licitmenet-sor")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LICREN .lr importáló")
    ap.add_argument("fajl", help="A .lr rendszerfájl")
    ap.add_argument("--kod", required=True, help="Rendszerkód, pl. LICREN_STAND")
    ap.add_argument("--nev", required=True)
    ap.add_argument("--csalad", default="EGYEB",
                    choices=["NATURAL", "STRONG_CLUB", "ACOL", "PRECISION",
                             "POLISH", "EGYEB"])
    ap.add_argument("--szulo", default=None,
                    help="Szülőrendszer kódja: CSAK az eltéréseket viszi be")
    ap.add_argument("--szulo-fajl", default=None,
                    help="A szülő .lr fájlja az eltérés-számításhoz")
    ap.add_argument("--dokumentum", default=None,
                    help="forras_dokumentum kód")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    if a.szulo and not a.szulo_fajl:
        ap.error("A --szulo mellé kell a --szulo-fajl is")

    r = olvas(a.fajl)
    st = Statisztika()
    szulo = szulo_azonositok(a.szulo_fajl) if a.szulo_fajl else None
    sorok = sorok_gyujtese(r, st, szulo)
    st.kiir(a.kod, betoltes=not a.dry_run)

    if a.dry_run:
        print("\nElső 5 sor:")
        for s in sorok[:5]:
            print(f"  {s['minta']:<20} pri={s['prioritas']:<4} "
                  f"spec={s['specifikussag']:<3} {s['feltetel_szoveg'][:60]}")
        return 0

    betolt(sorok, a.kod, a.nev, a.csalad, a.szulo, a.dokumentum, a)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
