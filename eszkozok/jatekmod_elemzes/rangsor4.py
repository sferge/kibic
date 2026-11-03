"""
Rangsor a speciális módok gyors esélyével (2026-11-03): a jelölt speciális módok
a NYERESÉGÜK szerint (a mód esélye - az alap esélye, tervmodesely), az alapjáték
a küszöb (az alapjáték esélye a színtáblázatból) szerint előre vagy a harmadik
helyre. Kétszeres keresztvalidáció: a küszöböket az egyik félen választjuk, a
másikon mérünk.

    PYTHONPATH=src python3 eszkozok/jatekmod_elemzes/rangsor4.py --pbn <fájl> [--szalak 32] [--alap mod|tabla|tempo] [--mind]

    --alap   az alapjáték esélye a küszöbhöz: mod = a módok közös modellje (alap),
             tabla = a színtáblázat (rangsor3), tempo = a táblázat a vesztésekkel
    --mind   minden mód jelölt (a felismerő szabályok nélkül)
    --kalibral  a módok nem a nyereségük nagysága szerint, hanem a nyereségük sávjához
             tartozó mért pontosság szerint jönnek (a tanuló félen mérve); az alapjáték is
             így, az esélye sávja szerint — a küszöbök helyett

Előtte a színtáblázat a kezelések kimeneteivel (különben a mindent látó közelítés):
    PYTHONPATH=src python3 -m kibic.cli.szintabla --pbn <fájl> --kimenet

A partinkénti esélyek egy gyorsítótárba kerülnek (~/.cache/kibic/modesely.pkl,
a forrás és a parti szerint), így az újrafuttatás azonnali.
"""
import collections, hashlib, os, pickle, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from rangsor import GYOKER, deal_szoveg, modok, partik_cimkekkel     # noqa: E402
from rangsor2 import szabalyok                                      # noqa: E402

sys.path.insert(0, str(GYOKER / "src"))
KUSZOBOK = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01]
NYERESEG_KUSZOB = [0.0, 0.01, 0.02, 0.05, 0.1]
SPEC = ["KIMAGASITAS", "LOPAS_ROVID", "ASZTALFORDITAS", "KERESZTLOPAS", "VEGJATEK", "BESZORITAS",
        "VESZTOCSERE", "ADUPUCCS"]


def _tar_ut():
    from kibic.motor import tervmodesely, tervszinkezeles
    from kibic.motor import tervszintabla as tsz
    h = hashlib.sha1()
    for m in (tervmodesely, tervszinkezeles, tsz):
        h.update(Path(m.__file__).read_bytes())
    h.update(str(len(tsz.kimenet_tabla())).encode())       # a kimenet-táblázat mérete is
    return Path.home() / ".cache" / "kibic" / f"modesely-{h.hexdigest()[:10]}.pkl"


def _szamol(arg):
    D, U, adu, cel = arg
    from kibic.motor import tervmodesely as tm
    e = tm.mod_eselyek(D, U, adu, cel)
    tm.gyorsitotar_urites()
    return e


def rang(jel, p_alap, ny, pont, ku, nyk):
    """jel: a jelölt speciális módok; ny: {mód: nyereség}."""
    spec = sorted(jel, key=lambda m: (-ny.get(m, 0.0), -pont.get(m, 0.0)))
    eros = [m for m in spec if ny.get(m, 0.0) > nyk]
    gyenge = [m for m in spec if m not in eros]
    if p_alap >= ku:
        return ["ALAPJATEK"] + eros + gyenge
    return eros[:2] + ["ALAPJATEK"] + eros[2:] + gyenge


NY_SAV = [0.0, 0.02, 0.1, 0.25]          # a nyereség sávjai (felső határ nélkül az utolsó)
ALAP_SAV = [0.0, 0.2, 0.4, 0.6, 0.8, 0.95]


