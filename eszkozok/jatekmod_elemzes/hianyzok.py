"""A jelöltekből kimaradt partik: melyik feltétel nem teljesül (2026-11-02)."""
import collections, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rangsor import GYOKER, modok, partik_cimkekkel                      # noqa: E402
from jeloltek import jelolt                                 # noqa: E402

def main():
    sys.path.insert(0, str(GYOKER / "src"))
    from kibic.cli.jatekmeres import partik_fajlbol
    from kibic.cli.tervfelismeres import cimkek_pbnbol
    from kibic.motor import terv as tv
    sorok = tv.tervsorok_yamlbol([str(GYOKER / "rendszerek" / "tervek")])
    adat = collections.defaultdict(list)
    for p, c in partik_cimkekkel():
        h = tv.helyzet_partibol(p)
        if c is None or h is None:
            continue
        g, sz = tv.jellemzok(h)
        j = jelolt(tv.felismeres(sorok, h))
        rov = {}
        if h.adu:
            for s in "SHDC":
                if s != h.adu:
                    rov[s] = (sum(1 for l in h.kez if l.szin == s), sum(1 for l in h.asztal if l.szin == s))
        for m in modok(c):
            adat[m].append((m in j, g, rov, p.azonosito, c))
    def felt(m, nev, f):
        rr = adat[m]
        ki = [x for x in rr if not x[0]]
        print(f"   {nev:58s} a kimaradtak {100*sum(1 for x in ki if f(x))/max(1,len(ki)):4.0f}%-ában igaz "
              f"(a megtaláltak {100*sum(1 for x in rr if x[0] and f(x))/max(1,len(rr)-len(ki)):4.0f}%)")
    print("KERESZTLOPÁS", len(adat["KERESZTLOPAS"]))
    felt("KERESZTLOPAS", "mindkét kézben 3+ adu", lambda x: x[1]["adu_d"] >= 3 and x[1]["adu_y"] >= 3)
    felt("KERESZTLOPAS", "a felvevő egy mellékszínben <=1", lambda x: any(d <= 1 for d, _ in x[2].values()))
    felt("KERESZTLOPAS", "az asztal egy mellékszínben <=1", lambda x: any(y <= 1 for _, y in x[2].values()))
    felt("KERESZTLOPAS", "  ... vagy <=2 (dubló is)", lambda x: any(d <= 2 for d, _ in x[2].values()) and any(y <= 2 for _, y in x[2].values()))
    felt("KERESZTLOPAS", "nincs közös rövid szín", lambda x: not any(d <= 1 and y <= 1 for d, y in x[2].values()))
    felt("KERESZTLOPAS", "adu együtt <= 8", lambda x: x[1]["adu_egyutt"] <= 8)
    print("VESZTŐCSERE", len(adat["VESZTOCSERE"]))
    felt("VESZTOCSERE", "vesztok_tobblet >= 1", lambda x: (x[1]["vesztok_tobblet"] or 0) >= 1)
    felt("VESZTOCSERE", "dobas >= 1", lambda x: x[1]["dobas"] >= 1)
    felt("VESZTOCSERE", "színjáték", lambda x: x[1]["felvetel"] == "SZIN")
    print("LOPÁS A RÖVID KÉZBEN", len(adat["LOPAS_ROVID"]))
    felt("LOPAS_ROVID", "lopas_rovid >= 1", lambda x: x[1]["lopas_rovid"] >= 1)
    felt("LOPAS_ROVID", "vesztok_tobblet >= 1", lambda x: (x[1]["vesztok_tobblet"] or 0) >= 1)
    felt("LOPAS_ROVID", "a rövid adus kéz rövidebb egy mellékszínben", lambda x: any(
        (d < y if x[1]["adu_d"] <= x[1]["adu_y"] else y < d) for d, y in x[2].values()))
    print("BESZORÍTÁS", len(adat["BESZORITAS"]))
    felt("BESZORITAS", "fenyegetes_mind >= 2", lambda x: x[1]["fenyegetes_mind"] >= 2)
    felt("BESZORITAS", "fenyegetes_mind >= 1", lambda x: x[1]["fenyegetes_mind"] >= 1)
    felt("BESZORITAS", "hiany_terv <= 2", lambda x: x[1]["hiany_terv"] <= 2)
    print("ASZTALFORDÍTÁS", len(adat["ASZTALFORDITAS"]))
    felt("ASZTALFORDITAS", "asztal adu >= 3", lambda x: x[1]["adu_y"] >= 3)
    felt("ASZTALFORDITAS", "a rövid adu >= 3 (bármelyik kéz)", lambda x: x[1]["rovid_adu"] >= 3)
    felt("ASZTALFORDITAS", "adu_felso >= 2", lambda x: x[1]["adu_felso"] >= 2)
    felt("ASZTALFORDITAS", "felvevő >= asztal adu", lambda x: x[1]["adu_d"] >= x[1]["adu_y"])
    print("KIMAGASÍTÁS", len(adat["KIMAGASITAS"]))
    felt("KIMAGASITAS", "tobblet_osszes >= 1", lambda x: x[1]["tobblet_osszes"] >= 1)
    felt("KIMAGASITAS", "lopasos_fenyegetes >= 1", lambda x: x[1]["lopasos_fenyegetes"] >= 1)

if __name__ == "__main__":
    main()
