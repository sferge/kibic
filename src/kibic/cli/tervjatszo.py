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


def egy_parti(p, vilag: int, max_terv: int, mag: int, tar_fv=None) -> dict | None:
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
    lejatszott = [(kijatszo, elso)]
    cel = 6 + k.szint
    # DD az indulás után (a mérce)
    dd0 = lap_elemzes(p.leosztas, [str(elso)], k)
    dd_ertek = max(e.felvevo_osszesen for e in dd0)
    # a felvevő szemszöge: a második lap előtt (az asztal lapja)
    keres = pozicio_keres(p, 1)
    allas = lj.allas_keresbol(keres)
    tar = tar_fv(keres) if tar_fv else None
    m = lj.mintavetel(allas, tar, db=vilag, mag=mag)
    vilagok = m.leosztasok
    sulyok = m.sulyok or [1.0] * len(vilagok)
    d = set(p.leosztas.kezek[felvevo].lapok)
    y = set(p.leosztas.kezek[asztal].lapok)

    def kint(sz):
        return [l for l in tj._osszes(sz) if l not in d and l not in y and l != elso]
    tervek = tj.jeloltek(d, y, adu, kint, max_terv)
    ert = tj.ertekel(tervek, vilagok, sulyok, felvevo, k, lejatszott)
    valodi = {u: set(p.leosztas.kezek[u].lapok) for u in "NESW"}
    vedo = tj.vedo_dd(lap_elemzes, p.leosztas, k)
    legjobb = ert[0]
    ut = tj.lejatszik(valodi, felvevo, adu, lejatszott, legjobb.terv, vedo)
    # a jelöltállító lefedése: van-e teljesítő terv a valódi leosztásban
    valodi_ut = {str(e.terv): tj.lejatszik(valodi, felvevo, adu, lejatszott, e.terv, vedo) for e in ert}
    teljesito = [t for t, u in valodi_ut.items() if u >= cel]
    return {"tabla": p.azonosito, "kontraktus": str(k), "cel": cel, "dd": dd_ertek,
            "dd_teljesul": dd_ertek >= cel, "terv": str(legjobb.terv), "esely": round(legjobb.esely, 3),
            "atlag": round(legjobb.atlag, 2), "utesek": ut, "teljesult": ut >= cel,
            "jeloltek": len(tervek), "vilagok": len(vilagok),
            "van_teljesito_jelolt": bool(teljesito), "teljesito_db": len(teljesito),
            "legjobb_valodi": max(valodi_ut.values()),
            "top3": [(str(e.terv), round(e.esely, 2)) for e in ert[:3]],
            "ms": int((time.time() - t0) * 1000)}


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
    n = tel = dd_tel = fed = 0
    for p in partik:
        r = egy_parti(p, a.vilag, a.terv, a.mag, tar_fv)
        if r is None:
            continue
        n += 1
        tel += r["teljesult"]
        dd_tel += r["dd_teljesul"]
        fed += r["van_teljesito_jelolt"] or not r["dd_teljesul"]
        print(f'{r["tabla"].rsplit("#",1)[1]:>4} {r["kontraktus"]:4} cél {r["cel"]:2} DD {r["dd"]:2} '
              f'→ {r["utesek"]:2} {"OK " if r["teljesult"] else "BUK"} esély {r["esely"]:.2f} '
              f'| jelölt {r["jeloltek"]:2}, teljesítő {r["teljesito_db"]:2} | {r["terv"]} '
              f'({r["ms"]//1000}s)', flush=True)
        if f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
    print(f"\npartik {n}: teljesült {tel}, DD szerint teljesíthető {dd_tel}, "
          f"a jelöltek között volt teljesítő (vagy DD-n sem teljesíthető) {fed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
