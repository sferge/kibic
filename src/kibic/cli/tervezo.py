"""
A sémákból dolgozó felvevő tervező egy állásra (2026-10-31, Felvevő tervjáték).

    PYTHONPATH=src python -m kibic.cli.tervezo --pbn tanpartik/Pavlicek_felvevo/4Q01.pbn \\
        --tabla 1 --utes 3 [--feltevés E:S:5+]

Az állás: a PBN valódi lejátszása az `--utes`-edik ütés végéig. A kimenet: a
helyzetelemzés, a technikák a lapokon, és a tervek táblázata (elvi esély: csak
a sikerfeltétel; kockázattal: az általános szabályokkal — ellopás, átmenet,
kiaduzás), a választott terv.
"""
from __future__ import annotations

import argparse
import re
import sys

from ..domain import Lap, kovetkezo_ules, vonal
from ..motor import tervjatszo as tj
from ..motor.tervsema import Allas, peldanyok, technikak_betoltese
from ..motor.tervszamolo import Korlat
from ..motor.tervezo import tervez, helyzetelemzes
from .jatekmeres import fajlok_kibontasa, partik_fajlbol
from .tervjatszo import tabla_szam


def allas_partibol(p, utes: int) -> tuple[Allas, dict]:
    """Az állás a valódi lejátszás `utes` ütése után (ütés elején); és a védők
    eddig lejátszott lapjai színenként (a feltevésekhez)."""
    k = p.kontraktus
    adu = None if k.szin == "NT" else k.szin
    kezek = {u: set(p.leosztas.kezek[u].lapok) for u in "NESW"}
    g = tj.Jatek(kezek, k.felvevo, adu, [], tj.Terv(()))
    g.tesz(kovetkezo_ules(k.felvevo), Lap.parse(str(p.lapok[0])))
    for c in p.lapok[1:4 * utes]:
        g.tesz(g.soron(), Lap.parse(str(c)))
    asztal = kovetkezo_ules(k.felvevo, 2)
    nyert = g.felvevo_utesek()
    hatra = 13 - utes
    soron = g.soron()
    if vonal(soron) != vonal(k.felvevo):
        raise SystemExit("a védők vannak hívásban — a tervező a mi hívásunkra dolgozik")
    allas = Allas(k.felvevo, adu, {u: set(g.kezek[u]) for u in (k.felvevo, asztal)},
                  set(g.kezek[kovetkezo_ules(k.felvevo, 1)]) | set(g.kezek[kovetkezo_ules(k.felvevo, 3)]),
                  6 + k.szint - nyert, hatra, soron)
    jatszott = {u: [l for uu, l in g.lapok if uu == u] for u in allas.vedok}
    return allas, jatszott, list(g.lapok)


def feltevesek(szovegek: list[str], jatszott: dict) -> list[Korlat]:
    """„E:S:5+” → Kelet legalább 5 pikk (a már lejátszottakkal együtt)."""
    ki = []
    for s in szovegek or []:
        m = re.fullmatch(r"([NESW]):([SHDC]):(\d+)(\+|-)?", s.strip())
        if not m:
            raise SystemExit(f"rossz feltevés: {s}")
        kez, sz, n, jel = m.group(1), m.group(2), int(m.group(3)), m.group(4)
        volt = sum(1 for l in jatszott[kez] if l.szin == sz)
        if jel == "-":
            ki.append(Korlat(kez, sz, 0, max(0, n - volt)))
        elif jel == "+":
            ki.append(Korlat(kez, sz, max(0, n - volt), 13))
        else:
            ki.append(Korlat(kez, sz, max(0, n - volt), max(0, n - volt)))
    return ki


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A sémákból dolgozó felvevő tervező egy állásra")
    ap.add_argument("--pbn", required=True)
    ap.add_argument("--tabla", type=int, required=True)
    ap.add_argument("--utes", type=int, default=0, help="a valódi lejátszás ennyi ütése után")
    ap.add_argument("--feltevés", "--felteves", dest="felteves", action="append",
                    help="pl. E:S:5+ (Kelet legalább 5 pikk); többször is")
    ap.add_argument("--db", type=int, default=15, help="ennyi tervet ír ki")
    ap.add_argument("--ellenorzes", type=int, default=0,
                    help="ennyi sorsolt világon DD-védők ellen is lejátssza a legjobb tervek kottáját")
    ap.add_argument("--ellenorzott", type=int, default=5, help="ennyi tervet ellenőriz")
    a = ap.parse_args(argv)
    partik = [p for p in partik_fajlbol(fajlok_kibontasa([a.pbn], ".pbn"), "IMP", 1)
              if tabla_szam(p.azonosito) == a.tabla]
    if not partik:
        print("nincs ilyen tábla", file=sys.stderr)
        return 1
    p = partik[0]
    allas, jatszott, sor = allas_partibol(p, a.utes)
    korl = feltevesek(a.felteves, jatszott)
    h = helyzetelemzes(allas)
    print(f"{p.azonosito} {p.kontraktus}, a {a.utes + 1}. ütéstől; {h.szoveg()}")
    if korl:
        print("feltevés: " + "; ".join(f"{k.kez} {k.szin} a kint lévők közül {k.min}..{k.max}" for k in korl))
    print("technikák a lapokon: " + ", ".join(pp.rovid for pp in peldanyok(allas, technikak_betoltese())))
    _, ert = tervez(allas, korl)
    print(f"\n{'elvi':>6} {'kockázattal':>11} {'adu előbb':>9}  terv")
    kdsz = lambda n: "mind" if n >= 13 else str(n)
    for e in ert[:a.db]:
        print(f"{e.elvi:6.1%} {e.kockazattal:11.1%} {kdsz(e.terv.kiaduzas):>9}  {e.terv.nev}  [{e.terv.strategia}]")
    print("adu előbb: ennyi adukör a technikák előtt („mind”: végig)")
    if a.ellenorzes:
        from ..motor.tervellenorzo import ellenoriz, vilagok
        rel = {l for pp in peldanyok(allas, technikak_betoltese()) for l in pp.relevans}
        vl = vilagok(p.leosztas, sor, allas.kint, a.ellenorzes, korl, vedok=allas.vedok)
        print(f"\nDD-ellenőrzés ({len(vl)} sorsolt világ, DD-védők ellen):")
        print(f"{'modell':>7} {'DD':>6} {'eltér':>6}  terv")
        for e in ert[:a.ellenorzott]:
            r = ellenoriz(h, e.terv, e.politika, vl, p.kontraktus, sor, rel)
            print(f"{r.modell_esely:7.1%} {r.esely:6.1%} {r.n - r.egyezik:6d}  {e.terv.nev}", flush=True)
            for pe in r.peldak[:4]:
                print(f"           modell {pe[0]} / DD {pe[1]} {pe[2]}  K: {pe[3]}")
    if ert:
        v = ert[0]
        print(f"\nválasztás: {v.terv.nev} ({v.kockazattal:.1%}); a következő technika: "
              f"{v.terv.lepesek[0].sema.nev} ({v.terv.lepesek[0].rovid})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
