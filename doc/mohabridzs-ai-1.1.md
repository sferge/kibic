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
hármat teszi a protokoll részévé. Emellett a MohaBridzs átadhatja, milyen
rendszert játszanak a vonalak — a jó licithez az AI-nak tudnia kell, mit
játszik az ellenfél, az alertálatlan licitek értelmezéséhez is. Minden
**visszafelé kompatibilis**: minden 1.0-s kérés és válasz változatlanul
érvényes.

A rendszer **kiválasztása** (rendszerlista, más rendszer kártyája,
váltás) nem része az 1.1-nek: az `mohabridzs-ai-1.2-tervezet.md`-ben van.
Az 1.1-ben egy AI-játékos egy rendszert játszik (a kibicnél: egy
szolgáltatás-példány = egy rendszer).

Ez a dokumentum csak a változásokat írja le; minden, amit nem említ (fejlécek,
idempotencia, határidő, jelölések, adatvédelem), az 1.0.1 szerint marad.

---

## 1. Áttekintés

| Elem | Új? | Kötelező? | Röviden |
|---|---|---|---|
| `GET /v1/bridge/capabilities` | új végpont | SHOULD | Mit tud az AI-szolgáltatás, melyik rendszert játssza, és milyen rendszereket ismer. |
| `game.systems` a kérésekben | új mező (MB küldi) | MAY | Melyik vonal milyen rendszert játszik. Az AI ebből tudja, mit játszik az ellenfél. |
| `history.auction[].alert` | új mező (MB küldi) | MAY | Az elhangzott licit alertje és magyarázata, ahogy az asztalnál elhangzott. |
| `alert` a licitválaszban | új mező (AI küldi) | SHOULD | Ha a választott licit a rendszer szerint alertálandó: a megállapodás szövege. |
| `POST /v1/bridge/explain` | új végpont | SHOULD | Egy elhangzott licit jelentése a pár rendszerében — **kéz nélkül**. |
| `POST /v1/bridge/card` | új végpont | MAY | Az AI-játékos konvenciókártyája (WBF-szerkezet, JSON + nyomtatható HTML). |

A MohaBridzs az 1.0-s AI-t továbbra is ugyanúgy hívja. Egy 1.1-es AI-nál a
`capabilities` válasza mondja meg, melyik új funkció érhető el; amit nem
támogat, azt a MohaBridzs nem kéri, és a felületen nem kínálja fel. Az új
kérésmezőket az 1.0-s AI figyelmen kívül hagyja (1.0.1: ismeretlen mező nem hiba).

---

## 2. Kötelező és ajánlott követelmények (az 1.0.1 2. pontjának kiegészítése)

| Szint | Követelmény | Előírás |
|---|---|---|
| MUST | Visszafelé kompatibilitás | Az 1.1-es AI az `X-MohaBridzs-Protocol: 1.0` fejlécű kérést is kiszolgálja, változatlanul. |
| MUST | Az új kérésmezők nem kötelezők | A `game.systems` és a `history.auction[].alert` hiánya, `null` értéke vagy ismeretlen rendszerkód nem hiba: az AI ilyenkor úgy dönt, mint nélkülük. |
| MUST | A magyarázat nem ismerheti a kezet | Az `explain` és a `card` válasz **kizárólag a megállapodásból** készül. A kérés nem tartalmaz kezet; ha mégis tartalmazna, az AI figyelmen kívül hagyja. A válasz a kéztől semmilyen módon nem függhet. |
| MUST | Saját vonal | Az `explain` csak a magyarázó AI **saját vonalán** elhangzott licitet magyarázza. Az ellenfél licitjére hibát ad (HTTP 400). |
| MUST | Őszinteség | Ha a licitre nincs megállapodás, az `explain` ezt mondja (`agreed: false`), nem talál ki jelentést. |
| SHOULD | Alert a licittel | Ha a választott licit alertálandó, a licitválasz `alert` mezője tartalmazza a szöveget. |
| SHOULD | Képességek | A `GET /v1/bridge/capabilities` végpont megvalósítása. |
| SHOULD | Rövid magyarázat | Az `explain` szövege legfeljebb 300 karakter; belső gondolatmenetet nem tartalmaz. |
| SHOULD (MB) | A vonalak rendszere | Ha a MohaBridzs tudja, milyen rendszert játszanak a párok, küldje a `game.systems`-ben. |

