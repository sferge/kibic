"""
Karbantartás: a SZÁRMAZTATOTT adatok újraszámolása.

    source .env
    python -m kibic.cli.karbantartas --mind

A projekt elve szerint minden származtatott adat bármikor eldobható és
újraépíthető. Ez a modul ezt teszi meg — és azért kell RENDSZERESEN
futtatni, mert az importálás után ezek elavulnak:

  --hash    A `jatszma_hash` pótlása a régi soroknál. A korábbi
            importálások még a duplikáció-védelem bevezetése előtt
            futottak, ezért azok a sorok védtelenek.
  --parok   A `par` tábla újratöltése és a partiszám újraszámolása.
            Minden import után elavul.
  --ember   A robotok jelölése (`~~` előtagú BBO-nevek).
  --ertekek A `kez_ertek` tábla feltöltése a hiányzó leosztásokra.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

from ..domain import ERTEKELOK, ULESEK, ertekeld, Kez, Leosztas


def _kapcsolat(a):
    import pymysql
    return pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4",
                           autocommit=False)


# --- jatszma_hash pótlása --------------------------------------------

def hash_potlas(conn, koteg: int = 1000) -> tuple[int, int]:
    """
    A hiányzó `jatszma_hash` értékek kiszámítása a tárolt adatokból.
    Ugyanaz a képlet, mint az importálóban: leosztás + játékosok + licit.

    KÉT FÁZISBAN dolgozik, és ez fontos: előbb KISZÁMOLJA az összes
    hasht, és csak utána ír. Így a valódi ütközések a számított értékek
    összevetéséből derülnek ki, nem az adatbázis hibájából.

    (A korábbi változat az egyedi index kivételére támaszkodott, és
    ütközéskor az EGÉSZ köteget visszagörgette — emiatt a köteg többi
    sora tévesen kapott 'duplikatum' címkét.)
    """
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jatszma WHERE jatszma_hash IS NULL")
    hatra = cur.fetchone()[0]
    print(f"  Hash nélküli játszma: {hatra}")
    if not hatra:
        return 0, 0

    # 1. fázis: MINDEN hash kiszámítása
    cur.execute(
        "SELECT j.id, l.leosztas_hash, j.licit,"
        "       jn.azonosito, je.azonosito, js.azonosito, jw.azonosito"
        "  FROM jatszma j"
        "  JOIN leosztas l ON l.id = j.leosztas_id"
        "  LEFT JOIN jatekos jn ON jn.id = j.n_jatekos_id"
        "  LEFT JOIN jatekos je ON je.id = j.e_jatekos_id"
        "  LEFT JOIN jatekos js ON js.id = j.s_jatekos_id"
        "  LEFT JOIN jatekos jw ON jw.id = j.w_jatekos_id"
        " WHERE j.jatszma_hash IS NULL")
    szamitott: dict[int, str] = {}
    for jid, lhash, licit_j, n, e, s_, w in cur.fetchall():
        try:
            licitek = json.loads(licit_j) if licit_j else []
        except (TypeError, ValueError):
            licitek = []
        resz = [lhash,
                "|".join((x or "").strip().lower() for x in (n, e, s_, w)),
                "|".join(f"{b.get('ules')}{b.get('licit')}" for b in licitek)]
        szamitott[jid] = hashlib.sha256("~".join(resz).encode()).hexdigest()

    # 2. fázis: a MÁR MEGLÉVŐ hash-ek beolvasása, és az ütközések keresése
    cur.execute("SELECT jatszma_hash FROM jatszma WHERE jatszma_hash IS NOT NULL")
    foglalt = {r[0] for r in cur.fetchall()}

    kesz = dupla = 0
    latott: dict[str, int] = {}
    for jid in sorted(szamitott):
        h = szamitott[jid]
        if h in foglalt or h in latott:
            # VALÓDI duplikátum: ugyanaz a leosztás, ugyanazok a játékosok,
            # ugyanaz a licitmenet. Megtartjuk, de megjelöljük.
            cur.execute(
                "UPDATE jatszma SET jatszma_hash=%s,"
                "       cimkek = CONCAT_WS(',', cimkek, 'duplikatum')"
                " WHERE id=%s", (f"{h[:50]}#{jid}", jid))
            dupla += 1
        else:
            cur.execute("UPDATE jatszma SET jatszma_hash=%s WHERE id=%s",
                        (h, jid))
            latott[h] = jid
            kesz += 1
        if (kesz + dupla) % koteg == 0:
            conn.commit()
            print(f"\r    {kesz + dupla}/{hatra}", end="", flush=True)
    conn.commit()
    print(f"\r    {kesz + dupla}/{hatra}")
    return kesz, dupla


# --- par tábla frissítése --------------------------------------------

def parok_frissitese(conn) -> int:
    cur = conn.cursor()
    for sql in (
        "INSERT IGNORE INTO par (jatekos_a, jatekos_b)"
        " SELECT DISTINCT LEAST(n_jatekos_id,s_jatekos_id),"
        "                 GREATEST(n_jatekos_id,s_jatekos_id) FROM jatszma"
        "  WHERE n_jatekos_id IS NOT NULL AND s_jatekos_id IS NOT NULL"
        "    AND n_jatekos_id <> s_jatekos_id",
        "INSERT IGNORE INTO par (jatekos_a, jatekos_b)"
        " SELECT DISTINCT LEAST(e_jatekos_id,w_jatekos_id),"
        "                 GREATEST(e_jatekos_id,w_jatekos_id) FROM jatszma"
        "  WHERE e_jatekos_id IS NOT NULL AND w_jatekos_id IS NOT NULL"
        "    AND e_jatekos_id <> w_jatekos_id",
        "UPDATE par p SET partik = ("
        "  SELECT COUNT(*) FROM jatszma j"
        "   WHERE (LEAST(j.n_jatekos_id,j.s_jatekos_id)=p.jatekos_a"
        "          AND GREATEST(j.n_jatekos_id,j.s_jatekos_id)=p.jatekos_b)"
        "      OR (LEAST(j.e_jatekos_id,j.w_jatekos_id)=p.jatekos_a"
        "          AND GREATEST(j.e_jatekos_id,j.w_jatekos_id)=p.jatekos_b))",
        "UPDATE par p JOIN jatekos a ON a.id=p.jatekos_a"
        "  JOIN jatekos b ON b.id=p.jatekos_b"
        "  SET p.nev = CONCAT(a.megjelenit,' - ',b.megjelenit)"
        " WHERE p.nev IS NULL",
        # robot-pár: ha bármelyik tag robot
        "UPDATE par p JOIN jatekos a ON a.id=p.jatekos_a"
        "  JOIN jatekos b ON b.id=p.jatekos_b"
        "  SET p.ember = 0 WHERE a.ember = 0 OR b.ember = 0",
    ):
        cur.execute(sql)
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM par")
    return cur.fetchone()[0]


# --- robotjelölés -----------------------------------------------------

def robotok_jelolese(conn) -> int:
    cur = conn.cursor()
    cur.execute("UPDATE jatekos SET ember = 0 WHERE azonosito LIKE '~~%%'")
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM jatekos WHERE ember = 0")
    return cur.fetchone()[0]


# --- kez_ertek pótlása ------------------------------------------------

def ertekek_potlasa(conn, koteg: int = 200) -> int:
    """A `kez_ertek` feltöltése azokra a leosztásokra, ahol hiányzik."""
    cur = conn.cursor()
    cur.execute("SELECT kod, id FROM ertekelo WHERE aktiv=1")
    ertekelo = {k: i for k, i in cur.fetchall() if k in ERTEKELOK}
    cur.execute(
        "SELECT COUNT(*) FROM leosztas l"
        " WHERE NOT EXISTS (SELECT 1 FROM kez_ertek k WHERE k.leosztas_id=l.id)")
    hatra = cur.fetchone()[0]
    print(f"  Kézérték nélküli leosztás: {hatra}")
    kesz = 0
    while kesz < hatra:
        cur.execute(
            "SELECT l.id, l.kezek_pbn, l.oszto, l.beliallas FROM leosztas l"
            " WHERE NOT EXISTS (SELECT 1 FROM kez_ertek k"
            "                    WHERE k.leosztas_id=l.id) LIMIT %s", (koteg,))
        sorok = cur.fetchall()
        if not sorok:
            break
        adatok = []
        for lid, pbn_s, oszto, beli in sorok:
            try:
                leosztas = Leosztas.pbn_bol(pbn_s, oszto, beli)
            except ValueError:
                continue
            for u in ULESEK:
                for kod, ertek in ertekeld(leosztas.kezek[u]).items():
                    if kod in ertekelo:
                        adatok.append((lid, u, ertekelo[kod], ertek))
        if adatok:
            cur.executemany(
                "INSERT IGNORE INTO kez_ertek"
                " (leosztas_id, ules, ertekelo_id, ertek) VALUES (%s,%s,%s,%s)",
                adatok)
        conn.commit()
        kesz += len(sorok)
        print(f"\r    {kesz}/{hatra}", end="", flush=True)
    print()
    return kesz


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Származtatott adatok frissítése")
    ap.add_argument("--mind", action="store_true", help="Minden lépés")
    ap.add_argument("--hash", action="store_true")
    ap.add_argument("--parok", action="store_true")
    ap.add_argument("--ember", action="store_true")
    ap.add_argument("--ertekek", action="store_true")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)
    if not (a.mind or a.hash or a.parok or a.ember or a.ertekek):
        ap.error("Adj meg legalább egy lépést, vagy használd a --mind kapcsolót")

    conn = _kapcsolat(a)
    try:
        if a.mind or a.ember:
            print("ROBOTJELÖLÉS")
            print(f"  Robot játékos: {robotok_jelolese(conn)}")
        if a.mind or a.hash:
            print("JÁTSZMA-HASH PÓTLÁSA")
            kesz, dupla = hash_potlas(conn)
            print(f"  Kiszámolva: {kesz}, duplikátumnak jelölve: {dupla}")
        if a.mind or a.ertekek:
            print("KÉZÉRTÉKEK PÓTLÁSA")
            print(f"  Feldolgozva: {ertekek_potlasa(conn)}")
        if a.mind or a.parok:
            print("PÁROK FRISSÍTÉSE")
            print(f"  Pár összesen: {parok_frissitese(conn)}")

        cur = conn.cursor()
        print("\nÁLLAPOT")
        for nev, sql in [
            ("játszma", "SELECT COUNT(*) FROM jatszma"),
            ("  ebből hash-elt", "SELECT COUNT(*) FROM jatszma"
                                 " WHERE jatszma_hash IS NOT NULL"),
            ("  ebből nevekkel", "SELECT COUNT(*) FROM jatszma"
                                 " WHERE n_jatekos_id IS NOT NULL"),
            ("leosztás", "SELECT COUNT(*) FROM leosztas"),
            ("  ebből DDS-sel", "SELECT COUNT(*) FROM leosztas"
                                " WHERE dds_utesek IS NOT NULL"),
            ("pár", "SELECT COUNT(*) FROM par"),
            ("  legalább 50 parti", "SELECT COUNT(*) FROM par WHERE partik>=50"),
            ("  robot-pár", "SELECT COUNT(*) FROM par WHERE ember=0"),
        ]:
            cur.execute(sql)
            print(f"  {nev:<22} {cur.fetchone()[0]}")
        print("\nA LEGTÖBBET JÁTSZOTT PÁROK")
        cur.execute("SELECT nev, partik, ember FROM par"
                    " ORDER BY partik DESC LIMIT 15")
        for nev, partik, ember in cur.fetchall():
            jel = "" if ember else "  [robot]"
            print(f"  {(nev or '?')[:44]:<46}{partik:>5}{jel}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
