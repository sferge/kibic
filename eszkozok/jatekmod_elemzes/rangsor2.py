"""
Jelölt módok javított felismerő szabályokkal, és rangsoruk a szabályok mért
pontossága szerint (2026-11-02). Kétszeres keresztvalidáció: a pontosságot a
partik egyik felén mérjük, a rangsort a másikon értékeljük.

    PYTHONPATH=src python3 eszkozok/jatekmod_elemzes/rangsor2.py [--regi]
"""
import collections, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rangsor import GYOKER, modok, partik_cimkekkel                      # noqa: E402
from jeloltek import jelolt as regi_jelolt                  # noqa: E402


def szabalyok(h, g, fel):
    """{mód: igaz-e} — a javított felismerés."""
    ki = {"ALAPJATEK": True,
          "KIMAGASITAS": "KIMAGASITAS" in fel,
          "VESZTOCSERE": "VESZTOCSERE" in fel,
          "VEGJATEK": "VEGJATEK" in fel,
          "BESZORITAS": "BESZORITAS" in fel or (g["fenyegetes_mind"] >= 2 and g["hiany_terv"] <= 3)}
    if not h.adu:
        return ki
    hossz = {s: (sum(1 for l in h.kez if l.szin == s), sum(1 for l in h.asztal if l.szin == s)) for s in "SHDC"}
    ad, ay = hossz[h.adu]
    oldal = [s for s in "SHDC" if s != h.adu]
    # a rövid adus kéz (egyenlőnél bármelyik): rövidebb egy mellékszínben, mint a másik kéz
    def rovidebb(kez_i):
        return any(hossz[s][kez_i] < hossz[s][1 - kez_i] for s in oldal)
    if ad == ay:
        lopas = ad >= 1 and (rovidebb(0) or rovidebb(1))
    else:
        r = 1 if ay < ad else 0
        lopas = hossz[h.adu][r] >= 1 and rovidebb(r)
    ki["LOPAS_ROVID"] = lopas
    # keresztlopás: mindkét kézben 3+ adu; két irányú rövidség (dubló is), aszimmetrikusan
    ki["KERESZTLOPAS"] = ad >= 3 and ay >= 3 and any(
        hossz[s][0] <= 2 and hossz[s][1] >= 3 and any(hossz[t][1] <= 2 and hossz[t][0] >= 3
                                                      for t in oldal if t != s) for s in oldal)
    # asztalfordítás: a rövid adu 3+, erős adu; a HOSSZÚ adus kéz rövid (<=1) egy
    # mellékszínben, amelyből a rövid adus kéznek 3+ lapja van
    hosszu_i = 0 if ad >= ay else 1
    ki["ASZTALFORDITAS"] = min(ad, ay) >= 3 and g["adu_felso"] >= 2 and any(
        hossz[s][hosszu_i] <= 1 and hossz[s][1 - hosszu_i] >= 3 for s in oldal)
    return ki


def main():
    regi = "--regi" in sys.argv
    sys.path.insert(0, str(GYOKER / "src"))
    from kibic.cli.jatekmeres import partik_fajlbol
    from kibic.cli.tervfelismeres import cimkek_pbnbol
    from kibic.motor import terv as tv
    sorok = tv.tervsorok_yamlbol([str(GYOKER / "rendszerek" / "tervek")])
    adat = []
    for p, c in partik_cimkekkel():
        h = tv.helyzet_partibol(p)
        if c is None or h is None:
            continue
        g, _ = tv.jellemzok(h)
        fel = tv.felismeres(sorok, h)
        if regi:
            j = regi_jelolt(fel)
            sz = {m: m in j for m in ["ALAPJATEK", "KIMAGASITAS", "VESZTOCSERE", "VEGJATEK", "BESZORITAS",
                                      "LOPAS_ROVID", "KERESZTLOPAS", "ASZTALFORDITAS"]}
        else:
            sz = szabalyok(h, g, fel)
        adat.append((sz, modok(c)))
    n = len(adat)
    lef = sum(1 for sz, ms in adat if any(sz.get(m) for m in ms))
    db = sum(sum(sz.values()) for sz, _ in adat) / n
    print(f"{'régi' if regi else 'javított'} szabályok: {n} parti; jelölt átlag {db:.1f}; "
          f"a címke módja a jelöltek közt {100*lef/n:.0f}%")

    def pontossag(resz):
        tuz, jo = collections.Counter(), collections.Counter()
        for sz, ms in resz:
            for m, v in sz.items():
                if v:
                    tuz[m] += 1
                    jo[m] += m in ms
        return {m: jo[m] / tuz[m] for m in tuz if tuz[m]}

    e1 = e2 = 0
    modonkent = collections.defaultdict(lambda: [0, 0, 0, 0])
    for fold in (0, 1):
        pont = pontossag([x for i, x in enumerate(adat) if i % 2 == fold])
        for i, (sz, ms) in enumerate(adat):
            if i % 2 == fold:
                continue
            rang = sorted((m for m, v in sz.items() if v), key=lambda m: -pont.get(m, 0))
            e1 += rang[0] in ms
            e2 += bool(set(rang[:2]) & ms)
            for m in ms:
                modonkent[m][0] += 1
                modonkent[m][1] += bool(sz.get(m))
                modonkent[m][2] += rang[0] == m
                modonkent[m][3] += m in rang[:2]
    print(f"rangsor a szabályok pontossága szerint: első hely {100*e1/n:.0f}%, első kettő {100*e2/n:.0f}%")
    print(f"\n{'mód':16s} {'partik':>6} {'jelölt':>7} {'1. hely':>8} {'első kettő':>11}   a szabály pontossága")
    pont = pontossag(adat)
    for m, (d, j, a1, a2) in sorted(modonkent.items(), key=lambda x: -x[1][0]):
        print(f"{m:16s} {d:6d} {100*j/d:6.0f}% {100*a1/d:7.0f}% {100*a2/d:10.0f}%   {100*pont.get(m,0):4.0f}%")


if __name__ == "__main__":
    main()
