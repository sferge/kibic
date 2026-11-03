"""
Játékmód-rangsor a kezekből (2026-11-02): mennyire ismerhető fel a Pavlicek-partik
játékmódja a felvevő + asztal kezéből (az indulás előtt)? A mérce: a két legesélyesebb
mód között ott van-e a szerző címkéje szerinti mód.

A pontozás „mintázat”: naiv Bayes a kezdőjegyeken és a tervtár felismerésén
(rendszerek/tervek/alap.yaml), kétszeres keresztvalidációval (a páros partikon tanul,
a páratlanokon mér, és fordítva) — a mért szám tehát nem a tanult partikon született.

    PYTHONPATH=src python3 eszkozok/jatekmod_elemzes/rangsor.py
"""
import collections
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jegyek import jegyek                                   # noqa: E402

GYOKER = Path(__file__).resolve().parents[2]
# a címkézett partik: --pbn <fájlok vagy könyvtárak> (alap: tanpartik/pavlicek_teljes)
PBN = [GYOKER / "tanpartik" / "pavlicek_teljes"]


def pbn_utak() -> list[str]:
    """A --pbn utáni utak (a parancssorból), különben az alapértelmezett."""
    a = sys.argv[1:]
    if "--pbn" in a:
        i = a.index("--pbn")
        utak = []
        for x in a[i + 1:]:
            if x.startswith("--"):
                break
            utak.append(x)
        return utak
    return [str(u) for u in PBN]


def partik_cimkekkel():
    """(parti, „Play:” címkék) minden megadott PBN-fájlból (a címke None, ha nincs)."""
    sys.path.insert(0, str(GYOKER / "src"))
    from kibic.cli.jatekmeres import fajlok_kibontasa, partik_fajlbol
    from kibic.cli.tervfelismeres import cimkek_pbnbol
    for ut in fajlok_kibontasa(pbn_utak(), ".pbn"):
        cimkek = cimkek_pbnbol(ut)
        for i, p in enumerate(partik_fajlbol([ut], "IMP")):
            yield p, (cimkek[i] if i < len(cimkek) else None)

MOD_CIMKE = {
    "KIMAGASITAS": ["Set up dummy’s suit", "Establish side suit", "Set up suit at notrump"],
    "LOPAS_ROVID": ["Ruff in short hand", "Delay drawing trumps", "Ruffing with 4-4 fit"],
    "KERESZTLOPAS": ["Crossruff"],
    "ASZTALFORDITAS": ["Dummy reversal"],
    "VESZTOCSERE": ["Loser-on-loser play", "Obtain early discard", "Shed loser to avert tap"],
    "VEGJATEK": ["Elimination technique", "Throw-in play", "Ruff/discard endplay", "Trump endplay"],
    "BESZORITAS": ["squeeze", "Vienna coup", "Isolate threat", "Correct loser count"],
    "ADUPUCCS": ["Trump coup"],
}


def modok(cimkek):
    sz = "; ".join(cimkek)
    m = {mod for mod, cs in MOD_CIMKE.items() if any(c in sz for c in cs)}
    return m or {"ALAPJATEK"}


def deal_szoveg(p):
    ki = []
    for u in "NESW":
        lapok = p.leosztas.kezek[u].lapok
        ki.append(".".join("".join(sorted((l.ertek for l in lapok if l.szin == s),
                                          key=lambda c: -"23456789TJQKA".index(c))) for s in "SHDC"))
    return "N:" + " ".join(ki)


import os
VALTOZAT = os.environ.get("RANGSOR_JEGYEK", "mind")   # mind / kez / tervtar


def diszkret(f, fel, eleg):
    """A jegyek diszkrét értékei (a naiv Bayes „szavai”)."""
    sz = f["szan"]
    w = [f"szan={sz}", f"szint={min(f['szint'], 6)}", f"hcp={min(32, max(20, f['hcp'])) // 3}",
         f"hiany={min(f['hiany'], 5)}", f"szingli={min(f['szingli_db'], 3)}",
         f"hosszu={min(max(f['hosszu_szin'], 6), 9)}", f"tobblet={min(f['tobblet'], 4)}",
         f"kontroll={min(f['kontroll'], 10) // 2}"]
    if not sz:
        w += [f"adu={min(max(f['adu_egyutt'], 7), 10)}", f"adu_rovid={min(f['adu_rovid'], 4)}",
              f"rovid_fig={min(f['rovid_adu_figura'], 3)}", f"kereszt={f['keresztlop_szerk']}",
              f"egyirany={f['egy_iranyu_lopas']}", f"elo={min(f['eloszlas_pont'], 6)}",
              f"aduAK8={f['adu_8_AK_D_nelkul']}", f"egyforma={f['adu_egyforma']}"]
    if VALTOZAT == "kez":
        return w
    tt = [f"tervtar:{t}" for t in fel] + [f"eleg:{t}" for komb in eleg.get("elegendo", []) for t in komb]
    if VALTOZAT == "tervtar":
        return [w[0]] + tt
    return w + tt


