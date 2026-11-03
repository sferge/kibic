"""
Rangsor az alapjáték gyors esélyével (2026-11-02): ha az alapjáték esélye nagy,
az az első; ha kicsi, a speciális módok kerülnek előre (a szabályaik pontossága
szerint). Kétszeres keresztvalidáció: a küszöböt és a pontosságokat az egyik
félen választjuk, a másikon mérünk.

    PYTHONPATH=src python3 eszkozok/jatekmod_elemzes/rangsor3.py [--tempo]

    --tempo: az alapjáték esélye a vesztett ütésekkel együtt (a tartalékon belül;
    ehhez a pontos színtáblázat kell)
"""
import collections, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rangsor import GYOKER, modok, partik_cimkekkel                      # noqa: E402
from rangsor2 import szabalyok                              # noqa: E402

KUSZOBOK = [0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]


def rang(sz, p_alap, pont, kuszob):
    spec = sorted((m for m, v in sz.items() if v and m != "ALAPJATEK"), key=lambda m: -pont.get(m, 0))
    # ha az alapjáték esélye kicsi, a két legjobb speciális mód kerül előre (az
    # alapjáték csak a harmadik)
    return (["ALAPJATEK"] + spec) if p_alap >= kuszob else (spec[:2] + ["ALAPJATEK"] + spec[2:])


def main():
    sys.path.insert(0, str(GYOKER / "src"))
    from kibic.cli.jatekmeres import partik_fajlbol
    from kibic.cli.tervfelismeres import cimkek_pbnbol
    from kibic.domain import kovetkezo_ules
    from kibic.motor import terv as tv
    from kibic.motor import tervszintabla as tsz
    sorok = tv.tervsorok_yamlbol([str(GYOKER / "rendszerek" / "tervek")])
    adat = []
    pontos = 0.0
    for p, c in partik_cimkekkel():
        h = tv.helyzet_partibol(p)
        if c is None or h is None:
            continue
        g, _ = tv.jellemzok(h)
        k = p.kontraktus
        X = p.leosztas.kezek[k.felvevo].lapok
        Y = p.leosztas.kezek[kovetkezo_ules(k.felvevo, 2)].lapok
        D = {sz: {l.rang for l in X if l.szin == sz} for sz in "SHDC"}
        U = {sz: {l.rang for l in Y if l.szin == sz} for sz in "SHDC"}
        if "--tempo" in sys.argv:
            pa, ok = tsz.alapjatek_eselye_tempoval(D, U, 6 + k.szint)
        else:
            pa, ok = tsz.alapjatek_eselye(D, U, 6 + k.szint)
        pontos += ok
        adat.append((szabalyok(h, g, tv.felismeres(sorok, h)), modok(c), pa))
    n = len(adat)
    print(f"{n} parti; a színek {100*pontos/n:.0f}%-a a pontos táblázatból, a többi közelítés")
    # az alapjáték esélye a címke szerint
    for nev, f in (("alapjáték-címke", lambda ms: "ALAPJATEK" in ms), ("speciális mód", lambda ms: "ALAPJATEK" not in ms)):
        v = sorted(pa for _, ms, pa in adat if f(ms))
        print(f"  {nev:16s}: az alapjáték gyors esélyének mediánja {v[len(v)//2]:.2f}, "
              f"negyedei {v[len(v)//4]:.2f}–{v[3*len(v)//4]:.2f}")

    def pontossag(resz):
        tuz, jo = collections.Counter(), collections.Counter()
        for sz, ms, _ in resz:
            for m, v in sz.items():
                if v:
                    tuz[m] += 1
                    jo[m] += m in ms
        return {m: jo[m] / tuz[m] for m in tuz}

    def ertek(resz, pont, ku):
        return sum(bool(set(rang(sz, pa, pont, ku)[:2]) & ms) for sz, ms, pa in resz)

    e1 = e2 = 0
    modonkent = collections.defaultdict(lambda: [0, 0])
    for fold in (0, 1):
        tan = [x for i, x in enumerate(adat) if i % 2 == fold]
        tes = [x for i, x in enumerate(adat) if i % 2 != fold]
        pont = pontossag(tan)
        ku = max(KUSZOBOK, key=lambda q: ertek(tan, pont, q))
        print(f"  {fold}. fél: a választott küszöb {ku}  (az alapjáték e alatt a harmadik helyre kerül)")
        for sz, ms, pa in tes:
            r = rang(sz, pa, pont, ku)
            e1 += r[0] in ms
            e2 += bool(set(r[:2]) & ms)
            for m in ms:
                modonkent[m][0] += 1
                modonkent[m][1] += m in r[:2]
    print(f"\nelső hely {100*e1/n:.0f}%, első kettő {100*e2/n:.0f}%  (a gyors esély nélkül: 58%)")
    for m, (d, a2) in sorted(modonkent.items(), key=lambda x: -x[1][0]):
        print(f"  {m:16s} {d:5d}  az első kettőben {100*a2/d:4.0f}%")


if __name__ == "__main__":
    main()
