# `POST /v1/kibic/dd-tabla` — leosztás-elemzés

*Interfészleírás a MohaBridzs számára. Verzió: 1.0 (2026-09-30).*
*Géppel olvasható sémák: `doc/semak/kibic-dd-tabla.request.schema.json`,
`doc/semak/kibic-dd-tabla.response.schema.json` (JSON Schema 2020-12).*

## Mit ad

Egy **teljes leosztásra** (nem egy játékállásra, arra a `/v1/kibic/dd` való):

| mező | jelentés |
|---|---|
| `dd_table` | A 20 mezős double dummy tábla: 4 felvevő × 5 szín, hány ütést visz a felvevő tökéletes játékkal. |
| `side_max` | Vonalanként (NS / EW) és színenként a jobbik felvevő ütésszáma és a legmagasabb teljesíthető szint. |
| `best_contract` | Vonalanként a legtöbbet érő teljesíthető kontraktus, az ellenfelet figyelmen kívül hagyva („mit tudunk mi”). |
| `par` | Az optimum: mi lenne az eredmény, ha mindkét vonal nyílt lapokkal, tökéletesen licitálna (feláldozással együtt). |
| `contract_analysis` | Ha a kérés hozza a játszott kontraktust: annak DD-értéke, a tényleges eredmény, és az eltérés a partól pontban és IMP-ben, **licitre és játékra bontva**. |

**Mikor hívjuk:** leosztásonként egyszer, legcélszerűbben a lejátszás végén
(akkor már az eredmény is megy vele). A számítás egy teljes DD-tábla,
jellemzően néhány tized másodperc — a `/v1/kibic/dd` játék közbeni
hívásait nem érdemes ezzel terhelni.

**Átlag:** a versenybridzs „átlaga” (százalék, datum) a többi asztal
eredményeiből jön, egy leosztásból nem számolható. Egyasztalos mérceként a
`contract_analysis.vs_par` szolgál.

## Hívás

```
POST /v1/kibic/dd-tabla
Content-Type: application/json
Authorization: Bearer <KIBIC_SHARED_SECRET>     # ugyanaz, mint a /v1/kibic/dd-nél
```

## Kérés

**Ugyanaz a kéréstest, mint a `/v1/kibic/dd`-nél** — a meglévő hívás
payloadja változtatás nélkül elküldhető ide is. Eltérések:

* **ÚJ `dealer`** (N/E/S/W) — az osztó. A parhoz kell: ha mindkét vonal
  ugyanazt tudja, az nyer, aki előbb szól. Ha hiányzik, feltételezzük
  (felvevő, különben N), és a válasz jelzi (`par.dealer_assumed`,
  `par.dealer_sensitive`).
* **ÚJ `declarer_tricks`** (0–13) — a felvevő tényleges ütésszáma. Ha
  megvan, nem kell hozzá a teljes `play`.
* A `contract` és a `declarer` itt **opcionális**. Kontraktus nélkül csak a
  tábla és a par jön. Passzolt lap: `"contract": "P"`.
* A tényleges ütésszám forrása: `declarer_tricks`, vagy ha nincs, a
  `play`, amennyiben mind az 52 lapot tartalmazza.

| mező | kötelező | típus | megjegyzés |
|---|---|---|---|
| `request_id` | – | string | visszakapjuk |
| `hands` | **igen** | `{N,E,S,W: [lap]}` vagy PBN | teljes 52 lap, vagy a még kézben lévők + `play` |
| `vulnerability` | – | `none` `ns` `ew` `both` | alap: `none` |
| `dealer` | ajánlott | `N` `E` `S` `W` | **új** |
| `contract` | – | `"4S"` `"3NT"`/`"3N"` `"5DX"` `"P"` vagy `{level,strain,multiplier}` | |
| `declarer` | ha van `contract` | `N` `E` `S` `W` | |
| `play` | – | `[{seat,card}]` vagy `["D4",...]` | időrendben |
| `declarer_tricks` | – | 0–13 | **új** |