def main():
    sys.path.insert(0, str(GYOKER / "src"))
    from kibic.cli.jatekmeres import partik_fajlbol
    from kibic.cli.tervfelismeres import cimkek_pbnbol
    from kibic.motor import terv as tv
    sorok = tv.tervsorok_yamlbol([str(GYOKER / "rendszerek" / "tervek")])
    adat = []
    for p, c in partik_cimkekkel():
        h = tv.helyzet_partibol(p)
        if c is None or h is None or p.kontraktus is None:
            continue
        k = p.kontraktus
        szerz = f"{k.szint}{'N' if k.szin == 'NT' else k.szin}"
        try:
            f = jegyek(deal_szoveg(p), k.felvevo, szerz)
            fel = tv.felismeres(sorok, h)
            el = tv.elegendo(sorok, h, fel)
        except Exception:
            continue
        adat.append((diszkret(f, fel, el), modok(c), f["szan"]))
    print(len(adat), "címkézett parti")
    oszt = collections.Counter(m for _, ms, _ in adat for m in ms)
    print("módok (címke szerint):", dict(oszt.most_common()))

    def tanul(resz):
        n = collections.Counter(); szo = collections.defaultdict(collections.Counter)
        for w, ms, _ in resz:
            for m in ms:
                n[m] += 1
                szo[m].update(set(w))
        return n, szo

    # egy jegy lehetséges értékeinek száma (a simításhoz): jegy = a „név=érték” neve;
    # a tervtár-jelzők kétértékűek (van / nincs)
    ertekek = collections.defaultdict(set)
    for w, _, _ in adat:
        for x in w:
            ertekek[x.split("=")[0] if "=" in x else x].add(x)
    jelzok = sorted({x for w, _, _ in adat for x in w if "=" not in x})

    def rangsor(model, w, szan):
        n, szo = model
        N = sum(n.values())
        w = set(w)
        pont = {}
        for m in n:
            if szan and m in ("LOPAS_ROVID", "KERESZTLOPAS", "ASZTALFORDITAS", "VESZTOCSERE", "ADUPUCCS"):
                continue                               # színjátékos mód szanban nem jöhet szóba
            s = math.log(n[m] / N)
            for x in w:
                if "=" in x:                           # kategória: értékek száma szerinti simítás
                    V = len(ertekek[x.split("=")[0]])
                    s += math.log((szo[m][x] + 1.0) / (n[m] + V))
            for x in jelzok:                           # kétértékű jelző: van vagy nincs
                p1 = (szo[m][x] + 1.0) / (n[m] + 2.0)
                s += math.log(p1 if x in w else 1 - p1)
            pont[m] = s
        return sorted(pont, key=lambda m: -pont[m])

    talal1 = talal2 = 0
    modonkent = collections.defaultdict(lambda: [0, 0, 0])
    for fold in (0, 1):
        tanulo = [x for i, x in enumerate(adat) if i % 2 == fold]
        teszt = [x for i, x in enumerate(adat) if i % 2 != fold]
        model = tanul(tanulo)
        for w, ms, szan in teszt:
            r = rangsor(model, w, szan)
            t1, t2 = r[0] in ms, bool(set(r[:2]) & ms)
            talal1 += t1; talal2 += t2
            for m in ms:
                modonkent[m][0] += 1
                modonkent[m][1] += m == r[0]
                modonkent[m][2] += m in r[:2]
    n = len(adat)
    print(f"\nösszesen: az első helyen {100*talal1/n:.0f}%, az első kettőben {100*talal2/n:.0f}%"
          f"  (vak tipp „mindig ALAPJÁTÉK + a leggyakoribb”: "
          f"{100*sum(1 for _, ms, _ in adat if ms & {'ALAPJATEK', oszt.most_common(2)[1][0]})/n:.0f}%)")
    print(f"\n{'mód':16s} {'partik':>6} {'1. hely':>8} {'első kettő':>11}")
    for m, (db, e1, e2) in sorted(modonkent.items(), key=lambda x: -x[1][0]):
        print(f"{m:16s} {db:6d} {100*e1/db:7.0f}% {100*e2/db:10.0f}%")


if __name__ == "__main__":
    main()
