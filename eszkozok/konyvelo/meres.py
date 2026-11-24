"""A 40 partis mérés párhuzamosan: partinként külön folyamat (`minta.py --csak`).

Használat (a repó gyökeréből):

    python3 eszkozok/konyvelo/meres.py tanpartik/Pavlicek_felvevo --szal 24 --ki meres_B.txt
    python3 eszkozok/konyvelo/meres.py tanpartik/Pavlicek_felvevo --szal 24 --ki meres_C.txt \\
        --alap meres_B.txt --env KIBIC_K_FOGAS_VEDES=0

- `--szal`: ennyi parti fut egyszerre (egy parti legfeljebb ~3 GB memóriát és egy magot
  használ; a leglassabb ~8–10 perc);
- `--ki`: a kimenet. Minden futás a fájl VÉGÉRE kerül (2026-11-24): egy fejléc (dátum, a kód
  verziója, a beállítások és a futáskor érvényes `KIBIC_*` változók), a `minta.py` sorai
  partinként, rendezve, az összesítés, és ha van `--alap`, az eltérések. `--felulir`: a régi
  viselkedés (a fájl újraírása);
- `--alap`: egy korábbi kimenet — a terv esélyének 5 pontnál nagyobb eltérései partinként.
  A fájl utolsó futása; egy korábbi futás sorszámmal: `--alap meres.txt#2` (1-től; a negatív
  a végéről számol: `#-2` az utolsó előtti). A régi, fejléc nélküli fájl egy futás;
- `--env`: környezeti változók a futáshoz (többször is megadható);
- `--vilag`, `--partik`: mint a `minta.py`-ban.

A mérés determinisztikus (rögzített véletlenmagok), így két gépen ugyanazt adja."""
from __future__ import annotations

import argparse
import datetime
import os
import platform
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


FEJ = "=== mérés "                 # egy futás fejlécének eleje


def futasok(ut: Path) -> list[list[str]]:
    """A fájl futásai (soraik); a fejléc nélküli (régi) fájl egyetlen futás."""
    blokkok: list[list[str]] = []
    for s in ut.read_text(encoding="utf-8").splitlines():
        if s.startswith(FEJ) or not blokkok:
            blokkok.append([])
        blokkok[-1].append(s)
    return [b for b in blokkok if any(SOR.match(x) for x in b)]


def beolvas(ut: Path | str) -> dict:
    """Egy futás partisorai: `fajl` (az utolsó futás) vagy `fajl#n` (az n-edik, 1-től;
    negatív: a végéről)."""
    ut = str(ut)
    n = -1
    if "#" in ut and re.fullmatch(r"-?\d+", ut.rsplit("#", 1)[1]):
        ut, sz = ut.rsplit("#", 1)
        n = int(sz) - 1 if int(sz) > 0 else int(sz)
    blokkok = futasok(Path(ut))
    d = {}
    for s in (blokkok[n] if blokkok else []):
        m = SOR.match(s)
        if m:
            d[m[1]] = (float(m[3]), float(m[4]), m[2], m[5])
    return d


def _git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=GYOKER, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    except Exception:                                    # noqa: BLE001
        return ""


TITOK = re.compile(r"SECRET|PASS|TOKEN|KEY", re.I)


def fejlec(a, env: dict, argv: list[str]) -> str:
    """A futás fejléce: dátum, kód, beállítások, a `KIBIC_*` változók (a titkok nélkül)."""
    most = datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")
    commit = _git("rev-parse", "--short", "HEAD") or "?"
    ag = _git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    valt = _git("status", "--porcelain", "--untracked-files=no")
    kibic = sorted((k, v) for k, v in env.items() if k.startswith("KIBIC_") and not TITOK.search(k))
    sorok = [f"{FEJ}{most} ===",
             f"kód: {commit} ({ag}){', helyi módosításokkal' if valt else ''}",
             f"gép: {platform.node()}, python {platform.python_version()}",
             f"parancs: meres.py {' '.join(argv)}",
             f"beállítások: könyvtár {a.konyvtar}, {a.partik} parti/fájl, {a.vilag} világ, {a.szal} szál",
             f"megadott env: {' '.join(a.env) or '—'}",
             "KIBIC_* a futásban: " + (", ".join(f"{k}={v}" for k, v in kibic) or "—")]
    return "\n".join(sorok)


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
    ap.add_argument("--felulir", action="store_true", help="a kimenet újraírása (nem hozzáfűzés)")
    argv = sys.argv[1:] if argv is None else argv
    a = ap.parse_args(argv)
    konyvtar = Path(a.konyvtar).resolve()
    env = dict(os.environ, PYTHONPATH=str(GYOKER / "src"), PYTHONHASHSEED="0")
    env.setdefault("KIBIC_TERVMUHELY_UTES_VILAG", str(a.vilag))
    for x in a.env:
        k, v = x.split("=", 1)
        env[k] = v
    lista = partik(konyvtar, a.partik)
    fej = fejlec(a, env, argv)
    print(fej, flush=True)
    t0 = time.time()
    eredm = {}
    with ThreadPoolExecutor(max_workers=a.szal) as ex:
        for azon, sor, ido in ex.map(lambda z: egy(konyvtar, z, a.vilag, env), lista):
            eredm[azon] = sor
            print(f"{sor}   [{ido:.0f} s]", flush=True)
    ki = Path(a.ki)
    sorok = [eredm[z] for z in sorted(eredm)]
    d = {}
    for s in sorok:
        m = SOR.match(s)
        if m:
            d[m[1]] = (float(m[3]), float(m[4]), m[2], m[5])
    osz = f"{osszesit(d)}; {time.time() - t0:.0f} s, {a.szal} szál; env: {' '.join(a.env) or '—'}"
    vege = [osz]
    if a.alap:
        b = beolvas(a.alap)
        vege.append(f"alap ({a.alap}): {osszesit(b)}")
        for z in sorted(set(b) & set(d)):
            if abs(b[z][0] - d[z][0]) >= 5:
                vege.append(f"  {z:<12} {b[z][0]:5.1f} → {d[z][0]:5.1f}   {d[z][3][:90]}")
    blokk = "\n".join([fej, *sorok, "", *vege]) + "\n"
    if a.felulir or not ki.exists() or not ki.read_text(encoding="utf-8").strip():
        ki.write_text(blokk, encoding="utf-8")
    else:
        with ki.open("a", encoding="utf-8") as f:
            f.write("\n" + blokk)
    print("\n" + "\n".join(vege))


if __name__ == "__main__":
    main()
