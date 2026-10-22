# kibic DD elemző interfész

**Kiegészítés a MohaBridzs AI Gateway interfész dokumentumhoz**

| Tétel | Érték |
|---|---|
| Vezetékprotokoll | `kibic-dd/1.0` |
| Dokumentumverzió | 1.0 |
| Állapot | Aktuális interfész a double dummy elemzéshez |
| Kapcsolódó dokumentum | MohaBridzs AI Gateway interfész, protokoll `mohabridzs-ai/1.0` |

**Cél és eredmény.** Ez a dokumentum azt írja le, hogyan kérhető egy
befejezett vagy félbehagyott bridzsállás double dummy elemzése. A
szolgáltatás a soron lévő játékos minden játszható lapjához megadja,
milyen végeredményt hozna tökéletes folytatás mellett, és mennyit veszít
a legjobb laphoz képest. Tipikus felhasználás: „hol hibáztunk" típusú
utólagos elemzés a játékosoknak.

---

## 1 Hatókör és viszony az AI Gateway protokollhoz

Ez a végpont **nem része** a `mohabridzs-ai/1.0` szerződésnek, és nem is
helyettesíti azt. A két protokoll különböző célú:

| | `mohabridzs-ai/1.0` | `kibic-dd/1.0` |
|---|---|---|
| Mire való | **döntés** játék közben | **elemzés** utólag |
| Mit lát | csak a látható kezeket | mind a négy kezet |
| Időkorlát | kötelező (`deadline_ms`) | nincs |
| Válasz | pontosan egy akció | minden lap kiértékelése |
| Ki használja | a játékmotor | a felhasználói felület |

**Ezért nem keverhető össze a kettő:** a döntéshozó AI szándékosan
nem látja az ellenfelek lapjait; ez a szolgáltatás viszont éppen azért
használható, mert látja. Játék közbeni tanácsadásra **nem szabad**
használni.

A **jelölések azonosak** a két protokollban, hogy a hívó alkalmazásnak
ne kelljen kétféle konvenciót kezelnie (lásd 5. fejezet).

---

## 2 Kötelező integrációs követelmények

| Szint | Követelmény | Előírás |
|---|---|---|
| MUST | Egy végpont | A szolgáltatás megvalósítja a `POST /v1/kibic/dd` végpontot. |
| MUST | Teljes kiosztás | A kérés mind a négy kezet tartalmazza. Hiányos kezek esetén a `play` elemei `seat` mezővel érkeznek. |
| MUST | Közös titok | Ha be van állítva, ellenőrzi az `Authorization: Bearer` fejlécet. |
| MUST | Kérésazonosító | A válaszban változtatás nélkül visszaadja a kérés `request_id` értékét, ha volt. |
| MUST | Korlát közlése | A válasz tartalmazza a `warning` mezőt a double dummy értelmezési korlátjáról. |
| SHOULD | Válaszidő | Egy állás kiértékelése tipikusan 5–50 ms; a hívó 5 másodperces időkorlátot alkalmazzon. |
| SHOULD | Korlát megjelenítése | A felhasználói felület a `warning` tartalmát is mutassa meg, ne csak a számokat. |

---

## 3 HTTP kapcsolat

### 3.1 Végpontok

```
POST {alapcím}/v1/kibic/dd          elemzés
GET  {alapcím}/v1/kibic/allapot     életjel
```

Belső hálózati példa: `http://192.168.77.70:9050`. Nyilvános hálózaton
HTTPS szükséges.

### 3.2 Fejlécek

```
Accept: application/json
Content-Type: application/json; charset=utf-8
Authorization: Bearer <KIBIC_SHARED_SECRET>
```

Az `Authorization` fejléc akkor kötelező, ha a szolgáltatásban be van
állítva a `KIBIC_SHARED_SECRET`.

### 3.3 HTTP eredmény

| Státusz | Jelentés |
|---|---|
| 200 | Sikeres elemzés |
| 400 | Hibás kérés; a `detail` mező magyarázza (lásd 7. fejezet) |
| 401 | Hiányzó vagy érvénytelen titok |
| 503 | A double dummy motor nem érhető el a szolgáltatásban |

---

## 4 Kérés objektum

| Mező | Típus | Kötelező | Jelentés |
|---|---|---|---|
| `request_id` | string | nem | Átlátszatlan azonosító; változatlanul visszaadjuk. |
| `hands` | object | igen | Égtájanként a lapok. Lásd 4.1. |
| `contract` | object vagy string | igen | A felvétel. Lásd 4.2. |
| `declarer` | `N E S W` | igen | A felvevő égtája. |
| `vulnerability` | enum | nem | `none`, `ns`, `ew` vagy `both`. Alapértelmezés: `none`. |
| `play` | array | nem | A kijátszott lapok időrendben. Lásd 4.3. |

### 4.1 Hands objektum

Mind a négy égtáj kötelező. Kétféleképp adható meg:

**Teljes kiosztás** — összesen 52 lap:

```json
"hands": {
  "N": ["SJ","S3","H9","DA","DQ","DT","D8","CA","CQ","CJ","C7","C6","C3"],
  "E": ["SA","ST","S6","HA","H7","H5","H4","D4","D2","CK","CT","C8","C5"],
  "S": ["SK","S8","S7","S2","HQ","HJ","H8","H3","DJ","D7","D3","C9","C2"],
  "W": ["SQ","S9","S5","S4","HK","HT","H6","H2","DK","D9","D6","D5","C4"]
}
```

**Még kézben lévő lapok** — kevesebb mint 52. Ilyenkor a szolgáltatás a
`play` alapján visszaállítja az eredeti kiosztást, ezért a `play` minden
elemének tartalmaznia kell a `seat` mezőt. A játékalkalmazásnak ez a
természetesebb: a pillanatnyi állapotot küldi.

A `hands` megadható PBN deal-szövegként is:
`"N:J3.9.AQT8.AQJ763 AT6.A754.42.KT85 ..."`.

### 4.2 Contract

Objektumként, az AI Gateway protokoll alakjában:

```json
"contract": {"level": 3, "strain": "C", "multiplier": 2}
```

A `multiplier` értéke `1` (sima), `2` (kontrázott) vagy `4`
(rekontrázott). Szövegként is megadható: `"3CX"`, `"4H"`, `"6NXX"`.

### 4.3 Play tömb

Időrendben, az első kijátszástól, beleértve a folyamatban lévő ütés már
kijátszott lapjait is:

```json
"play": [
  {"seat": "E", "card": "D4"},
  {"seat": "S", "card": "DJ"},
  {"seat": "W", "card": "DK"},
  {"seat": "N", "card": "DA"}
]
```

Ha a `hands` a teljes kiosztást tartalmazza, a `seat` mező elhagyható, és
a `play` lehet lapok sima listája: `["D4","DJ","DK","DA"]`. A
szolgáltatás ilyenkor a felvétel alapján vezeti le, ki következett.

A `play` üres vagy hiányzó, ha a lejátszás még nem kezdődött el — ekkor
az elemzés az **indító kijátszásra** vonatkozik.

---

## 5 Jelölések

Azonosak a `mohabridzs-ai/1.0` protokolléval.

| Fogalom | Megengedett értékek | Példák |
|---|---|---|
| Égtáj | `N E S W` | `N` = Észak |
| Szín | `C D H S` | treff, káró, kőr, pikk |
| Rang | `2 3 4 5 6 7 8 9 T J Q K A` | `T` = tízes |
| Lap | szín + rang | `C2`, `DT`, `HQ`, `SA` |
| Felvétel színe | `C D H S N` | `N` jelenti a szant |
| Beliállás | `none ns ew both` | |

Minden kód nagybetűs és kis-nagybetű érzékeny.

---

## 6 Válasz objektum

| Mező | Típus | Jelentés |
|---|---|---|
| `request_id` | string vagy null | A kérésből változatlanul. |
| `seat` | `N E S W` | A soron lévő játékos égtája. |
| `contract` | string | A felvétel kanonikus alakja, pl. `3CX`. |
| `declarer` | `N E S W` | A felvevő. |
| `needed_tricks` | egész | A teljesítéshez szükséges ütésszám (szint + 6). |
| `tricks` | object | Az eddigi ütések állása. Lásd 6.1. |
| `best_cards` | array | A legjobb lap(ok) jelölése. |
| `cards` | array | Minden játszható lap kiértékelése. Lásd 6.2. |
| `warning` | string | A double dummy értelmezési korlátja. |
| `elapsed_ms` | egész | A feldolgozás ideje. |

### 6.1 Tricks objektum

| Mező | Jelentés |
|---|---|
| `completed` | Lement teljes ütések száma. |
| `declarer_won` | Ebből a felvevő vonaláé. |
| `defenders_won` | Ebből a védőké. |
| `remaining` | Hátralévő ütések száma. |
| `cards_in_current_trick` | A folyamatban lévő ütésbe már kijátszott lapok száma. |

### 6.2 Cards tömb

A lapok a legjobbtól a leggyengébb felé rendezve.

| Mező | Típus | Jelentés |
|---|---|---|
| `card` | string | A lap jelölése, pl. `C5`. |
| `declarer_total` | egész | A felvevő végső ütésszáma, ha ezt a lapot hívja. |
| `result` | string | A felvételhez viszonyított eredmény: `-2`, `-1`, `=`, `+1`. |
| `score_ns` | egész | Az Észak–Dél pár pontszáma, előjelesen. |
| `best` | boolean | Igaz, ha ez (az egyik) legjobb választás. |
| `loss` | egész | Hány ütést ad fel a legjobbhoz képest. |

**A `loss` a felhasználónak a legbeszédesebb mező.** `loss: 0` hibátlan
választás; `loss: 2` azt jelenti, hogy a lap két ütést dobott el.

---

## 7 Példa

### 7.1 Kérés