def sav(x, hatarok):
    i = 0
    for j, h in enumerate(hatarok):
        if x > h or (j == 0 and x >= h):
            i = j
    return i if x > 0 or hatarok is ALAP_SAV else -1


def kalibral(resz, a=5.0):
    """{(mód, sáv): simított pontosság} — a tanuló félen: ha a mód jelölt és a nyeresége
    (az alapjátéknál az esélye) ebbe a sávba esik, milyen gyakran az a címke."""
    tuz, jo, tuz_m, jo_m = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    for jel, ms, pa, ny in resz:
        for m in ["ALAPJATEK"] + list(jel):
            b = sav(pa, ALAP_SAV) if m == "ALAPJATEK" else sav(ny.get(m, 0.0), NY_SAV)
            tuz[(m, b)] += 1
            jo[(m, b)] += m in ms
            tuz_m[m] += 1
            jo_m[m] += m in ms
    elo = {m: jo_m[m] / tuz_m[m] for m in tuz_m}
    return {k: (jo[k] + a * elo[k[0]]) / (tuz[k] + a) for k in tuz}, elo


def rang_kal(jel, pa, ny, kal):
    k, elo = kal

    def pont(m):
        b = sav(pa, ALAP_SAV) if m == "ALAPJATEK" else sav(ny.get(m, 0.0), NY_SAV)
        return k.get((m, b), elo.get(m, 0.0))
    return sorted(["ALAPJATEK"] + list(jel), key=lambda m: -pont(m))


