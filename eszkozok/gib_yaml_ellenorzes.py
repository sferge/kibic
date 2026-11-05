#!/usr/bin/env python3
"""
A YAML-ból épített GIB rendszer mérése a ROBOT SAJÁT LICITJEI ellen.

    source .env
    PYTHONPATH=src python eszkozok/gib_yaml_ellenorzes.py [--rendszer GIB] [--csak-nyitas]

A régi `gib_ellenorzes.py` (a `gib.lr` nyitásaira) utóda. A gyűjtemény
gépi magyarázatú (GIB-generált, alertelt) licitjeinél megkérdezi a kibicet:
ugyanebben a helyzetben, ezzel a kézzel, a `GIB` rendszerrel mit licitálna?

    * EGYEZIK / ELTÉR — licitenként és a menet eleje szerint csoportosítva;
    * az eltéréseknél a robot magyarázata mellett a kibic magyarázata;
    * (A) a robot állítása (hossz, HCP, total points) teljesül-e a kézen —
      a pontsávot a TOTAL_POINTS és az AP_321 szerint is nézzük, így
      kiderül, melyik a GIB valódi „total points”-ja.

A GIB determinisztikus: minden eltérés a mi fordításunk hibája (vagy a
robot olyan döntése, amit a leírás nem ír le) — a lista a következő
javítások forrása. A rendszer a YAML-ból jön (adatbázis csak az adatokhoz).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gib_ellenorzes import TP_RE, allitas, allitas_teljesul, gepi  # noqa: E402


def _kanon(L: str) -> str:
    L = (L or "").upper().replace("PASS", "P").replace("DBL", "X").replace("RDBL", "XX")
    if L.endswith("N") and not L.endswith("NT"):
        L += "T"
    return L


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A YAML GIB rendszer mérése")
    ap.add_argument("--rendszer", default="GIB")
    ap.add_argument("--yaml", default="rendszerek/yaml")
    ap.add_argument("--csak-nyitas", action="store_true")
    ap.add_argument("--max", type=int, default=0, help="legfeljebb ennyi licit (0 = mind)")
    ap.add_argument("--peldak", type=int, default=40)
    ap.add_argument("--json", default=None, help="az eltérések JSON-ba")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)

    import pymysql
    from kibic.domain import ERTEKELOK, Leosztas, ULESEK
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.kriterium import Parametertar
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    from kibic.szolgaltatas.licit import licit_elemzes

    g = betolt([Path(a.yaml)])
    f, _ = feloldas_forrasokbol(g, a.rendszer)
    pt = Parametertar(rendszer_ertek=dict(g[a.rendszer].parameterek))
    forras = lambda k, p, t=None: (f.sorok, pt)            # noqa: E731

    conn = pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4")
    cur = conn.cursor()
    cur.execute("SELECT j.id, j.licit, l.kezek_pbn, l.oszto, l.beliallas"
                "  FROM jatszma j JOIN leosztas l ON l.id=j.leosztas_id"
                " WHERE j.licit IS NOT NULL")

    db = egyezik = 0
    hazug: Counter = Counter()
    csoport: dict[str, Counter] = defaultdict(Counter)
    tevesztes: Counter = Counter()
    peldak: list[dict] = []
    for jid, licit_j, kezek_pbn, oszto, beli in cur.fetchall():
        try:
            licitek = json.loads(licit_j)
            leosztas = Leosztas.pbn_bol(kezek_pbn, oszto, beli)
        except Exception:                                       # noqa: BLE001
            continue
        menet: list[str] = []
        for b in licitek:
            L = _kanon(b.get("licit"))
            mag = b.get("magyarazat") or ""
            ules = b.get("ules")
            nyitas = all(x == "P" for x in menet)
            if (b.get("alert") and gepi(mag) and ules in ULESEK
                    and (nyitas or not a.csak_nyitas)):
                kez = leosztas.kezek[ules]
                db += 1
                # (A) a robot állítása — két total-point definícióval
                all_ = allitas(mag)
                for kod in ("TOTAL_POINTS", "AP_321"):
                    if TP_RE.search(mag.lower()) and allitas_teljesul(
                            {k: v for k, v in all_.items() if k == "tp"}, kez,
                            {**ERTEKELOK, "AP_321": ERTEKELOK.get(kod) or ERTEKELOK["AP_321"]}):
                        hazug[kod] += 1
                # (B) mit licitálna a kibic?
                try:
                    v = licit_elemzes({"hand": [sz + e for sz, lap in zip("SHDC", kez.pbn().split(".")) for e in lap], "seat": ules, "dealer": oszto,
                                       "vulnerability": (beli or "none").lower(),
                                       "auction": list(menet), "system": a.rendszer,
                                       "test_mode": True}, forras)
                    mienk = _kanon(v.get("call"))
                    expl = v.get("explanation", "")
                except Exception as e:                          # noqa: BLE001
                    mienk, expl = "HIBA", str(e)[:80]
                elo = " ".join(menet[:3]) or "(nyitás)"
                if mienk == L:
                    egyezik += 1
                    csoport[elo]["egyezik"] += 1
                else:
                    csoport[elo]["elter"] += 1
                    tevesztes[f"{' '.join(menet) or '-'}: {L} -> {mienk}"] += 1
                    if len(peldak) < a.peldak:
                        peldak.append({"jatszma": jid, "menet": " ".join(menet), "gib": L,
                                       "kibic": mienk, "kez": kez.pbn(),
                                       "gib_magyarazat": mag[:120], "kibic_magyarazat": expl[:120]})
                if a.max and db >= a.max:
                    break
            menet.append(L)
        if a.max and db >= a.max:
            break

    print("=" * 72)
    print(f"  Gépi magyarázatú GIB-licit: {db}   egyezik: {egyezik}"
          f"  ({100 * egyezik / db if db else 0:.1f}%)")
    print("  A robot pontállítása NEM teljesül (total points definíciónként):")
    for kod in ("TOTAL_POINTS", "AP_321"):
        print(f"      {kod:13} {hazug[kod]}")
    print("-" * 72)
    print("  A menet eleje szerint (egyezik / eltér):")
    for elo, c in sorted(csoport.items(), key=lambda x: -sum(x[1].values()))[:30]:
        print(f"      {elo:24} {c['egyezik']:4} / {c['elter']:4}")
    print("-" * 72)
    print("  A leggyakoribb eltérések:")
    for t, n in tevesztes.most_common(25):
        print(f"      {n:4}  {t}")
    print("-" * 72)
    for p in peldak[:a.peldak]:
        print(f"  #{p['jatszma']} [{p['menet'] or '-'}] GIB {p['gib']} / kibic {p['kibic']}  {p['kez']}")
        print(f"      GIB:   {p['gib_magyarazat']}")
        print(f"      kibic: {p['kibic_magyarazat']}")
    if a.json:
        Path(a.json).write_text(json.dumps(peldak, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
