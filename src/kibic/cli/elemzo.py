"""
MIT GONDOL A KIBIC EGY PARTIRÓL? — a teljes lánc egy leosztáson.

Eddig minden darab külön tesztelhető volt, de együtt sehol nem látszott.
Ez a parancs végigviszi egy valódi partin az egészet, és emberi nyelven
kiírja, mit ért meg belőle:

    1. a leosztás és a licitmenet
    2. LICITENKÉNT: mit jelent a rendszer szerint — és mit NEM értett
    3. a KÉNYSZERTÁR állása: ki mit ígért a licitjeivel
    4. egy választott pontnál: mit licitálna a kibic, és miért
       (a jelölthalmazzal együtt — ahol több a jelölt, ott a rendszer
        önmagában nem dönt)
    5. ha van MÉRLEGELENDŐ jelölt: a szimuláció (mintavétel a
       kényszertárból, DDS, várható írás IMP-ben és MP-ben)

A 3. pont a legárulkodóbb: ha a kényszertár üres marad, akkor a rendszer
nem a liciteket értette félre, hanem nincs is mit mondania róluk.

HASZNÁLAT
---------
    source .env

    # egy parti az adatbázisból, a betöltött rendszer szemüvegén át
    python -m kibic.cli.elemzo --jatszma 1234 --rendszer LICREN_STAND

    # csak addig a licitig, ameddig érdekes (0-tól számozva)
    python -m kibic.cli.elemzo --jatszma 1234 --rendszer LICREN_STAND --meddig 3

    # találomra egy kompetitív parti a gyűjteményből
    python -m kibic.cli.elemzo --veletlen --ag VEDEKEZO --rendszer LICREN_STAND
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from ..domain import ULESEK, ULES_NEV, Kez, Leosztas, vonal
from ..motor.feloldas import feloldas
from ..motor.helyzet import Allas
from ..motor.kifejezes import rendszer_kontextus
from ..motor.licital import Licitmotor
from ..motor.minta import kanonizal, menet_ag
from ..motor.propagal import Propagalo

VONAL = "-" * 70


def _kapcsolat(a):
    try:
        import pymysql
    except ImportError:
        print("A pymysql csomag nem érhető el.", file=sys.stderr)
        sys.exit(2)
    return pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4",
                           autocommit=False)


# --- Betöltés ---------------------------------------------------------

SQL_JATSZMA = """
SELECT j.id, l.kezek_pbn, l.oszto, l.beliallas, j.licit,
       j.kontraktus, j.felvevo, j.eredmeny_utes, l.dds_utesek,
       COALESCE(jn.megjelenit,'?'), COALESCE(je.megjelenit,'?'),
       COALESCE(js.megjelenit,'?'), COALESCE(jw.megjelenit,'?')
  FROM jatszma j
  JOIN leosztas l ON l.id = j.leosztas_id
  LEFT JOIN jatekos jn ON jn.id = j.n_jatekos_id
  LEFT JOIN jatekos je ON je.id = j.e_jatekos_id
  LEFT JOIN jatekos js ON js.id = j.s_jatekos_id
  LEFT JOIN jatekos jw ON jw.id = j.w_jatekos_id
 WHERE j.licit IS NOT NULL
