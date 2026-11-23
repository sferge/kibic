"""A 40 partis mérés párhuzamosan: partinként külön folyamat (`minta.py --csak`).

Használat (a repó gyökeréből):

    python3 eszkozok/konyvelo/meres.py tanpartik/Pavlicek_felvevo --szal 24 --ki meres_B.txt
    python3 eszkozok/konyvelo/meres.py tanpartik/Pavlicek_felvevo --szal 24 --ki meres_C.txt \\
        --alap meres_B.txt --env KIBIC_K_FOGAS_VEDES=0

- `--szal`: ennyi parti fut egyszerre (egy parti legfeljebb ~3 GB memóriát és egy magot
  használ; a leglassabb ~8–10 perc);
- `--ki`: a kimenet (a `minta.py` sorai partinként, rendezve, és az összesítés);
- `--alap`: egy korábbi kimenet — a terv esélyének 5 pontnál nagyobb eltérései partinként;
- `--env`: környezeti változók a futáshoz (többször is megadható);
- `--vilag`, `--partik`: mint a `minta.py`-ban.

A mérés determinisztikus (rögzített véletlenmagok), így két gépen ugyanazt adja."""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

GYOKER = Path(__file__).resolve().parents[2]
SOR = re.compile(r"(\S+pbn#\d+)\s+(\S+)\s+terv\s+([\d.]+)%\s+DD\s+([\d.]+)%\s*(.*)")


def partik(konyvtar: Path, db: int) -> list[str]:
    sys.path.insert(0, str(GYOKER / "src"))
    from kibic.cli.jatekmeres import _pbn_olvas
    ki = []
    for ut in sorted(konyvtar.glob("*.pbn")):
        n = 0
        for j0 in _pbn_olvas(str(ut)):
            if n >= db:
                break
            if not j0.leosztas or not j0.kontraktus or not j0.felvevo or not j0.lapok:
                continue
            n += 1
            ki.append(f"{ut.name}#{j0.tabla_szam}")
    return ki


def egy(konyvtar: Path, azon: str, vilag: int, env: dict) -> tuple[str, str, float]:
    t0 = time.time()
    p = subprocess.run([sys.executable, str(GYOKER / "eszkozok/konyvelo/minta.py"), str(konyvtar),
                        "--vilag", str(vilag), "--csak", azon],
                       cwd=GYOKER, env=env, capture_output=True, text=True)
    sor = next((s for s in p.stdout.splitlines() if SOR.match(s)), None)
    if sor is None:
        sor = f"{azon}  HIBA: {(p.stderr.strip().splitlines() or ['?'])[-1][:200]}"
    return azon, sor, time.time() - t0


def beolvas(ut: Path) -> dict:
    d = {}
    for s in ut.read_text(encoding="utf-8").splitlines():
        m = SOR.match(s)
        if m:
            d[m[1]] = (float(m[3]), float(m[4]), m[2], m[5])
    return d


def osszesit(d: dict) -> str:
    def atl(f, i=0):
        x = [v[i] for k, v in d.items() if f(v)]
        return f"{sum(x) / len(x):.1f}%" if x else "—"
    return (f"{len(d)} parti: terv {atl(lambda v: True)} (szan {atl(lambda v: v[2].endswith('NT'))}, "
            f"szín {atl(lambda v: not v[2].endswith('NT'))}), DD {atl(lambda v: True, 1)}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("konyvtar")
    ap.add_argument("--szal", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    ap.add_argument("--ki", default="meres.txt")
    ap.add_argument("--alap", default=None)
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--vilag", type=int, default=30)
    ap.add_argument("--partik", type=int, default=2)
    a = ap.parse_args(argv)
    konyvtar = Path(a.konyvtar).resolve()
    env = dict(os.environ, PYTHONPATH=str(GYOKER / "src"), PYTHONHASHSEED="0")
    env.setdefault("KIBIC_TERVMUHELY_UTES_VILAG", str(a.vilag))
    for x in a.env:
        k, v = x.split("=", 1)
        env[k] = v
    lista = partik(konyvtar, a.partik)
    t0 = time.time()
    eredm = {}
    with ThreadPoolExecutor(max_workers=a.szal) as ex:
        for azon, sor, ido in ex.map(lambda z: egy(konyvtar, z, a.vilag, env), lista):
            eredm[azon] = sor
            print(f"{sor}   [{ido:.0f} s]", flush=True)
    ki = Path(a.ki)
    sorok = [eredm[z] for z in sorted(eredm)]
    ki.write_text("\n".join(sorok) + "\n", encoding="utf-8")
    d = beolvas(ki)
    osz = osszesit(d)
    with ki.open("a", encoding="utf-8") as f:
        f.write(f"\n{osz}; {time.time() - t0:.0f} s, {a.szal} szál; env: {' '.join(a.env) or '—'}\n")
    print(f"\n{osz}; {time.time() - t0:.0f} s")
    if a.alap:
        b = beolvas(Path(a.alap))
        print(f"alap ({a.alap}): {osszesit(b)}")
        for z in sorted(set(b) & set(d)):
            if abs(b[z][0] - d[z][0]) >= 5:
                print(f"  {z:<12} {b[z][0]:5.1f} → {d[z][0]:5.1f}   {d[z][3][:90]}")


if __name__ == "__main__":
    main()
