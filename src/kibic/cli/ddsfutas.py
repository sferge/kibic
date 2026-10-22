"""
DDS-futtató CLI — a 0. fázis utolsó tétele.

Három üzemmód:

    python -m kibic.cli.ddsfutas --tabla          # dds_utesek feltöltése
    python -m kibic.cli.ddsfutas --par            # par-eredmények kiszámítása
    python -m kibic.cli.ddsfutas --claim          # terítések ellenőrzése

A --tabla mód idempotens: csak azokat a leosztásokat számolja, ahol a
`dds_utesek` még NULL. Bármikor megszakítható és folytatható.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from ..domain import Leosztas, Kontraktus
from ..solver import dds


def _kapcsolat(a):
    try:
        import pymysql
    except ImportError:
        print("A pymysql csomag nem érhető el.", file=sys.stderr)
        sys.exit(2)
    return pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4",
                           autocommit=False)


# --- 1. DD-tábla feltöltése ------------------------------------------

def tabla_feltolt(conn, koteg: int, limit: int | None) -> None:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM leosztas WHERE dds_utesek IS NULL")
    hatra = cur.fetchone()[0]
    if limit:
        hatra = min(hatra, limit)
    print(f"Kiszámítandó leosztás: {hatra}")
    if not hatra:
        return

    kesz = 0
    start = time.time()
    while kesz < hatra:
        meret = min(koteg, hatra - kesz)
        cur.execute(
            "SELECT id, kezek_pbn, oszto, beliallas FROM leosztas"
            " WHERE dds_utesek IS NULL LIMIT %s", (meret,))
        sorok = cur.fetchall()
        if not sorok:
            break

        leosztasok, idk = [], []
        for lid, pbn_str, oszto, beli in sorok:
            try:
                leosztasok.append(Leosztas.pbn_bol(pbn_str, oszto, beli))
                idk.append(lid)
            except ValueError as e:
                print(f"  #{lid} kihagyva: {e}")

        if not leosztasok:
            break
        tablak = dds.dd_tablak(leosztasok, koteg=len(leosztasok))
        cur.executemany(
            "UPDATE leosztas SET dds_utesek=%s WHERE id=%s",
            [(json.dumps(t), i) for t, i in zip(tablak, idk)])
        conn.commit()

        kesz += len(sorok)
        eltelt = time.time() - start
        seb = kesz / eltelt if eltelt else 0
        hatralevo = (hatra - kesz) / seb if seb else 0
        print(f"\r  {kesz}/{hatra}  |  {seb:6.1f} leosztás/mp  |  "
              f"hátra ~{hatralevo/60:5.1f} perc", end="", flush=True)

    eltelt = time.time() - start
    print(f"\n\nKész: {kesz} leosztás {eltelt:.1f} mp alatt "
          f"({kesz/eltelt if eltelt else 0:.1f} leosztás/mp).")
    print(f"Extrapoláció: 1 millió leosztás ≈ "
          f"{1_000_000/(kesz/eltelt)/3600 if eltelt and kesz else 0:.1f} óra.")


# --- 2. Par-eredmények -----------------------------------------------

def par_feltolt(conn, limit: int | None) -> None:
    cur = conn.cursor()
    cur.execute("SELECT id, kezek_pbn, oszto, beliallas FROM leosztas"
                " WHERE dds_par IS NULL" + (f" LIMIT {int(limit)}" if limit else ""))
    sorok = cur.fetchall()
    print(f"Par-számítás: {len(sorok)} leosztás")
    start, kesz = time.time(), 0
    for lid, pbn_str, oszto, beli in sorok:
        try:
            l = Leosztas.pbn_bol(pbn_str, oszto, beli)
            pont, leiras = dds.par_eredmeny(l)
            cur.execute("UPDATE leosztas SET dds_par=%s WHERE id=%s",
                        (f"{pont}|{leiras}", lid))
        except Exception as e:                       # noqa: BLE001
            print(f"  #{lid}: {e}")
        kesz += 1
        if kesz % 200 == 0:
            conn.commit()
            print(f"\r  {kesz}/{len(sorok)}", end="", flush=True)
    conn.commit()
    print(f"\nKész {time.time()-start:.1f} mp alatt.")


# --- 3. Terítés-ellenőrzés -------------------------------------------

def claim_ellenoriz(conn, limit: int | None) -> None:
    cur = conn.cursor()
    cur.execute(
        "SELECT j.id, l.kezek_pbn, l.oszto, l.beliallas, j.lejatszas,"
        "       j.kontraktus, j.felvevo, j.eredmeny_utes"
        "  FROM jatszma j JOIN leosztas l ON l.id = j.leosztas_id"
        " WHERE j.lejatszas IS NOT NULL"
        "   AND JSON_EXTRACT(j.lejatszas, '$.claim_utes') IS NOT NULL"
        "   AND j.eredmeny_utes IS NOT NULL"
        + (f" LIMIT {int(limit)}" if limit else ""))
    sorok = cur.fetchall()
    print(f"Terítéses parti: {len(sorok)}\n")

    egyezik = tul_sok = tul_keves = hibas = 0
    peldak: list[str] = []
    start = time.time()

    for (jid, pbn_str, oszto, beli, lejatszas_j,
         kontraktus_s, felvevo, jk_utes) in sorok:
        try:
            l = Leosztas.pbn_bol(pbn_str, oszto, beli)
            k = Kontraktus.parse(kontraktus_s or "", felvevo or "N")
            lapok = (json.loads(lejatszas_j) or {}).get("lapok") or []
            if k is None:
                continue
            e = dds.maradek_utesek(l, lapok, k)
            if e.hiba:
                hibas += 1
                if len(peldak) < 20:
                    peldak.append(f"#{jid}: {e.hiba}")
                continue
            if e.felvevo_osszesen == jk_utes:
                egyezik += 1
            elif jk_utes > e.felvevo_osszesen:
                tul_sok += 1
                if len(peldak) < 20:
                    peldak.append(
                        f"#{jid} {kontraktus_s} {felvevo}: bemondott {jk_utes}, "
                        f"double dummy {e.felvevo_osszesen} "
                        f"({e.lejatszott_utes} ütés után {e.felvevo_eddig}+"
                        f"{e.felvevo_meg})")
            else:
                tul_keves += 1
        except Exception as ex:                      # noqa: BLE001
            hibas += 1
            if len(peldak) < 20:
                peldak.append(f"#{jid}: {ex}")

    osszes = egyezik + tul_sok + tul_keves
    print("=" * 62)
    print(f"  Ellenőrzött terítés:        {osszes}")
    print(f"    pontosan egyezik:         {egyezik}")
    print(f"    a bemondott TÖBB, mint a double dummy maximum: {tul_sok}")
    print(f"      (ez valódi ellentmondás — vagy hibás jegyzőkönyv,")
    print(f"       vagy az ellenfél elfogadott egy túl optimista terítést)")
    print(f"    a bemondott KEVESEBB:     {tul_keves}")
    print(f"      (nem hiba: a felvevő biztosra ment, vagy az ellenfél")
    print(f"       hibázott volna a folytatásban)")
    print(f"    feldolgozási hiba:        {hibas}")
    if peldak:
        print("-" * 62)
        for p in peldak[:15]:
            print(f"    ! {p}")
    print(f"  Futásidő: {time.time()-start:.1f} mp")
    print("=" * 62)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="DDS-futtató")
    ap.add_argument("--tabla", action="store_true",
                    help="A dds_utesek gyorsítótár feltöltése")
    ap.add_argument("--par", action="store_true",
                    help="Par-eredmények kiszámítása")
    ap.add_argument("--claim", action="store_true",
                    help="Terítések ellenőrzése double dummy módszerrel")
    ap.add_argument("--koteg", type=int, default=32,
                    help="Kötegméret a DDS-hívásokhoz (max 32)")
    ap.add_argument("--limit", type=int, default=None,
                    help="Csak ennyi rekord (próbafutáshoz)")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host",   default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user",   default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    if not (a.tabla or a.par or a.claim):
        ap.error("Adj meg legalább egy módot: --tabla / --par / --claim")

    conn = _kapcsolat(a)
    try:
        if a.tabla:
            tabla_feltolt(conn, min(a.koteg, 32), a.limit)
        if a.par:
            par_feltolt(conn, a.limit)
        if a.claim:
            claim_ellenoriz(conn, a.limit)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
