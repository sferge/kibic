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


def tabla_szam(azonosito: str) -> int:
    """A tábla száma: „fájl#n” → n; ha a fájl egyetlen partit tartalmaz és a neve
    számra végződik (pl. hand-of-the-day-0617.pbn#1), a fájlnév száma."""
    import re
    nev, _, n = azonosito.rpartition("#")
    m = re.search(r"(\d+)\.\w+$", nev)
    return int(m.group(1)) if n == "1" and m else int(n)


def _rontas(p, k, g, u, lap, cel, forras, terv_jx, mag, adu_kezeles=False) -> dict | None:
    """Diagnózis: a valódi leosztás DD-je szerint ez a lap ütést vesztett-e (a
    tökéletes folytatáshoz képest)? Ha a teljesítést rontotta el, és tervbeli hívás
    volt, megnézzük a jelöltállító lefedését: van-e a (vágatlan) jelöltek között
    olyan terv, amely a valódi leosztásban — kukucskálás nélkül, a védők DD-vel —
    teljesít, és hányadik a jelöltlistában."""
    from ..solver.dds import lap_elemzes
    jatszott = [str(l) for _, l in g.lapok]
    ered = lap_elemzes(p.leosztas, jatszott, k)
    ertek = {e.lap: e.felvevo_osszesen for e in ered}
    legj = max(ertek.values())
    ez = ertek.get(str(lap), legj)
    if ez >= legj:
        return None
    r = {"utes": len(g.lapok) // 4 + 1, "poz": len(g.aktualis()) + 1, "ules": u, "lap": str(lap),
         "forras": forras, "dd_elotte": legj, "dd_utana": ez,
         "teljesitest_rontja": legj >= cel > ez,
         "jobb": sorted(x for x, v in ertek.items() if v == legj),
         "terv": str(terv_jx.terv) if terv_jx is not None else None}
    if r["teljesitest_rontja"] and forras == "TERV_HIVAS":
        r["lefedes"] = lefedes(p, k, g, cel, adu_kezeles=adu_kezeles)
    return r


def lefedes(p, k, g, cel, max_terv: int = 40, adu_kezeles: bool = False) -> dict:
    """A vágatlan jelöltlista minden terve a valódi leosztásban (a felvevő a terv
    szerint és a saját követési szabályai szerint, a védők DD-vel)."""
    from ..solver.dds import lap_elemzes
    adu = None if k.szin == "NT" else k.szin
    felvevo = k.felvevo
    asztal = kovetkezo_ules(felvevo, 2)
    valodi = {u: set(p.leosztas.kezek[u].lapok) for u in "NESW"}
    tervek = tj.jeloltek(g.kezek[felvevo], g.kezek[asztal], adu, g.kint, max_db=100000,
                         adu_kezeles=adu_kezeles)
    vedo = tj.vedo_dd(lap_elemzes, p.leosztas, k)
    jok = []
    for i, t in enumerate(tervek):
        ut = tj.lejatszik(valodi, felvevo, adu, list(g.lapok), t, vedo)
        if ut >= cel:
            jok.append((i, str(t)))
    return {"jeloltek": len(tervek), "teljesito": len(jok),
            "elso_teljesito": jok[0] if jok else None,
            "vagas_utan": bool(jok) and jok[0][0] >= max_terv}