---

## 3. `GET /v1/bridge/capabilities`

Kérés: törzs nélküli `GET`. Titok (`Authorization`) nem szükséges; a válasz
nem tartalmaz érzékeny adatot.

```json
{
  "protocol": "mohabridzs-ai/1.1",
  "accepts": ["mohabridzs-ai/1.0", "mohabridzs-ai/1.1"],
  "endpoints": {"bid": true, "play": true, "explain": true, "card": true},
  "bid_alert": true,
  "default_system": "KIBIC_STAND",
  "systems": [
    {
      "code": "KIBIC_STAND",
      "name": "Kibic standard",
      "kind": "KONVENCIOKARTYA",
      "family": "NATURAL",
      "description": "...",
      "version": "1.0",
      "default": true,
      "summary": {
        "openings": "1♣ 3+ 12–21 · 1♦ 3+ 12–21 · 1♥ 5+ 12–21 · 1♠ 5+ 12–21 · 1NT 15–17 · 2♣ 22+ (alert) · ...",
        "general": "Ötös nemes, erős szan (15-17), 2/1 gémforsz ...",
        "conventions": ["Negatív kontra", "Stayman", "Jacoby-transzfer", "..."]
      }
    }
  ]
}
```

| Mező | Típus | Jelentés |
|---|---|---|
| `protocol` | string | A legmagasabb támogatott protokoll. |
| `accepts` | string[] | Az elfogadott `X-MohaBridzs-Protocol` verziók. |
| `endpoints.*` | boolean | Melyik végpont érhető el. `false` esetén a MohaBridzs nem hívja. |
| `bid_alert` | boolean | Ad-e a licitválasz `alert` mezőt. |
| `default_system` | string | A rendszer, amit ez az AI-játékos játszik. |
| `systems[]` | array | Az AI által **ismert** rendszerek (amelyeknek van konvenciókártyájuk). Ezek kódjai használhatók a `game.systems`-ben. |
| `systems[].code` | string | A rendszer kódja. |
| `systems[].name`, `description`, `family`, `version` | string / null | Emberi név és leírás. |
| `systems[].summary` | object / null | Rövid kivonat a kártyából: `openings` (a nyitások egy sorban), `general` (stílus), `conventions` (a konvenciók nevei). |
| `systems[].default` | boolean | Ezt játssza-e az AI. |

**MohaBridzs-oldali ajánlás:** a meccs indítása előtt kérdezze le. A
`systems` listák uniója jó alap ahhoz a listához, amiből a humán párok is
kiválaszthatják a rendszerüket (plusz „természetes / ismeretlen”). Ha a
végpont nem létezik (404), az AI 1.0-snak tekintendő: csak `bid` és `play`.

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

## 5. A vonalak rendszere és az alertek a kérésben

Két új, **nem kötelező** kérésmező a `bid`, `play` és `explain` kérésben.

### 5.1 `game.systems`

```json
"game": {
  "match_id": "5aa92d15-...", "board_number": 3, "table_index": 0,
  "vulnerability": "ns",
  "systems": {"NS": "KIBIC_STAND", "EW": "PRECISION"}
}
```

| Mező | Típus | Jelentés |
|---|---|---|
| `game.systems.NS`, `game.systems.EW` | string vagy null | A vonal rendszerének kódja. `null` vagy hiányzik: nem ismert (természetesnek vehető). |

**Miért kell.** A licitek értelmezése — az alertálatlanoké is — attól
függ, mit játszik a pár: erős vagy gyenge treff, mekkora az 1NT, mit
jelent egy közbeszólás. Az AI a saját vonala rendszerét ismeri; az
ellenfelét ebből tudja meg. Egyetlen AI-játékos esetén is számít, akár
emberekkel játszik egy asztalnál, akár ellenük.

**Rendszerkódok.** A kódok a `capabilities` `systems[].code` értékei. Egy
rendszert, amit az AI nem ismer, továbbra is értelmes elküldeni: az AI
akkor tudja, hogy az ellenfél „nem ismert rendszert” játszik, és általános
elvek szerint értelmez.

**Az AI kötelezettsége:** MUST — a mező hiánya vagy ismeretlen kódja nem
hiba. MAY — a saját vonalra küldött kódot összevetheti azzal, amit
játszik, és eltérésnél a naplóban jelezheti (a kibic: `meta.kibic.systems.own_mismatch`).