def main():
    from kibic.domain import kovetkezo_ules
    from kibic.motor import terv as tv
    from kibic.motor import tervszintabla as tsz
    szalak = int(sys.argv[sys.argv.index("--szalak") + 1]) if "--szalak" in sys.argv else (os.cpu_count() or 1)
    mind = "--mind" in sys.argv
    sorok = tv.tervsorok_yamlbol([str(GYOKER / "rendszerek" / "tervek")])
    ut = _tar_ut()
    try:
        tar = pickle.loads(ut.read_bytes())
    except Exception:              # noqa: BLE001
        tar = {}
    adat, feladat = [], []
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
        alap_mod = sys.argv[sys.argv.index("--alap") + 1] if "--alap" in sys.argv else "mod"
        if alap_mod == "tempo":
            pa, _ = tsz.alapjatek_eselye_tempoval(D, U, 6 + k.szint)
        elif alap_mod == "tabla":
            pa, _ = tsz.alapjatek_eselye(D, U, 6 + k.szint)
        else:
            pa = None
        kulcs = (deal_szoveg(p), k.felvevo, k.szint, k.szin)
        sz = szabalyok(h, g, tv.felismeres(sorok, h))
        jel = [m for m in SPEC if mind or sz.get(m)]
        adat.append([kulcs, jel, modok(c), pa])
        if kulcs not in tar:
            feladat.append((kulcs, (D, U, None if k.szin == "NT" else k.szin, 6 + k.szint)))
    n = len(adat)
    if feladat:
        print(f"{n} parti; most számolandó {len(feladat)} ({szalak} szál)", flush=True)
        t0 = time.time()
        with ProcessPoolExecutor(max_workers=szalak) as pool:
            for i, (kk, e) in enumerate(zip([k for k, _ in feladat],
                                            pool.map(_szamol, [a for _, a in feladat], chunksize=1))):
                tar[kk] = e
                if (i + 1) % 50 == 0 or i + 1 == len(feladat):
                    ut.parent.mkdir(parents=True, exist_ok=True)
                    ut.write_bytes(pickle.dumps(tar))
                    el = time.time() - t0
                    print(f"  {i+1}/{len(feladat)}  {el:.0f} s  (még kb. {el/(i+1)*(len(feladat)-i-1):.0f} s)",
                          flush=True)
    sor = []
    for kulcs, jel, ms, pa in adat:
        e = tar[kulcs]
        if pa is None:
            pa = e["ALAP"]
        ny = {m: (e[m][1] if m in e else 0.0) for m in SPEC}
        sor.append((jel, ms, pa, ny))

    # a nyereség a címke szerint
    kt = tsz.kimenet_tabla()
    print(f"{n} parti{' (minden mód jelölt)' if mind else ''}; a kimenet-táblázatban {len(kt)} szín")
    for nev, f in (("alapjáték-címke", lambda ms: "ALAPJATEK" in ms), ("speciális mód", lambda ms: "ALAPJATEK" not in ms)):
        v = sorted(x[2] for x in sor if f(x[1]))
        if v:
            print(f"  {nev:16s}: az alapjáték esélyének mediánja {v[len(v)//2]:.2f}, "
                  f"negyedei {v[len(v)//4]:.2f}–{v[3*len(v)//4]:.2f}")
    print("\nA módok nyeresége (átlag), a címke szerint:")
    fej = ["ALAPJATEK"] + SPEC[:6]
    print(f"{'címke':16s} {'db':>4} " + " ".join(f"{m[:6]:>7s}" for m in SPEC[:6]))
    for cim in fej:
        r = [x for x in sor if cim in x[1]]
        if not r:
            continue
        print(f"{cim:16s} {len(r):4d} " + " ".join(f"{sum(x[3][m] for x in r)/len(r):7.3f}" for m in SPEC[:6]))

    def pontossag(resz):
        tuz, jo = collections.Counter(), collections.Counter()
        for jel, ms, _, _ in resz:
            for m in jel:
                tuz[m] += 1
                jo[m] += m in ms
        return {m: jo[m] / tuz[m] for m in tuz}

    def ertek(resz, pont, ku, nyk):
        return sum(bool(set(rang(j, pa, ny, pont, ku, nyk)[:2]) & ms) for j, ms, pa, ny in resz)

    e1 = e2 = e3 = 0
    modonkent = collections.defaultdict(lambda: [0, 0])
    print()
    for fold in (0, 1):
        tan = [x for i, x in enumerate(sor) if i % 2 == fold]
        tes = [x for i, x in enumerate(sor) if i % 2 != fold]
        pont = pontossag(tan)
        if "--kalibral" in sys.argv:
            kal = kalibral(tan)
        else:
            ku, nyk = max(((q, d) for q in KUSZOBOK for d in NYERESEG_KUSZOB), key=lambda x: ertek(tan, pont, *x))
            print(f"  {fold}. fél: az alapjáték küszöbe {ku}, a nyereség küszöbe {nyk}")
        for j, ms, pa, ny in tes:
            r = rang_kal(j, pa, ny, kal) if "--kalibral" in sys.argv else rang(j, pa, ny, pont, ku, nyk)
            e1 += r[0] in ms
            e2 += bool(set(r[:2]) & ms)
            e3 += bool(set(r[:3]) & ms)
            for m in ms:
                modonkent[m][0] += 1
                modonkent[m][1] += m in r[:2]
    print(f"\nelső hely {100*e1/n:.0f}%, első kettő {100*e2/n:.0f}%, első három {100*e3/n:.0f}%")
    if "--kalibral" in sys.argv:
        k, elo = kalibral(sor)
        print("\na mért pontosság sávonként (az összes partin; sáv: " +
              f"nyereség {NY_SAV}, alapjáték esélye {ALAP_SAV}):")
        for m in ["ALAPJATEK"] + SPEC:
            sorok_ = sorted((b, v) for (mm, b), v in k.items() if mm == m)
            if sorok_:
                print(f"  {m:16s} " + "  ".join(f"{b}:{v:.2f}" for b, v in sorok_))
    for m, (d, a2) in sorted(modonkent.items(), key=lambda x: -x[1][0]):
        print(f"  {m:16s} {d:5d}  az első kettőben {100*a2/d:4.0f}%")


if __name__ == "__main__":
    main()
