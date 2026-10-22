"""
Parancssori kipróbáló a leosztás-elemzőhöz (DD-tábla + par).

    python -m kibic.cli.ddtabla --pelda > keres.json
    python -m kibic.cli.ddtabla keres.json
    cat keres.json | python -m kibic.cli.ddtabla -

    # A saját par-számítás összevetése az endplay/DDS par-jával
    # véletlen leosztásokon (beliállás és osztó is véletlen):
    python -m kibic.cli.ddtabla --osszevet 200
"""
from __future__ import annotations

import argparse
import json
import random
import sys

from ..szolgaltatas.dd import DdHiba
from ..szolgaltatas.ddtabla import ddtabla_elemzes
from .ddelemzo import PELDA as _DD_PELDA

PELDA = {
    **{k: v for k, v in _DD_PELDA.items() if k != "play"},
    "request_id": "tabla-proba-1",
    "dealer": "N",
    "declarer_tricks": 8,
}

_BELI = ["none", "ns", "ew", "both"]


def _veletlen_kezek(rnd: random.Random) -> dict[str, list[str]]:
    pakli = [s + e for s in "SHDC" for e in "AKQJT98765432"]
    rnd.shuffle(pakli)
    return {u: pakli[i * 13:(i + 1) * 13] for i, u in enumerate("NESW")}


def osszevet(db: int, mag: int) -> int:
    """A saját par pontszáma == az endplay par-ja? Eltéréskor kiírja."""
    from ..solver.dds import par_eredmeny
    from ..szolgaltatas.dd import BELI_TERKEP, _leosztas

    rnd = random.Random(mag)
    elteres = 0
    for n in range(1, db + 1):
        keres = {"hands": _veletlen_kezek(rnd),
                 "vulnerability": rnd.choice(_BELI),
                 "dealer": rnd.choice("NESW")}
        sajat = ddtabla_elemzes(keres)
        leosztas = _leosztas(keres["hands"], [], keres["dealer"],
                             BELI_TERKEP[keres["vulnerability"].upper()])
        ep_pont, ep_leiras = par_eredmeny(leosztas)
        if sajat["par"]["score_ns"] != ep_pont:
            elteres += 1
            print(f"ELTÉRÉS #{n}: saját {sajat['par']['score_ns']} "
                  f"({[c['contract'] + ' ' + c['side'] for c in sajat['par']['contracts']]}), "
                  f"endplay {ep_pont} ({ep_leiras})")
            print("  " + json.dumps(keres, ensure_ascii=False))
    print(f"\n{db} leosztás, {elteres} eltérés")
    return 1 if elteres else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="DD-tábla és par egy leosztásra")
    ap.add_argument("fajl", nargs="?", help="kérés JSON ('-' = stdin)")
    ap.add_argument("--pelda", action="store_true",
                    help="Minta-kérés kiírása (átirányítható fájlba)")
    ap.add_argument("--osszevet", type=int, metavar="N",
                    help="N véletlen leosztáson összeveti a par-t az endplay-jel")
    ap.add_argument("--mag", type=int, default=1, help="véletlenmag (--osszevet)")
    a = ap.parse_args(argv)

    if a.pelda:
        print(json.dumps(PELDA, ensure_ascii=False, indent=2))
        return 0
    if a.osszevet:
        return osszevet(a.osszevet, a.mag)
    if not a.fajl:
        ap.error("Adj meg fájlt, vagy használd a --pelda / --osszevet kapcsolót")

    szoveg = sys.stdin.read() if a.fajl == "-" else open(
        a.fajl, encoding="utf-8").read()
    try:
        valasz = ddtabla_elemzes(json.loads(szoveg))
    except DdHiba as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(valasz, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
