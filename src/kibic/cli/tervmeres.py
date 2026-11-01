"""
A felvevő tervező mérése sok partin (2026-11-01, Felvevő tervjáték).

    PYTHONPATH=src python -m kibic.cli.tervmeres \\
        --pbn tanpartik/Pavlicek_felvevo/4Q01.pbn [--tablak 1-6] [--szalak 32] \\
        [--teljes] [--kimenet tervmeres.tsv]

Partinként: a tervezés pillanata (RELEVANS_UTES: az első saját hívás; a
releváns védői hívások jelölve), a felismerés, a választott terv és esélye, a
lépcsők ideje (olcsó tervek, becslés, pontos számítás) és a kiszámolt
elemzések száma. `--teljes`: utána minden drága tervet pontosan is számol, és
összeveti, ugyanazt választaná-e (a lépcsők ellenőrzése).

Az elemzések gyűlő tára: ~/.cache/kibic/elemzes (KIBIC_ELEMZES_TAR); a
második futás ugyanazokon a partikon már a tárból dolgozik — az első futás
mutatja a valódi időt.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback


def _tablak(szoveg: str | None) -> set[int] | None:
    if not szoveg:
        return None
    ki = set()
    for resz in szoveg.split(","):
        if "-" in resz:
            a, b = resz.split("-")
            ki |= set(range(int(a), int(b) + 1))
        else:
            ki.add(int(resz))
    return ki


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A felvevő tervező mérése sok partin")
    ap.add_argument("--pbn", default="tanpartik/Pavlicek_felvevo/4Q01.pbn")
    ap.add_argument("--tablak", help="pl. 1-6 vagy 1,2,5 (alapból mind)")
    ap.add_argument("--szalak", type=int, help="párhuzamos folyamatok (alapból a logikai processzorok)")
    ap.add_argument("--teljes", action="store_true", help="összevetés: minden drága terv pontosan")
    ap.add_argument("--kimenet", default="tervmeres.tsv")
    a = ap.parse_args(argv)
    if a.szalak:
        os.environ["KIBIC_SZALAK"] = str(a.szalak)

    from ..motor.tervezo import tervez, helyzetelemzes
    from ..motor.tervparhuzam import szalak_szama, verzio, _konyvtar
    from ..motor.tervsema import problemakep
    from .jatekmeres import fajlok_kibontasa, partik_fajlbol
    from .tervjatszo import tabla_szam
    from .tervezo import allas_partibol, szinhianyok, tervezesi_pont

    valaszt = _tablak(a.tablak)
    partik = [p for p in partik_fajlbol(fajlok_kibontasa([a.pbn], ".pbn"), "IMP", 1)
              if valaszt is None or tabla_szam(p.azonosito) in valaszt]
    print(f"{len(partik)} parti; szálak {szalak_szama()} (os.cpu_count {os.cpu_count()}); "
          f"tár {_konyvtar()}/{verzio()}", flush=True)
    sorok = []
    fej = ["tabla", "kontraktus", "pont", "relevans_vedoi", "valasztas", "esely", "tervek",
           "draga", "draga_pontos", "elemzes", "ido_s", "olcso_s", "becsles_s", "pontos_s",
           "teljes_valasztas", "teljes_esely", "teljes_ido_s", "egyezik", "fal_s", "hiba"]
    for p in partik:
        r = {k: "" for k in fej}
        r["tabla"], r["kontraktus"] = tabla_szam(p.azonosito), str(p.kontraktus)
        print(f"\n== {p.azonosito} {p.kontraktus}", flush=True)
        t_parti = time.time()
        try:
            pont, naplo = tervezesi_pont(p)
            for t, l, rel, miert in naplo:
                print(f"   {t}. ütés: védői hívás {l} — {'RELEVÁNS' if rel else 'nem releváns'} ({miert})")
            r["relevans_vedoi"] = ",".join(str(t) for t, _, rel, _ in naplo if rel)
            if pont is None:
                raise RuntimeError("nincs saját hívásunk")
            r["pont"] = pont + 1
            allas, jatszott, sor = allas_partibol(p, pont)
            h = helyzetelemzes(allas)
            print(f"   tervezés a {pont + 1}. ütésnél; {h.szoveg()}")
            print("   felismerés: " + problemakep(allas, h.hiany, h.tartalek), flush=True)
            korl = szinhianyok(sor, allas.vedok)
            stat = {}
            _, ert = tervez(allas, korl, stat=stat)
            v = ert[0] if ert else None
            r.update(valasztas=v.terv.nev if v else "-", esely=f"{v.kockazattal:.3f}" if v else "",
                     tervek=stat["tervek"], draga=stat["draga"], draga_pontos=stat["draga_pontos"],
                     elemzes=stat["elemzes_szamolt"], ido_s=f"{stat['ossz_s']:.1f}",
                     olcso_s=f"{stat['olcso_s']:.1f}", becsles_s=f"{stat['becsles_s']:.1f}",
                     pontos_s=f"{stat['pontos_s']:.1f}")
            print(f"   választás: {r['valasztas']} ({v.kockazattal:.1%}); tervek {stat['tervek']}, "
                  f"drága {stat['draga']} (pontosan {stat['draga_pontos']}); elemzés {stat['elemzes_szamolt']}; "
                  f"{stat['ossz_s']:.0f} s (olcsó {stat['olcso_s']:.0f}, becslés {stat['becsles_s']:.0f}, "
                  f"pontos {stat['pontos_s']:.0f})" if v else "   nincs terv", flush=True)
            if a.teljes and stat["draga"] > stat["draga_pontos"]:
                st2 = {}
                _, ert2 = tervez(allas, korl, teljes=True, stat=st2)
                v2 = ert2[0]
                r.update(teljes_valasztas=v2.terv.nev, teljes_esely=f"{v2.kockazattal:.3f}",
                         teljes_ido_s=f"{st2['ossz_s']:.1f}",
                         egyezik="igen" if v2.terv.nev == r["valasztas"] or
                         abs(v2.kockazattal - v.kockazattal) < 1e-9 else "NEM")
                print(f"   teljes: {v2.terv.nev} ({v2.kockazattal:.1%}), {st2['ossz_s']:.0f} s — "
                      f"egyezik: {r['egyezik']}", flush=True)
            elif a.teljes:
                r["egyezik"] = "igen (nincs becsült terv)"
        except Exception as e:     # a mérés megy tovább; a hibát rögzítjük
            r["hiba"] = f"{type(e).__name__}: {e}".replace("\t", " ")[:200]
            print("   HIBA: " + r["hiba"], flush=True)
            if os.environ.get("KIBIC_HIBA_RESZLET"):
                traceback.print_exc()
        r["fal_s"] = f"{time.time() - t_parti:.1f}"
        print(f"   parti ideje: {float(r['fal_s']):.0f} s", flush=True)
        sorok.append(r)
        with open(a.kimenet, "w", encoding="utf-8") as f:
            f.write("\t".join(fej) + "\n")
            for x in sorok:
                f.write("\t".join(str(x[k]) for k in fej) + "\n")
    print(f"\n{'tábla':>5} {'kontr.':>6} {'ütés':>4} {'esély':>6} {'idő s':>6}  választás / hiba")
    for x in sorok:
        print(f"{x['tabla']:>5} {x['kontraktus']:>6} {str(x['pont']):>4} {x['esely'] or '-':>6} "
              f"{float(x['fal_s']):6.0f}  {x['hiba'] or x['valasztas']}")
    ok = [x for x in sorok if not x["hiba"]]
    ido = sum(float(x["fal_s"]) for x in sorok)
    print(f"\nösszesen {len(sorok)} parti, {len(ok)} tervezve, {len(sorok) - len(ok)} hiba; "
          f"összes idő {ido:.0f} s; eredmény: {a.kimenet}")
    if a.teljes:
        nem = [x["tabla"] for x in ok if x["egyezik"] == "NEM"]
        print("a lépcsők más tervet választottak: " + (", ".join(map(str, nem)) if nem else "egyik partin sem"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
