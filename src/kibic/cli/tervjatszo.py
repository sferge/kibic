"""
A tervjátszó mérése (2026-10-25): a valódi indulás után a kibic tervet választ
(a jelöltek esélye a sorsolt világokon), és azt játssza végig a valódi
leosztásban (a védők DD szerint). Visszajelzés partinként:
  - a választott terv és becsült esélye;
  - teljesült-e a valódi leosztásban;
  - DD szerint teljesíthető volt-e (az indulás után);
  - volt-e a jelöltek között olyan, amely a valódi leosztásban teljesít
    (a jelöltállító lefedése).

    PYTHONPATH=src python -m kibic.cli.tervjatszo --pbn tanpartik/Pavlicek_felvevo \
        --tol 0 --db 20 --vilag 20 --json ki.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from ..domain import kovetkezo_ules
from ..motor import lejatszas as lj
from ..motor import tervjatszo as tj
from ..motor.lejatszas_meres import _lap, ulesek_sorrendben, pozicio_keres
from .jatekmeres import fajlok_kibontasa, partik_fajlbol


def egy_parti(p, vilag: int, max_terv: int, mag: int, tar_fv=None, naplo=None) -> dict | None:
    """A valódi leosztás végigjátszása: a felvevő minden HÍVÁSÁNÁL újratervez (a
    jelöltek a mostani lapokból, az esély a mostani helyzettel összeférő
    világokon), a követő lapnál a terv szándéka vagy a világok DD-szavazása dönt;
    a védők DD szerint."""
    from dataclasses import replace
    from ..solver.dds import lap_elemzes
    k = p.kontraktus
    if k is None or not p.lapok:
        return None
    t0 = time.time()
    adu = None if k.szin == "NT" else k.szin
    felvevo = k.felvevo
    asztal = kovetkezo_ules(felvevo, 2)
    elso = _lap(p.lapok[0])
    kijatszo = kovetkezo_ules(felvevo)
    cel = 6 + k.szint
    dd0 = lap_elemzes(p.leosztas, [str(elso)], k)
    dd_ertek = max(e.felvevo_osszesen for e in dd0)
    valodi = {u: set(p.leosztas.kezek[u].lapok) for u in "NESW"}
    g = tj.Jatek(valodi, felvevo, adu, [(kijatszo, elso)], tj.Terv(()))
    terv_jx = None
    tervek_log = []
    dontesek = 0
    while len(g.lapok) < 52:
        u = g.soron()
        if not g.mi(u):
            lap = tj._vedo_lap(lap_elemzes(p.leosztas, [str(l) for _, l in g.lapok], k))
        else:
            utes = g.aktualis()
            van = [l for l in g.kezek[u] if utes and l.szin == utes[0][1].szin]
            legalis = van or sorted(g.kezek[u], key=lambda l: (l.szin, l.rang))
            if len(legalis) == 1:
                lap = legalis[0]
            elif utes and terv_jx is not None and tj._szandekos(terv_jx, u):
                lap = tj.felvevo_lap(terv_jx, u)
            else:
                dontesek += 1
                jatszott = [str(l) for _, l in g.lapok]
                keres = pozicio_keres(replace(p, lapok=jatszott + [jatszott[0]]), len(jatszott))
                allas = lj.allas_keresbol(keres)
                tar = tar_fv(keres) if tar_fv else None
                try:
                    m = lj.mintavetel(allas, tar, db=vilag, mag=mag + len(jatszott))
                except lj.LejatszasHiba:
                    m = None
                vilagok = m.leosztasok if m else []
                sulyok = (m.sulyok or [1.0] * len(vilagok)) if m else []
                if not vilagok:
                    lap = legalis[0]
                elif not utes:
                    d, y = g.kezek[felvevo], g.kezek[asztal]
                    tervek = tj.jeloltek(d, y, adu, g.kint, max_terv)
                    ert = tj.ertekel_lepcsos(tervek, vilagok, sulyok, felvevo, k, list(g.lapok))
                    terv_jx = tj.Jatek(valodi, felvevo, adu, list(g.lapok), ert[0].terv)
                    lap = tj.felvevo_lap(terv_jx, u)
                    tervek_log.append((len(g.lapok) // 4 + 1, str(ert[0].terv), round(ert[0].esely, 2)))
                    if naplo:
                        naplo(f"   {len(g.lapok)//4+1:>2}. ütés: {ert[0].esely:.2f} {ert[0].terv}")
                else:
                    ered = [lap_elemzes(lo, jatszott, k) for lo in vilagok]
                    lap = tj.dd_szavazas(ered, sulyok, cel)
            lap = tj.szabalyos(g, u, lap)
        g.tesz(u, lap)
        if terv_jx is not None and len(terv_jx.lapok) < len(g.lapok):
            terv_jx.tesz(u, lap)
    ut = g.felvevo_utesek()
    return {"tabla": p.azonosito, "kontraktus": str(k), "cel": cel, "dd": dd_ertek,
            "dd_teljesul": dd_ertek >= cel, "utesek": ut, "teljesult": ut >= cel,
            "tervek": tervek_log, "dontesek": dontesek, "ms": int((time.time() - t0) * 1000)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A tervjátszó mérése")
    ap.add_argument("--pbn", nargs="+", required=True)
    ap.add_argument("--tol", type=int, default=0)
    ap.add_argument("--db", type=int, default=10)
    ap.add_argument("--csak", nargs="*", type=int, help="csak ezek a táblaszámok")
    ap.add_argument("--vilag", type=int, default=20)
    ap.add_argument("--terv", type=int, default=40)
    ap.add_argument("--mag", type=int, default=1)
    ap.add_argument("--licit", default="", help="a licitrendszer (üres: licit nélkül sorsol)")
    ap.add_argument("--json")
    ap.add_argument("--reszletes", action="store_true")
    a = ap.parse_args(argv)
    tar_fv = None
    if a.licit:
        from .jatekmeres import yaml_dontes  # noqa: F401 — a betöltő
        from .aranykeszlet import yaml_betolto
        from ..szolgaltatas.atjaro import licit_tudas
        from .jatekmeres import GYOKER
        betolto = yaml_betolto([str(GYOKER / "rendszerek" / "yaml")])

        def tar_fv(keres):
            st = keres.get("state") or {}
            try:
                return licit_tudas({"seat": keres["state"].get("acting_for_seat") or st.get("dealer"),
                                    "dealer": st.get("dealer"),
                                    "vulnerability": (keres.get("game") or {}).get("vulnerability") or "none",
                                    "auction": (keres.get("history") or {}).get("auction") or [],
                                    "system": a.licit}, betolto, 0)[0]
            except Exception:                    # noqa: BLE001
                return None
    f = open(a.json, "w", encoding="utf-8") if a.json else None
    partik = list(partik_fajlbol(fajlok_kibontasa(a.pbn, ".pbn"), "IMP"))
    if a.csak:
        partik = [p for p in partik if int(p.azonosito.rsplit("#", 1)[1]) in a.csak]
    else:
        partik = partik[a.tol:a.tol + a.db]
    n = tel = dd_tel = 0
    for p in partik:
        r = egy_parti(p, a.vilag, a.terv, a.mag, tar_fv, print if a.reszletes else None)
        if r is None:
            continue
        n += 1
        tel += r["teljesult"]
        dd_tel += r["dd_teljesul"]
        elso_terv = r["tervek"][0] if r["tervek"] else (0, "-", 0)
        print(f'{r["tabla"].rsplit("#",1)[1]:>4} {r["kontraktus"]:4} cél {r["cel"]:2} DD {r["dd"]:2} '
              f'→ {r["utesek"]:2} {"OK " if r["teljesult"] else "BUK"} | első terv {elso_terv[2]:.2f} '
              f'{elso_terv[1]} ({r["ms"]//1000}s)', flush=True)
        if f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
    print(f"\npartik {n}: teljesült {tel}, DD szerint teljesíthető {dd_tel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