Jelölések (mint a `/dd`-nél): égtáj `N E S W`, szín `C D H S`, szan `N`,
lap `SA` / `HT` / `D2` (tízes = `T`).

### Példa

```json
{
  "request_id": "board-17",
  "hands": {
    "N": ["SJ", "S3", "H9", "DA", "DQ", "DT", "D8", "CA", "CQ", "CJ", "C7", "C6", "C3"],
    "E": ["SA", "ST", "S6", "HA", "H7", "H5", "H4", "D4", "D2", "CK", "CT", "C8", "C5"],
    "S": ["SK", "S8", "S7", "S2", "HQ", "HJ", "H8", "H3", "DJ", "D7", "D3", "C9", "C2"],
    "W": ["SQ", "S9", "S5", "S4", "HK", "HT", "H6", "H2", "DK", "D9", "D6", "D5", "C4"]
  },
  "vulnerability": "ns",
  "dealer": "E",
  "contract": "4S",
  "declarer": "S",
  "declarer_tricks": 9
}
```

## Válasz (HTTP 200)

**Előjel:** minden `*_ns` pontszám É-D szemszögéből értendő, mint a
jegyzőkönyvekben (pozitív = NS nyer). Kivétel a `best_contract.<vonal>.score`,
ami a vonal saját szemszöge. A kontraktus-szöveg `4S` / `3NT` / `5DX` alakú,
a `strain` kód szanra `N`.

### Példa

*A számok szemléltetők (a tábla kitalált), a szerkezet és a számítás valódi.*

```json
{
  "request_id": "board-17",
  "vulnerability": "ns",
  "dealer": "E",
  "dd_table": {
    "N": {"C": 6, "D": 6, "H": 9, "S": 10, "N": 9},
    "E": {"C": 8, "D": 9, "H": 6, "S": 6, "N": 6},
    "S": {"C": 6, "D": 6, "H": 9, "S": 10, "N": 8},
    "W": {"C": 8, "D": 9, "H": 6, "S": 6, "N": 6}
  },
  "side_max": {
    "NS": {
      "C": {"tricks": 6, "declarers": ["N", "S"], "max_level": null},
      "D": {"tricks": 6, "declarers": ["N", "S"], "max_level": null},
      "H": {"tricks": 9, "declarers": ["N", "S"], "max_level": 3},
      "S": {"tricks": 10, "declarers": ["N", "S"], "max_level": 4},
      "N": {"tricks": 9, "declarers": ["N"], "max_level": 3}
    },
    "EW": {
      "C": {"tricks": 8, "declarers": ["E", "W"], "max_level": 2},
      "D": {"tricks": 9, "declarers": ["E", "W"], "max_level": 3},
      "H": {"tricks": 6, "declarers": ["E", "W"], "max_level": null},
      "S": {"tricks": 6, "declarers": ["E", "W"], "max_level": null},
      "N": {"tricks": 6, "declarers": ["E", "W"], "max_level": null}
    }
  },
  "best_contract": {
    "NS": {
      "score": 620,
      "contracts": [
        {
          "contract": "4S",
          "level": 4,
          "strain": "S",
          "doubled": false,
          "side": "NS",
          "declarers": ["N", "S"],
          "tricks": 10,
          "result": "=",
          "score_ns": 620
        }
      ]
    },
    "EW": {
      "score": 110,
      "contracts": [
        {
          "contract": "1D",
          "level": 1,
          "strain": "D",
          "doubled": false,
          "side": "EW",
          "declarers": ["E", "W"],
          "tricks": 9,
          "result": "+2",
          "score_ns": -110
        }
      ]
    }
  },
  "par": {
    "score_ns": 300,
    "contracts": [
      {
        "contract": "5DX",
        "level": 5,
        "strain": "D",
        "doubled": true,
        "side": "EW",
        "declarers": ["E", "W"],
        "tricks": 9,
        "result": "-2",
        "score_ns": 300
      }
    ],
    "passed_out": false,
    "dealer_sensitive": null,
    "dealer": "E",
    "dealer_assumed": false
  },
  "contract_analysis": {
    "contract": "4S",
    "declarer": "S",
    "side": "NS",
    "needed_tricks": 10,
    "dd_tricks": 10,
    "dd_result": "=",
    "dd_score_ns": 620,
    "actual_tricks": 9,
    "actual_result": "-1",
    "actual_score_ns": -100,
    "actual_source": "declarer_tricks",
    "vs_par": {
      "bidding": {
        "score_diff_ns": 320,
        "imp_ns": 8
      },
      "play_tricks_diff": -1,
      "total": {
        "score_diff_ns": -400,
        "imp_ns": -9
      }
    }
  },
  "warning": "Double dummy elemzés: nyílt lapokkal számol. A tábla azt mutatja, hány ütést visz a felvevő tökéletes játékkal, a par pedig azt, mi lenne az eredmény, ha mindkét vonal mindent látna és tökéletesen licitálna. Valódi játékban egyik sem elvárható mérce, csak viszonyítási pont.",
  "elapsed_ms": 41
}
```

