"""
A játékmódok a tervezőben (2026-11-03): megtalálja-e a tervező a mód tervét, és mit
ad a gyors esély szűrője.

Partinként (a játszma elején, a felvevő hív — a lejátszás nélküli BBO-partik miatt
mindenhol így) három tervezés:
  A  a mód technikája nélkül (a régi tervező),
  B  minden technikával,
  C  csak a gyors esély szerint kiválasztott módok technikáival (alapjáték + a két
     legnagyobb nyereségű speciális mód közül azok, amelyeknek már van technikája).
A kimenet: melyik terv nyer, az esélyek (kockázattal), az idők és az elemzések száma.

    PYTHONPATH=src python3 eszkozok/jatekmod_elemzes/modterv.py --pbn <Pavlicek PBN> \\
        [--bbo tanpartik/bbo_hotd] [--mod LOPAS_ROVID] [--kontroll 20] [--max N] [--kimenet modterv.tsv]

--pontos: a drága tervek pontosan is (lassú: partinként akár órák); alapból becsléssel.
--mod: a vizsgált mód (a címke); --kontroll: ennyi alapjáték-címkés színjáték-parti is
(azon nem szabad rontania). A tervező elemzései a közös tárba kerülnek: a B és a C
már az A elemzéseiből is dolgozik — az idők közül az A-é a hideg idő.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rangsor import GYOKER, modok, partik_cimkekkel        # noqa: E402

sys.path.insert(0, str(GYOKER / "src"))

# a gyors esély módnevei → a jatekmodok.yaml módjai (amelyeknek már van technikája)
TECHNIKAS = {"LOPAS_ROVID": "LOPAS_ROVID_KEZBEN", "KIMAGASITAS": "KIMAGASITAS"}
MOD_TECHNIKA = {"LOPAS_ROVID": "LOPAS_ROVID_KEZBEN", "KIMAGASITAS": "LOPASOS_KIMAGASITAS"}


def _arg(nev, alap=None):
    return sys.argv[sys.argv.index(nev) + 1] if nev in sys.argv else alap


def allas_eleje(p):
    from kibic.domain import kovetkezo_ules
    from kibic.motor.tervsema import Allas
    k = p.kontraktus
    X, Y = k.felvevo, kovetkezo_ules(k.felvevo, 2)
    kint = set()
    for u in "NESW":
        if u not in (X, Y):
            kint |= set(p.leosztas.kezek[u].lapok)
    return Allas(felvevo=X, adu=None if k.szin == "NT" else k.szin,
                 kezek={X: set(p.leosztas.kezek[X].lapok), Y: set(p.leosztas.kezek[Y].lapok)},
                 kint=kint, cel=6 + k.szint, hatra=13, soron=X)


def gyors_modok(p) -> list[str]:
    """A két legnagyobb nyereségű speciális mód (tervmodesely)."""
    from kibic.domain import kovetkezo_ules
    from kibic.motor import tervmodesely as tm
    k = p.kontraktus
    X = p.leosztas.kezek[k.felvevo].lapok
    Y = p.leosztas.kezek[kovetkezo_ules(k.felvevo, 2)].lapok
    D = {s: {l.rang for l in X if l.szin == s} for s in "SHDC"}
    U = {s: {l.rang for l in Y if l.szin == s} for s in "SHDC"}
    e = tm.mod_eselyek(D, U, None if k.szin == "NT" else k.szin, 6 + k.szint)
    tm.gyorsitotar_urites()
    spec = sorted((m for m in e if m != "ALAP" and e[m][1] > 0), key=lambda m: -e[m][1])
    return spec[:2]


def tervezes(allas, csak):
    from kibic.motor.tervezo import tervez
    stat = {}
    t = time.time()
    # alapból a drága (adu + szín együtt) tervek csak becsléssel: a 13 lapos pontos
    # számítás partinként órákig tart (a szerkesztő mérése, 2026-11-03)
    _, ert = tervez(allas, csak=csak, stat=stat, draga_pontos="--pontos" in sys.argv)
    v = ert[0] if ert else None
    return (v.terv.nev if v else "-", v.kockazattal if v else 0.0, time.time() - t,
            stat.get("elemzes_szamolt", 0))


def main():
    from kibic.motor.tervsema import mod_technikak, technikak_betoltese
    from rangsor4 import bbo_partik
    mod = _arg("--mod", "LOPAS_ROVID")
    kontroll = int(_arg("--kontroll", "20"))
    minden = set(technikak_betoltese())
    nelkule = minden - {MOD_TECHNIKA[mod]}
    partik = []
    db_k = 0
    for p, c in partik_cimkekkel():
        if c is None or p.kontraktus is None or p.kontraktus.szin == "NT":
            continue
        ms = modok(c)
        if mod in ms:
            partik.append((p, "P:" + mod))
        elif ms == {"ALAPJATEK"} and db_k < kontroll:
            partik.append((p, "P:ALAPJATEK"))
            db_k += 1
    if "--bbo" in sys.argv:
        for p, ms in bbo_partik(_arg("--bbo")):
            if mod in ms and p.kontraktus.szin != "NT":
                partik.append((p, "B:" + mod))
    if "--max" in sys.argv:
        partik = partik[:int(_arg("--max"))]
    print(f"{len(partik)} parti ({mod}: {sum(1 for _, c in partik if c.endswith(mod))}, "
          f"kontroll: {sum(1 for _, c in partik if c.endswith('ALAPJATEK'))})", flush=True)
    fej = ["parti", "cimke", "kontraktus", "gyors", "A_terv", "A", "A_s", "B_terv", "B", "B_s",
           "C_terv", "C", "C_s", "hiba"]
    sorok = []
    kimenet = _arg("--kimenet", "modterv.tsv")
    for p, cimke in partik:
        r = {k: "" for k in fej}
        r.update(parti=p.azonosito, cimke=cimke, kontraktus=str(p.kontraktus))
        try:
            allas = allas_eleje(p)
            gy = gyors_modok(p)
            r["gyors"] = ",".join(gy)
            csak = mod_technikak(["ALAPJATEK"] + [TECHNIKAS[m] for m in gy if m in TECHNIKAS])
            for betu, cs in (("A", nelkule), ("B", None), ("C", csak)):
                nev, e, t, _ = tervezes(allas, cs)
                r[betu + "_terv"], r[betu], r[betu + "_s"] = nev, f"{e:.3f}", f"{t:.1f}"
            print(f"{p.azonosito:28s} {cimke:14s} {str(p.kontraktus):6s} gyors={r['gyors']:24s} "
                  f"A {r['A']} B {r['B']} C {r['C']}  ({r['A_s']}/{r['B_s']}/{r['C_s']} s)  B: {r['B_terv']}",
                  flush=True)
        except Exception as e:      # noqa: BLE001 — a mérés megy tovább
            r["hiba"] = f"{type(e).__name__}: {e}"[:200]
            print(f"{p.azonosito}: HIBA {r['hiba']}", flush=True)
        sorok.append(r)
        with open(kimenet, "w", encoding="utf-8") as f:
            f.write("\t".join(fej) + "\n")
            for x in sorok:
                f.write("\t".join(str(x[k]) for k in fej) + "\n")
    # összegzés
    print()
    for csop in sorted({r["cimke"] for r in sorok}):
        rr = [r for r in sorok if r["cimke"] == csop and not r["hiba"]]
        if not rr:
            continue
        atl = lambda k: sum(float(r[k]) for r in rr) / len(rr)
        lop = sum(1 for r in rr if "lopás a rövid kézben" in r["B_terv"] or "lopásos" in r["B_terv"])
        jobb = sum(1 for r in rr if float(r["B"]) > float(r["A"]) + 0.005)
        c_rossz = sum(1 for r in rr if float(r["C"]) < float(r["B"]) - 0.005)
        print(f"{csop:14s} {len(rr):3d} parti: esély A {atl('A'):.3f} → B {atl('B'):.3f} (C {atl('C'):.3f}); "
              f"B jobb {jobb}, a B terve a móddal {lop}; C rosszabb B-nél {c_rossz}; "
              f"idő A {atl('A_s'):.0f} s, B {atl('B_s'):.0f} s, C {atl('C_s'):.0f} s")


if __name__ == "__main__":
    main()
