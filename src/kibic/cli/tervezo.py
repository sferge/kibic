"""
A sémákból dolgozó felvevő tervező egy állásra (2026-10-31, Felvevő tervjáték).

    PYTHONPATH=src python -m kibic.cli.tervezo --pbn tanpartik/Pavlicek_felvevo/4Q01.pbn \\
        --tabla 1 [--utes 3] [--feltevés E:S:5+] [--teljes]

Az `--utes` nélkül a tervezés pillanata az első saját hívás (RELEVANS_UTES).
A szálak száma: KIBIC_SZALAK (alapból a gép logikai processzorai).

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
from ..motor.tervsema import Allas, peldanyok, problemakep, technikak_betoltese
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


def tervezesi_pont(p) -> tuple[int | None, list, int]:
    """Az első ütés, amelyben döntésünk van (RELEVANS_UTES): a saját hívásunk
    (fajta 0), vagy a védő hívására dobás (2) vagy ütés-döntés (3). A naplóban az
    addigi védői hívások: (ütés, hívott lap, fajta, miért)."""
    from ..motor.tervpont import utes_fajta, NINCS_DONTES
    k = p.kontraktus
    adu = None if k.szin == "NT" else k.szin
    asztal = kovetkezo_ules(k.felvevo, 2)
    v1 = kovetkezo_ules(k.felvevo, 1)
    kezek = {u: set(p.leosztas.kezek[u].lapok) for u in "NESW"}
    g = tj.Jatek(kezek, k.felvevo, adu, [], tj.Terv(()))
    naplo = []
    lapok = [Lap.parse(str(c)) for c in p.lapok]
    for t in range(13):
        hivo = v1 if t == 0 else g.soron()
        if vonal(hivo) == vonal(k.felvevo):
            return t, naplo, 0
        if 4 * t >= len(lapok):
            break
        f, miert = utes_fajta(g.kezek[k.felvevo], g.kezek[asztal], lapok[4 * t], adu)
        naplo.append((t + 1, lapok[4 * t], f, miert))
        if f != NINCS_DONTES:
            return t, naplo, f
        for i, c in enumerate(lapok[4 * t:4 * t + 4]):
            g.tesz(hivo if (t == 0 and i == 0) else g.soron(), c)
    return None, naplo, 0


def utes_allas_partibol(p, utes: int):
    """A `utes`-edik ütés (0-tól) a védő hívása után: (UtesAllas, a valódi ütés)."""
    from ..motor.tervutes import UtesAllas
    k = p.kontraktus
    adu = None if k.szin == "NT" else k.szin
    asztal = kovetkezo_ules(k.felvevo, 2)
    v1, v2 = kovetkezo_ules(k.felvevo, 1), kovetkezo_ules(k.felvevo, 3)
    kezek = {u: set(p.leosztas.kezek[u].lapok) for u in "NESW"}
    g = tj.Jatek(kezek, k.felvevo, adu, [], tj.Terv(()))
    lapok = [Lap.parse(str(c)) for c in p.lapok]
    sor = []
    for i, c in enumerate(lapok[:4 * utes]):
        u = v1 if i == 0 else g.soron()
        g.tesz(u, c)
        sor.append((u, c))
    hivo = v1 if utes == 0 else g.soron()
    hivott = lapok[4 * utes]
    nyert = g.felvevo_utesek() if utes else 0
    a = UtesAllas(k.felvevo, adu, {u: set(g.kezek[u]) for u in (k.felvevo, asztal)},
                  (set(g.kezek[v1]) | set(g.kezek[v2])) - {hivott}, hivo, hivott,
                  6 + k.szint - nyert, 13 - utes, szinhianyok(sor, (v1, v2)))
    valodi = [(hivo, hivott)]
    u = hivo
    for c in lapok[4 * utes + 1:4 * utes + 4]:
        u = kovetkezo_ules(u, 1)
        valodi.append((u, c))
    return a, valodi


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
            ki.append(Korlat(kez, sz, 0, max(0, n - volt), "feltetelezett"))
        elif jel == "+":
            ki.append(Korlat(kez, sz, max(0, n - volt), 13, "feltetelezett"))
        else:
            ki.append(Korlat(kez, sz, max(0, n - volt), max(0, n - volt), "feltetelezett"))
    return ki


def szinhianyok(sor: list, vedok: tuple) -> list[Korlat]:
    """Megfigyelt színhiány: a védő nem adott színt, amikor a színt hívták."""
    ki = []
    for t in range(0, len(sor) - 3, 4):
        utes = sor[t:t + 4]
        hivott = utes[0][1].szin
        for u, l in utes[1:]:
            if u in vedok and l.szin != hivott:
                ki.append(Korlat(u, hivott, 0, 0, "megfigyelt"))
    return ki


FAJTA = {1: "nincs döntés", 2: "DOBÁS", 3: "ÜTÉS-DÖNTÉS"}


def utes_kozben(p, utes: int, naplo=print, stat: dict | None = None):
    """Tervezés a védő hívása után: a jelöltek értéke és a választás."""
    import time
    from ..motor.tervutes import UtesTervezo
    t0 = time.time()
    a, valodi = utes_allas_partibol(p, utes)
    naplo(f"{p.azonosito} {p.kontraktus}, a {utes + 1}. ütésben, {a.hivo} hívása után ({a.hivott}); "
          f"cél {a.cel} a hátralévő {a.hatra}-ból")
    ut = UtesTervezo(a, naplo=naplo)
    ert = ut.tervez()
    v = ert[0]
    naplo(f"választás: {v.szoveg()} ({v.ertek:.1%}); a valódi ütés: "
          + " ".join(f"{u}:{l}" for u, l in valodi))
    for w, leiras, e in sorted(v.csoportok, key=lambda x: -x[0])[:5]:
        naplo(f"   {w:5.1%}  {leiras}  → {e:.1%}")
    if stat is not None:
        stat.update(jeloltek=len(ert), tervezesek=ut.tervezesek, ossz_s=time.time() - t0,
                    valasztas=v.szoveg(), esely=v.ertek,
                    valodi=" ".join(f"{u}:{l}" for u, l in valodi))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A sémákból dolgozó felvevő tervező egy állásra")
    ap.add_argument("--pbn", required=True)
    ap.add_argument("--tabla", type=int, required=True)
    ap.add_argument("--utes", type=int, default=None,
                    help="a valódi lejátszás ennyi ütése után (alapból: az első saját hívásnál)")
    ap.add_argument("--teljes", action="store_true",
                    help="minden drága tervet pontosan számol (a lépcsők ellenőrzéséhez)")
    ap.add_argument("--feltevés", "--felteves", dest="felteves", action="append",
                    help="pl. E:S:5+ (Kelet legalább 5 pikk); többször is")
    ap.add_argument("--db", type=int, default=15, help="ennyi tervet ír ki")
    ap.add_argument("--szabad-helyek-feltevesbol", action="store_true",
                    help="a feltételezett hossz is súlyozza az elosztásokat (alapból csak az ismert)")
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
    if a.utes is None:
        a.utes, naplo, fajta = tervezesi_pont(p)
        for t, l, f, miert in naplo:
            print(f"{t}. ütés: a védők hívása {l} — {FAJTA[f]} ({miert})")
        if a.utes is None:
            print("nincs döntési pont a lejátszásban", file=sys.stderr)
            return 1
        if fajta:
            return utes_kozben(p, a.utes)
    allas, jatszott, sor = allas_partibol(p, a.utes)
    korl = feltevesek(a.felteves, jatszott) + szinhianyok(sor, allas.vedok)
    h = helyzetelemzes(allas)
    print(f"{p.azonosito} {p.kontraktus}, a {a.utes + 1}. ütéstől; {h.szoveg()}")
    if korl:
        print("feltevés: " + "; ".join(f"{k.kez} {k.szin} a kint lévők közül {k.min}..{k.max}" for k in korl))
    print("technikák a lapokon: " + ", ".join(pp.rovid for pp in peldanyok(allas, technikak_betoltese())))
    print("felismerés: " + problemakep(allas, h.hiany, h.tartalek))
    stat = {}
    _, ert = tervez(allas, korl, feltevesbol=a.szabad_helyek_feltevesbol, teljes=a.teljes, stat=stat)
    print(f"tervek: {stat['tervek']} (olcsó {stat['olcso']}, drága {stat['draga']}, ebből pontosan "
          f"{stat['draga_pontos']}); elemzés számolva {stat['elemzes_szamolt']}; idő {stat['ossz_s']:.0f} s "
          f"(olcsó {stat['olcso_s']:.0f}, becslés {stat['becsles_s']:.0f}, pontos {stat['pontos_s']:.0f})")
    if any(k.tudas == "feltetelezett" for k in korl) and not a.szabad_helyek_feltevesbol:
        print("(a feltevés a SZABAD_HELYEK szabály szerint nem súlyoz — csak az ismert hossz)")
    print(f"\n{'elvi':>6} {'kockázattal':>11} {'adu előbb':>9}  terv")
    kdsz = lambda n: "mind" if n >= 13 else str(n)
    for e in ert[:a.db]:
        if e.becsult:
            print(f"{'':>6} {e.kockazattal:10.1%}~ {'':>9}  {e.terv.nev}  [becslés]")
            continue
        print(f"{e.elvi:6.1%} {e.kockazattal:11.1%} {kdsz(e.terv.kiaduzas):>9}  {e.terv.nev}  [{e.terv.strategia}]")
    print("adu előbb: ennyi adukör a technikák előtt („mind”: végig); ~: becslés (a drága lépés "
          "a két szín külön, korlátlan átmenettel)")
    if a.ellenorzes:
        from ..motor.tervellenorzo import ellenoriz, vilagok
        rel = {l for pp in peldanyok(allas, technikak_betoltese()) for l in pp.relevans}
        vl = vilagok(p.leosztas, sor, allas.kint, a.ellenorzes, korl, vedok=allas.vedok)
        print(f"\nDD-ellenőrzés ({len(vl)} sorsolt világ, DD-védők ellen):")
        print(f"{'modell':>7} {'DD':>6} {'eltér':>6}  terv")
        for e in [x for x in ert if not x.becsult][:a.ellenorzott]:
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
