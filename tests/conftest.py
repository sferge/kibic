"""
Pytest-beállítások.

Két dolgot csinál:
 1. Elérhetővé teszi a `src`-t akkor is, ha a csomag nincs telepítve.
 2. BETÖLTI A .env FÁJLT — a pytest ezt magától NEM teszi meg
    (nincs beépített dotenv-támogatása), ezért a KIBIC_USER/KIBIC_PASS
    változók egyébként hiányoznának, és az integrációs tesztek
    csendben kimaradnának.

FONTOS: a conftest.py-ból nem lehet nevet importálni a tesztmodulokba
(a pytest csak fixture-öket és hook-okat vesz át innen). A skip-feltételek
ezért a tesztmodulokban élnek.
"""
import os
import sys
from pathlib import Path

GYOKER = Path(__file__).resolve().parent.parent

# 1. src elérhetővé tétele
SRC = GYOKER / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# 2. .env betöltése (a meglévő környezeti változókat NEM írja felül)
def _env_betolt(ut: Path) -> None:
    if not ut.is_file():
        return
    for sor in ut.read_text(encoding="utf-8").splitlines():
        sor = sor.strip()
        if not sor or sor.startswith("#"):
            continue
        if sor.startswith("export "):
            sor = sor[7:].lstrip()
        if "=" not in sor:
            continue
        kulcs, ertek = sor.split("=", 1)
        kulcs = kulcs.strip()
        ertek = ertek.strip().strip('"').strip("'")
        os.environ.setdefault(kulcs, ertek)


for nev in (".env", ".env.local"):
    _env_betolt(GYOKER / nev)


# 3. A kizárásos következtetés (licitmotor-szimuláció) lassú: a tesztekben
#    alapból kikapcsolva; a saját tesztje kérésenként kapcsolja be.
os.environ.setdefault("KIBIC_KOVETKEZTETES_MS", "0")
# 4. A kijátszás gondolkodási ideje (KIBIC_GONDOLKODAS_MS) a tesztekben kikapcsolva;
#    a saját tesztje a modulváltozót állítja.
os.environ.setdefault("KIBIC_GONDOLKODAS_MS", "0")
