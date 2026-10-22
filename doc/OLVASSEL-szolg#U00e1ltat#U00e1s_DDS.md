# DD állás-elemző szolgáltatás

| fájl | hova |
|---|---|
| `szolgaltatas/__init__.py` | `src/kibic/szolgaltatas/__init__.py` — ÚJ (üres) |
| `szolgaltatas/dd.py` | `src/kibic/szolgaltatas/dd.py` — ÚJ |
| `szolgaltatas/api.py` | `src/kibic/szolgaltatas/api.py` — ÚJ (FastAPI) |
| `cli/ddelemzo.py` | `src/kibic/cli/ddelemzo.py` — ÚJ |
| `solver/dds.py` | cserélni (`lap_elemzes` hozzáadva) |
| `tests/test_dd_szolgaltatas.py` | ÚJ (13 teszt, endplay nélkül is fut) |

## Miért nem a `mohabridzs-ai/1.0` protokoll része

Az a szerződés **döntéshozatalról** szól (`deadline_ms`, `legal_actions`,
"pontosan egy Action"), ez pedig **utólagos elemzés** emberi fogyasztásra.
Ezért saját névtérben él: `POST /v1/kibic/dd`.

A **jelölések viszont azonosak**, hogy a hívó appnak ne kelljen kétféle
konvenciót kezelnie: égtáj `N E S W`, szín `C D H S`, szan `N`, lap
`SA`/`DT`, beliállás `none ns ew both`.

## Indítás

```bash
pip install "fastapi" "uvicorn[standard]" endplay
export KIBIC_SHARED_SECRET=valami-titok      # opcionális
uvicorn kibic.szolgaltatas.api:app --host 0.0.0.0 --port 9050
```

Ellenőrzés: `GET /v1/kibic/allapot` — megmondja, elérhető-e a DDS.

## Kipróbálás szerver nélkül

```bash
python -m kibic.cli.ddelemzo --pelda > keres.json
python -m kibic.cli.ddelemzo keres.json
```

## Bemenet

```json
{
  "request_id": "opcionális",
  "hands": {"N": ["SJ","S3",...], "E": [...], "S": [...], "W": [...]},
  "contract": {"level": 3, "strain": "C", "multiplier": 2},
  "declarer": "N",
  "vulnerability": "none",
  "play": [{"seat":"E","card":"D4"}, {"seat":"S","card":"DJ"}]
}
```

**A `hands` lehet a teljes kiosztás VAGY a még kézben lévő lapok** — az
utóbbi esetben a szolgáltatás a `play`-ből visszaállítja az eredetit
(a játékapp így küldené természetesen). A `contract` megadható `"3CX"`
szövegként is, a `play` pedig lapok sima listájaként.

## Válasz

```json
{
  "seat": "N", "contract": "3CX", "needed_tricks": 9,
  "tricks": {"completed":1, "declarer_won":1, "remaining":12},
  "best_cards": ["C5"],
  "cards": [
    {"card":"C5","declarer_total":10,"result":"+1","score_ns":570,
     "best":true,"loss":0},
    {"card":"C8","declarer_total":9,"result":"=","score_ns":470,
     "best":false,"loss":1}
  ],
  "warning": "..."
}
```

A `result` a kontraktushoz viszonyított eredmény (`-1`, `=`, `+1`), a
`score_ns` az É-D pontszám, a `loss` pedig hány ütést ad fel a lap a
legjobbhoz képest. **A `loss` a legbeszédesebb a felhasználónak:**
`loss: 0` = hibátlan, `loss: 2` = két ütést dobott el.

## Amit a szolgáltatás elkap

Hiányzó vagy érvénytelen `declarer`, rossz beliállás, hiányzó kéz,
érvénytelen lapjelölés, 52-től eltérő lapszám, és — ami a leghasznosabb —
**rossz kijátszási sorrend**: "A 3. lapnál E következne, a kérés szerint
N." Mindegyik `DdHiba`, amit az API HTTP 400-zá fordít.

## Korlát, amit a felhasználónak is mutass meg

Double dummy elemzés: **nyílt lapokkal** számol. Azt mondja meg, mi lett
volna a legjobb teljes információ birtokában — emberi hiba megítélésére
**felső korlát**. Egy gyengébbnek jelölt lap teljesen ésszerű lehetett az
akkori tudás alapján. A válasz `warning` mezője ezt tartalmazza.

## Üzemeltetés

A DDS globális állapotot használ és a szálbiztonsága nem garantált,
ezért az API zár mögött hívja. Ha ez szűk keresztmetszet lesz, több
**folyamatot** indíts (uvicorn `--workers`), ne szálat.