"""


def parti_betolt(conn, jatszma_id=None, veletlen=False, ag_szuro=None):
    cur = conn.cursor()
    if jatszma_id:
        cur.execute(SQL_JATSZMA + " AND j.id = %s", (jatszma_id,))
        sor = cur.fetchone()
        if not sor:
            raise SystemExit(f"Nincs ilyen játszma: {jatszma_id}")
        return sor
    cur.execute(SQL_JATSZMA + " ORDER BY RAND() LIMIT 400")
    for sor in cur.fetchall():
        licitek = json.loads(sor[4]) if isinstance(sor[4], str) else sor[4]
        if not licitek or len(licitek) < 4:
            continue
        if ag_szuro:
            # az ág a MÁSODIK licitelő szemszögéből nézve érdekes
            ules = licitek[1].get("ules")
            _, tok = kanonizal(licitek[:1], ules)
            if menet_ag(tok) != ag_szuro:
                continue
        return sor
    raise SystemExit("Nem találtam ilyen partit. Próbáld szűrő nélkül.")


# --- Kiírás -----------------------------------------------------------

def leosztas_kiir(lo: Leosztas, nevek: dict) -> None:
    print(VONAL)
    print(f"  LEOSZTÁS   osztó: {ULES_NEV[lo.oszto]}   beli: {lo.beliallas}")
    print(VONAL)
    for u in ("N", "E", "S", "W"):
        k = lo.kezek[u]
        from ..domain import ERTEKELOK
        hcp = ERTEKELOK["HCP"](k)
        print(f"  {ULES_NEV[u]:7s} {nevek.get(u,'?'):14s} {k.pbn():20s}"
              f" {hcp:2.0f} FP")


def licitmenet_kiir(licitek: list[dict], meddig: int | None) -> None:
    print()
    print(VONAL)
    print("  LICITMENET")
    print(VONAL)
    sor = "  "
    for i, elem in enumerate(licitek):
        jel = "*" if meddig is not None and i == meddig else " "
        sor += f"{elem['ules']}:{str(elem.get('licit','')).upper():4s}{jel}"
        if (i + 1) % 4 == 0:
            print(sor)
            sor = "  "
    if sor.strip():
        print(sor)
    if meddig is not None:
        print("  (* = eddig a pontig vizsgáljuk)")


def propagalas_kiir(er, licitek: list[dict]) -> None:
    print()
    print(VONAL)
    print("  MIT ÉRTETT MEG A RENDSZER?")
    print(VONAL)
    print(f"  {er.osszefoglalo()}")
    if er.nem_ertett:
        print(f"  NEM értett: {', '.join(er.nem_ertett)}")
        print("  (ezekre nincs szabálya — nem félreértés, hanem hiány)")
    if er.tobbertelmu:
        print(f"  Többértelmű: {', '.join(er.tobbertelmu)}")
    if er.ellentmondas:
        print(f"  ELLENTMONDÁS: {', '.join(er.ellentmondas)}"
              "  <- a rendszer leírása inkonzisztens")
    print()
    print("  A KÉNYSZERTÁR — ki mit ígért a licitjeivel:")
    for u in ULESEK:
        ig = er.kenyszertar[u]
        allapot = ig.leiras() if ig.nyilatkozott else "(nem nyilatkozott)"
        print(f"    {ULES_NEV[u]:7s} {allapot}")


def dontes_kiir(d, ules: str, kez: Kez, valodi: str | None) -> None:
    print()
    print(VONAL)
    print(f"  MIT LICITÁLNA A KIBIC? ({ULES_NEV[ules]}, {kez.pbn()})")
    print(VONAL)
    print(f"  {d.osszefoglalo()}")
    if valodi:
        egyezik = (d.licit or "").upper() == valodi.upper()
        print(f"  A valóságban: {valodi}"
              f"   {'EGYEZIK' if egyezik else '<- ELTÉR'}")
    if d.jeloltek:
        print()
        print("  Jelöltek:")
        for j in sorted(d.jeloltek, key=lambda x: -x.minta_specifikussag):
            print(f"    {j.licit:4s} <- {j.sor.minta:16s} "
                  f"{(j.sor.magyarazat or j.indoklas or '')[:60]}")
    if d.merlegelendo:
        print()
        print("  MÉRLEGELENDŐ (a szabály nem dönt, csak beengedi):")
        for j in d.merlegelendo:
            print(f"    {j.licit:4s} <- {j.sor.minta:16s} "
                  f"{(j.sor.magyarazat or '')[:60]}")
    if d.eldonthetetlen:
        print(f"  Eldönthetetlen szabály: {d.eldonthetetlen}"
              "  (feloldatlan metrikára hivatkozik)")
    if not d.jeloltek and not d.merlegelendo:
        print("  Egyetlen szabály sem illeszkedik erre a helyzetre.")


def merlegeles_kiir(allas: Allas, kez: Kez, minta_db: int,
                    kalibracio_ut: str | None) -> None:
    from ..motor.mintavetel import mintavetel, MintavetelHiba
    from ..motor.merlegel import Kalibracio, buntetes_vagy_sajat

    print()
    print(VONAL)
    print("  MÉRLEGELÉS — a lehetséges leosztások szimulációja")
    print(VONAL)
    try:
        m = mintavetel(kez, allas.ules, allas.kenyszertar, db=minta_db,
                       beliallas=allas.beliallas, mag=1)
    except MintavetelHiba as e:
        print(f"  Nem sikerült mintát venni: {e}")
        return
    print(f"  {m.osszefoglalo()}")
    if not m.leosztasok:
        return

    kal = Kalibracio.betolt(kalibracio_ut) if kalibracio_ut else Kalibracio()
    try:
        o = buntetes_vagy_sajat(allas, m.leosztasok, kalibracio=kal, mag=1)
    except ValueError as e:
        print(f"  Nincs mit összemérni: {e}")
        return
    except ImportError:
        print("  Az endplay csomag nem érhető el — DDS nélkül nem megy.")
        return
    print()
    for sor in o.osszefoglalo().split("\n"):
        print(f"  {sor}")


# --- Fő menet ---------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Mit gondol a kibic egy partiról? A teljes lánc.")
    ap.add_argument("--jatszma", type=int, help="Játszma azonosítója")
    ap.add_argument("--veletlen", action="store_true",
                    help="Találomra egy parti a gyűjteményből")
    ap.add_argument("--ag", choices=("PAROS", "KUZDELMI", "VEDEKEZO"),
                    help="A --veletlen szűrése ágra")
    ap.add_argument("--rendszer", default=None,
                    help="Melyik rendszer szemüvegén át (pl. LICREN_STAND)")
    ap.add_argument("--meddig", type=int, default=None,
                    help="Hányadik licitnél álljunk meg (0-tól). "
                         "Alapból az UTOLSÓ nem-passz licit előtt.")
    ap.add_argument("--minta", type=int, default=60,
                    help="Hány leosztást vegyen a mérlegeléshez")
    ap.add_argument("--kalibracio", default=None,
                    help="A ddtorzitas --mentes fájlja")
    ap.add_argument("--teszt", action="store_true",
                    default=os.getenv("KIBIC_TESZT_MOD", "") in ("1", "igen", "true"),
                    help="Teszt mód: a JAVASOLT szabálysorokat is használja")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host",   default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user",   default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    if not a.jatszma and not a.veletlen:
        ap.error("Adj meg --jatszma ID-t vagy --veletlen kapcsolót")

    conn = _kapcsolat(a)
    try:
        sor = parti_betolt(conn, a.jatszma, a.veletlen, a.ag)
        sorok = feloldas(conn, a.rendszer, teszt=a.teszt).sorok \
            if a.rendszer else []
    finally:
        conn.close()

    (jid, pbn, oszto, beli, licit_json, kontraktus, felvevo, utes,
     dds, nn, ne, ns, nw) = sor
    licitek = json.loads(licit_json) if isinstance(licit_json, str) else licit_json
    lo = Leosztas.pbn_bol(pbn, oszto, beli)
    nevek = {"N": nn, "E": ne, "S": ns, "W": nw}

    print()
    print("=" * 70)
    print(f"  KIBIC-ELEMZÉS — {jid}. játszma"
          + (f",  {a.rendszer} szerint" if a.rendszer else ""))
    print("=" * 70)
    leosztas_kiir(lo, nevek)

    # Melyik licitnél álljunk meg? Alapból az utolsó nem-passz előtt —
    # ott van a legtöbb információ a menetben, és még van mit dönteni.
    meddig = a.meddig
    if meddig is None:
        meddig = 0
        for i, e in enumerate(licitek):
            if str(e.get("licit", "")).upper() not in ("P", "PASS"):
                meddig = i
    meddig = max(0, min(meddig, len(licitek) - 1))
    licitmenet_kiir(licitek, meddig)

    if not sorok:
        print()
        print("  (Rendszer nélkül csak a leosztást és a menetet mutatom."
              " Adj meg --rendszer kódot.)")
        return 0

    ules = licitek[meddig]["ules"]
    kez = lo.kezek[ules]
    elozmeny = licitek[:meddig]

    from ..motor.kriterium import parametertar_betolt
    conn2 = _kapcsolat(a)
    try:
        paramtar = parametertar_betolt(conn2, a.rendszer)
    finally:
        conn2.close()

    prop = Propagalo(sorok, paramtar)
    er = prop.kenyszertar(elozmeny, oszto=oszto)
    propagalas_kiir(er, elozmeny)

    allas = Allas(ules=ules, beliallas=beli, licitek=list(elozmeny),
                  oszto=oszto, kenyszertar=er.kenyszertar)
    print(f"\n  Ág: {allas.ag}")

    motor = Licitmotor(sorok, rendszer_kontextus(paramtar),
                       mod="SPECIFIKUSSAG")
    d = motor.licital(elozmeny, ules, kez, beliallas=beli,
                      allas=allas, oszto=oszto)
    dontes_kiir(d, ules, kez, str(licitek[meddig].get("licit", "")))

    if d.merlegelendo:
        merlegeles_kiir(allas, kez, a.minta, a.kalibracio)

    print()
    print("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
