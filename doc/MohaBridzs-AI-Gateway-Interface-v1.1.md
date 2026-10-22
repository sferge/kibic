# MohaBridzs AI Gateway — `mohabridzs-ai/1.1` kiegészítés

| Tétel | Érték |
|---|---|
| Vezetékprotokoll | `mohabridzs-ai/1.1` |
| Alapja | MohaBridzs AI Gateway interfész, dokumentumverzió 1.0.1 (`mohabridzs-ai/1.0`) |
| Kiegészítés verziója | 1.1.0 — **tervezet** |
| Dátum | 2026. szeptember 27. |
| Referencia-megvalósítás | kibic (`src/kibic/szolgaltatas/atjaro.py`, `magyarazat.py`) |

**Cél.** A bridzsszabály szerint az ellenfél bármikor megkérdezheti, mit jelent
egy licit a pár rendszerében, és jogosult a pár konvenciókártyájára, az
alertálandó licitet pedig a licitálónak jeleznie kell. Ez a kiegészítés ezt a
hármat teszi a protokoll részévé, **visszafelé kompatibilisen**: minden 1.0-s
kérés és válasz változatlanul érvényes.

Ez a dokumentum csak a változásokat írja le; minden, amit nem említ (fejlécek,
idempotencia, határidő, jelölések, adatvédelem), az 1.0.1 szerint marad.

---

## 1. Áttekintés

| Elem | Új? | Kötelező? | Röviden |
|---|---|---|---|
| `GET /v1/bridge/capabilities` | új végpont | SHOULD | Mit tud az AI-szolgáltatás. Ebből dönti el a MohaBridzs, mit kérhet tőle. |
| `alert` a licitválaszban | új mező | SHOULD | Ha a választott licit a rendszer szerint alertálandó: a megállapodás szövege. |
| `POST /v1/bridge/explain` | új végpont | SHOULD | Egy elhangzott licit jelentése a pár rendszerében — **kéz nélkül**. |
| `POST /v1/bridge/card` | új végpont | MAY | A pár konvenciókártyája (WBF-formátum). *A kibicben még nincs kész.* |

A MohaBridzs az 1.0-s AI-t továbbra is ugyanúgy hívja. Egy 1.1-es AI-nál a
`capabilities` válasza mondja meg, melyik új funkció érhető el; amit nem
támogat, azt a MohaBridzs nem kéri, és a felületen nem kínálja fel.

---

## 2. Kötelező és ajánlott követelmények (az 1.0.1 2. pontjának kiegészítése)

| Szint | Követelmény | Előírás |
|---|---|---|
| MUST | Visszafelé kompatibilitás | Az 1.1-es AI az `X-MohaBridzs-Protocol: 1.0` fejlécű kérést is kiszolgálja, változatlanul. |
| MUST | A magyarázat nem ismerheti a kezet | Az `explain` és a `card` válasz **kizárólag a megállapodásból** készül. A kérés nem tartalmaz kezet; ha mégis tartalmazna, az AI figyelmen kívül hagyja. A válasz a kéztől semmilyen módon nem függhet. |
| MUST | Saját vonal | Az `explain` csak a magyarázó AI **saját vonalán** elhangzott licitet magyarázza. Az ellenfél licitjére hibát ad (HTTP 400). |
| MUST | Őszinteség | Ha a licitre nincs megállapodás, az `explain` ezt mondja (`agreed: false`), nem talál ki jelentést. |
| SHOULD | Alert a licittel | Ha a választott licit alertálandó, a licitválasz `alert` mezője tartalmazza a szöveget. |
| SHOULD | Képességek | A `GET /v1/bridge/capabilities` végpont megvalósítása. |
| SHOULD | Rövid magyarázat | Az `explain` szövege legfeljebb 300 karakter; belső gondolatmenetet nem tartalmaz. |

---

## 3. `GET /v1/bridge/capabilities`

Kérés: törzs nélküli `GET`. Titok (`Authorization`) nem szükséges; a válasz
nem tartalmaz érzékeny adatot.

```json
{
  "protocol": "mohabridzs-ai/1.1",
  "accepts": ["mohabridzs-ai/1.0", "mohabridzs-ai/1.1"],
  "endpoints": {"bid": true, "play": true, "explain": true, "card": false},
  "bid_alert": true
}
```

| Mező | Típus | Jelentés |
|---|---|---|
| `protocol` | string | A legmagasabb támogatott protokoll. |
| `accepts` | string[] | Az elfogadott `X-MohaBridzs-Protocol` verziók. |
| `endpoints.*` | boolean | Melyik végpont érhető el. `false` esetén a MohaBridzs nem hívja. |
| `bid_alert` | boolean | Ad-e a licitválasz `alert` mezőt. |

