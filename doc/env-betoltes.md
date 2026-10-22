# A `.env` és az 1045-ös hiba

## Mi történt

```
pymysql.err.OperationalError:
    (1045, "Access denied for user 'kibic'@'localhost' (using password: NO)")
```

A `using password: **NO**` a lényeg: nem rossz jelszót küldött a kliens,
hanem **egyáltalán nem küldött**. A `KIBIC_PASS` üres volt az uvicorn
folyamatában, mert a `source .env` kimaradt a szerverindítás előtt.

Ezért volt az egész olyan megtévesztő:

| ami működött | miért |
|---|---|
| `/openapi.json`, `/docs` | nem nyúl adatbázishoz |
| `/v1/kibic/dd` | tiszta DDS-számítás |
| mind a 695 teszt | a `tests/conftest.py` **maga betölti a `.env`-et** |
| a szerkesztő, a licit | adatbázist olvas → 1045 |

**A tesztek és a szerver közti aszimmetria volt a csapda.** A pytestnek
volt `.env`-betöltője, a szolgáltatásnak nem — tehát a tesztek akkor is
zöldek, ha a szerver nem látja a jelszót. Ez a legcsendesebb fajta hiba:
a mérőműszer hazudik.

## Az azonnali gyógyszer

```bash
cd /scratch/mohAIbridzs/neuro_szimbolikus_hibrid
set -a; source .env; set +a
uvicorn kibic.szolgaltatas.api:app --host 0.0.0.0 --port 9050
```

A `set -a` azért kell, mert a `.env`-ben `export` nélküli sorok is vannak:
`source` beállítja őket a shellben, de az uvicorn gyerekfolyamat nem látja.
A `set -a` minden hozzárendelést exportál is.

## A tartós megoldás

A `src/kibic/env.py` modul betölti a `.env`-et, és a `src/kibic/__init__.py`
importálja. Következmény: **bármelyik belépési ponton** (uvicorn, CLI,
pytest, `python -c`) a `.env` be van töltve, mire bármi mást tenne.

Három tulajdonsága van, ami fontos:

1. **A meglévő környezeti változót nem írja felül.** A systemd
   `EnvironmentFile`, a Docker `-e` és a parancssori előtag erősebb, mint
   a fejlesztői `.env`. Tehát élesben nem tudja véletlenül visszaütni.
2. **Megtalálja a `.env`-et akkor is, ha a munkakönyvtár nem a repó** —
   először a munkakönyvtárból indul felfelé (így tud egy könyvtárból
   indított program a saját beállítását használni), aztán a csomag
   fölötti repógyökérből. Pont ez a második hiányzott.
3. **Kimondja, ha hiányzik a jelszó** — az `env.allapot()` hívás a
   pymysql veremkivonata helyett egy mondatot ad.

## Tedd bele az életjelbe

Hogy többé ne verem-kivonatból kelljen rájönni, érdemes a
`/v1/kibic/allapot` válaszába beírni. Az `api.py` `allapot()` függvényébe,
a `return` elé:

```python
from ..env import allapot as _env_allapot
ki["kornyezet"] = _env_allapot()
```

Ettől a `curl -sS localhost:9050/v1/kibic/allapot` így felel, ha baj van:

```json
"kornyezet": {
  "env_fajlok": "nem találtam .env-et",
  "hianyzo_adatbazis_valtozo": ["KIBIC_USER", "KIBIC_PASS", "KIBIC_DB"],
  "figyelmeztetes": "A KIBIC_PASS üres: az adatbázist olvasó végpontok
                     1045-öt fognak adni (»using password: NO«).
                     Indítás előtt: set -a; source .env; set +a"
}
```

A jelszó értéke **nem** szerepel benne, csak az, hogy be van-e állítva és
hány karakter — ez igaz a `*_SECRET` kulcsokra is.

## Figyelem a `__init__.py`-ra

A csomag `src/kibic/__init__.py` fájlja nálam üres volt. Ha nálad azóta
került bele bármi, **ne írd felül** — csak tedd a két sort a tetejére,
minden más import ELŐTT:

```python
from . import env as _env          # noqa: F401
_env.betolt()
```

A sorrend nem formaság: a modulszintű `os.getenv(...)` hívások (például a
`TITOK` és az `ATJARO_TITOK` az `api.py`-ban) azonnal lefutnak, tehát a
`.env`-nek előbb kell betöltődnie.
