"""
Parancssori kipróbáló a DD-elemzőhöz.

    python -m kibic.cli.ddelemzo keres.json
    cat keres.json | python -m kibic.cli.ddelemzo -
    python -m kibic.cli.ddelemzo --pelda            # minta-kérés kiírása
"""
from __future__ import annotations

import argparse
import json
import sys

from ..szolgaltatas.dd import DdHiba, dd_elemzes

PELDA = {
    "request_id": "proba-1",
    "hands": {
        "N": ["SJ", "S3", "H9", "DA", "DQ", "DT", "D8",
              "CA", "CQ", "CJ", "C7", "C6", "C3"],
        "E": ["SA", "ST", "S6", "HA", "H7", "H5", "H4", "D4", "D2",
              "CK", "CT", "C8", "C5"],
        "S": ["SK", "S8", "S7", "S2", "HQ", "HJ", "H8", "H3",
              "DJ", "D7", "D3", "C9", "C2"],
        "W": ["SQ", "S9", "S5", "S4", "HK", "HT", "H6", "H2",
              "DK", "D9", "D6", "D5", "C4"],
    },
    "contract": {"level": 3, "strain": "C", "multiplier": 2},
    "declarer": "N",
    "vulnerability": "none",
    "play": [
        {"seat": "E", "card": "D4"}, {"seat": "S", "card": "DJ"},
        {"seat": "W", "card": "DK"}, {"seat": "N", "card": "DA"},
    ],
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="DD állás-elemző")
    ap.add_argument("fajl", nargs="?", help="kérés JSON ('-' = stdin)")
    ap.add_argument("--pelda", action="store_true",
                    help="Minta-kérés kiírása (átirányítható fájlba)")
    a = ap.parse_args(argv)

    if a.pelda:
        print(json.dumps(PELDA, ensure_ascii=False, indent=2))
        return 0
    if not a.fajl:
        ap.error("Adj meg fájlt, vagy használd a --pelda kapcsolót")

    szoveg = sys.stdin.read() if a.fajl == "-" else open(
        a.fajl, encoding="utf-8").read()
    try:
        valasz = dd_elemzes(json.loads(szoveg))
    except DdHiba as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(valasz, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
