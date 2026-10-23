"""
Egy kijátszás-döntés VISSZAJÁTSZÁSA a naplóból — mit látott a kibic, mit
gondolt laponként, és miért azt tette.

A naplóban a kérés csak akkor van benne, ha a szolgáltatás ezzel fut:
    KIBIC_ATJARO_NAPLO=/út/kibic-atjaro.jsonl  KIBIC_ATJARO_NAPLO_KERES=1

    python -m kibic.cli.jatekelemzes --naplo kibic-atjaro.jsonl            # a play-döntések listája
    python -m kibic.cli.jatekelemzes --naplo kibic-atjaro.jsonl --sor 17   # egy döntés újra, laponként
    python -m kibic.cli.jatekelemzes --keres keres.json                    # egy kérés fájlból

A jelzésrendszer és a licitrendszer a YAML-ból jön (rendszerek/), nem az
adatbázisból; `--rendszer` felülírja a kérés game.systems-ét.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[3]


def _sorok(ut: str) -> list[dict]:
    ki = []
    with open(ut, encoding="utf-8") as f:
        for i, sor in enumerate(f, 1):
            try:
                d = json.loads(sor)
            except ValueError:
                continue
            d["_sor"] = i
            ki.append(d)
    return ki


def elemez(keres: dict, rendszer: str | None = None, ido_s: float = 20.0,
           mag: int | None = 1) -> str:
    from ..motor import lejatszas as lj
    from ..motor.kartya import jelzesek_rendszerhez_yaml
    allas = lj.allas_keresbol(keres)
    rs = ((keres.get("game") or {}).get("systems") or {})
    from ..domain import vonal
    kod = rendszer or rs.get(vonal(allas.ules)) or "KIBIC_STAND"
    if isinstance(kod, dict):
        kod = kod.get("code") or "KIBIC_STAND"
    jelz = jelzesek_rendszerhez_yaml(kod)
    tar, valoszinu = None, {}
    try:
        from .aranykeszlet import yaml_betolto
        from ..szolgaltatas.atjaro import licit_tudas
        st = keres.get("state") or {}
        tar, valoszinu = licit_tudas({
            "seat": allas.ules, "dealer": st.get("dealer") or allas.ules,
            "vulnerability": (keres.get("game") or {}).get("vulnerability") or "none",
            "auction": (keres.get("history") or {}).get("auction") or [], "system": kod},
            yaml_betolto([str(GYOKER / "rendszerek" / "yaml")]), 15000)
    except Exception as e:                       # noqa: BLE001
        print(f"(kényszertár nélkül: {type(e).__name__}: {e})", file=sys.stderr)
    e = lj.jatek_dontes(allas, jelz, tar, ido_keret_s=ido_s, db=2000, mag=mag,
                        valoszinu=valoszinu)
    k = allas.kontraktus
    sor = [f"{allas.ules} dönt — {k.szint}{k.szin}{k.kontra} {k.felvevo}, "
           f"{len(allas.lejatszott)} lap lement; látható: "
           + ", ".join(f"{u}: {' '.join(str(l) for l in sorted(v, key=lambda l: (l.szin, -l.rang)))}"
                       for u, v in allas.lathato.items()),
           f"jelzésrendszer: {jelz.rendszer.kod if jelz and jelz.rendszer else '—'}; "
           f"kényszertár: {'van' if tar else 'nincs'}",
           f"elemzés: {e.mintak} {'(MIND a lehetséges elosztás)' if e.kimerito else 'minta'}, "
           f"ismeretlen lap: {e.ismeretlen}, JÓ-tűrés: {e.tures:.2f} ütés",
           f"DÖNTÉS: {e.dontes.lap} — {e.dontes.indok}"
           + (f" [{e.dontes.szabaly}]" if e.dontes.szabaly else ""), ""]
    if e.stat:
        sor.append(f"{'lap':<5}{'osztály':<16}{'ütés':>6}{'veszt':>7}{'rosszabb':>10}{'legjobb':>9}")
        for l, s_ in sorted(e.stat.items(), key=lambda x: -x[1].utes):
            sor.append(f"{str(l):<5}{s_.osztaly:<16}{s_.utes:>6.2f}{s_.veszt:>7.2f}"
                       f"{s_.rossz:>9.0%}{s_.legjobb:>9.0%}")
    return "\n".join(sor)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Kijátszás-döntés visszajátszása")
    ap.add_argument("--naplo", help="a KIBIC_ATJARO_NAPLO fájl")
    ap.add_argument("--sor", type=int, help="a napló sorszáma (a lista mutatja)")
    ap.add_argument("--request-id", help="vagy a request_id")
    ap.add_argument("--keres", help="egy kérés JSON-fájlban")
    ap.add_argument("--rendszer", help="licitrendszer (alap: a kérés game.systems-e)")
    ap.add_argument("--ido", type=float, default=20.0, help="időkeret másodpercben (alap 20)")
    a = ap.parse_args(argv)
    if a.keres:
        print(elemez(json.load(open(a.keres, encoding="utf-8")), a.rendszer, a.ido))
        return 0
    if not a.naplo:
        ap.error("--naplo vagy --keres kell")
    sorok = [d for d in _sorok(a.naplo) if d.get("decision") == "play"]
    if a.sor is None and not a.request_id:
        for d in sorok:
            k = (d.get("meta") or {}).get("kibic") or {}
            print(f"{d['_sor']:>5}  {d.get('ts', '')}  {(d.get('action') or {}).get('card', ''):<4}"
                  f"{k.get('situation', 'KENYSZER'):<10} {'kérés: van' if 'request' in d else 'kérés: NINCS'}"
                  f"  {d.get('explanation', '')[:70]}")
        return 0
    d = next((x for x in sorok if x["_sor"] == a.sor or x.get("request_id") == a.request_id), None)
    if d is None:
        print("nincs ilyen sor", file=sys.stderr)
        return 1
    if "request" not in d:
        print("Ebben a sorban nincs benne a kérés: a szolgáltatás fusson "
              "KIBIC_ATJARO_NAPLO_KERES=1-gyel.", file=sys.stderr)
        return 1
    print(f"napló: {d.get('action')} — {d.get('explanation')}")
    print(elemez(d["request"], a.rendszer, a.ido))
    return 0


if __name__ == "__main__":
    sys.exit(main())
