"""
A tervtár felismerésének mérése (2026-10-25): a kibic a Pavlicek-partikat (vagy
bármely PBN-t, amelynek „Play:” címkéi vannak) a tervsorok szerint felcímkézi,
és típusonként összeveti a szerző címkéivel.

    PYTHONPATH=src python -m kibic.cli.tervfelismeres --pbn <fájl> [--tervek rendszerek/tervek]
        [--reszletes] [--json ki.jsonl]

Típusonként: hány partinál ismerte fel (találat), hánynál nem (kimaradt), és
hánynál jelezte, bár a szerző nem (téves). Csak a címkézett partik számítanak.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ..motor import terv as tv

GYOKER = Path(__file__).resolve().parents[3]


def cimkek_pbnbol(ut: str) -> list[list[str] | None]:
    """A „Play:” címkék játszmánként (a fájl sorrendjében; None: nincs címke)."""
    szoveg = Path(ut).read_text(encoding="utf-8", errors="replace")
    blokkok = [b for b in re.split(r"\n(?=\[Event )", szoveg) if b.lstrip().startswith("[Event")]
    ki = []
    for b in blokkok:
        m = re.search(r"^Play: (.*)$", b, re.M)
        ki.append([t.strip() for t in m.group(1).split(";")] if m else None)
    return ki


def _sor(t, x) -> str:
    cim = x["talalat"] + x["kimaradt"]
    jelez = x["talalat"] + x["teves"]
    pont = f"{100 * x['talalat'] / jelez:.0f}%" if jelez else "–"
    lef = f"{100 * x['talalat'] / cim:.0f}%" if cim else "–"
    return f"| {t} | {cim} | {x['talalat']} | {x['kimaradt']} | {x['teves']} | {pont} | {lef} |"


def merni(utak: list[str], tervek: list[str], reszletes: bool = False, json_ki=None) -> str:
    from .jatekmeres import partik_fajlbol
    sorok = tv.tervsorok_yamlbol(tervek)
    tipusok = {s.kod: s for s in sorok if s.fajta == "TIPUS"}
    stat = {t: {"talalat": 0, "kimaradt": 0, "teves": 0} for t in tipusok}
    stat2 = {t: {"talalat": 0, "kimaradt": 0, "teves": 0} for t in tipusok}
    nem_eleg = 0
    n = cimkezett = 0
    for ut in utak:
        cimkek = cimkek_pbnbol(ut)
        for i, p in enumerate(partik_fajlbol([ut], "IMP")):
            c = cimkek[i] if i < len(cimkek) else None
            h = tv.helyzet_partibol(p)
            if h is None:
                continue
            n += 1
            fel = tv.felismeres(sorok, h)
            el = tv.elegendo(sorok, h, fel)
            # az elegendő terv: a forrás-típusok az elegendő kombinációkból, a kísérő
            # szempontok (potenciál nélküli típusok) a felismerésből
            el_tip = {t for komb in el["elegendo"] for t in komb} | {
                t for t in fel if tipusok[t].potencial is None}
            if not el["eleg"]:
                nem_eleg += 1
            if json_ki is not None:
                json_ki.write(json.dumps({"tabla": p.azonosito, "kontraktus": str(p.kontraktus),
                                          "cimkek": c, "felismert": fel, "elegendo": el},
                                         ensure_ascii=False) + "\n")
            if c is None:
                continue
            cimkezett += 1
            szoveg = "; ".join(c)
            for t, s in tipusok.items():
                van = any(k in szoveg for k in s.cimkek)
                for st, ismert in ((stat, t in fel), (stat2, t in el_tip)):
                    if van and ismert:
                        st[t]["talalat"] += 1
                    elif van:
                        st[t]["kimaradt"] += 1
                    elif ismert:
                        st[t]["teves"] += 1
    sor = [f"partik: {n} · címkézett: {cimkezett} · ahol a típusok elvi ütései együtt sem elegendők: {nem_eleg}"]
    for cim_, st in (("LEHETSÉGES (a feltételek igazak)", stat),
                     ("ELVILEG ELEGENDŐ (a legkisebb elegendő típus / kombináció)", stat2)):
        sor += ["", f"### {cim_}", "",
                "| típus | címke szerint | felismerte | kimaradt | jelezte, címke nélkül | pontosság | lefedés |",
                "|---|---|---|---|---|---|---|"]
        o = {"talalat": 0, "kimaradt": 0, "teves": 0}
        for t, x in st.items():
            for kk in o:
                o[kk] += x[kk]
            sor.append(_sor(t, x))
        sor.append(_sor("**összesen**", o))
    sor += ["", "pontosság: a kibic jelzéseiből hány esik egybe a címkével; lefedés: a szerző címkéiből hányat ismert fel."]
    return "\n".join(sor)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A tervtár felismerésének mérése a címkézett partikon")
    ap.add_argument("--pbn", nargs="+", required=True)
    ap.add_argument("--tervek", nargs="+", default=[str(GYOKER / "rendszerek" / "tervek")])
    ap.add_argument("--json", help="partinként a címkék és a felismert típusok")
    ap.add_argument("--reszletes", action="store_true")
    a = ap.parse_args(argv)
    from .jatekmeres import fajlok_kibontasa
    utak = fajlok_kibontasa(a.pbn, ".pbn")
    ki = open(a.json, "w", encoding="utf-8") if a.json else None
    try:
        print(merni(utak, a.tervek, a.reszletes, ki))
    finally:
        if ki:
            ki.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
