# Leosztás-elemző: DD-tábla + par (`POST /v1/kibic/dd-tabla`)

A zipet a projektgyökérben kell kibontani.

| fájl | |
|---|---|
| `src/kibic/szolgaltatas/ddtabla.py` | ÚJ — a szolgáltatás (tábla, vonal-max, par, eltérés) |
| `src/kibic/szolgaltatas/api.py` | MÓDOSÍTOTT — új végpont a `/v1/kibic/dd` után |
| `src/kibic/cli/ddtabla.py` | ÚJ — parancssori kipróbáló + összevetés az endplay par-jával |
| `tests/test_ddtabla.py` | ÚJ — 30 teszt, endplay nélkül fut |
| `doc/kibic-dd-tabla.md` | ÚJ — interfészleírás a MohaBridzsnek |
| `doc/semak/*.schema.json` | ÚJ — kérés- és válaszséma (JSON Schema 2020-12) |

## Első lépések nálad

```bash
pytest tests/test_ddtabla.py tests/test_dd_szolgaltatas.py

# A par saját számítás (tiszta Python a DD-táblából). MIELŐTT élesre megy,
# vesd össze az endplay/DDS par-jával véletlen leosztásokon:
python -m kibic.cli.ddtabla --osszevet 300

python -m kibic.cli.ddtabla --pelda > keres.json
python -m kibic.cli.ddtabla keres.json
```

Az `--osszevet` csak a par PONTSZÁMOT hasonlítja (a par-kontraktusok
leírását az endplay szövegként adja). Eltérésnél kiírja a leosztást —
azt küldd el, és megnézzük, melyik számol rosszul.
