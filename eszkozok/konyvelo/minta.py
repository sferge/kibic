"""
A tervkönyvelő mérése egy szélesebb mintán (2026-11-18): Pavlicek-felvevőpartik az
indulás után; partinként a legjobb terv esélye és a mindent látó (DD) felvevő aránya
ugyanazokon a sorsolt világokon.

    PYTHONPATH=src python3 eszkozok/konyvelo/minta.py tanpartik/Pavlicek_felvevo \
        [--partik 2] [--vilag 30] [--csak-szin]

A szabályok a KIBIC_K_* változókkal kapcsolhatók ki (tervkonyvelo.SZABALY).
"""
from __future__ import annotations

import argparse
import dataclasses
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from kibic.cli.jatekmeres import _pbn_olvas                  # noqa: E402
from kibic.domain import Lap, kovetkezo_ules                   # noqa: E402
from kibic.motor import tervjatszo as tj                       # noqa: E402
from kibic.solver.dds import lap_elemzes                       # noqa: E402
from kibic.szolgaltatas import tervmuhely as tm               # noqa: E402


def keres(j: tj.Jatek, k) -> dict:
    u = j.soron()
    utes = j.aktualis()
    van = [l for l in j.kezek[u] if utes and l.szin == utes[0][1].szin]
    F, A = j.felvevo, j.asztal
    return {"protocol": "mohabridzs-ai/1.0", "request_id": "m", "decision": "play", "deadline_ms": 600000,
            "game": {"match_id": "minta", "table_index": 0, "board_number": 1},
            "actor": {"seat": F, "acting_for_seat": u},
            "state": {"phase": "play", "dealer": "N",
                      "contract": {"level": k.szint, "strain": "NT" if k.szin == "NT" else k.szin,
                                   "multiplier": 1},
                      "declarer": F, "dummy": A,
                      "visible_hands": {x: sorted(str(l) for l in j.kezek[x]) for x in (F, A)}},
            "history": {"auction": [], "play": [{"seat": s, "card": str(l)} for s, l in j.lapok]},
            "legal_actions": {"cards": sorted(str(l) for l in (van or j.kezek[u]))}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("konyvtar")
    ap.add_argument("--partik", type=int, default=2, help="fájlonként ennyi parti")
    ap.add_argument("--vilag", type=int, default=30)
    ap.add_argument("--csak-szin", action="store_true")
    a = ap.parse_args(argv)
    sorok = []
    t0 = time.time()
    for ut in sorted(Path(a.konyvtar).glob("*.pbn")):
        db = 0
        for j0 in _pbn_olvas(str(ut)):
            if db >= a.partik:
                break
            if not j0.leosztas or not j0.kontraktus or not j0.felvevo or not j0.lapok:
                continue
            if a.csak_szin and j0.kontraktus.szin == "NT":
                continue
            db += 1
            F = j0.felvevo
            k = dataclasses.replace(j0.kontraktus, felvevo=F)
            lo = j0.leosztas
            adu = None if k.szin == "NT" else k.szin
            j = tj.Jatek({u: set(lo.kezek[u].lapok) for u in "NESW"}, F, adu,
                         [(kovetkezo_ules(F, 1), Lap.parse(j0.lapok[0]))], tj.Terv(()))
            from kibic.motor.tervszinpolitika import urites
            urites()                              # partik között: a memória
            h = tm.helyzet(keres(j, k))
            rek = tm.tervez(h, lap_elemzes, 9999, vilag_db=a.vilag)
            r = rek.eredmenyek[0]
            sorok.append((ut.name, j0.tabla_szam, f"{k.szint}{k.szin}", r.esely, rek.dd_felso or 0.0, r.terv.nev))
            print(f"{ut.name}#{j0.tabla_szam:<3} {k.szint}{k.szin:<3} terv {100 * r.esely:5.1f}%  DD {100 * (rek.dd_felso or 0):5.1f}%  "
                  f"{r.terv.nev}", flush=True)
    n = len(sorok)
    if n:
        pt = sum(x[3] for x in sorok) / n
        pd = sum(x[4] for x in sorok) / n
        kozel = sum(1 for x in sorok if x[3] >= x[4] - 0.10)
        print(f"\n{n} parti, {time.time() - t0:.0f} s: terv átlag {100 * pt:.1f}%, DD átlag {100 * pd:.1f}%, "
              f"arány {pt / pd if pd else 0:.2f}; a DD-hez 10 ponton belül: {kozel}/{n}")


if __name__ == "__main__":
    main()
