"""
Az indulások kimutatása (2026-10-24): ahol a kibic rosszul indult, minden
lehetséges induló lapra

  * a kibic BECSLÉSE az indulás pillanatában (a mintákból: átlagos védőütés,
    hány %-ban buktat, az IMP-veszteség a minta legjobb lapjához képest), és
  * a VALÓDI osztás DD-eredménye (védőütés, buktat-e, IMP-veszteség),

valamint a leosztás JELLEGE — hány induló lap buktat:

  NEM_BUKTATHATO (egy sem), AKTIV (legfeljebb harmaduk: meg kell találni),
  VEGYES, PASSZIV (több mint kétharmaduk: csak ne adjunk ütést), MINDIG
  (mind buktat: közömbös) — a mintákban (a kibic képe) és a valóságban.

    python -m kibic.cli.inditaselemzes --json pav_ind.jsonl --pbn "tanpartik/Pavlicek(rfp)/" \\
        --mag 1 --parhuzamos 16 --html inditasok.html

A `--json` a jatekmeres kimenete (`--oldal vedo --max-dontes 1` elég). Alapból
csak azok az indulások, ahol a kibic IMP-t vesztett a valódi osztáson
(`--mind`: mind; `--rosszabb`: csak ahol az ember jobban indult).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from collections import Counter, defaultdict

from .jatekmeres import GYOKER, fajlok_kibontasa, partik_fajlbol

OSZTALYOK = ("NEM_BUKTATHATO", "AKTIV", "VEGYES", "PASSZIV", "MINDIG")
OSZTALY_NEV = {"NEM_BUKTATHATO": "nem buktatható", "AKTIV": "aktív (kevés lap buktat)",
               "VEGYES": "vegyes", "PASSZIV": "passzív (kevés lap ad ütést)",
               "MINDIG": "mindig bukik"}


def osztaly(arany: float) -> str:
    """A buktató induló lapok aránya -> a leosztás jellege."""
    if arany <= 0:
        return "NEM_BUKTATHATO"
    if arany >= 1:
        return "MINDIG"
    if arany <= 1 / 3:
        return "AKTIV"
    if arany <= 2 / 3:
        return "VEGYES"
    return "PASSZIV"


def _vedo_pont(k, felvevo_utes: int, beli: str) -> int:
    from ..domain.pontozas import pontszam
    return -pontszam(k, felvevo_utes, beli or "NONE")


def inditas_elemzes(p, jelz, betolto, minta: int = 200, mag: int | None = 1,
                    kovetkeztetes_ms: int = 300_000, rendszer: str = "KIBIC_STAND",
                    dd_fv=None, hangolas: tuple = ()) -> dict:
    """Egy leosztás indulása: a kibic mintái és a valódi osztás DD-je, laponként."""
    from ..domain.pontozas import imp
    from ..motor import lejatszas as lj
    from ..motor import lejatszas_meres as lm
    from ..szolgaltatas.atjaro import licit_tudas
    if dd_fv is None:
        from ..solver.dds import lap_elemzes as dd_fv
    k = p.kontraktus
    beli = p.leosztas.beliallas
    cel = 6 + k.szint
    keres = lm.pozicio_keres(p, 0, rendszer)
    allas = lj.allas_keresbol(keres)
    st = keres.get("state") or {}
    try:
        tar, valoszinu = licit_tudas({
            "seat": allas.ules, "dealer": st.get("dealer") or allas.ules,
            "vulnerability": (keres.get("game") or {}).get("vulnerability") or "none",
            "auction": (keres.get("history") or {}).get("auction") or [], "system": rendszer},
            betolto, kovetkeztetes_ms)
    except Exception:                               # noqa: BLE001
        tar, valoszinu = None, {}
    rejtett = [u for u in "NESW" if u not in allas.lathato]
    kov = lj.kovetkeztetes_beallitas(allas, jelz, rejtett, valoszinu)
    m = lj.mintavetel(allas, tar, db=minta, mag=mag, max_proba=max(4000, 30 * minta),
                      kovetkeztetes=kov)
    sulyok = m.sulyok or [1.0] * len(m.leosztasok)
    hiheto = lj.felvetel_hiheto(allas, kov)
    lapok = [str(l) for l in allas.legalis]
    # hangolás: a FELVETEL_HIHETO több súlyával egyszerre (ugyanazokon a mintákon)
    hiheto_el = allas.vedo and not k.kontra and lj.gem_vagy_szlem(k)
    hang = {v: {"W": 0.0, "buk": dict.fromkeys(lapok, 0.0), "imp": dict.fromkeys(lapok, 0.0),
                "barmely": 0.0} for v in hangolas}
    gy = {l: [0.0, 0.0, 0.0] for l in lapok}        # védőütés, buktat, IMP-veszteség (súlyozva)
    W = 0.0
    jelleg_m = Counter()
    arany_ossz = 0.0
    for lo, w in zip(m.leosztasok, sulyok):
        dd = lm._dd_szotar(dd_fv, lo, [], k)
        if not dd or any(l not in dd for l in lapok):
            continue
        w0 = w
        if hiheto is not None:                      # ugyanaz a súlyozás, mint a döntésben
            w = w * lj.hiheto_suly(list(dd.values()), cel, hiheto)
        pont = {l: _vedo_pont(k, dd[l].felvevo_osszesen, beli) for l in lapok}
        legjobb = max(pont.values())
        for v, h in hang.items():
            wv = w0 * (lj.hiheto_suly(list(dd.values()), cel, v) if hiheto_el else 1.0)
            h["W"] += wv
            h["barmely"] += wv * any(dd[l].felvevo_osszesen < cel for l in lapok)
            for l in lapok:
                h["buk"][l] += wv * (dd[l].felvevo_osszesen < cel)
                h["imp"][l] += wv * imp(legjobb - pont[l])
        buktat = 0
        for l in lapok:
            felv = dd[l].felvevo_osszesen
            gy[l][0] += w * (13 - felv)
            gy[l][1] += w * (felv < cel)
            gy[l][2] += w * imp(legjobb - pont[l])
            buktat += felv < cel
        W += w
        a = buktat / len(lapok)
        arany_ossz += w * a
        jelleg_m[osztaly(a)] += w
    valodi = lm._dd_szotar(dd_fv, p.leosztas, [], k)
    v_pont = {l: _vedo_pont(k, valodi[l].felvevo_osszesen, beli) for l in lapok if l in valodi}
    v_legjobb = max(v_pont.values()) if v_pont else 0
    sorok = []
    for l in lapok:
        s = gy[l]
        sorok.append({
            "lap": l,
            "minta": {"vedo_utes": round(s[0] / W, 2), "buktat": round(s[1] / W, 3),
                      "imp": round(s[2] / W, 2)} if W else None,
            "valodi": {"vedo_utes": 13 - valodi[l].felvevo_osszesen,
                       "buktat": valodi[l].felvevo_osszesen < cel,
                       "imp": imp(v_legjobb - v_pont[l])} if l in valodi else None})
    v_buktat = [r for r in sorok if r["valodi"] and r["valodi"]["buktat"]]
    v_arany = len(v_buktat) / len(sorok) if sorok else 0.0
    kez = {sz: "".join(x.ertek for x in sorted((l for l in allas.lathato[allas.ules] if l.szin == sz),
                                                key=lambda l: -l.rang)) for sz in "SHDC"}
    return {
        "tabla": p.azonosito, "kontraktus": str(k), "felvevo": k.felvevo, "indito": allas.ules,
        "beliallas": beli, "licit": " ".join(f"{x.get('ules')}:{x.get('licit')}" for x in p.licit),
        "kez": kez, "lapok": sorok, "minta_db": len(m.leosztasok), "lazitott": m.lazitott,
        "hangolas": {str(v): {"barmely": round(h["barmely"] / h["W"], 3),
                              "buktat": {l: round(x / h["W"], 3) for l, x in h["buk"].items()},
                              "imp": {l: round(x / h["W"], 2) for l, x in h["imp"].items()}}
                     for v, h in hang.items() if h["W"]},
        "jelleg_minta": {"arany": round(arany_ossz / W, 3) if W else None,
                         "osztaly": osztaly(arany_ossz / W) if W else None,
                         "eloszlas": {o: round(jelleg_m[o] / W, 3) for o in OSZTALYOK} if W else {}},
        "jelleg_valodi": {"arany": round(v_arany, 3), "osztaly": osztaly(v_arany),
                          "buktato_szinek": sorted({r["lap"][0] for r in v_buktat})},
    }


# --- párhuzamos futtatás --------------------------------------------------------

_M: dict = {}


def _init(mappak, rendszer, minta, mag, kov_ms, hangolas=()):
    from ..motor.kartya import jelzesek_rendszerhez_yaml
    from .aranykeszlet import yaml_betolto
    _M.update(partik={p.azonosito: p for p in partik_fajlbol(fajlok_kibontasa(mappak, ".pbn"), "IMP")},
              jelz=jelzesek_rendszerhez_yaml(rendszer),
              betolto=yaml_betolto([str(GYOKER / "rendszerek" / "yaml")]),
              rendszer=rendszer, minta=minta, mag=mag, kov_ms=kov_ms, hangolas=tuple(hangolas))


def _egy(meres: dict) -> dict | None:
    p = _M["partik"].get(meres["tabla"])
    if p is None:
        return None
    e = inditas_elemzes(p, _M["jelz"], _M["betolto"], _M["minta"], _M["mag"], _M["kov_ms"],
                        _M["rendszer"], hangolas=_M["hangolas"])
    e.update(kibic_lap=meres["lap"], ember_lap=meres.get("emberi_lap"), szabaly=meres.get("szabaly"))
    return e


# --- jelentés -----------------------------------------------------------------

def _valodi_imp(e: dict, lap: str | None) -> int | None:
    r = next((x for x in e["lapok"] if x["lap"] == lap), None)
    return r["valodi"]["imp"] if r and r["valodi"] else None


BIZTOSSAG = (("azonos lap", 0, 0), ("az emberét látta jobbnak", -99, 0),
             ("0–0,25 IMP", 0, 0.25), ("0,25–0,5 IMP", 0.25, 0.5),
             ("0,5–1 IMP", 0.5, 1), ("1 IMP fölött", 1, 99))
KALIBRACIO = (("0–10%", 0, .1), ("10–30%", .1, .3), ("30–50%", .3, .5),
              ("50–70%", .5, .7), ("70–100%", .7, 1.01))


def vallalas_tipus(kontraktus: str) -> str:
    """'4SX' -> 'szín gém, kontrázva'."""
    from ..domain.pontozas import Kontraktus
    from ..motor.lejatszas import gem_vagy_szlem
    k = Kontraktus.parse(kontraktus)
    if k is None:
        return "?"
    szint = "szlem" if k.szint >= 6 else ("gém" if gem_vagy_szlem(k) else "részszerződés")
    return f"{'szan' if k.szin == 'NT' else 'szín'} {szint}" + (", kontrázva" if k.kontra else "")


def osszegzes(elemzesek: list[dict]) -> dict:
    """A valódi jelleg szerint: darab, a kibic és az ember IMP-vesztesége; és a
    mintákból becsült jelleg a valódihoz képest (keveredési tábla)."""
    szerint = defaultdict(lambda: {"db": 0, "kibic_imp": 0, "ember_imp": 0})
    kever = defaultdict(Counter)
    for e in elemzesek:
        o = e["jelleg_valodi"]["osztaly"]
        szerint[o]["db"] += 1
        szerint[o]["kibic_imp"] += _valodi_imp(e, e["kibic_lap"]) or 0
        szerint[o]["ember_imp"] += _valodi_imp(e, e["ember_lap"]) or 0
        kever[e["jelleg_minta"]["osztaly"]][o] += 1
    # a döntés biztossága: a kibic a SAJÁT becslése szerint mennyivel látta jobbnak
    # a lapját az emberénél (minta-IMP), és mi lett belőle a valóságban
    biztos = {nev: {"db": 0, "kibic_imp": 0, "ember_imp": 0} for nev, _, _ in BIZTOSSAG}
    # kalibráció: a kibic becsülte esély a buktatásra és a valóság
    kal = {nev: {"db": 0, "becsult": 0.0, "kibic_lapja": 0, "becsult_barmely": 0.0, "barmely": 0}
           for nev, _, _ in KALIBRACIO}
    tipus: dict = defaultdict(lambda: {"db": 0, "becsult": 0.0, "kibic_lapja": 0,
                                       "becsult_barmely": 0.0, "barmely": 0})
    for e in elemzesek:
        kl = next((r for r in e["lapok"] if r["lap"] == e["kibic_lap"]), None)
        el = next((r for r in e["lapok"] if r["lap"] == e["ember_lap"]), None)
        if kl and kl["minta"] and kl["valodi"]:
            t = tipus[vallalas_tipus(e["kontraktus"])]
            t["db"] += 1
            t["becsult"] += kl["minta"]["buktat"]
            t["kibic_lapja"] += bool(kl["valodi"]["buktat"])
            t["becsult_barmely"] += 1 - (e["jelleg_minta"].get("eloszlas") or {}).get("NEM_BUKTATHATO", 0)
            t["barmely"] += e["jelleg_valodi"]["osztaly"] != "NEM_BUKTATHATO"
        if kl and el and kl["minta"] and el["minta"]:
            if kl["lap"] == el["lap"]:
                nev = "azonos lap"
            else:
                d = el["minta"]["imp"] - kl["minta"]["imp"]
                nev = next(n for n, lo, hi in BIZTOSSAG if n != "azonos lap" and lo <= d < hi)
            biztos[nev]["db"] += 1
            biztos[nev]["kibic_imp"] += kl["valodi"]["imp"] if kl["valodi"] else 0
            biztos[nev]["ember_imp"] += el["valodi"]["imp"] if el["valodi"] else 0
        if kl and kl["minta"] and kl["valodi"]:
            b = kl["minta"]["buktat"]
            nev = next(n for n, lo, hi in KALIBRACIO if lo <= b < hi)
            k = kal[nev]
            k["db"] += 1
            k["becsult"] += b
            k["kibic_lapja"] += bool(kl["valodi"]["buktat"])
            k["becsult_barmely"] += 1 - (e["jelleg_minta"].get("eloszlas") or {}).get("NEM_BUKTATHATO", 0)
            k["barmely"] += e["jelleg_valodi"]["osztaly"] != "NEM_BUKTATHATO"
    hang: dict = {}
    for e in elemzesek:
        if not e.get("hangolas"):
            continue
        csoport = "gém/szlem, kontrázatlan" if (vallalas_tipus(e["kontraktus"]).split(" ")[1] in ("gém", "szlem")
                                               and "kontrázva" not in vallalas_tipus(e["kontraktus"])) else "egyéb"
        valodi = {r["lap"]: r["valodi"] for r in e["lapok"] if r["valodi"]}
        for v, h in e["hangolas"].items():
            x = hang.setdefault((csoport, v), {"db": 0, "kibic_varhato": 0.0, "kibic_valoban": 0,
                                               "barmely_varhato": 0.0, "barmely_valoban": 0,
                                               "legjobb_imp": 0, "kibic_imp": 0, "ember_imp": 0})
            x["db"] += 1
            x["kibic_varhato"] += h["buktat"].get(e["kibic_lap"], 0)
            x["kibic_valoban"] += bool(valodi.get(e["kibic_lap"], {}).get("buktat"))
            x["barmely_varhato"] += h["barmely"]
            x["barmely_valoban"] += e["jelleg_valodi"]["osztaly"] != "NEM_BUKTATHATO"
            best = min(h["imp"], key=lambda l: h["imp"][l])
            x["legjobb_imp"] += valodi.get(best, {}).get("imp", 0)
            x["kibic_imp"] += valodi.get(e["kibic_lap"], {}).get("imp", 0)
            x["ember_imp"] += valodi.get(e["ember_lap"], {}).get("imp", 0) if e["ember_lap"] else 0
    return {"hangolas": {f"{c} | súly {v}": {kk: (round(vv, 1) if isinstance(vv, float) else vv)
                                              for kk, vv in x.items()}
                         for (c, v), x in sorted(hang.items())},
            "jelleg_szerint": {o: szerint[o] for o in OSZTALYOK if o in szerint},
            "becsult_vs_valodi": {b: dict(v) for b, v in kever.items()},
            "biztossag": {n: v for n, v in biztos.items() if v["db"]},
            "kalibracio": {n: {**v, "becsult": round(v["becsult"], 1),
                               "becsult_barmely": round(v["becsult_barmely"], 1)}
                           for n, v in kal.items() if v["db"]},
            "kalibracio_tipus": {n: {**v, "becsult": round(v["becsult"], 1),
                                     "becsult_barmely": round(v["becsult_barmely"], 1)}
                                 for n, v in sorted(tipus.items(), key=lambda kv: -kv[1]["db"])}}


_SZIN = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
_ERTEK = {"A": "Á", "Q": "D", "J": "B", "T": "10"}


def _szep(lap: str) -> str:
    return _SZIN[lap[0]] + _ERTEK.get(lap[1], lap[1])


def html_jelentes(elemzesek: list[dict], cim: str = "Indulások kimutatása") -> str:
    o = osszegzes(elemzesek)
    e_ = html.escape
    ki = [f"""<!doctype html><html lang="hu"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e_(cim)}</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--ln:#e3e0d8;--hi:#fff3c4;--jo:#1f7a4d;--rossz:#b3261e;--kb:#2a5bd7}}
