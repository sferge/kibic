"""
Ütésbesorolás mérése a címkézett partikon (2026-10-25).

Két lapsoron soroljuk be az ütéseket:
  KÖNYV — a könyv lejátszása (a szerző terve), a hiányzó vége DD szerint;
  DD    — csak a valódi indulás, utána mind a négy kéz DD szerint.
A technikákból tervtípus lesz (motor/utesbesorolas.TIPUS_ESEMENY), és ezt vetjük
össze a „Play:” címkékkel — a típusok címke-részszavai a tervtárból jönnek.

    PYTHONPATH=src python -m kibic.cli.utesbesorolas --pbn tanpartik/Pavlicek_felvevo \
        --json ki.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from ..domain import kovetkezo_ules
from ..motor import terv as tv
from ..motor import utesbesorolas as ub
from ..motor.lejatszas_meres import _lap
from .tervfelismeres import _sor, cimkek_pbnbol


def _fajlok(utak):
    for u in utak:
        p = Path(u)
        yield from (sorted(p.glob("*.pbn")) if p.is_dir() else [p])


def merni(utak, tervek, json_ki=None, csak_dd=False) -> str:
    from .jatekmeres import partik_fajlbol
    sorok = tv.tervsorok_yamlbol(tervek)
    cimke_szo = {s.kod: s.cimkek for s in sorok if s.fajta == "TIPUS"}
    modok = ("DD",) if csak_dd else ("KONYV", "DD")
    stat = {m: {t: {"talalat": 0, "kimaradt": 0, "teves": 0} for t in ub.TIPUS_ESEMENY} for m in modok}
    esem_cimkes = {m: Counter() for m in modok}
    esem_ossz = {m: Counter() for m in modok}
    n = 0
    for ut in _fajlok(utak):
        cimkek = cimkek_pbnbol(str(ut))
        for i, p in enumerate(partik_fajlbol([str(ut)], "IMP")):
            c = cimkek[i] if i < len(cimkek) else None
            k = p.kontraktus
            if k is None or not p.lapok:
                continue
            n += 1
            adu = None if k.szin == "NT" else k.szin
            kezek = {u: list(p.leosztas.kezek[u].lapok) for u in "NESW"}
            rekord = {"tabla": p.azonosito, "kontraktus": str(k), "cimkek": c}
            szoveg = "; ".join(c or [])
            for m in modok:
                eleje = p.lapok if m == "KONYV" else p.lapok[:1]
                sor = ub.dd_lapsor(p.leosztas, k, eleje)
                b = ub.besorol(kezek, k.felvevo, adu, [_lap(x) for x in sor])
                tip = ub.tipusok(b)
                rekord[m] = {"tipusok": sorted(tip), "esemenyek": dict(b.fajtak()),
                             "felvevo_utes": b.felvevo_utes}
                if c is None:
                    continue
                for e in b.fajtak():
                    esem_ossz[m][e] += 1
                for t in ub.TIPUS_ESEMENY:
                    cimkes = any(w in szoveg for w in cimke_szo.get(t, []))
                    if cimkes:
                        for e in b.fajtak():
                            if e in ub.TIPUS_ESEMENY[t]:
                                esem_cimkes[m][e] += 1
                    x = stat[m][t]
                    if cimkes and t in tip:
                        x["talalat"] += 1
                    elif cimkes:
                        x["kimaradt"] += 1
                    elif t in tip:
                        x["teves"] += 1
            if json_ki is not None:
                json_ki.write(json.dumps(rekord, ensure_ascii=False) + "\n")
                json_ki.flush()
    ki = [f"partik: {n}"]
    for m in modok:
        ki += ["", f"### {m} lapsor — a típus, ha legalább egy technikája előfordul", "",
               "| típus | címke szerint | felismerte | kimaradt | jelezte, címke nélkül | pontosság | lefedés |",
               "|---|---|---|---|---|---|---|"]
        ki += [_sor(t, x) for t, x in stat[m].items()]
        ki += ["", "| technika | partik (címkézett) | ebből a típusa címkés |", "|---|---|---|"]
        for t, es in ub.TIPUS_ESEMENY.items():
            for e in es:
                ki.append(f"| {t} / {e} | {esem_ossz[m][e]} | {esem_cimkes[m][e]} |")
    return "\n".join(ki)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Ütésbesorolás mérése a címkézett partikon")
    ap.add_argument("--pbn", nargs="+", required=True)
    ap.add_argument("--tervek", nargs="+", default=["rendszerek/tervek"])
    ap.add_argument("--json")
    ap.add_argument("--csak-dd", action="store_true")
    a = ap.parse_args(argv)
    f = open(a.json, "w", encoding="utf-8") if a.json else None
    print(merni(a.pbn, a.tervek, f, a.csak_dd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