```json
{
  "request_id": "5aa92d15:24:0:1:dd:9",
  "hands": {
    "N": ["SJ","S3","H9","DQ","DT","D8","CA","CQ","CJ","C7","C6","C3"],
    "E": ["SA","ST","S6","HA","H7","H5","H4","D2","CK","CT","C8","C5"],
    "S": ["SK","S8","S7","S2","HQ","HJ","H8","H3","D7","D3","C9","C2"],
    "W": ["SQ","S9","S5","S4","HK","HT","H6","H2","D9","D6","D5","C4"]
  },
  "contract": {"level": 3, "strain": "C", "multiplier": 2},
  "declarer": "N",
  "vulnerability": "none",
  "play": [
    {"seat": "E", "card": "D4"},
    {"seat": "S", "card": "DJ"},
    {"seat": "W", "card": "DK"},
    {"seat": "N", "card": "DA"}
  ]
}
```

*(A `hands` itt a még kézben lévő lapokat tartalmazza: az első ütés négy
lapja már hiányzik belőle.)*

### 7.2 Válasz

```json
{
  "request_id": "5aa92d15:24:0:1:dd:9",
  "seat": "N",
  "contract": "3CX",
  "declarer": "N",
  "vulnerability": "none",
  "needed_tricks": 9,
  "tricks": {
    "completed": 1,
    "declarer_won": 1,
    "defenders_won": 0,
    "remaining": 12,
    "cards_in_current_trick": 0
  },
  "best_cards": ["CA"],
  "cards": [
    {"card":"CA","declarer_total":10,"result":"+1","score_ns":570,
     "best":true,"loss":0},
    {"card":"CQ","declarer_total":10,"result":"+1","score_ns":570,
     "best":true,"loss":0},
    {"card":"SJ","declarer_total":9,"result":"=","score_ns":470,
     "best":false,"loss":1}
  ],
  "warning": "Double dummy elemzés: nyílt lapokkal számol...",
  "elapsed_ms": 12
}
```

---

## 8 Hibák

Hiba esetén HTTP 400, és a válasz `detail` mezője magyarázza. Tipikus
üzenetek:

| Üzenet | Ok |
|---|---|
| `Hiányzó vagy érvénytelen declarer` | A `declarer` nincs megadva vagy nem `N E S W`. |
| `A vulnerability none / ns / ew / both lehet` | Ismeretlen beliállás. |
| `Hiányzik a(z) W kéz...` | Nem mind a négy kéz érkezett. |
| `Érvénytelen lapjelölés: 'XY'` | Nem értelmezhető lapkód. |
| `A kiosztás 53 lapot tartalmaz 52 helyett` | Duplikált vagy hiányzó lap. |
| `A 3. lapnál E következne, a kérés szerint N` | A kijátszás sorrendje nem konzisztens. |
| `Hiányos kezek esetén a play elemeinél kell a seat mező` | Nem állítható vissza az eredeti kiosztás. |
| `A lejátszás már befejeződött` | Mind az 52 lap ki van játszva; nincs mit elemezni. |

A sorrend-ellenőrzés a leghasznosabb: azonnal megmutatja, ha a hívó
oldalon elcsúszott a lejátszás nyilvántartása.

---

## 9 Korlátok és helyes értelmezés

**Ez double dummy elemzés: nyílt lapokkal számol.** Azt mondja meg, mi
lett volna a legjobb teljes információ birtokában. A valódi játékban a
játékos nem látja az ellenfelek lapjait, ezért:

* Az itt gyengébbnek jelölt választás **lehetett teljesen ésszerű** az
  akkori információ alapján. Egy elhibázott impassz a double dummy
  szerint hiba; a valóságban lehetett a legjobb esély.
* A `loss` értéke **felső korlát** az emberi hibára, nem pontos mérték.
* A védekezésnél a torzítás nagyobb, mint a felvevőjátéknál: a double
  dummy védelem olyan információt használ, amit a védők soha nem
  kaphatnak meg.

Ezért a felhasználói felület a számok mellett **mutassa meg a `warning`
tartalmát is**, és kerülje a „hiba" szó használatát; a „double dummy
szerint jobb lett volna" megfogalmazás pontosabb.

---

## 10 Üzemeltetés

A double dummy motor globális állapotot használ, szálbiztossága nem
garantált, ezért a szolgáltatás zár mögött hívja. Nagyobb terhelésnél
több **folyamatot** kell indítani, nem szálat:

```bash
uvicorn kibic.szolgaltatas.api:app --host 0.0.0.0 --port 9050 --workers 4
```

Az elemzés állapotmentes: nincs munkamenet, nincs adatbázis-igény,
minden kérés önmagában teljes.

---

## 11 Verziózás

A `kibic-dd` protokoll függetlenül verziózódik a `mohabridzs-ai`
protokolltól. Visszafelé kompatibilis bővítés esetén a szolgáltatás új
válaszmezőket adhat; a hívó **hagyja figyelmen kívül az általa nem
ismert mezőket**. Törő változás esetén új útvonal jön létre
(`/v2/kibic/dd`), a régi pedig legalább egy átmeneti ideig megmarad.