**MohaBridzs-oldali ajánlás:** a profil mentésekor és a meccs indításakor
kérdezze le, és tárolja a profilhoz. Ha a végpont nem létezik (404), az AI
1.0-snak tekintendő: csak `bid` és `play`.

---

## 4. Az `alert` mező a licitválaszban (`POST /v1/bridge/bid`)

A kérés változatlan. A válasz új, opcionális felső szintű mezőt kaphat:

```json
{
  "request_id": "5aa92d15:17:0:1:bid:6",
  "action": {"type": "bid", "call": "2C"},
  "confidence": 0.8,
  "explanation": "2C — Stayman: 4-es nemest kérdez",
  "alert": {
    "text": "Stayman: 4-es nemest kérdez",
    "text_en": null
  },
  "meta": {"source": "model", "pipeline": "kibic_bid", "elapsed_ms": 31,
           "fallback_reason": null}
}
```

| Mező | Típus és korlát | Jelentés |
|---|---|---|
| `alert` | object vagy hiányzik | Csak akkor van jelen, ha a licit a rendszer szerint alertálandó. |
| `alert.text` | string, ≤ 300 karakter | A megállapodás rövid szövege, magyarul. |
| `alert.text_en` | string vagy null | Ugyanez angolul, ha van. |

**Szabályok:**

* Az `alert` a **megállapodást** írja le, nem a kezet (ugyanaz a szöveg jár
  bármelyik kézzel, amivel ez a licit a rendszerben mondható).
* Tartalék licitnél (`meta.source = fallback`) nincs `alert`: arra nincs
  megállapodás.
* Az `explanation` (1.0.1, 9.2) ettől független: az a döntés rövid
  indoklása az admin naplónak. Az ellenfélnek az `alert` szól.

**MohaBridzs-oldali ajánlás:** az `alert` jelenlétekor a licit mellett
alert-jel; a szöveg az ellenfeleknek kattintásra (vagy azonnal) látható, a
licitáló partnerének **nem** (a partner a saját rendszeréből kell tudja,
mit jelent — ez bridzsszabály).

---

## 5. `POST /v1/bridge/explain`

Egy **már elhangzott** licit jelentése a pár rendszerében.

A MohaBridzs annak az AI-játékosnak küldi, akinek a vonalán a licit
elhangzott — a valódi asztalnál a licitáló **partnere** magyaráz. AI-párnál
bármelyik tagja válaszolhat; a válasz ugyanaz, mert a megállapodásból jön.

### 5.1 Fejlécek

Mint az 1.0.1 3.2 pontjában, az alábbi eltérésekkel:

```
X-MohaBridzs-Protocol: 1.1
Idempotency-Key: nem szükséges (a válasz az állapotból determinisztikus)
```

### 5.2 Kérés

```json
{
  "protocol": "mohabridzs-ai/1.1",
  "request_id": "5aa92d15:17:0:1:explain:2",
  "deadline_ms": 5000,
  "game": {
    "match_id": "5aa92d15-...",
    "board_number": 3,
    "table_index": 0,
    "vulnerability": "ns"
  },
  "actor": {
    "seat": "S",
    "profile_code": "kibic_stand"
  },
  "state": {"dealer": "N"},
  "history": {
    "auction": [
      {"seat": "N", "call": "1N"},
      {"seat": "E", "call": "P"},
      {"seat": "S", "call": "2C"},
      {"seat": "W", "call": "X"},
      {"seat": "N", "call": "2D"}
    ]
  },
  "question": {
    "call_index": 4,
    "asked_by": "E"
  }
}
```

| Mező | Típus | Kötelező | Jelentés |
|---|---|---|---|
| `protocol` | string | igen | `mohabridzs-ai/1.1` |
| `request_id` | string | igen | Változtatás nélkül visszaadandó. |
| `deadline_ms` | egész | igen | A teljes kérésre rendelkezésre álló idő. |
| `game` | object | igen | Mint 1.0.1, 4.1; a `vulnerability` számít. |
| `actor.seat` | NESW | igen | A **magyarázó** AI-játékos ülése. |
| `actor.profile_code` | string | ajánlott | Melyik rendszerrel játszik (mint a licitkérésben). |
| `state.dealer` | NESW | igen | Az osztó. |
| `history.auction` | array | igen | A licitmenet legalább a kérdezett licitig (utána jöhet több is). |
| `question.call_index` | egész | igen | A kérdezett licit sorszáma a `history.auction`-ben, **0-tól**. |
| `question.asked_by` | NESW | nem | Ki kérdezett. Naplózásra; a választ nem befolyásolja. |

**A kérés NEM tartalmaz** `visible_hands`-et, `legal_actions`-t és
`history.play`-t. A MohaBridzs ne is küldje őket; ha mégis jönnek, az AI
figyelmen kívül hagyja (MUST, 2. pont).

### 5.3 Válasz