A példa olvasata: NS beliben 4♠-ot tud (620), de K-Ny mansban 5♦X −2-vel
(−300) jobban jár → **par: 5♦X K-Ny, NS +300**. NS 4♠-ot mondott
(`bidding`: DD szerint 620, ez 320-szal **jobb** a parnál, mert a valóságban
senki nem áldozott), de 1 bukással játszotta (`play_tricks_diff: -1`),
így a végeredmény −100, ami a parhoz képest −400 pont, **−9 IMP**.

### A mezők részletesen

**`par.contracts[]`** és **`best_contract.*.contracts[]`** eleme:

| mező | jelentés |
|---|---|
| `contract` | `"4S"`, `"5DX"` (a bukó kontraktus a par-konvenció szerint mindig kontrázott) |
| `level`, `strain` | szint (1–7), szín (`C D H S N`) |
| `doubled` | kontrázott-e |
| `side` | `NS` / `EW` |
| `declarers` | melyik felvevővel (mindkettő, ha egyenlő) |
| `tricks`, `result` | DD-ütésszám és eredményjel: `=`, `+1`, `-2` |
| `score_ns` | pontszám NS szemszögből |

Azonos pontszámnál ugyanabban a színben mindig a **legalacsonyabb** szint
szerepel többletütéssel (`4S` `+1`, nem `5S`; részjátszmánál ezért lehet
pl. `1D` `+2`). Ha két szín egyenértékű (4♥ és 4♠), mindkettő ott van.

**`contract_analysis.vs_par`** — a hármas bontás a lényeg:

| mező | kérdés, amire felel |
|---|---|
| `bidding` | Jó kontraktusba került-e a pár? (a kontraktus DD-értéke − par) |
| `play_tricks_diff` | Jól játszott-e a felvevő / a védekezés? (tényleges − DD ütés, felvevő szemszögből) |
| `total` | Összesen hol állnak a parhoz képest? (tényleges pontszám − par) |

`total` és a tényleges mezők `null`-ok, ha a tényleges ütésszám nem ismert.

## Hibák

| HTTP | mikor | törzs |
|---|---|---|
| 400 | hibás bemenet (hiányzó kéz, rossz lap, rossz `dealer`, kontraktus felvevő nélkül, `declarer_tricks` nem 0–13 közötti egész, rossz kijátszási sorrend…) | `{"detail": "magyar nyelvű üzenet"}` |
| 401 | rossz vagy hiányzó titok | `{"detail": "Érvénytelen titok"}` |
| 503 | a DDS (endplay) nincs telepítve a szerveren | `{"detail": "A DDS nem elérhető: …"}` |

## Megjelenítési javaslat

* A `warning` szövegét érdemes a felhasználónak is megmutatni: a DD és a
  par nyílt lapos mérce, valódi játékban nem elvárás.
* A `dealer_assumed: true` esetén, ha `dealer_sensitive: true`, a par
  mellé kell egy „az osztótól függ” megjegyzés — jobb megoldás a `dealer`
  elküldése.
