"""
A `.env` BETÖLTÉSE — egy helyen, mindenkinek.

MIÉRT KELL
----------
A `tests/conftest.py` maga betölti a `.env`-et, a szolgáltatás és a CLI-k
viszont nem. Ebből az az alattomos helyzet áll elő, hogy **a 695 teszt
zöld, a szerver mégis 1045-öt kap**:

    pymysql.err.OperationalError:
        (1045, "Access denied for user 'kibic'@'localhost'
                (using password: NO)")

A `using password: NO` a kulcs: nem rossz jelszó, hanem HIÁNYZÓ. Az
uvicorn nem olvas `.env`-et, tehát ha a `source .env` kimaradt a
szerverindítás előtt, a `KIBIC_PASS` üres. Ilyenkor minden működni
LÁTSZIK, ami nem nyúl adatbázishoz (`/docs`, `/v1/kibic/dd`), és csak az
adatbázist olvasó végpontok hasalnak el.

Ez a modul ezt a különbséget szünteti meg: aki importálja, annak a
`.env` már be van töltve.

HASZNÁLAT
---------
A belépési pontok ELSŐ importja legyen ez, minden más import előtt
(mert a modulszintű `os.getenv(...)` hívások azonnal lefutnak):

    from .. import env as _env       # a .env betöltése, mellékhatásként
    _env.betolt()

Kétszer meghívni ártalmatlan.

MIT NEM TESZ
------------
**Nem írja felül a már beállított környezeti változót.** A `source .env`,
a systemd `EnvironmentFile`, a Docker `-e` és a parancssori előtag mind
erősebb — ez csak a HIÁNYZÓT pótolja. Így a termelési beállítást nem
tudja véletlenül visszaütni egy fejlesztői `.env`.
"""
from __future__ import annotations

import os
from pathlib import Path

# Amit a kibic használ. Csak a diagnosztikához kell: a betöltés minden
# kulcsot visz, de az `allapot()` ezekről mond véleményt.
KULCSOK = ("KIBIC_HOST", "KIBIC_USER", "KIBIC_PASS", "KIBIC_DB",
           "KIBIC_RENDSZER", "KIBIC_PAR", "KIBIC_SHARED_SECRET",
           "KIBIC_AI_SHARED_SECRET", "KIBIC_PROFILOK",
           "KIBIC_ATJARO_NAPLO", "KIBIC_ATJARO_SZIMULACIO")

TITKOS = ("PASS", "SECRET", "TITOK", "PASSWORD")

FAJLOK = (".env", ".env.local")

# Mi történt a legutóbbi betöltésnél — az `allapot()` ebből válaszol.
_betoltott: list[str] = []
_kesz = False


def _gyokerek() -> list[Path]:
    """
    Hol keressük a `.env`-et, és milyen sorrendben?

    1. A **munkakönyvtár** és fölötte néhány szint. Ez nyer, mert aki egy
       adott könyvtárból indítja a programot, az ott lévő beállítást
       akarja (így tudnak a tesztek is ideiglenes `.env`-et adni).
    2. A **csomag fölötti repógyökér** (`src/kibic/env.py` -> két szint
       föl). Ez akkor kell, ha a szolgáltatás systemd alól vagy bárhonnan
       indul, és a munkakönyvtár nem a repó — pontosan az az eset, amiből
       az 1045-ös hiba lett.

    Az első találat nyer; nem gyűjtünk össze többet.
    """
    ki: list[Path] = []

    def be(p: Path) -> None:
        if p not in ki:
            ki.append(p)

    munka = Path.cwd().resolve()
    be(munka)
    for p in list(munka.parents)[:5]:
        be(p)

    sajat = Path(__file__).resolve()
    be(sajat.parent.parent.parent)      # src/kibic/env.py -> repógyökér
    be(sajat.parent.parent)             # -> src/
    return ki


def _egy_fajl(ut: Path) -> int:
    """Egy fájl betöltése. Visszaadja, hány kulcsot ténylegesen beállított."""
    db = 0
    try:
        szoveg = ut.read_text(encoding="utf-8")
    except OSError:
        return 0
    for sor in szoveg.splitlines():
        sor = sor.strip()
        if not sor or sor.startswith("#"):
            continue
        if sor.startswith("export "):
            sor = sor[7:].lstrip()
        if "=" not in sor:
            continue
        kulcs, ertek = sor.split("=", 1)
        kulcs = kulcs.strip()
        ertek = ertek.strip()
        # Idézőjel le, de csak ha párban van (különben a jelszóban lévő
        # idézőjel elveszne).
        if len(ertek) >= 2 and ertek[0] == ertek[-1] and ertek[0] in "\"'":
            ertek = ertek[1:-1]
        if not kulcs or kulcs in os.environ:
            continue               # a meglévő környezet ERŐSEBB
        os.environ[kulcs] = ertek
        db += 1
    return db


def betolt(ujra: bool = False) -> list[str]:
    """
    A `.env` és a `.env.local` betöltése. Idempotens.

    Visszaadja a betöltött fájlok útvonalát (üres lista: nem talált
    egyet sem — ez nem hiba, csak jelzés).
    """
    global _kesz
    if _kesz and not ujra:
        return list(_betoltott)
    _betoltott.clear()
    for gyoker in _gyokerek():
        for nev in FAJLOK:
            ut = gyoker / nev
            if ut.is_file():
                _egy_fajl(ut)
                _betoltott.append(str(ut))
        if _betoltott:
            break                  # az első találat nyer, nem gyűjtünk
    _kesz = True
    return list(_betoltott)


def _elrejt(kulcs: str, ertek: str) -> str:
    """A titkot nem írjuk ki — csak azt, hogy VAN."""
    if any(t in kulcs.upper() for t in TITKOS):
        return f"beállítva ({len(ertek)} karakter)" if ertek else "ÜRES"
    return ertek


def allapot() -> dict:
    """
    Diagnosztika az életjelhez: honnan jött a beállítás és mi hiányzik.

    Ez az a három sor, amiből a fenti 1045-ös hiba egy pillantásra
    látszik, ahelyett hogy a pymysql veremkivonatát kelljen olvasni.
    """
    hiany = [k for k in ("KIBIC_USER", "KIBIC_PASS", "KIBIC_DB")
             if not os.getenv(k)]
    return {
        "env_fajlok": list(_betoltott) or "nem találtam .env-et",
        "beallitva": {k: _elrejt(k, os.environ[k])
                      for k in KULCSOK if k in os.environ},
        "hianyzo_adatbazis_valtozo": hiany,
        "figyelmeztetes": (
            "A KIBIC_PASS üres: az adatbázist olvasó végpontok 1045-öt "
            "fognak adni (»using password: NO«). Indítás előtt: "
            "set -a; source .env; set +a"
        ) if "KIBIC_PASS" in hiany else None,
    }


# A puszta import is betölt: így az sem baj, ha valaki elfelejti hívni.
betolt()