```json
{
  "request_id": "5aa92d15:17:0:1:explain:2",
  "explanation": {
    "index": 4,
    "seat": "N",
    "call": "2D",
    "agreed": true,
    "alert": true,
    "text": "Nincs 4-es nemes",
    "text_en": null,
    "shows": {
      "suits": {"S": [0, 3], "H": [0, 3]},
      "described": "S: 0-3; H: 0-3",
      "understood": true
    },
    "forcing": null,
    "conventions": ["STAYMAN"],
    "principle": false
  },
  "meta": {"source": "model", "pipeline": "kibic_explain", "elapsed_ms": 4,
           "system": "KIBIC_STAND"}
}
```

| Mező | Típus | Jelentés |
|---|---|---|
| `explanation.index`, `seat`, `call` | | A kérdezett licit (a `call` a vezetékjelölésben: `1N`, `2D`, `X`...). |
| `explanation.agreed` | boolean | Van-e rá megállapodás. `false`: a `text` ezt mondja ki. |
| `explanation.alert` | boolean | Alertálandó-e a rendszer szerint. |
| `explanation.text` | string ≤ 300 | A jelentés röviden. Ha több megállapodás is illik (pl. „gyenge VAGY gémforsz”), `VAGY`-gyal összefűzve. |
| `explanation.text_en` | string vagy null | Angolul, ha van. |
| `explanation.shows` | object vagy null | Amit a licit **biztosan** ígér: `points` = [min, max] figurapont, `suits` = színenként [min, max] hossz, `denies` = tagadott jellemzők, `described` = emberi összefoglaló. Csak a ténylegesen szűkített mezők szerepelnek. `null`, ha a licit nem szűkít (pl. mesterséges kérdés). |
| `explanation.forcing` | string vagy null | `EGY_MENET`, `GEMFORSZ`, `SZLEMFORSZ`; `KIZARO` = kizáró (nem forsz). |
| `explanation.conventions` | string[] | Melyik rendszerből/konvencióból jön (pl. `STAYMAN`). |
| `explanation.principle` | boolean | Igaz, ha csak általános elv szerint értelmezhető (nincs konkrét megállapodás, de van elv). |

**Nincs megállapodás:**

```json
{"explanation": {"index": 6, "seat": "S", "call": "4S", "agreed": false,
                 "alert": false, "text": "Nincs rá kifejezett megállapodásunk.",
                 "text_en": "No specific agreement.", "shows": null,
                 "forcing": null, "conventions": []}}
```

**Hibák:** HTTP 400, ha a `call_index` kívül esik a licitmeneten, ha a
kérdezett licit nem a magyarázó vonalán hangzott el, vagy ha a kérés hibás.
A MohaBridzs ilyenkor „nincs magyarázat” üzenetet mutat — a parti ettől nem áll meg.

### 5.4 MohaBridzs-oldali ajánlás

* Az ellenfél licitjére kattintva (vagy „Mit jelent?” gombbal) az MB a
  licitáló **vonalán ülő AI-nak** küld `explain` kérést; emberi pár esetén a
  saját, meglévő magyarázó-folyamatát használja.
* A választ a kérdezőnek mutatja. A `shows.described` és a `text` együtt
  jó rövid megjelenítés; a `forcing` külön jelölhető.
* Az AI-partner saját licitjére nem kell `explain`-t küldeni (a partner a
  rendszeréből tudja).

---

## 6. `POST /v1/bridge/card` — tervezet

A pár konvenciókártyája a szabványos WBF-kártya szerkezetében. **A kibicben
még nincs megvalósítva** (`capabilities.endpoints.card = false`); a
formátumot a következő kiegészítés rögzíti. Előzetes váz:

```json
{"protocol": "mohabridzs-ai/1.1", "request_id": "...",
 "actor": {"seat": "S", "profile_code": "kibic_stand"},
 "format": "html"}
```

Válasz: `{"request_id": "...", "card": {...WBF-szerkezet JSON...},
"html": "<!doctype html>..."}`. A kártyaválasz méretkorlátja 256 KiB
(eltérés az 1.0.1 64 KiB-jától).

---

## 7. Adatvédelem (az 1.0.1 12. pontjának kiegészítése)

* Az `explain` és a `card` válasza nem tartalmazhat kéz-adatot, és nem
  függhet tőle.
* Az AI-szolgáltatás **teszt/tanító** kiegészítései (a kibicnél
  `meta.kibic.debug`, `/v1/kibic/*`) nem részei ennek a protokollnak, és
  éles asztalon nem használhatók: azok a licitáló kezét is tartalmazzák.

---

## 8. Változásnapló

| Verzió | Változás |
|---|---|
| 1.1.0 (tervezet) | `capabilities`, `alert` a licitválaszban, `explain`, `card` (tervezet). |
