"""
A lejátszás mérése: lapankénti DD-veszteség (motor/lejatszas_meres.py).

    # a kibic saját partijai a naplóból (KIBIC_ATJARO_NAPLO_KERES=1 kell)
    python -m kibic.cli.jatekmeres --naplo kibic-atjaro.jsonl

    # mérőpad valódi partikon: a kibic lapja vs. az emberé, pozícióról pozícióra
    python -m kibic.cli.jatekmeres --lin partik/*.lin --jatekos gal --oldal vedo
    python -m kibic.cli.jatekmeres --pbn verseny.pbn --oldal felvevo
    python -m kibic.cli.jatekmeres --pbn tanpartik/          # a mappa összes .pbn-je
    python -m kibic.cli.jatekmeres --db --jatekos korszurku --limit 50 --minta 100

    közös: --json ki.jsonl (minden mérés soronként), --reszletes (a legrosszabbak)

A mérőpadon a kibic jelzés- és licitrendszere a YAML-ból jön (`--rendszer`,
alap: KIBIC_STAND, mindkét vonalra). Egy döntés 1–5 másodperc (`--minta`,
`--ido` szabja); a `--max-dontes` / `--limit` a próbafutáshoz.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[3]


# --- a kibic döntése a YAML-ból (mint a jatekelemzes) ---------------------------------

# --mag mellett az idő nem lehet döntő: a terheléstől (16 párhuzamos folyamat, a
# processzor órajele) függne, hány minta fér bele, és két futás eltérne.
PONTOS_IDO_S = 120
PONTOS_KOVETKEZTETES_MS = 300_000


def yaml_dontes(rendszer: str, ido_s: float, minta: int, kovetkeztetes_ms: int = 15000,
                mag: int | None = None):
    from ..motor import lejatszas as lj
    from ..motor.kartya import jelzesek_rendszerhez_yaml
    from .aranykeszlet import yaml_betolto
    from ..szolgaltatas.atjaro import licit_tudas
    jelz = jelzesek_rendszerhez_yaml(rendszer)
    betolto = yaml_betolto([str(GYOKER / "rendszerek" / "yaml")])
    tar_cache: dict = {}

    def fv(keres: dict):
        allas = lj.allas_keresbol(keres)
        st = keres.get("state") or {}
        auction = (keres.get("history") or {}).get("auction") or []
        kulcs = (allas.ules, st.get("dealer"), json.dumps(auction))
        if kulcs not in tar_cache:
            try:
                tar_cache[kulcs] = licit_tudas({
                    "seat": allas.ules, "dealer": st.get("dealer") or allas.ules,
                    "vulnerability": (keres.get("game") or {}).get("vulnerability") or "none",
                    "auction": auction, "system": rendszer}, betolto, kovetkeztetes_ms)
            except Exception:                    # noqa: BLE001 — licit nélkül is mérünk
                tar_cache[kulcs] = (None, {})
        if len(allas.legalis) == 1:
            return next(iter(allas.legalis.values())), {"kibic": {"situation": "KENYSZER"}}
        tar, valoszinu = tar_cache[kulcs]
        e = lj.jatek_dontes(allas, jelz, tar, ido_keret_s=ido_s, db=minta, mag=mag,
                            valoszinu=valoszinu)
        return allas.legalis[e.dontes.lap], {"kibic": lj.meta(e)}
    return fv


# párhuzamos futtatáshoz: a munkafolyamat saját döntés-függvénye
_MUNKAS: dict = {}


def _munkas_init(rendszer: str, ido_s: float, minta: int, kov_ms: int = 15000,
                 mag: int | None = None) -> None:
    _MUNKAS["fv"] = yaml_dontes(rendszer, ido_s, minta, kov_ms, mag)


def _munkas_parti(feladat):
    from ..motor import lejatszas_meres as lm
    p, ulesek, oldal, rendszer, max_dontes = feladat[:5]
    if len(feladat) > 5 and feladat[5]:          # teljes lejátszás
        m = lm.teljes_lejatszas(p, _MUNKAS["fv"], rendszer=rendszer)
        return [m] if m else []
    return lm.parti_meres(p, _MUNKAS["fv"], ulesek=ulesek, felvevo_oldal=oldal,
                          rendszer=rendszer, max_dontes=max_dontes)


# --- források ---------------------------------------------------------------------

def _pbn_olvas(ut: str):
    from ..impex.pbn import olvas
    nyers = open(ut, "rb").read()
    for kod in ("utf-8-sig", "utf-8", "cp1250", "iso-8859-2"):
        try:
            return olvas(nyers.decode(kod))
        except UnicodeDecodeError:
            continue
    return olvas(nyers.decode("utf-8", errors="replace"))


def fajlok_kibontasa(utak: list[str], kiterj: str) -> list[str]:
    """A megadott utak közül a mappákat kibontja: a bennük (almappákban is) lévő
    `kiterj` kiterjesztésű fájlok, útvonal szerint rendezve. A fájlok változatlanul maradnak."""
    ki = []
    for ut in utak:
        p = Path(ut)
        if p.is_dir():
            ki += sorted(str(f) for f in p.rglob("*")
                         if f.is_file() and f.suffix.lower() == kiterj)
        else:
            ki.append(ut)
    return ki


def partik_fajlbol(utak: list[str], pontozas: str, min_lapok: int = 2):
    """LIN- és PBN-fájlok (a kiterjesztés dönt) -> Parti. `min_lapok`: legalább
    ennyi lejátszott lap kell (a teljes lejátszáshoz elég az indulás: 1 — pl. a
    BBO „Hand of the Day” partik, ahol csak az indulás ismert)."""
    from ..domain import kovetkezo_ules
    from ..impex.lin import olvas_fajl
    from ..motor.lejatszas_meres import Parti
    for ut in utak:
        jatszmak = _pbn_olvas(ut) if ut.lower().endswith(".pbn") else olvas_fajl(ut)
        for n, j in enumerate(jatszmak, 1):
            if j.leosztas and j.licit and (not j.felvevo or not j.kontraktus):
                # üres [Declarer]: a felvevő (és a kontraktus) a licitmenetből
                from ..motor.visszajatszo import licit_ellenoriz
                try:
                    k_, f_, _, _ = licit_ellenoriz(j.licit, j.leosztas.oszto)
                except Exception:                # noqa: BLE001
                    k_, f_ = None, None
                if f_ and k_:
                    j.felvevo = f_
                    if not j.kontraktus:
                        j.kontraktus = k_
            if not j.leosztas or not j.kontraktus or not j.felvevo or len(j.lapok) < min_lapok:
                continue
            k = replace(j.kontraktus, felvevo=j.felvevo)
            ules, licit = j.leosztas.oszto, []
            for x in j.licit:                    # a LIN licitjéhez nem tartozik ülés
                licit.append({**x, "ules": x.get("ules") or ules})
                ules = kovetkezo_ules(ules)
            yield Parti(f"{Path(ut).name}#{n}", j.leosztas, k, licit, list(j.lapok),
                        pontozas, j.jatekosok())


partik_linbol = partik_fajlbol


def partik_dbbol(a, pontozas: str):
    from ..domain import Leosztas, Kontraktus
    from ..motor.lejatszas_meres import Parti
    try:
        import pymysql
    except ImportError:
        sys.exit("A pymysql csomag nem érhető el.")
    conn = pymysql.connect(host=a.host, user=a.user, password=a.jelszo,
                           database=a.adatbazis, charset="utf8mb4")
    cur = conn.cursor()
    szuro, par = "", []
    if a.jatekos:
        szuro = " AND %s IN (jn.azonosito, je.azonosito, js.azonosito, jw.azonosito)"
        par.append(a.jatekos.lower())
    cur.execute(
        "SELECT j.id, l.kezek_pbn, l.oszto, l.beliallas, j.licit, j.lejatszas, j.kontraktus,"
        " j.felvevo, jn.azonosito, je.azonosito, js.azonosito, jw.azonosito"
        " FROM jatszma j JOIN leosztas l ON l.id = j.leosztas_id"
        " LEFT JOIN jatekos jn ON jn.id = j.n_jatekos_id LEFT JOIN jatekos je ON je.id = j.e_jatekos_id"
        " LEFT JOIN jatekos js ON js.id = j.s_jatekos_id LEFT JOIN jatekos jw ON jw.id = j.w_jatekos_id"
        " WHERE j.lejatszas IS NOT NULL AND j.felvevo IS NOT NULL AND j.kontraktus <> 'PASS'"
        + szuro + " ORDER BY j.id" + (f" LIMIT {int(a.limit)}" if a.limit else ""), par)
    for (jid, pbn, oszto, beli, licit, lejatszas, kontr, felvevo, n, e, s, w) in cur.fetchall():
        try:
            lo = Leosztas.pbn_bol(pbn, oszto=oszto, beliallas=beli)
            k = Kontraktus.parse(kontr, felvevo)
            lj_ = json.loads(lejatszas) if isinstance(lejatszas, (str, bytes)) else lejatszas
            li = json.loads(licit) if isinstance(licit, (str, bytes)) else (licit or [])
        except Exception:                        # noqa: BLE001
            continue
        lapok = (lj_ or {}).get("lapok") or []
        if k is None or len(lapok) < 2:
            continue
        yield Parti(f"jatszma#{jid}", lo, k, li, lapok, pontozas,
                    {"N": n or "", "E": e or "", "S": s or "", "W": w or ""})


# --- kiírás -------------------------------------------------------------------------

def _sor(nev: str, b: dict) -> str:
    if not b["db"]:
        return f"{nev:<10}{0:>6}"
    s = (f"{nev:<10}{b['db']:>6}{b['veszt_ossz'] / b['db']:>9.3f}"
         f"{b['hibas_lap'] / b['db']:>9.0%}{b['eredmeny_veszt']:>8}{b['imp_ossz']:>7}")
    if "ember_veszt_ossz" in b:
        s += (f" │{b['ember_veszt_ossz'] / b['db']:>9.3f}{b['ember_hibas_lap'] / b['db']:>9.0%}"
              f"{b['ember_eredmeny_veszt']:>8}{b['ember_imp_ossz']:>7}"
              f" │{b['kibic_jobb']:>7}{b['ember_jobb']:>7}")
    return s


def jelentes(meresek, stat: dict | None = None, reszletes: bool = False) -> str:
    from ..motor.lejatszas_meres import osszesit
    o = osszesit(meresek)
    emberrel = any(m.emberi_veszt is not None for m in meresek)
    ki = []
    if stat:
        ki.append(" · ".join(f"{k}: {v}" for k, v in stat.items()))
    fej = f"{'':<10}{'döntés':>6}{'veszt/lap':>9}{'hibás':>9}{'eredm.':>8}{'IMP':>7}"
    if emberrel:
        fej += f" │{'EMBER v/l':>9}{'hibás':>9}{'eredm.':>8}{'IMP':>7} │{'kibic+':>7}{'ember+':>7}"
    ki += ["", "KIBIC" + (" " * 47 + "EMBER (ugyanott)" if emberrel else ""), fej]
    ki.append(_sor("összesen", o["osszes"]))
    idore = sum(1 for m in meresek if m.megallt == "IDO")
    ki.append(_sor("felvevő", o["felvevo"]))
    ki.append(_sor("védő", o["vedo"]))
    ki.append("")
    for h, b in o["helyzetenkent"].items():
        ki.append(_sor(h, b))
    ki += ["", "veszt/lap: átlagos DD-ütésveszteség lapanként; hibás: a lapok hány %-a adott el "
               "ütést; eredm.: ennyi lap rontotta el a teljesítést / buktatást; IMP: az összes "
               "IMP-veszteség a DD legjobb lapjához képest (beliállással, kontrával)."]
    if emberrel:
        ki.append("kibic+ / ember+: ennyi helyzetben vesztett kevesebbet a kibic / az ember "
                  "(IMP-ben, egyenlőségnél ütésben).")
    if idore:
        ki.append(f"{idore} döntés az időkorlátnál állt meg: ezek a gép terhelésétől függnek, "
                  "két futás itt eltérhet.")
    if reszletes:
        bizt = [m for m in meresek if m.bizonytalan and (m.veszt_max or 0) > 0]
        if bizt:
            ki += ["", "Bizonytalan (a napló nem adja ki a teljes osztást; a veszteség a "
                       "lehetséges kiegészítéseken):"]
            for m in bizt:
                ki.append(f"  {m.tabla} {m.utes:>2}. ütés {m.ules} {m.helyzet:<9} kibic {m.lap} "
                          f"(-{m.veszt}…-{m.veszt_max})" + (f"  [{m.szabaly}]" if m.szabaly else ""))
        meresek = [m for m in meresek if not m.bizonytalan]
        rossz = sorted(meresek, key=lambda m: (-(m.veszt - (m.emberi_veszt or 0)), -m.veszt))
        ki += ["", "A legrosszabb kibic-döntések:"]
        for m in rossz[:15]:
            if m.veszt <= (m.emberi_veszt or 0) and emberrel:
                break
            if m.veszt == 0:
                break
            ki.append(f"  {m.tabla} {m.utes:>2}. ütés {m.ules} {m.helyzet:<9} kibic {m.lap} "
                      f"(-{m.veszt}{', EREDMÉNY' if m.eredmeny_veszt else ''})"
                      + (f"  ember {m.emberi_lap} (-{m.emberi_veszt})" if emberrel else "")
                      + f"  legjobb: {' '.join(m.legjobb)}"
                      + (f"  [{m.szabaly}]" if m.szabaly else ""))
    return "\n".join(ki)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="A lejátszás mérése (lapankénti DD-veszteség)")
    forras = ap.add_mutually_exclusive_group(required=True)
    forras.add_argument("--naplo", help="a KIBIC_ATJARO_NAPLO fájl (kérésekkel)")
    forras.add_argument("--lin", nargs="+", help="LIN-fájlok vagy mappák (valódi partik)")
    forras.add_argument("--pbn", nargs="+", help="PBN-fájlok vagy mappák (valódi partik, lejátszással)")
    forras.add_argument("--db", action="store_true", help="a jatszma tábla")
    ap.add_argument("--jatekos", help="csak ennek a játékosnak a lapjait méri (valódi parti)")
    ap.add_argument("--oldal", choices=["mind", "felvevo", "vedo"], default="mind")
    ap.add_argument("--rendszer", default="KIBIC_STAND", help="licit- és jelzésrendszer (YAML)")
    ap.add_argument("--pontozas", choices=["IMP", "MP"], default="IMP")
    ap.add_argument("--minta", type=int, default=200, help="minta döntésenként (alap 200)")
    ap.add_argument("--ido", type=float, default=4.0,
                    help="időkeret döntésenként, mp (--mag mellett: legalább %d)" % PONTOS_IDO_S)
    ap.add_argument("--suly", action="append", default=[], metavar="KOD=SULY",
                    help="egy következtetés-sor súlyának felülírása (hangoláshoz), pl. FELVETEL_HIHETO=0.4")
    ap.add_argument("--kovetkeztetes-ms", type=int, default=15000,
                    help="a licit kizárásos következtetésének ideje leosztásonként (alap 15000; 0: ki)")
    ap.add_argument("--mag", type=int,
                    help="véletlen mag: ugyanaz a futás ugyanazt adja (az időkorlát ilyenkor "
                         "csak biztonsági felső határ, a döntés a minta számán áll meg)")
    ap.add_argument("--idokorlat", action="store_true",
                    help="--mag mellett is a valódi időkorlátokkal (mint az élő asztalon)")
    ap.add_argument("--max-parti", type=int)
    ap.add_argument("--max-dontes", type=int, help="partinként legfeljebb ennyi döntés")
    ap.add_argument("--parhuzamos", type=int, default=1,
                    help="ennyi folyamat dolgozik egyszerre (partinként; alap 1)")
    ap.add_argument("--json", help="minden mérés ide, soronként")
    ap.add_argument("--teljes", action="store_true",
                    help="teljes lejátszás: a valódi indulás után a kibic játssza végig a felvevőt, "
                         "a védők tökéletesen (DD); partinként egy eredmény")
    ap.add_argument("--reszletes", action="store_true")
    ap.add_argument("--limit", type=int, help="--db: legfeljebb ennyi parti")
    ap.add_argument("--adatbazis", default=os.getenv("KIBIC_DB", "kibic"))
    ap.add_argument("--host", default=os.getenv("KIBIC_HOST", "localhost"))
    ap.add_argument("--user", default=os.getenv("KIBIC_USER", "kibic"))
    ap.add_argument("--jelszo", default=os.getenv("KIBIC_PASS", ""))
    a = ap.parse_args(argv)
    if a.suly:
        os.environ["KIBIC_KOVETKEZTETES_SULY"] = ",".join(a.suly)
    from ..motor import lejatszas_meres as lm

    if a.mag is not None and not a.idokorlat:
        a.ido = max(a.ido, PONTOS_IDO_S)
        a.kovetkeztetes_ms = max(a.kovetkeztetes_ms, PONTOS_KOVETKEZTETES_MS) if a.kovetkeztetes_ms else 0
    if a.naplo:
        sorok = []
        with open(a.naplo, encoding="utf-8") as f:
            for s in f:
                try:
                    sorok.append(json.loads(s))
                except ValueError:
                    continue
        meresek, stat = lm.naplo_meres(sorok)
        if stat.get("keres_nelkul") and not meresek:
            print("A naplóban nincs kérés: a szolgáltatás fusson KIBIC_ATJARO_NAPLO_KERES=1-gyel.",
                  file=sys.stderr)
    else:
        from ..domain import kovetkezo_ules
        if a.lin or a.pbn:
            utak = fajlok_kibontasa(a.lin or a.pbn, ".lin" if a.lin else ".pbn")
            if not utak:
                print("Nincs mérhető fájl a megadott helyen.", file=sys.stderr)
                return 1
            partik = partik_fajlbol(utak, a.pontozas, 1 if a.teljes else 2)
        else:
            partik = partik_dbbol(a, a.pontozas)
        oldal = {"mind": None, "felvevo": True, "vedo": False}[a.oldal]
        feladatok = []
        for p in partik:
            if a.max_parti and len(feladatok) >= a.max_parti:
                break
            ulesek = None
            if a.jatekos:
                ulesek = {u for u, nev in p.jatekosok.items()
                          if nev and nev.strip().lower() == a.jatekos.lower()}
                if not ulesek:
                    continue
                if p.kontraktus.felvevo in ulesek:      # az asztal lapjait a felvevő teszi
                    ulesek.add(kovetkezo_ules(p.kontraktus.felvevo, 2))
            feladatok.append((p, ulesek, oldal, a.rendszer, a.max_dontes, a.teljes))
        meresek, stat = [], {"partik": 0, "dontesek": 0}
        # a --json partinként íródik (menet közben is olvasható, megszakításnál sem vész el)
        kimenet = open(a.json, "w", encoding="utf-8") if a.json else None

        def jegyez(m):
            meresek.extend(m)
            if kimenet is not None:
                for x in m:
                    kimenet.write(json.dumps(x.szotar(), ensure_ascii=False) + "\n")
                kimenet.flush()
            stat["partik"] += 1
            stat["dontesek"] += len(m)
            print(f"\r{stat['partik']}/{len(feladatok)} parti, {stat['dontesek']} döntés",
                  end="", file=sys.stderr)
        if a.parhuzamos > 1:
            import multiprocessing as mp
            with mp.get_context("spawn").Pool(a.parhuzamos, _munkas_init,
                                              (a.rendszer, a.ido, a.minta, a.kovetkeztetes_ms,
                                               a.mag)) as pool:
                for m in pool.imap_unordered(_munkas_parti, feladatok):
                    jegyez(m)
        else:
            _munkas_init(a.rendszer, a.ido, a.minta, a.kovetkeztetes_ms, a.mag)
            for f in feladatok:
                jegyez(_munkas_parti(f))
        print(file=sys.stderr)
        if kimenet is not None:
            kimenet.close()
    if getattr(a, "teljes", False) and not a.naplo:
        print(teljes_jelentes(meresek))
        return 0
    if a.naplo and a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            for m in meresek:
                f.write(json.dumps(m.szotar(), ensure_ascii=False) + "\n")
    print(jelentes(meresek, stat, a.reszletes))
    return 0


def teljes_jelentes(meresek) -> str:
    """A teljes lejátszás összesítése."""
    n = len(meresek)
    if not n:
        return "Nincs mért parti."
    tel = sum(1 for m in meresek if m.teljesult)
    dd_tel = sum(1 for m in meresek if m.dd_teljesul)
    bukott = [m for m in meresek if m.dd_teljesul and not m.teljesult]
    tobb = sum(1 for m in meresek if m.utesek > m.dd_indulas_utan)
    kev = [m for m in meresek if m.utesek < m.dd_indulas_utan]
    sorok = [f"partik: {n}",
             f"teljesült: kibic {tel} · tökéletes felvevővel (DD az indulás után) {dd_tel}",
             f"a teljesíthetőből elbukta: {len(bukott)}",
             f"kevesebb ütés a DD-nél: {len(kev)} parti, összesen {sum(m.dd_indulas_utan - m.utesek for m in kev)} ütés, "
             f"{sum(m.imp_veszt for m in meresek)} IMP · több (a védők DD-hibája nem lehet): {tobb}",
             "", "A teljesíthetőből elbukott partik (az első ütésvesztő lap):"]
    for m in sorted(bukott, key=lambda m: -m.imp_veszt)[:30]:
        h = m.hibak[0] if m.hibak else {}
        sorok.append(f"  {m.tabla:<45} {m.kontraktus:<6} {m.utesek}/{m.cel} (DD {m.dd_indulas_utan})  "
                     f"{h.get('utes', '?')}. ütés {h.get('ules', '')} {h.get('lap', '')} → legjobb {','.join(h.get('legjobb', []))}")
    return "\n".join(sorok)


if __name__ == "__main__":
    sys.exit(main())
