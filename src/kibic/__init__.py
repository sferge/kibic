"""
kibic — bridzsjátékos MI.

Az első dolog, ami bármelyik belépési ponton lefut: a `.env` betöltése.
Enélkül a szolgáltatás és a CLI-k csak akkor látják az adatbázis-jelszót,
ha a hívó nem felejtette el a `source .env`-et — a pytest viszont a
`conftest.py`-ból mindig betölti, és ebből a különbségből az a csapda
lesz, hogy MINDEN TESZT ZÖLD, miközben a szerver 1045-öt kap.

A betöltés sosem írja felül a már beállított környezeti változót, tehát a
systemd `EnvironmentFile`, a Docker `-e` és a parancssori előtag erősebb.
"""
from . import env as _env          # noqa: F401  (mellékhatás: betölt)

_env.betolt()