### 5.2 `history.auction[].alert`

```json
"auction": [
  {"seat": "N", "call": "1C", "alert": "Erős treff, 16+"},
  {"seat": "E", "call": "1D", "alert": null},
  {"seat": "S", "call": "P"}
]
```

| Mező | Típus | Jelentés |
|---|---|---|
| `alert` | string, null vagy hiányzik | Ha a licitet alertálták: az asztalnál elhangzott magyarázat (vagy üres string, ha csak alertálták). `null`/hiányzik: nem alertálták. |

Az ellenfél mesterséges licitjeit így az AI akkor is érti, ha a
rendszerüket nem ismeri. **Csak az AI számára szabályosan ismert
alerteket** szabad küldeni: amit a döntő játékos az asztalnál megtudott
volna (ellenfél alertje és magyarázata igen; a saját partner alertje a
bridzsszabály szerint a partner számára nem információ, azt ne küldje).

### 5.3 A kibic megvalósításának állapota

| Lépés | Állapot |
|---|---|
| A mezők fogadása; a vonalak rendszerének naplózása (`meta.kibic.systems`) | kész |
| Védekező szabályok feltétele az ellenfél rendszere (`ha: {ellenfel_pont}`, `ha: {ellenfel_csalad}`) | kész (2026-10-01) |
| Az ellenfél licitjeinek értelmezése az ő rendszerük (vagy rendszercsaládjuk) szabályai szerint | kész (2026-10-01) — lásd `MohaBridzs-kibic-interfesz.md` 3. pont |
| Az alertszöveg felhasználása | tervezett |

---

## 6. `POST /v1/bridge/explain`

Egy **már elhangzott** licit jelentése a pár rendszerében.

A MohaBridzs annak az AI-játékosnak küldi, akinek a vonalán a licit
elhangzott — a valódi asztalnál a licitáló **partnere** magyaráz. AI-párnál
bármelyik tagja válaszolhat; a válasz ugyanaz, mert a megállapodásból jön.

### 6.1 Fejlécek

Mint az 1.0.1 3.2 pontjában, az alábbi eltérésekkel:

```
X-MohaBridzs-Protocol: 1.1
Idempotency-Key: nem szükséges (a válasz az állapotból determinisztikus)
```

### 6.2 Kérés

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
    "profile_code": "kibic"
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
| `actor.profile_code` | string | ajánlott | Mint a licitkérésben. |
| `state.dealer` | NESW | igen | Az osztó. |
| `history.auction` | array | igen | A licitmenet legalább a kérdezett licitig (utána jöhet több is). |
| `question.call_index` | egész | igen | A kérdezett licit sorszáma a `history.auction`-ben, **0-tól**. |
| `question.asked_by` | NESW | nem | Ki kérdezett. Naplózásra; a választ nem befolyásolja. |

**A kérés NEM tartalmaz** `visible_hands`-et, `legal_actions`-t és
`history.play`-t. A MohaBridzs ne is küldje őket; ha mégis jönnek, az AI
figyelmen kívül hagyja (MUST, 2. pont).

### 6.3 Válasz

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

### 6.4 MohaBridzs-oldali ajánlás

* Az ellenfél licitjére kattintva (vagy „Mit jelent?” gombbal) az MB a
  licitáló **vonalán ülő AI-nak** küld `explain` kérést; emberi pár esetén a
  saját, meglévő magyarázó-folyamatát használja.
* A választ a kérdezőnek mutatja. A `shows.described` és a `text` együtt
  jó rövid megjelenítés; a `forcing` külön jelölhető.
* Az AI-partner saját licitjére nem kell `explain`-t küldeni (a partner a
  rendszeréből tudja).

---

## 7. `POST /v1/bridge/card`

Az AI-játékos **konvenciókártyája** a szabványos WBF-kártya szerkezetében:
„partner, mutasd a kártyádat, mit játszunk?”. Bárki elkérheti az
asztalnál — partner és ellenfél is —, mert a megállapodást írja le, kezet
nem tartalmaz. (Más rendszer kártyájának kérése: 1.2-tervezet.)

### 7.1 Kérés

```json
{
  "protocol": "mohabridzs-ai/1.1",
  "request_id": "5aa92d15:card:S",
  "actor": {"seat": "S", "profile_code": "kibic"},
  "format": "html"
}
```