def egy_parti(p, vilag: int, max_terv: int, mag: int, tar_fv=None, naplo=None,
              diagnozis: bool = False, kovetes_terv: int = 0,
              adu_kezeles: bool = False) -> dict | None:
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
    terv_tar: list = []           # a legutóbbi tervértékelés sorrendje (a követéshez)
    kovetesek = []
    rontasok = []                 # a felvevő oldal lapjai, amelyek a valódi DD szerint ütést vesztettek
    dontesek = 0
    while len(g.lapok) < 52:
        u = g.soron()
        forras = None
        if not g.mi(u):
            lap = tj._vedo_lap(lap_elemzes(p.leosztas, [str(l) for _, l in g.lapok], k))
        else:
            utes = g.aktualis()
            van = [l for l in g.kezek[u] if utes and l.szin == utes[0][1].szin]
            legalis = van or sorted(g.kezek[u], key=lambda l: (l.szin, l.rang))
            if len(legalis) == 1:
                lap = legalis[0]
                forras = "KENYSZER"
            elif utes and terv_jx is not None and tj._szandekos(terv_jx, u):
                lap = tj.felvevo_lap(terv_jx, u)
                forras = "TERV_SZANDEK"
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
                    forras = "NINCS_VILAG"
                elif not utes:
                    forras = "TERV_HIVAS"
                    d, y = g.kezek[felvevo], g.kezek[asztal]
                    tervek = tj.jeloltek(d, y, adu, g.kint, max_terv, adu_kezeles=adu_kezeles)
                    ert = tj.ertekel_lepcsos(tervek, vilagok, sulyok, felvevo, k, list(g.lapok))
                    terv_jx = tj.Jatek(valodi, felvevo, adu, list(g.lapok), ert[0].terv)
                    terv_tar = [e.terv for e in ert]
                    lap = tj.felvevo_lap(terv_jx, u)
                    tervek_log.append((len(g.lapok) // 4 + 1, str(ert[0].terv), round(ert[0].esely, 2)))
                    if naplo:
                        naplo(f"   {len(g.lapok)//4+1:>2}. ütés: {ert[0].esely:.2f} {ert[0].terv}")
                else:
                    valasztas = tj.kovetesi_valasztas(legalis, utes, adu) if kovetes_terv else []
                    if valasztas:
                        d, y = g.kezek[felvevo], g.kezek[asztal]
                        if terv_tar:
                            tervek = terv_tar[:kovetes_terv]
                        else:
                            tervek = [e.terv for e in tj.ertekel_lepcsos(
                                tj.jeloltek(d, y, adu, g.kint, max_terv, adu_kezeles=adu_kezeles), vilagok[:4], sulyok[:4],
                                felvevo, k, list(g.lapok))][:kovetes_terv]
                        lap, kn = tj.kovetes_tervvel(valasztas, tervek, vilagok, sulyok, felvevo, k,
                                                     list(g.lapok), u)
                        forras = "KOVETES_TERVVEL"
                        kovetesek.append((len(g.lapok) // 4 + 1, u, kn))
                        if naplo:
                            naplo(f"   {len(g.lapok)//4+1:>2}. ütés {u} követés: "
                                  + "; ".join(f"{a} {b:.2f}" for a, b, _, _ in kn))
                    else:
                        ered = [lap_elemzes(lo, jatszott, k) for lo in vilagok]
                        lap = tj.dd_szavazas(ered, sulyok, cel)
                        forras = "DD_SZAVAZAS" if terv_jx is not None else "DD_SZAVAZAS_TERV_ELOTT"
            lap = tj.szabalyos(g, u, lap)
            if forras != "KENYSZER" and diagnozis:
                r = _rontas(p, k, g, u, lap, cel, forras, terv_jx, mag, adu_kezeles)
                if r:
                    rontasok.append(r)
        g.tesz(u, lap)
        if terv_jx is not None and len(terv_jx.lapok) < len(g.lapok):
            terv_jx.tesz(u, lap)
    ut = g.felvevo_utesek()
    return {"tabla": p.azonosito, "kontraktus": str(k), "cel": cel, "dd": dd_ertek,
            "dd_teljesul": dd_ertek >= cel, "utesek": ut, "teljesult": ut >= cel,
            "tervek": tervek_log, "dontesek": dontesek, "rontasok": rontasok, "kovetesek": kovetesek, "ms": int((time.time() - t0) * 1000)}


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
    ap.add_argument("--kovetes-terv", type=int, default=0,
                    help="ha >0: a fedés / kihagyás jellegű követő döntést a legjobb ennyi terv dönti el "
                         "(a világokon, kukucskálás nélkül), nem a DD-szavazás")
    ap.add_argument("--adu-kezeles", action="store_true",
                    help="a jelöltek az aduszínt is kezelhetik (impassz, kiadás) a felülről kiaduzás helyett")
    ap.add_argument("--diagnozis", action="store_true",
                    help="a felvevő oldal ütésvesztő lapjai (a valódi DD szerint), a döntés forrásával; "
                         "tervbeli hívásnál a jelöltállító lefedése is")
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
    partik = list(partik_fajlbol(fajlok_kibontasa(a.pbn, ".pbn"), "IMP", 1))
    if a.csak:
        partik = [p for p in partik if tabla_szam(p.azonosito) in a.csak]
    else:
        partik = partik[a.tol:a.tol + a.db]
    n = tel = dd_tel = 0
    for p in partik:
        r = egy_parti(p, a.vilag, a.terv, a.mag, tar_fv, print if a.reszletes else None,
                      diagnozis=a.diagnozis, kovetes_terv=a.kovetes_terv,
                      adu_kezeles=a.adu_kezeles)
        if r is None:
            continue
        n += 1
        tel += r["teljesult"]
        dd_tel += r["dd_teljesul"]
        elso_terv = r["tervek"][0] if r["tervek"] else (0, "-", 0)
        print(f'{tabla_szam(r["tabla"]):>4} {r["kontraktus"]:4} cél {r["cel"]:2} DD {r["dd"]:2} '
              f'→ {r["utesek"]:2} {"OK " if r["teljesult"] else "BUK"} | első terv {elso_terv[2]:.2f} '
              f'{elso_terv[1]} ({r["ms"]//1000}s)', flush=True)
        for x in r.get("rontasok", []):
            if x["teljesitest_rontja"]:
                print(f'      {x["utes"]:>2}. ütés {x["poz"]}. hely {x["ules"]} {x["lap"]} [{x["forras"]}] '
                      f'DD {x["dd_elotte"]}→{x["dd_utana"]}, jobb: {",".join(x["jobb"])}'
                      + (f' | lefedés: {x["lefedes"]}' if x.get("lefedes") else ""), flush=True)
        if f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
    print(f"\npartik {n}: teljesült {tel}, DD szerint teljesíthető {dd_tel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
