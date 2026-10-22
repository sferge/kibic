"""
TELJES LICITMENET-MÉRÉS — az 1. fázis zárómérése.

Nem csak a nyitásokat vizsgálja, hanem minden licitet, KÉTFÉLEKÉPP:

POZÍCIÓNKÉNT
    Minden valódi licitnél megkérdezzük a motort, mit mondana — de a
    licitmenetet a VALÓDI licitekkel visszük tovább. Így minden döntés
    önálló, az eltérések nem halmozódnak, és megmondja, HOL romlik el.

SZIMULÁCIÓ
    A motor végiglicitál a saját döntéseivel; az ellenfél licitjeit a
    valódi menetből vesszük. A végén a KONTRAKTUST hasonlítjuk össze —
    és ami fontosabb, a DDS-táblából azt is, hogy MELYIK JOBB, IMP-ben.

    Csapda, amit jelezni kell: ha a motor eltér, az ellenfél a
    valóságban másképp licitált volna. Ezért a szimuláció onnantól
    HIPOTETIKUS. A jelentés külön mutatja azokat a partikat, ahol a
    motor végig egyezett (ott hiteles), és ahol eltért (ott becslés).

    A DDS-alapú összehasonlítás viszont ettől FÜGGETLEN és megbízható:
    azt méri, mennyire jó az elért kontraktus, nem azt, hogyan jutottunk
    oda.

HASZNÁLAT
    python -m kibic.cli.licitmeres --lr rendszerek/gfk/stand.lr \\
        --par "gal - korszurku" --metrika P_HOSSZ
    python -m kibic.cli.licitmeres --rendszer LICREN_STAND --par-id 12
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..domain import (ERTEKELOK, Kontraktus, Leosztas, ULESEK,
                      kovetkezo_ules, pontszam_ns, imp, vonal)
from ..impex.licren import fordit, olvas
from ..motor.feloldas import Sor
from ..motor.kifejezes import Kontextus, leiras
from ..motor.licital import Licitmotor


# --- Szabályok betöltése ---------------------------------------------

def sorok_lrbol(ut: str) -> list[Sor]:
    r = olvas(ut)
    ki: list[Sor] = []
    seq = 0

    def blokk(helyzet: str, szabalyok):
        nonlocal seq
        for sz in szabalyok:
            if not sz.ast:
                continue
            seq += 10
            minta = sz.licit if helyzet == "START" else f"{helyzet}-{sz.licit}"
            fa = fordit(sz.ast)
            ki.append(Sor(seq, 1, "LR", 0, minta, minta, helyzet, seq, 0,
                          fa, leiras(fa)[:200], None, "NEM", None))

    blokk("START", r.inditasok.szabalyok)
    for h in r.helyzetek:
        blokk(h.minta, h.szabalyok)
    return ki


def sorok_dbbol(conn, rendszer_kod: str) -> list[Sor]:
    from ..motor.feloldas import feloldas
    return feloldas(conn, rendszer_kod).sorok


# --- Mérési eredmény --------------------------------------------------

@dataclass
class Eredmeny:
    # pozíciónként
    licit_ossz: int = 0
    licit_egyezik: int = 0
    licit_nincs_dontes: int = 0
    fedett_egyezik: int = 0
    nemfedett_pass: int = 0
    kompetitiv: int = 0
    kompetitiv_fedett: int = 0
    licit_bizonytalan: int = 0
    melyseg_ossz: Counter = field(default_factory=Counter)
    melyseg_egyezik: Counter = field(default_factory=Counter)
    tevesztes: Counter = field(default_factory=Counter)

    # szimuláció
    parti: int = 0
    vegig_egyezett: int = 0
    kontraktus_egyezik: int = 0
    imp_ossz: float = 0.0
    imp_db: int = 0
    jobb: int = 0
    rosszabb: int = 0
    dontetlen: int = 0
    peldak: list[str] = field(default_factory=list)

    def kiir(self, cimke: str, peldak_szama: int) -> None:
        p = print
        p("=" * 72)
        p(f"  {cimke}")
        p("=" * 72)
        p("  POZÍCIÓNKÉNT — minden döntés önálló, a menet a valódival megy")
        o = self.licit_ossz or 1
        fedett = self.licit_ossz - self.licit_nincs_dontes
        p(f"    vizsgált licit:      {self.licit_ossz}")
        p(f"    LEFEDETTSÉG:         {fedett}  ({100*fedett/o:.1f}%)"
          f"   <- volt-e EGYÁLTALÁN szabály")
        if fedett:
            p(f"    pontosság a lefedetteken: {self.fedett_egyezik}/{fedett}"
              f"  ({100*self.fedett_egyezik/fedett:.1f}%)   <- EZ A VALÓDI MÉRCE")
        p(f"    nincs szabály:       {self.licit_nincs_dontes}"
          f"   (ebből a valódi is passz volt: {self.nemfedett_pass})")
        a = 100 * self.licit_egyezik / o
        p(f"    nyers egyezés:       {self.licit_egyezik}  ({a:.1f}%)"
          f"   (a passz-fallbackkel együtt — FÉLREVEZETŐ)")
        if self.kompetitiv:
            p(f"    kompetitív helyzet:  {self.kompetitiv}"
              f"   (ebből lefedett: {self.kompetitiv_fedett})")
        p(f"    több jelölt volt:    {self.licit_bizonytalan}")
        if self.melyseg_ossz:
            p("    bontás a licit sorszáma szerint:")
            for m in sorted(self.melyseg_ossz):
                o, e = self.melyseg_ossz[m], self.melyseg_egyezik[m]
                p(f"      {m+1}. licit: {e:>5}/{o:<5} ({100*e/o:5.1f}%)")
        if self.tevesztes:
            p("    leggyakoribb eltérések:")
            for minta, db in self.tevesztes.most_common(peldak_szama):
                p(f"      {db:>4}x  {minta}")
        p("-" * 72)
        p("  SZIMULÁCIÓ — a motor végiglicitál, az ellenfél a valódi")
        p(f"    parti:               {self.parti}")
        p(f"    végig egyezett:      {self.vegig_egyezett}"
          f"   (itt a szimuláció HITELES)")
        p(f"    azonos kontraktus:   {self.kontraktus_egyezik}")
        p("-" * 72)
        p("  DOUBLE DUMMY ÖSSZEHASONLÍTÁS — melyik kontraktus jobb?")
        p(f"    kiértékelt parti:    {self.imp_db}")
        p(f"    a kibic JOBB:        {self.jobb}")
        p(f"    a kibic ROSSZABB:    {self.rosszabb}")
        p(f"    döntetlen:           {self.dontetlen}")
        if self.imp_db:
            p(f"    átlagos IMP-különbség: {self.imp_ossz/self.imp_db:+.3f}"
              f"   (pozitív = a kibic jobb)")
        if self.peldak:
            p("-" * 72)
            p("  PÉLDÁK (a legnagyobb különbségek):")
            for x in self.peldak[:peldak_szama]:
                p(f"      {x}")
        p("=" * 72)


# --- A mérés ----------------------------------------------------------

def _dd_utes(dds: dict, felvevo: str, szin: str) -> int | None:
    try:
        return int(dds[felvevo][szin])
    except (KeyError, TypeError, ValueError):
        return None


def _dd_pontszam(dds: dict, kontraktus: Kontraktus, beli: str) -> int | None:
    """A kontraktus É-D pontszáma TÖKÉLETES lejátszás mellett."""
    u = _dd_utes(dds, kontraktus.felvevo, kontraktus.szin)
    return None if u is None else pontszam_ns(kontraktus, u, beli)


def mer(motor: Licitmotor, partik, mi_vonalunk, ktx_alap: Kontextus,
        er: Eredmeny, peldak_max: int = 12) -> None:
    for (leosztas, licitek, dds, beli, vonal_jel) in partik:
        er.parti += 1

        # --- POZÍCIÓNKÉNT ---
        vegig = True
        for i, b in enumerate(licitek):
            ules = b.get("ules")
            if ules not in ULESEK or vonal(ules) != vonal_jel:
                continue
            valodi = (b.get("licit") or "").upper()
            d = motor.licital(licitek[:i], ules, leosztas.kezek[ules], beli)
            javasolt = d.licit or "PASS"
            er.licit_ossz += 1
            er.melyseg_ossz[i] += 1
            kompetitiv = any(vonal(x.get("ules", "N")) != vonal_jel
                             and (x.get("licit") or "").upper() != "PASS"
                             for x in licitek[:i])
            if kompetitiv:
                er.kompetitiv += 1
            if d.licit is None:
                er.licit_nincs_dontes += 1
                if valodi == "PASS":
                    er.nemfedett_pass += 1
            else:
                if kompetitiv:
                    er.kompetitiv_fedett += 1
                if javasolt == valodi:
                    er.fedett_egyezik += 1
            if d.bizonytalan:
                er.licit_bizonytalan += 1
            if javasolt == valodi:
                er.licit_egyezik += 1
                er.melyseg_egyezik[i] += 1
            else:
                er.tevesztes[f"{valodi} -> {javasolt}"] += 1
                vegig = False
        if vegig:
            er.vegig_egyezett += 1

        # --- SZIMULÁCIÓ ---
        sajat = list(licitek)
        uj: list[dict] = []
        ellenfel = [b for b in licitek if vonal(b.get("ules", "N")) != vonal_jel]
        ell_i = 0
        u = leosztas.oszto
        for _ in range(40):
            if vonal(u) == vonal_jel:
                d = motor.licital(uj, u, leosztas.kezek[u], beli)
                licit = d.licit or "PASS"
            else:
                licit = ((ellenfel[ell_i].get("licit") or "PASS").upper()
                         if ell_i < len(ellenfel) else "PASS")
                ell_i += 1
            uj.append({"ules": u, "licit": licit})
            u = kovetkezo_ules(u)
            if len(uj) >= 4 and all(x["licit"] == "PASS" for x in uj[-3:]) \
                    and any(x["licit"] != "PASS" for x in uj):
                break
            if len(uj) == 4 and all(x["licit"] == "PASS" for x in uj):
                break

        from ..motor.visszajatszo import licit_ellenoriz
        k_kibic, _, _, _ = licit_ellenoriz(uj, leosztas.oszto)
        k_valodi, _, _, _ = licit_ellenoriz(licitek, leosztas.oszto)
        if (k_kibic is None) == (k_valodi is None) and (
                k_kibic is None or (
                    k_kibic.szint == k_valodi.szint
                    and k_kibic.szin == k_valodi.szin
                    and k_kibic.felvevo == k_valodi.felvevo)):
            er.kontraktus_egyezik += 1

        # --- DOUBLE DUMMY ÖSSZEHASONLÍTÁS ---
        if not dds:
            continue
        p_kibic = _dd_pontszam(dds, k_kibic, beli) if k_kibic else 0
        p_valodi = _dd_pontszam(dds, k_valodi, beli) if k_valodi else 0
        if p_kibic is None or p_valodi is None:
            continue
        # a MI vonalunk szemszögéből
        elojel = 1 if vonal_jel == "NS" else -1
        kul = imp((p_kibic - p_valodi) * elojel)
        er.imp_ossz += kul
        er.imp_db += 1
        if kul > 0:
            er.jobb += 1
        elif kul < 0:
            er.rosszabb += 1
        else:
            er.dontetlen += 1
        if abs(kul) >= 6 and len(er.peldak) < peldak_max:
            er.peldak.append(
                f"{kul:+3d} IMP  valódi {k_valodi or 'PASS'} vs "
                f"kibic {k_kibic or 'PASS'}   ({leosztas.pbn('N')[:46]}...)")


# --- Adatbetöltés -----------------------------------------------------

def partik_dbbol(conn, par_nev: str | None, par_id: int | None, limit: int):
    cur = conn.cursor()
    felt, param = "", []
    if par_id or par_nev:
        if par_nev and not par_id:
            cur.execute("SELECT id FROM par WHERE nev=%s", (par_nev,))
            r = cur.fetchone()
            if not r:
                raise SystemExit(f"Nincs ilyen pár: {par_nev!r}")
            par_id = r[0]
        cur.execute("SELECT jatekos_a, jatekos_b FROM par WHERE id=%s",
                    (par_id,))
        a, b = cur.fetchone()
        felt = (" AND ((LEAST(j.n_jatekos_id,j.s_jatekos_id)=%s"
                " AND GREATEST(j.n_jatekos_id,j.s_jatekos_id)=%s)"
                " OR (LEAST(j.e_jatekos_id,j.w_jatekos_id)=%s"
                " AND GREATEST(j.e_jatekos_id,j.w_jatekos_id)=%s))")
        param = [a, b, a, b]

    cur.execute(
        "SELECT l.kezek_pbn, l.oszto, l.beliallas, j.licit, l.dds_utesek,"
        "       j.n_jatekos_id, j.s_jatekos_id, j.e_jatekos_id, j.w_jatekos_id"
        "  FROM jatszma j JOIN leosztas l ON l.id = j.leosztas_id"
        " WHERE j.licit IS NOT NULL" + felt +
        (f" LIMIT {int(limit)}" if limit else ""), param)

    ki = []
    for (pbn_s, oszto, beli, licit_j, dds_j, n, s, e, w) in cur.fetchall():
        try:
            leosztas = Leosztas.pbn_bol(pbn_s, oszto, beli)
            licitek = json.loads(licit_j) if isinstance(licit_j, str) else licit_j
        except Exception:                          # noqa: BLE001
            continue
        dds = json.loads(dds_j) if isinstance(dds_j, str) else dds_j
        vonal_jel = "NS"
        if par_id:
            cur2 = conn.cursor()
            cur2.execute("SELECT jatekos_a, jatekos_b FROM par WHERE id=%s",
                         (par_id,))
            a, b = cur2.fetchone()
            if {n, s} != {a, b}:
                vonal_jel = "EW"
        ki.append((leosztas, licitek or [], dds, beli, vonal_jel))
    return ki


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Teljes licitmenet-mérés")
    ap.add_argument("--lr", help="LICREN .lr fájl")
    ap.add_argument("--rendszer", help="Rendszerkód az adatbázisból")
    ap.add_argument("--par", help="Pár neve, pl. 'gal - korszurku'")
    ap.add_argument("--par-id", type=int)
    ap.add_argument("--metrika", default="P_HOSSZ")
    ap.add_argument("--jatekutes", default="J_KLASSZIKUS")
    ap.add_argument("--mod", default="SORREND",
                    choices=["SORREND", "SPECIFIKUSSAG"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--peldak", type=int, default=12)
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)
    if not (a.lr or a.rendszer):
        ap.error("Adj meg --lr vagy --rendszer paramétert")

    import pymysql
    conn = pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4")
    from ..domain.ertekelo import betolt_adatbazisbol
    betolt_adatbazisbol(conn)

    sorok = sorok_lrbol(a.lr) if a.lr else sorok_dbbol(conn, a.rendszer)
    ktx = Kontextus(metrika={"PONT": a.metrika, "JATEKUTES": a.jatekutes})
    motor = Licitmotor(sorok, ktx, mod=a.mod)

    partik = partik_dbbol(conn, a.par, a.par_id, a.limit)
    if not partik:
        raise SystemExit("Nincs mérhető parti")

    er = Eredmeny()
    mer(motor, partik, None, ktx, er, a.peldak)
    cimke = (f"{a.lr or a.rendszer}   |   {a.par or a.par_id or 'minden pár'}"
             f"   |   @PONT = {a.metrika}   |   {a.mod}")
    er.kiir(cimke, a.peldak)
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
