"""A tervtár felismeréséből a jelölt módok halmaza: mekkora, és benne van-e a
szerző címkéje szerinti mód (2026-11-02)."""
import collections, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rangsor import PBN, GYOKER, modok                      # noqa: E402

VALT = {"LOPAS_ROVID_KEZBEN": "LOPAS_ROVID", "ASZTALFORDITAS": "ASZTALFORDITAS",
        "KERESZTLOPAS": "KERESZTLOPAS"}


def jelolt(fel):
    ki = {"ALAPJATEK"}
    for t, valt in fel.items():
        if t == "LOPAS":
            ki |= {VALT[v] for v in valt if v in VALT}
        elif t in ("KIMAGASITAS", "VESZTOCSERE", "VEGJATEK", "BESZORITAS"):
            ki.add(t)
    return ki


def main():
    sys.path.insert(0, str(GYOKER / "src"))
    from kibic.cli.jatekmeres import partik_fajlbol
    from kibic.cli.tervfelismeres import cimkek_pbnbol
    from kibic.motor import terv as tv
    sorok = tv.tervsorok_yamlbol([str(GYOKER / "rendszerek" / "tervek")])
    cimkek = cimkek_pbnbol(str(PBN))
    n = bent = 0
    meret = collections.Counter()
    modonkent = collections.defaultdict(lambda: [0, 0])
    for i, p in enumerate(partik_fajlbol([str(PBN)], "IMP")):
        c = cimkek[i] if i < len(cimkek) else None
        h = tv.helyzet_partibol(p)
        if c is None or h is None:
            continue
        j = jelolt(tv.felismeres(sorok, h))
        ms = modok(c)
        n += 1
        meret[len(j)] += 1
        bent += bool(j & ms)
        for m in ms:
            modonkent[m][0] += 1
            modonkent[m][1] += m in j
    print(f"{n} parti; a jelöltek száma átlagosan {sum(k*v for k, v in meret.items())/n:.1f} "
          f"(eloszlás {dict(sorted(meret.items()))}); a címke módja a jelöltek közt: {100*bent/n:.0f}%")
    for m, (db, b) in sorted(modonkent.items(), key=lambda x: -x[1][0]):
        print(f"  {m:16s} {db:5d}  a jelöltek közt {100*b/db:4.0f}%")


if __name__ == "__main__":
    main()