| Mező | Kötelező | Jelentés |
|---|---|---|
| `actor.profile_code` | ajánlott | Mint a licitkérésben. |
| `actor.seat` | nem | Naplózásra. |
| `format` | nem | `html` (alap): adat + nyomtatható HTML; `json`: csak adat. |

### 7.2 Válasz

```json
{
  "request_id": "5aa92d15:card:S",
  "system": "KIBIC_STAND",
  "name": "Kibic standard",
  "card": {
    "system": "KIBIC_STAND",
    "name": "Kibic standard",
    "header": {"jatekosok": "...", "kategoria": "..."},
    "general": "Ötös nemes, erős szan (15-17), 2/1 gémforsz ...",
    "openings": [
      {"opening": "1NT", "label": "1NT", "artificial": false,
       "points": [15, 17], "min_length": null, "neg_double_through": null,
       "description": "15-17 FP; 4333, 4432, 5332 vagy 6322 minorral",
       "responses": [{"call": "2♣", "text": "Stayman: 4-es nemest kérdez", "alert": true}],
       "subsequent": ["Gerber", "Jacoby-transzfer", "Smolen", "Stayman", "Texas-transzfer"],
       "passed_hand": []}
    ],
    "competitive": {"overcalls": ["..."], "nt_overcall": ["..."], "takeout_double": ["..."],
                    "cue_bids": ["..."], "vs_nt": ["..."], "vs_preempts": ["..."]},
    "conventions": [{"code": "STAYMAN", "name": "Stayman", "summary": "..."}],
    "leads": null, "signals": null, "slam": ["..."],
    "forcing_pass": "...", "psychics": null, "special": ["..."],
    "stats": {"rules": 762, "alerts": 322}
  },
  "html": "<!doctype html>..."
}
```

| Mező | Jelentés |
|---|---|
| `system`, `name` | Melyik rendszer kártyája (az AI ezt játssza). |
| `card.openings[]` | A nyitások táblázata (a WBF-kártya második oldala): nyitás, mesterséges-e, minimális hossz, negatív kontra meddig, pontsáv, leírás, válaszok (alert-jelöléssel), a folytatás konvenciói, passzolt kéz. |
| `card.competitive` | Védekező és küzdelmi licitek fejezetenként; minden tétel „licit: jelentés” szöveg. Csak a nem üres fejezetek szerepelnek. |
| `card.conventions[]` | A használt konvenciók, rövid leírással. |
| `leads`, `signals`, `slam`, `forcing_pass`, `psychics`, `special`, `general` | A kártya kézzel írt része; `null`, ha nincs kitöltve (a HTML „kitöltendő”-t mutat). |
| `html` | Önálló HTML-oldal (A4 fekvő, két lap), böngészőben megjeleníthető és PDF-be nyomtatható. |

**Hibák:** HTTP 400, ha a kártya nem készíthető el.

**Előállítás.** Az AI a kártyát a kérésre állítja elő a rendszer aktuális
szabályaiból, és a rendszer következő változásáig ugyanazt adja. A
MohaBridzs gyorsítótárazhatja a `system` szerint.

A kártyaválasz méretkorlátja **256 KiB** (eltérés az 1.0.1 64 KiB-jától).

**MohaBridzs-oldali ajánlás:** „Konvenciókártya” gomb az AI-játékos neve
mellett; a `html` új lapon vagy beágyazott keretben (`iframe srcdoc`).

---

## 8. Adatvédelem (az 1.0.1 12. pontjának kiegészítése)

* Az `explain` és a `card` válasza nem tartalmazhat kéz-adatot, és nem
  függhet tőle.
* Az AI-szolgáltatás **teszt/tanító** kiegészítései (a kibicnél
  `meta.kibic.debug`, `/v1/kibic/*`) nem részei ennek a protokollnak, és
  éles asztalon nem használhatók: azok a licitáló kezét is tartalmazzák.

---

## 9. Változásnapló

| Verzió | Változás |
|---|---|
| 1.1.0 (tervezet) | `capabilities`, `alert` a licitválaszban, `explain`, `card`. |
| 1.1.0 (tervezet, 2. kör) | `game.systems` és `history.auction[].alert` a kérésekben (5. pont); `capabilities.default_system` és `systems`. A rendszerválasztás az 1.2-tervezetbe került. |