@media (prefers-color-scheme:dark){{:root{{--bg:#1a1a18;--fg:#ecebe6;--mut:#a3a19a;--ln:#3a3935;--hi:#4a4220;--jo:#5cc08f;--rossz:#f08a80;--kb:#8fb0ff}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;margin:0;padding:16px;max-width:1100px}}
h1{{font-size:22px}} h2{{font-size:17px;margin-top:28px}} table{{border-collapse:collapse;margin:8px 0}}
td,th{{border-bottom:1px solid var(--ln);padding:3px 8px;text-align:right}} th{{color:var(--mut);font-weight:600}}
td:first-child,th:first-child{{text-align:left}} details{{border-top:1px solid var(--ln);padding:6px 0}}
summary{{cursor:pointer}} .mut{{color:var(--mut)}} .jo{{color:var(--jo)}} .rossz{{color:var(--rossz)}}
tr.kb td{{background:var(--hi)}} .tag{{font-size:12px;padding:1px 6px;border-radius:8px;border:1px solid var(--ln)}}
.wrap{{overflow-x:auto}}
</style></head><body><h1>{e_(cim)}</h1>
<p class="mut">{len(elemzesek)} indulás. A „minta” oszlopok a kibic becslése az indulás pillanatában
(átlagos védőütés, hány %-ban buktat, IMP-veszteség a minta legjobb lapjához képest); a „valódi”
oszlopok a valódi osztás DD-eredménye. A jelleg: hány induló lap buktat.</p>
<h2>A valódi jelleg szerint</h2><div class="wrap"><table><tr><th>jelleg</th><th>indulás</th>
<th>kibic IMP</th><th>ember IMP</th></tr>"""]
    for osz, b in o["jelleg_szerint"].items():
        ki.append(f"<tr><td>{OSZTALY_NEV[osz]}</td><td>{b['db']}</td><td>{b['kibic_imp']}</td>"
                  f"<td>{b['ember_imp']}</td></tr>")
    ki.append("</table></div><h2>A kibic becsült jellege (sor) a valódihoz (oszlop) képest</h2>"
              "<div class='wrap'><table><tr><th></th>"
              + "".join(f"<th>{OSZTALY_NEV[x].split(' (')[0]}</th>" for x in OSZTALYOK) + "</tr>")
    for b in OSZTALYOK:
        if b in o["becsult_vs_valodi"]:
            ki.append(f"<tr><td>{OSZTALY_NEV[b].split(' (')[0]}</td>" + "".join(
                f"<td>{o['becsult_vs_valodi'][b].get(v, '') or ''}</td>" for v in OSZTALYOK) + "</tr>")
    ki.append("</table></div><h2>A döntés biztossága</h2><p class='mut'>A kibic a saját becslése "
              "szerint mennyivel látta jobbnak a lapját az emberénél, és mi lett belőle (valódi IMP).</p>"
              "<div class='wrap'><table><tr><th>a kibic előnye a mintákban</th><th>indulás</th>"
              "<th>kibic IMP</th><th>ember IMP</th></tr>")
    for n, v in o["biztossag"].items():
        ki.append(f"<tr><td>{n}</td><td>{v['db']}</td><td>{v['kibic_imp']}</td><td>{v['ember_imp']}</td></tr>")
    ki.append("</table></div><h2>Kalibráció: a buktatás becsült esélye és a valóság</h2>"
              "<div class='wrap'><table><tr><th>a kibic lapja buktat (becslés)</th><th>indulás</th>"
              "<th>várható buktatás</th><th>valóban buktatott</th><th>várható: bármelyik lap</th>"
              "<th>valóban bármelyik</th></tr>")
    for n, v in o["kalibracio"].items():
        ki.append(f"<tr><td>{n}</td><td>{v['db']}</td><td>{v['becsult']}</td><td>{v['kibic_lapja']}</td>"
                  f"<td>{v['becsult_barmely']}</td><td>{v['barmely']}</td></tr>")
    if o["hangolas"]:
        ki.append("</table></div><h2>Hangolás: a FELVETEL_HIHETO súlya</h2><div class='wrap'><table><tr>"
                  "<th>csoport | súly</th><th>indulás</th><th>a kibic lapja buktat: várható</th>"
                  "<th>valóban</th><th>bármelyik: várható</th><th>valóban</th>"
                  "<th>IMP: a minta legjobbja</th><th>kibic</th><th>ember</th></tr>")
        for n, v in o["hangolas"].items():
            ki.append(f"<tr><td>{n}</td><td>{v['db']}</td><td>{v['kibic_varhato']}</td>"
                      f"<td>{v['kibic_valoban']}</td><td>{v['barmely_varhato']}</td>"
                      f"<td>{v['barmely_valoban']}</td><td>{v['legjobb_imp']}</td>"
                      f"<td>{v['kibic_imp']}</td><td>{v['ember_imp']}</td></tr>")
    ki.append("</table></div><h2>Kalibráció vállalásonként</h2><div class='wrap'><table><tr>"
              "<th>vállalás</th><th>indulás</th><th>a kibic lapja buktat: várható</th><th>valóban</th>"
              "<th>bármelyik lap: várható</th><th>valóban</th></tr>")
    for n, v in o["kalibracio_tipus"].items():
        ki.append(f"<tr><td>{n}</td><td>{v['db']}</td><td>{v['becsult']}</td><td>{v['kibic_lapja']}</td>"
                  f"<td>{v['becsult_barmely']}</td><td>{v['barmely']}</td></tr>")
    ki.append("</table></div><h2>Leosztásonként</h2>")
    rendezett = sorted(elemzesek, key=lambda e: -((_valodi_imp(e, e["kibic_lap"]) or 0)
                                                  - (_valodi_imp(e, e["ember_lap"]) or 0)))
    for e in rendezett:
        ki_imp, em_imp = _valodi_imp(e, e["kibic_lap"]), _valodi_imp(e, e["ember_lap"])
        jm, jv = e["jelleg_minta"], e["jelleg_valodi"]
        kez = " ".join(f"{_SZIN[sz]}{''.join(_ERTEK.get(c, c) for c in e['kez'][sz]) or '—'}"
                       for sz in "SHDC")
        ki.append(f"<details><summary><b>{e_(e['kontraktus'])}</b> {e['felvevo']} — kibic "
                  f"{_szep(e['kibic_lap'])} ({ki_imp} IMP), ember "
                  f"{_szep(e['ember_lap']) if e['ember_lap'] else '—'} ({em_imp} IMP) "
                  f"<span class='tag'>minta: {OSZTALY_NEV.get(jm['osztaly'], '?').split(' (')[0]}</span> "
                  f"<span class='tag'>valódi: {OSZTALY_NEV[jv['osztaly']].split(' (')[0]}</span> "
                  f"<span class='mut'>{e_(e['tabla'])}</span></summary>"
                  f"<p>Licit: {e_(e['licit'])}<br>Az indító ({e['indito']}) keze: {kez} · "
                  f"beliállás: {e['beliallas']} · minták: {e['minta_db']}"
                  f"{' (lazított)' if e.get('lazitott') else ''} · szabály: {e_(str(e.get('szabaly')))}<br>"
                  f"Buktató lapok aránya: a mintákban átlag {jm['arany']}, a valóságban {jv['arany']}</p>"
                  "<div class='wrap'><table><tr><th>lap</th><th>minta: védőütés</th><th>buktat</th>"
                  "<th>IMP</th><th>valódi: védőütés</th><th>buktat</th><th>IMP</th><th></th></tr>")
        for r in sorted(e["lapok"], key=lambda r: ("SHDC".index(r["lap"][0]),
                                                    -"23456789TJQKA".index(r["lap"][1]))):
            mi, va = r["minta"] or {}, r["valodi"] or {}
            jel = ("kibic" if r["lap"] == e["kibic_lap"] else "") + \
                  (" ember" if r["lap"] == e["ember_lap"] else "")
            ki.append(f"<tr class='{'kb' if r['lap'] == e['kibic_lap'] else ''}'><td>{_szep(r['lap'])}</td>"
                      f"<td>{mi.get('vedo_utes', '')}</td><td>{round(100 * mi['buktat']) if mi else ''}%</td>"
                      f"<td>{mi.get('imp', '')}</td><td>{va.get('vedo_utes', '')}</td>"
                      f"<td class='{'jo' if va.get('buktat') else 'rossz'}'>{'igen' if va.get('buktat') else 'nem'}</td>"
                      f"<td>{va.get('imp', '')}</td><td class='mut'>{jel.strip()}</td></tr>")
        ki.append("</table></div></details>")
    ki.append("</body></html>")
    return "\n".join(ki)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m kibic.cli.inditaselemzes",
                                 description="Az indulások kimutatása: a kibic becslése és a DD laponként.")
    ap.add_argument("--json", required=True, help="a jatekmeres --json kimenete")
    ap.add_argument("--pbn", nargs="+", required=True, help="a partik PBN-fájljai vagy mappái")
    ap.add_argument("--rendszer", default="KIBIC_STAND")
    ap.add_argument("--minta", type=int, default=200)
    ap.add_argument("--mag", type=int, default=1)
    ap.add_argument("--suly", action="append", default=[], metavar="KOD=SULY",
                    help="egy következtetés-sor súlyának felülírása (hangoláshoz), pl. FELVETEL_HIHETO=0.4")
    ap.add_argument("--kovetkeztetes-ms", type=int, default=300_000)
    ap.add_argument("--mind", action="store_true", help="minden indulás (nem csak a rosszak)")
    ap.add_argument("--hangolas", help="a FELVETEL_HIHETO súlyai egyszerre (pl. 1,0.6,0.4,0.25): "
                                      "kalibráció és a minta szerinti legjobb lap súlyonként")
    ap.add_argument("--rosszabb", action="store_true", help="csak ahol az ember jobban indult")
    ap.add_argument("--max", type=int, help="legfeljebb ennyi leosztás")
    ap.add_argument("--parhuzamos", type=int, default=1)
    ap.add_argument("--html", help="a kimutatás HTML-ben")
    ap.add_argument("--ki", help="az elemzések JSON-ban (soronként)")
    a = ap.parse_args(argv)
    if a.suly:
        os.environ["KIBIC_KOVETKEZTETES_SULY"] = ",".join(a.suly)
    meresek = []
    with open(a.json, encoding="utf-8") as f:
        for s in f:
            try:
                m = json.loads(s)
            except ValueError:
                continue
            if m.get("helyzet") != "INDITAS":
                continue
            kimp, eimp = m.get("imp_veszt"), m.get("emberi_imp_veszt")
            if not a.mind and not (kimp or 0) > 0:
                continue
            if a.rosszabb and not (kimp or 0) > (eimp or 0):
                continue
            meresek.append(m)
    if a.max:
        meresek = meresek[:a.max]
    print(f"{len(meresek)} indulás", file=sys.stderr)
    arg = (a.pbn, a.rendszer, a.minta, a.mag, a.kovetkeztetes_ms,
           tuple(float(x) for x in a.hangolas.split(",")) if a.hangolas else ())
    if a.parhuzamos > 1:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(a.parhuzamos, _init, arg) as pool:
            elemzesek = [x for x in pool.imap(_egy, meresek, chunksize=2) if x]
    else:
        _init(*arg)
        elemzesek = [x for x in map(_egy, meresek) if x]
    if a.ki:
        with open(a.ki, "w", encoding="utf-8") as f:
            for x in elemzesek:
                f.write(json.dumps(x, ensure_ascii=False) + "\n")
    if a.html:
        with open(a.html, "w", encoding="utf-8") as f:
            f.write(html_jelentes(elemzesek))
    o = osszegzes(elemzesek)
    print(f"{'valódi jelleg':<28}{'db':>5}{'kibic IMP':>11}{'ember IMP':>11}")
    for osz, b in o["jelleg_szerint"].items():
        print(f"{OSZTALY_NEV[osz]:<28}{b['db']:>5}{b['kibic_imp']:>11}{b['ember_imp']:>11}")
    print("\na kibic előnye a mintákban      db  kibic IMP  ember IMP")
    for n, v in o["biztossag"].items():
        print(f"{n:<28}{v['db']:>5}{v['kibic_imp']:>11}{v['ember_imp']:>11}")
    print("\nkalibráció (a kibic lapja buktat)  db  várható  valóban  várható(bármely)  valóban(bármely)")
    for n, v in o["kalibracio"].items():
        print(f"{n:<32}{v['db']:>5}{v['becsult']:>9}{v['kibic_lapja']:>9}{v['becsult_barmely']:>18}{v['barmely']:>18}")
    print("\nvállalásonként                 db  várható  valóban  várható(bármely)  valóban(bármely)")
    for n, v in o["kalibracio_tipus"].items():
        print(f"{n:<28}{v['db']:>5}{v['becsult']:>9}{v['kibic_lapja']:>9}{v['becsult_barmely']:>18}{v['barmely']:>18}")
    if o["hangolas"]:
        print("\nhangolás (FELVETEL_HIHETO)            db  kibic lapja: várható/valóban  bármely: várható/valóban"
              "  IMP: minta legjobbja / kibic / ember")
        for n, v in o["hangolas"].items():
            print(f"{n:<36}{v['db']:>5}{v['kibic_varhato']:>16}/{v['kibic_valoban']:<6}"
                  f"{v['barmely_varhato']:>16}/{v['barmely_valoban']:<6}"
                  f"{v['legjobb_imp']:>12} /{v['kibic_imp']:>5} /{v['ember_imp']:>5}")
    print("\nbecsült (sor) / valódi (oszlop) jelleg:")
    print(" " * 16 + "".join(f"{x[:9]:>10}" for x in OSZTALYOK))
    for b in OSZTALYOK:
        if b in o["becsult_vs_valodi"]:
            print(f"{b[:15]:<16}" + "".join(f"{o['becsult_vs_valodi'][b].get(v, 0):>10}" for v in OSZTALYOK))
    return 0


if __name__ == "__main__":
    sys.exit(main())
