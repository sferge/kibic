# MohaBridzs ↔ kibic interfész — teljes leírás

| Tétel | Érték |
|---|---|
| Állapot | a kibic kódjának állapota **2026. október 21-én** (`src/kibic/szolgaltatas/api.py`) |
| Vezetékprotokoll | `mohabridzs-ai/1.0` és `mohabridzs-ai/1.1` (mindkettőt elfogadja); kiosztástervező: `mohabridzs-deal-design/1.1` (8. pont) |
| Új (1.2) | a vonalak rendszere (`game.systems`) és a rendszercsalád — **a kibicben megvalósítva 2026-10-01** (3. pont) |
| Kiváltja | ez a dokumentum az egyetlen áttekintés; a részletes leírások megmaradnak (1. pont) |

**Ez a KUMULÁLT dokumentum.** Minden, amit a kibic a MohaBridzs és az
emberek felé nyújt — végpontok, felületek (szerkesztő, kártya),
beállítások, titkok, adatvédelem — itt aktuálisan benne van, legalább
összefoglalva és hivatkozva. Ha egy új szolgáltatás vagy beállítás
megjelenik, ez a dokumentum vele együtt frissül (a változásnaplóban is). A
részletes leírások (1. pont) a részleteket adják; ha ellentmondás van, az
újabb dátumú szöveg érvényes, és ezt itt jelezni kell.

**Jelölés a dokumentumban.** ✅ megvalósítva és használható · 🟡 megvan, de
csak részben (pl. fogadja, naplózza, de a döntést még nem befolyásolja) ·
⏳ javaslat, még nincs kód.

---

## 1. A dokumentumok viszonya

| Dokumentum | Mit ír le | Viszony ehhez |
|---|---|---|
| `MohaBridzs-AI-Gateway-Interfesz-v1.0.1` (PDF / `…-v1.md`) | Az alapszerződés: `bid`, `play`, fejlécek, idempotencia, határidő, kártya- és licitkódolás, fallback. | **Érvényes.** Itt csak összefoglalva (4–5. pont). |
| `doc/mohabridzs-ai-1.1.md` | Kiegészítés: `capabilities`, `alert`, `explain`, `card`, `game.systems`, `auction[].alert`. | **Érvényes**, ennek a frissebb (2. körös) változata. Az MB-nél lévő régebbi `…-v1.1.md` még nem tartalmazza a `game.systems`-t és a kártyát. |
| `doc/mohabridzs-ai-1.2-tervezet.md` | Rendszerválasztás párokra. | Beolvadt a 3. és 6. pontba (kiegészítve az ellenfél rendszerével és a családdal). |
| `doc/kibic-dd-tabla.md` + `doc/semak/` | `POST /v1/kibic/dd-tabla` részletesen, JSON-sémával. | Érvényes; itt összefoglalva (9.2). |
| `doc/kibic-tanito-api.md` | Teszt mód, tanító nyom, `/v1/kibic/magyaraz`. | Érvényes; itt összefoglalva (10. pont). |
| `doc/szerkeszto.md` | A böngészős rendszerszerkesztő használata. | Érvényes; a végpontjai itt (11. pont). |
| `doc/mohabridzs-deal-design-1.1.md` | A kiosztástervező szerződése (`mohabridzs-deal-design/1.1`); kiváltja az MB `REBASE_1.1.28.md` kiosztástervező-részét. | Érvényes; itt összefoglalva (8. pont). |

---

## 2. Áttekintés

A kibic **egy** HTTP-szolgáltatás (FastAPI, alapból a `9050`-es porton), két
végpontcsaláddal:

* **`/v1/bridge/*` — a MohaBridzs AI Gateway szerződés.** Ezt hívja a
  MohaBridzs, amikor egy AI-játékos licitál, lapot tesz, magyaráz vagy a
  kártyáját mutatja. Szigorú szerződés: pontosan egy szabályos akció,
  határidő, idempotencia, **lapinformáció soha nem szivárog** a
  magyarázatba.
* **`/v1/kibic/*` — a kibic saját szolgáltatásai.** Double dummy elemzés
  (ezt a MohaBridzs is használja), a tanító / műhely felület (a licitáló
  kezét is tartalmazhatja — éles asztalon, ellenfélnek nem), és a
  rendszerszerkesztő.

A kibic **nem tárol asztali állapotot**: minden kérés hozza a szükséges
adatot (licitmenet, lapok, profil, rendszerek). Ezért egy kibic-példány sok
asztalt és sok AI-játékost szolgálhat ki párhuzamosan.

### 2.1 Végpontok egy táblázatban

| Végpont | Metódus | Titok | Mire | Kezet tartalmaz? | Állapot |
|---|---|---|---|---|---|
| `/v1/bridge/capabilities` | GET | — | mit tud az AI, milyen rendszereket ismer | nem | ✅ |
| `/v1/bridge/systems` | GET | — | a rendszerek katalógusa: család → alaprendszer → rendszer (választólistákhoz) | nem | ✅ 2026-10-02 |
| `/v1/bridge/bid` | POST | AI | licitdöntés | a kérés igen; a válasz nem (teszt módban: `meta.kibic.debug` igen) | ✅ |
| `/v1/bridge/play` | POST | AI | lapválasztás: minta a rejtett kezekből, DD-szűrő, a jelzésrendszer a jó lapok közül | a kérés igen; a válasz nem (teszt módban: `meta.kibic.debug` igen) | ✅ 2026-10-21 |
| `/v1/bridge/explain` | POST | AI | egy elhangzott licit jelentése (a megállapodás) | **nem** | ✅ |
| `/v1/bridge/card` | POST | AI | konvenciókártya (JSON + nyomtatható HTML) | **nem** | ✅ |
| `/v1/kibic/dd` | POST | kibic | double dummy egy játékállásra, laponként | igen (mind a négy kéz) | ✅ |
| `/v1/kibic/dd-tabla` | POST | kibic | DD-tábla, par, eltérés a partól — leosztásonként | igen | ✅ |
| `/v1/kibic/kiosztas` | POST | AI | kiosztássor: generált (célzott licit- / lejátszási helyzet), verseny-PBN, kész kiosztások ellenőrzése | igen (ez a lényege) | ✅ 2026-10-03 |
| `/v1/kibic/kiosztas/kepessegek` | GET | AI | mit vállal a kiosztástervező (helyzetek, technikák, korlátok) | nem | ✅ 2026-10-03 |
| `/v1/kibic/licit` | POST | kibic | műhely: mit licitálna a kibic, mit értett a menetből | igen | ✅ |
| `/v1/kibic/magyaraz` | POST | kibic | műhely: egy licit jelentése + mit mondott volna a kibic | igen (ha küldik) | ✅ |
| `/v1/kibic/kartya` | GET | — | a kártya HTML-ben, böngészőnek | nem | ✅ |
| `/v1/kibic/leiras` | GET | — | a rendszer TELJES leírása (HTML / Markdown) — a kártya hosszú párja | nem | ✅ |
| `/v1/kibic/allapot` | GET | — | állapot: DDS, adatbázis, teszt mód, betöltött rendszerek | nem | ✅ |
| `/v1/kibic/ujratolt` | POST | kibic | a gyorsítótárak ürítése (rendszer, kártya, idempotencia) | nem | ✅ |
| `/szerkeszto` és `/v1/kibic/szerk/*` | GET/POST | kibic | a rendszerszerkesztő | nem | ✅ |
| `/healthz`, `/readyz` | GET | — | életjel / kész-e (adatbázis) | nem | ✅ |

**Titkok — egy érték elég.** A titok mindig `Authorization: Bearer <titok>`
fejlécben megy. Két oldalon van, más néven:

| Hol | Változó | Mire |
|---|---|---|
| MB (`.env`) | `AI_SHARED_SECRET` | ezt KÜLDI az MB a kibicnek, minden hívásban (`/v1/bridge/*`, `/v1/kibic/dd*`, `/v1/kibic/kiosztas`) |
| kibic | `KIBIC_SHARED_SECRET` | ezt FOGADJA el a kibic — minden védett végponton |
| kibic | `KIBIC_AI_SHARED_SECRET` | **opcionális**: csak ha az AI-végpontoknak (oszlop: „AI”) KÜLÖN titkot akarsz; üresen a `KIBIC_SHARED_SECRET` érvényes rájuk is |

Az ajánlott (és eddig is működő) beállítás: a kibicben csak
`KIBIC_SHARED_SECRET`, ugyanazzal az értékkel, mint az MB
`AI_SHARED_SECRET`-je. A „Titok” oszlopban: „AI” = `KIBIC_AI_SHARED_SECRET`,
ha meg van adva, különben `KIBIC_SHARED_SECRET`; „kibic” = mindig
`KIBIC_SHARED_SECRET`; „—” = titok nélkül. Ha a kibic titka üres, a védett
végpontok is titok nélkül hívhatók (csak fejlesztéshez).

---

## 3. A legfontosabb kérdés: ki milyen rendszert játszik

### 3.1 Miért kell a kibicnek mindkét vonal rendszere

A kibic minden licitnél **kényszertárat** épít: a négy kézről azt, amit az
eddigi licitek biztosan elárulnak (pontsáv, színhosszak, tagadott dolgok).
Ebből dönt, ebből magyaráz, és ebből vesz mintát a szimulációhoz.

* A **saját vonal** licitjeit a saját rendszer szerint kell érteni.
* Az **ellenfél** licitjeit az **ő** rendszerük szerint: mást jelent az 1♣
  erős treffben és természetes rendszerben, más egy 1NT 12–14-es vagy
  15–17-es sávval. Csak így ismeri fel a kibic, hogy az ellenfél erős vagy
  gyenge, támadó vagy védekező licitet alkalmaz — támadó, küzdelmi és
  védekező helyzetben egyaránt.
* Ugyanez kell a **kijátszáshoz** (indulás, a rejtett kezek becslése a
  lejátszás közben): a lejátszó modul ugyanebből a kényszertárból dolgozik
  majd.

### 3.2 A rendszer azonosítója: `game.systems` (✅ 2026-10-01)

**Minden `bid`, `play` és `explain` kérésben** az MB megmondja, melyik
vonal mit játszik. A rendszert **nem** a `profile_code` jelöli ki: az az
AI-játékost (modellt, gépet) azonosítja.

```json
"game": {
  "match_id": "5aa92d15-...", "board_number": 3, "table_index": 0,
  "vulnerability": "ns",
  "systems": {"NS": "KIBIC_STAND", "EW": "STRONG_CLUB"}
}
```

Egy vonal értéke háromféle lehet:

| Érték | Példa | Mikor |
|---|---|---|
| ismert **rendszer** (vagy alaprendszer) kódja | `"KIBIC_STAND"` | a kibic ismeri a pár rendszerét (`/v1/bridge/systems`) |
| **rendszercsalád** kódja | `"STRONG_CLUB"` | csak a családja ismert (`/v1/bridge/systems` → `families[]`) |
| kód + család | `{"code": "KOVACS_PRECISION", "family": "STRONG_CLUB"}` | ismeretlen rendszer, ismert családdal — a kód a naplónak, a család a döntésnek |
| `null` / hiányzik | | semmit nem tudunk |

### 3.3 Rendszercsalád (RENDSZERCSALAD) — új rendszer-fajta (✅)

**A hierarchia (2026-10-02):** RENDSZERCSALÁD → ALAPRENDSZER → RENDSZER.

| Fajta | Mi | Kötelező kapcsolat |
|---|---|---|
| RENDSZERCSALÁD | egy család általános rendszere (`NATURAL`, `STRONG_CLUB`, `ACOL`, `POLISH`) | — |
| ALAPRENDSZER | emberi forrásból (klubstandard, SAYC, Precision, Heavy Club …) | pontosan **egy család** (`csalad`) |
| RENDSZER | amit egy pár játszik: alaprendszer + konvenciók | pontosan **egy alaprendszer** (aktív hivatkozás) és **egy család** — az alaprendszeréé |

A YAML-import ezt ellenőrzi (hiba, ha a rendszernek nincs vagy több
alaprendszere van, ha nincs családja, vagy ha a családja eltér az
alaprendszeréétől). **A Precision nem család**, hanem az erős treff család
egyik (alap)rendszere; a `"PRECISION"` családkódot a kibic `STRONG_CLUB`-ként
érti. **A lengyel treff (POLISH) család**: az 1♣ háromágú (gyenge szan /
természetes treff / erős) — se nem természetes, se nem erős treff.

A RENDSZER, ALAPRENDSZER, KONVENCIO, GYUJTEMENY mellé: egy rendszercsalád
**általános rendszere** — amit egy ismeretlen pár rendszeréről a családja
alapján feltételezni lehet. Tartalma:

* **a nyitások** a családra jellemző jelentéssel, tág sávokkal (pl. erős
  treff: 1♣ 16+ mesterséges; 1♦ 11–15, lehet rövid; 1M 5+ 11–15; 1NT 13–16;
  2♣ 11–15 hosszú treff; gyenge kettesek);
* **a legfontosabb válaszok** a mesterséges nyitásokra (1♣-1♦ negatív
  0–7; pozitív válaszok);
* **általános elvek** (az emelés elve);
* ami a család tagjai között nagyon eltér (pl. a 2♦ nyitás), az kimarad.

Ami a családban nincs leírva (pl. az ellenfél közbeszólásai), azt a kibic
**természetesen — a saját rendszere szerint** — érti; ez volt eddig az
egyetlen működés.

A kódja a meglévő `csalad` érték: `STRONG_CLUB`, `NATURAL`, `ACOL`,
`POLISH` (mind gépi javaslat, átnézendő). Minden ismert rendszer adatai közt ott a családja is
(`csalad`), így egy ismert rendszer a családján keresztül is hivatkozható.
Fájlok: `rendszerek/yaml/csaladok/`. Migráció: `schema/024_rendszercsalad.sql`.

### 3.4 Melyik rendszert használja a kibic (✅)

| Mire | Melyik rendszer | Ha nincs megadva vagy ismeretlen |
|---|---|---|
| a saját licitjeihez és a **saját vonal** licitjeinek megértéséhez | `game.systems[saját vonal]` (ismert rendszer) | a profilból (régi kliens); a napló jelzi: `own_source: "profile"`, `warning` |
| az **ellenfél** licitjeinek megértéséhez (kényszertár) | `game.systems[ellenfél]`: ismert rendszer, vagy a család általános rendszere | a saját rendszerünk szerint (a régi működés); `opponents_known: false` |
| `explain` | a magyarázó vonalának rendszere; az előtte elhangzott ellenfél-licitek az övék szerint | a profilból |
| `card` `system` nélkül | a saját vonal rendszere | a profilból |
| `play` | a saját vonal rendszere: a jelzésrendszere (`jelzesek:` profil) és a licit kényszertára; az ellenfél licitjei az ő rendszerük szerint (a mintavételhez) | jelzésrendszer nélkül csak a DD; kényszertár nélkül egyenletes minta |

**Tartalék a saját rendszerre** (régi kliens, `game.systems` nélkül), az
`actor.profile_code`-ból: (1) nincs profilkód → az alaprendszer
(`KIBIC_RENDSZER`, a mostani telepítésben `KIBIC_STAND`); (2) a kód a
`KIBIC_PROFILOK` leképzésben → az ott megadott rendszer; (3) a kód egy
kínált rendszer kódja → az a rendszer; (4) egyébként (pl. a modell neve) →
az alaprendszer.

### 3.5 A saját rendszerben: mi a teendő különféle ellenfél esetén (✅ a nyelvben)

Két új helyzeti feltétel (`ha:`) a kibic nyelvében:

| Kulcs | Jelentés | Példa |
|---|---|---|
| `ellenfel_pont: 16+` | valamelyik ellenfél a licitjeivel **tudottan** ennyi pontot ígért (a kényszertár szerint) | erős treff elleni védekezés: az 1♣ 16+ |
| `ellenfel_csalad: STRONG_CLUB` | az ellenfél vonalának rendszercsaládja (lista is lehet) | „erős treff ellen …” |
| `ellenfel_szin: {H: 5}` | az ellenfél **tudottan** ennyi lapot ígért a színben (rendszerükből vagy az alertjükből) | transzfer-közbeszólás az 1NT-re (Rubensohl) |
| `ellenfel_licitalt: true` | az ellenfél már mondott nem-passz licitet | küzdelmi elvek (a törvény) |

Példa: „erős treff ellen Timbuktut játszunk” (2026-10-02 óta a KIBIC_STAND
része: `konvenciok/timbuktu.yaml`):

```yaml
- {minta: "(1C) X", ha: {ellenfel_pont: 16+}, …, alert: "Timbuktu: …"}
- {minta: "(1C) 1D", ha: {ellenfel_pont: 16+}, …}
```

A **jelentéshez kötött** feltétel (`ellenfel_pont`) a jobb: magától él,
akárhonnan tudjuk, hogy az 1♣ erős — ismert rendszerből, a családból vagy
(később) az alertből —, és **nem** él az erős treffesek 2♣-je ellen (az
11–15), sem a természetes 1♣ ellen. A `ellenfel_csalad` akkor kell, ha a
teendő a család egészétől függ, nem egy licit jelentésétől. Ha a családot
nem tudjuk, a családhoz kötött sor nem él.

**Feltételes felülírás (2026-10-02):** ha egy kártyán előrébb álló
konvenció egy licitet CSAK helyzeti feltétellel (`ha:`) ír le — pl. a
Timbuktu az „(1C) X”-et csak 16+-os 1♣ ellen —, a hátrébb álló szabály
(az információs kontra) megmarad, és mindenhol él, ahol a felülíró
feltétele nem teljesül. A szerkesztő a feloldásnál ezt „feltételes
felülírás”-ként mutatja.

### 3.6 `history.auction[].alert` — az ellenfél magyarázata (✅ 2026-10-02)

```json
"auction": [
  {"seat": "N", "call": "1C", "alert": "Erős treff, 16+"},
  {"seat": "E", "call": "1D", "alert": null}
]
```

Az ellenfél alertje és az asztalnál adott magyarázata. Csak a döntő
játékos számára szabályosan ismert alertet szabad küldeni: az ellenfélét
igen, a saját partnerét nem. Az `alert` lehet szöveg, `{"text": "…"}`, vagy
`true` (alertálták, de magyarázat még nincs).

**Az ellenfél egy licitjét a kibic ebben a sorrendben érti:**

1. az **ő ismert rendszerük vagy családjuk** szerint (`game.systems`);
2. ha az nem írja le: az **alert szövegéből** — ami biztosan kiolvasható:
   pontsáv („11-15”, „16+”, „0-7 HCP”), színhossz („5+ kőr”, „6+ ♦”,
   „hosszú treff”, „mindkét nemes”), „egyenletes”, „gyenge / blokk”, „erős
   treff”, „természetes”. A **vagylagos** szövegből („káró, vagy mindkét
   nemes”) csak a pont olvasható ki, a színek nem;
3. ha az sincs: **természetesen, a saját rendszerünk szerint** (a régi működés).

Az alert tehát a saját rendszerünk ELŐTT jön: ha az ellenfél elmondta, mit
jelent a licitjük, az erősebb, mint amit mi jelentenénk vele. A műhely
válaszában (`/v1/kibic/licit`) az `auction_understanding[].source` mutatja,
honnan értette (`their_system` / `alert` / `own_system`), a
`coverage.from_alert` pedig, mely licitek jöttek az alertből.

**Magyarázatkérés (✅ 2026-10-02).** Ahogy az asztalnál a soron lévő
játékos megkérdezheti az ellenfél licitjének jelentését, a kibic is jelzi,
mire kér magyarázatot — a `bid` válasz `meta.kibic.explain_requests`
mezőjében:

```json
"explain_requests": [
  {"index": 3, "seat": "W", "call": "2D", "reason": "alerted_without_explanation"},
  {"index": 5, "seat": "E", "call": "3C", "reason": "not_understood"}
]
```

| `reason` | Mikor |
|---|---|
| `not_understood` | Az ellenfél licitjét se a rendszerük, se az alert, se a mi rendszerünk nem írja le. |
| `alerted_without_explanation` | Alertálták (`alert: true`), de szöveg nem jött, és az ő rendszerükből sem ismert. |

Az MB (SHOULD) a magyarázatot megszerzi — emberi ellenféltől
megkérdezi, AI-ellenféltől a `POST /v1/bridge/explain`-nel —, és a
**következő** kérésekben az `auction[index].alert`-ben küldi. Ha a döntés
még nem ment ki, ugyanazt a döntést **új `request_id`-vel** újra kérheti a
magyarázattal (az idempotencia-kulcs más). Az ellenfél **kártyáját** a
`game.systems` kódja adja; ismeretlen kódnál a családja.

**Információkérés licitdöntés közben (✅ 2026-10-04, az MB AI_PLAYER_API
v1.1 szerint).** Ha a kérés `protocol`-ja `mohabridzs-ai/1.1` (vagy újabb),
és a kibic az ellenvonal valamelyik licitjét nem érti (a fenti két `reason`
valamelyike), a végleges licit HELYETT köztes választ ad:

```json
{"request_id": "...",
 "action": {"type": "request_information", "bid_indices": [1, 3]},
 "explanation": "Magyarázatot kérek az ellenvonal licitjére: E:2D, W:3C."}
```

Az MB begyűjti a magyarázatokat, és ugyanebben a helyzetben új
`request_id`-val újra hív; a válasz a licit mellett jön:
`auction[i].information = {status: available|none|error, text, alerted}`. A
kibic az `available` szöveget úgy érti, mint egy alert szövegét (az ellenfél
rendszere után, a mienk előtt); a már megkérdezett licitet — bármi lett a
válasz (`none`, `error` is) — többször nem kérdezi, így nincs körbeforgás.
1.0-s protokollnál nem kérdez. Kikapcsolható: `KIBIC_INFO_KERES=0`. A
`capabilities` válaszban: `request_information: true`.

---

## 4. Közös szabályok a `/v1/bridge/*` végpontokra

| Téma | Szabály |
|---|---|
| Alapcím | Az AI-profil alapcíme (MB: `moha_club.email`), pl. `http://192.168.77.70:9050`. Útvonal-prefix megengedett. |
| Fejlécek | `Content-Type: application/json; charset=utf-8`, `Authorization: Bearer …`, `X-MohaBridzs-Protocol: 1.0` vagy `1.1`, `Idempotency-Key: <request_id>` (bid, play). |
| Protokollverzió | A kibic az 1.0-s és az 1.1-es kérést is kiszolgálja; a verziót nem ellenőrzi szigorúan, az ismeretlen mezőket figyelmen kívül hagyja. |
| `request_id` | Változtatás nélkül visszajön. |
| Idempotencia (bid, play) | Ugyanaz a kulcs + ugyanaz a törzs → a korábbi válasz. Ugyanaz a kulcs + más törzs → **HTTP 409**. A tár a memóriában él (512 döntés), újraindításkor elvész. |
| Határidő | A szimuláció (DD-mintavétel a mérlegelő helyzetekben) ALAPBÓL BE van kapcsolva (`KIBIC_ATJARO_SZIMULACIO=0` kapcsolja ki), időkerete `KIBIC_ATJARO_SZIM_MS` (alap: 10 000 ms). Ha a `deadline_ms` szorosabb, a keret `deadline_ms − KIBIC_ATJARO_SZIM_TARTALEK_MS` (alap tartalék: 1500 ms); 1 s alatti keretnél nincs szimuláció. Ha a keret letelik, az addig kiszámolt mintán dönt (legalább `KIBIC_SZIM_MIN_MINTA`, alap 12 minta), különben a szabály-alapú becslés. Szimuláció nélkül egy licitdöntés jellemzően néhány tíz ms. |
| Jelölések | Ülés `N E S W`; szín `C D H S`; szan a dróton **`N`** (`1N`, `3N`); lap `SA`, `HT` (a tízes `T`); hívás `P X XX`; beliállás `none ns ew both`. |
| Sikeres válasz | Csak HTTP 200. Méret: legfeljebb 64 KiB (a kártya: 256 KiB). |
| Hibák | 400 hibás kérés · 401 rossz titok · 404 ismeretlen rendszer (card) · 409 idempotencia-ütközés · 503 nincs DDS / adatbázis. |
| Tartalék | Ha a kibicnek nincs szabálya, szabályos tartalékot ad (`P`, ha lehet), és **bevallja**: `meta.source = "fallback"`, `meta.fallback_reason`. Az MB adminnaplója így magától mér lefedettséget. |

---

## 5. A `/v1/bridge/*` végpontok

### 5.1 `GET /v1/bridge/capabilities` ✅

Titok nélkül hívható. Az MB a profil mentésekor és a meccs indításakor
kérdezze le; ebből tudja, mit hívhat, és milyen rendszereket ismer az AI.

```json
{
  "protocol": "mohabridzs-ai/1.1",
  "accepts": ["mohabridzs-ai/1.0", "mohabridzs-ai/1.1"],
  "endpoints": {"bid": true, "play": true, "explain": true, "card": true,
                "systems": true},
  "bid_alert": true,
  "line_systems": true,
  "systems_catalog": "/v1/bridge/systems",
  "default_system": "KIBIC_STAND",
  "families": [
    {"code": "STRONG_CLUB", "name": "Erős treff (általános)", "description": "…"},
    {"code": "NATURAL", "name": "Természetes, 5-ös nemes (általános)", "description": "…"}
  ],
  "systems": [
    {"code": "KIBIC_STAND", "name": "Kibic standard", "kind": "RENDSZER",
     "family": "NATURAL", "description": "…", "version": "0.1", "default": true,
     "summary": {"openings": "1♣ 2+ 12–21 (alert) · 1♦ 4+ 12–21 · …",
                 "general": "Ötös nemes, erős szan (15-17), 2/1 …",
                 "conventions": ["Stayman", "Jacoby-transzfer", "…"]}}
  ]
}
```

| Mező | Jelentés |
|---|---|
| `endpoints.*` | Melyik végpont hívható. `false`-ra az MB nem hív. |
| `bid_alert` | Ad-e a licitválasz `alert` mezőt. |
| `line_systems` | `true`: a `game.systems` a döntésben is hat (saját és ellenfél, 3.4). |
| `families[]` | Az ismert rendszercsaládok: ezek kódjai is küldhetők a `game.systems`-ben (3.3). |
| `default_system` | Amit az AI `game.systems` nélkül (és rendszert nem jelölő profilkóddal) játszik. |
| `systems[]` | Az AI által **ismert** rendszerek (van kártyájuk). Ezek a kódok használhatók a profilban, a `game.systems`-ben és a `card` `system` mezőjében. |
| `systems[].summary` | Rövid kivonat a kártyából a választáshoz: nyitások egy sorban, stílus, konvenciók. |
| `systems_catalog` | A teljes katalógus címe (5.1a). |

### 5.1a `GET /v1/bridge/systems` ✅ (2026-10-02)

Titok nélkül hívható. A rendszerek **katalógusa** a hierarchia szerint
(3.3), csak az alapadatokkal — az MB ebből kínál választólistát a
játékosoknak (család → alaprendszer → rendszer), és ebből tölti a
`game.systems`-t. Gyorsítótárazható; a `/v1/kibic/ujratolt` után változhat.

```json
{
  "protocol": "mohabridzs-ai/1.2",
  "default_system": "KIBIC_STAND",
  "families": [
    {"code": "NATURAL", "name": "Természetes, 5-ös nemes (általános)",
     "name_en": "…", "description": "…", "generic_system": true,
     "base_systems": ["KIBICEGY_STAND"]},
    {"code": "STRONG_CLUB", "name": "Erős treff (általános)", "generic_system": true,
     "base_systems": []}
  ],
  "base_systems": [
    {"code": "KIBICEGY_STAND", "name": "Kibic egyesület standard", "family": "NATURAL",
     "description": "…", "version": "1.0", "systems": ["KIBIC_STAND"], "has_card": false}
  ],
  "systems": [
    {"code": "KIBIC_STAND", "name": "Kibic standard", "family": "NATURAL",
     "base_system": "KIBICEGY_STAND", "description": "…", "version": "0.1",
     "has_card": true, "playable": true}
  ]
}
```

| Mező | Jelentés |
|---|---|
| `families[]` | A rendszercsaládok. `generic_system: true`: van általános rendszere — a kód magában is küldhető a `game.systems`-ben. |
| `base_systems[]` | Az alaprendszerek, családjukkal és a rájuk épülő rendszerekkel. |
| `systems[]` | A rendszerek: `base_system` (pontosan egy), `family`, `playable` (a kibic ezzel tud licitálni — van kártyája). Ha valami nincs rendben: `problem`. |

**A `game.systems`-be** bármelyik kód mehet ellenfélnek (rendszer,
alaprendszer, család, vagy `{code, family}`); saját vonalnak a `playable`
rendszerek.

### 5.2 `POST /v1/bridge/bid` ✅

**Kérés:** az 1.0.1 szerint (`protocol`, `request_id`, `decision: "bid"`,
`deadline_ms`, `game`, `actor`, `state`, `history`, `legal_actions.calls`),
plusz az 1.1 nem kötelező mezői: `game.systems`, `history.auction[].alert`.

A kibic ezeket használja belőle:

| Mező | Mire |
|---|---|
| `actor.acting_for_seat` (vagy `seat`) | ki licitál |
| `game.systems` | a saját és az ellenfél rendszere (3.2–3.4) |
| `state.visible_hands[seat]` | a licitáló keze (**kötelező**) |
| `state.dealer`, `game.vulnerability` | osztó, beliállás |
| `history.auction` | a licitmenet |
| `legal_actions.calls` | a választható licitek — a válasz mindig ezek egyike |
| `deadline_ms` | szimuláció engedélyezése |
| `actor.profile_code` | csak tartalék: a saját rendszer, ha nincs `game.systems` (3.4) |

**Válasz:**

```json
{
  "request_id": "5aa92d15:17:0:1:bid:6",
  "action": {"type": "bid", "call": "2C"},
  "confidence": 0.8,
  "explanation": "2C — Stayman: 4-es nemest kérdez",
  "alert": {"text": "Stayman: 4-es nemest kérdez", "text_en": null},
  "meta": {
    "source": "model", "pipeline": "kibic_bid", "elapsed_ms": 31,
    "fallback_reason": null,
    "kibic": {"branch": "PAROS", "rule_source": "SZABALY",
              "understood": 2, "unknown": 0, "system": "KIBIC_STAND",
              "systems": {"own": "KIBIC_STAND", "own_source": "systems",
                          "own_sent": "KIBIC_STAND", "opponents": "STRONG_CLUB",
                          "opponents_family": "STRONG_CLUB",
                          "opponents_system": "STRONG_CLUB",
                          "opponents_known": true}}
  }
}
```

| Mező | Jelentés |
|---|---|
| `action.call` | Mindig a `legal_actions.calls` egyik eleme. |
| `confidence` | Nem valószínűség, hanem őszinteség: mennyi tudás állt mögötte (szabály 0,8; mérlegelés 0,7; elv 0,5; tartalék 0,05). |
| `explanation` | Rövid indoklás az adminnaplónak (≤ 500 karakter), gondolatmenet nélkül. Az ellenfélnek **nem** ez szól. |
| `alert` | Ha a licit a rendszer szerint alertálandó: **a megállapodás** szövege. Ha ugyanarra a licitre több szabály van, mindegyiké — így sosem árulja el, melyik ágba esik a kéz. Tartalék licitnél nincs. |
| `meta.source` | `model` vagy `fallback`. |
| `meta.kibic.rule_source` | `SZABALY` · `ELV` (általános elv) · `MERLEGELES` (a szimuláció döntött) · `HEZAG` (nincs rá szabály; a hézag-elv döntött, 5.2a) · `SPIRAL` (a kulcslap-válasz utáni spirál, 5.2b) · `NINCS` (ilyenkor tartalék passz, `meta.source = fallback`). |
| `situational_agreement` (műhely) | ha az ELV-réteg döntött, de a győztes sor egy konvenció helyzeti alakja (RKC, MOHA_3NT_4M, MOHA_SZLEM, GYORS_LASSU …): a konvenció kódja. Ilyenkor az átjáró magyarázata „Helyzeti megállapodás (KÓD) szerint.” kezdetű (nem „Nincs rá megállapodás”), a bizonyosság 0,8. |
| `meta.kibic.unknown_calls` | A menet licitjei, amelyeket a kibic nem értett — a rendszer hiányai. |
| `meta.kibic.understood_from_alert` | Az ellenfél licitjei, amelyeket az alertjük szövegéből értett (3.6). |
| `meta.kibic.explain_requests` | Mire kér a kibic magyarázatot (3.6). |
| `meta.kibic.system`, `.systems` | Melyik rendszerben döntött; a vonalak rendszere: `own`, `own_source` (`systems` / `profile` / `default`), `opponents`, `opponents_family`, `opponents_system` (ami szerint az ellenfelet érti), `opponents_known`, `own_mismatch`, `warning`. |
| `meta.kibic.debug` | **Csak teszt módban**: a tanító nyom — a licitáló kezének adataival. Éles asztalon a teszt mód legyen kikapcsolva. |

### 5.2a A hézag-elv ✅ 2026-10-03

Ha a licitre sem szabály, sem elv, sem mérlegelés nem ad hívást, a kibic NEM
passzol vakon. A **közös erő** és a **kényszer** alapján dönt, és a
szabályos hívások közül a **rendszerbeli jelentésük** szerint választ
(lezáró / géminvit / egy körre kényszerítő / gémforsz). A jelentést ugyanaz a
propagáló adja, amivel a kibic a partnert érti. Kód: `motor/hezag.py`.

* A = saját pont + a partner ígért minimuma; F = saját pont + a partner
  (valószínű) maximuma. Gémküszöb: nemes fittel 25, minor fittel 27, szanban
  24 egyenlő elosztásnál (mint a passz-elv `gemeselyes` feltétele).
* **0. Kényszer:** ha a partner utolsó (értett) licitje egy körre kényszerít,
  vagy gémforszban vagyunk és még gém alatt, passz nem lehet. A gémforsz
  gémszinten teljesül.
* **1. A ≥ gém:** gémforsz licit, ha van, különben gém.
* **2. F ≥ gém > A:** gém alatti géminvit, ha van; ha nincs, a gém esélye
  dönt (a partner sávjának alja valószínűbb; küszöb mansban 45%, bellben
  37%): gém; közepes eséllyel (25%+) gém alatti, egy körre kényszerítő leíró
  licit; különben a 3. pont.
* **3. F < gém:** kényszer nélkül passz, ha a felvétel a miénk és játszható,
  és nincs sokkal jobb fit (különben a legolcsóbb javítás oda). Kényszerben a
  legolcsóbb licit a fitbe, vagy a legolcsóbb leíró licit.
* **Játszható:** 8+ lapos fit; 7 lapos 5-2-ben; 4-3-ban csak rövidséggel a
  3 lapos adu mellett (a rövid aduból lopás plusz ütés). **Gém:** nemes
  fittel 4M; 3NT csak fogással az ellenfél színeiben; minor fittel 5m.
* A **passz-elv** (PASSZ_ELV) 2026-10-04 óta egyik sorával sem passzol
  gémesélynél vagy gémforszban (gém alatt) — ilyenkor a hézag-elv dönt.
* **4. A partner licitjét nem értjük:** ő a kapitány; a saját ígért sávom
  felső felével gém a fitben, az alsóval a legolcsóbb lezárás a legjobb
  fitben.
* **5. A partner büntetőre kontrázta a felvételüket:** büntető passz, ha a
  bukás többet ér a saját felvételünknél. Szimulációval (DD-mintavétel) a
  `buntetes_vagy_sajat` összemérés dönt; nélküle becslés: a saját
  védőütéseim + a partneré (~2) → hány bukás, és annak értéke (zóna szerint)
  a saját gémünk (×0,7) vagy részjátszmánk ellen. A partner 3-as szinten vagy
  följebb adott kontrája FOGÁST is jelent abban a színben (a 3NT-hez).
* **DD-mintavétel:** ha a kérés szimulációt enged (az átjárónál ez az
  alapműködés, 10 s időkerettel — lásd a Határidő sort), a
  „passz vagy javítás a jobb fitbe” kérdést a kényszertárból vett minta
  DD-eredménye dönti el (`vegkontraktus_valasztas`), nem a fitszámolás.

A válaszban: `meta.kibic.rule_source = "HEZAG"`, a magyarázat elején
„Nincs rá megállapodás; … hézag-elv (N. pont): …”, a bizonyosság 0,35. A
műhely-végponton (`/v1/kibic/licit`) a `gap` mező (`rule`, `reason`), és a
kérésben `"gap_principle": false` kikapcsolja. A kiosztástervező licitjében
az ilyen hívás `gap: true`.

**Szlem a hézag-elvben (✅ 2026-10-04/05).** A szerkesztő küszöbei: szín
30+, szan 33+, nagyszlem 35+ / 37+. Szan (nincs megállapodott adu): 4NT
kvantitatív invit / 6NT / 5NT / 7NT (a partner limitált sávjával). Szín
(megállapodott adu): ha a közös erő ALSÓ határa is 30+, nem áll meg a
gémben — ha még lehet, kulcslapot kérdez (kőr: 4♠, pikk: 4NT); ha a felső
határ 35+, gém fölötti kulcslicitet ad (ász / sikén, a 6-os adu alatt);
különben 6 az aduban. A partner gém fölötti, nem adu-színű licitje
megállapodott adu mellett kulcslicit: nem passzolható.

**Versenyforma (⏳ kérés az MB felé): `game.scoring`** = `"MP"` / `"BAM"` /
`"IMP"`. Párosversenyen (MP, BAM) a 6-os adu és a 6NT közül a DD-minta dönt
(a szan +10 pont, ha nem kell lopás), ha a szimuláció engedélyezett;
csapatversenyen (és ha a mező hiányzik) a biztosabb: az adu. A kibic a
mezőt már olvassa (`game.scoring` vagy `game.scoring_type`; értékek: `MP`,
`BAM`, `IMP`, kis- és nagybetű mindegy). A szimulációs mérlegelés is ehhez
igazodik: párosversenyen a büntetés akkor jobb, ha a leosztások többségén
jobb (MP-nyerési arány > 50%), csapatversenyen az IMP-átlag dönt; a
végkontraktus-választásnál MP-n a pontszám-átlag, IMP-n az IMP-átlag.

Nyitott: a „játszható” DD-mintás vizsgálata (a `deadline_ms` keretében).

### 5.2b A spirál (MOHA_SPIRAL) ✅ 2026-10-04

A kulcslap-válasz (RKC / ORKC, a MOHA_3NT_4M is) után a kérdezés és a
válasz a menetből számolódik (`motor/spiral.py`), nem szabálysorokból. A
tételek állandó sorrendben: adu dáma (ha a válaszból nem derült ki), a
külső királyok (♠ ♥ ♦ ♣, az adu kimarad), a dámák, a bubik (adu bubi
elöl); a tudott sikén királynak számít. A kérdező lépcsői: R1 relé (a
következő tétel), R2 szuper-relé (a következő réteg eleje), …; az adu
szín licitjei és a 4NT nem lépcsők, hanem LEÁLLÁS. A válasz lépcsői (itt
minden licit lépcső): L1 = a kérdezett tétel nincs, L2 = megvan, a
következő nincs, … A kérdező: 2+ hiányzó kulcslapnál 5m/5M; egynél kis
szlem, ha az adu dáma megvan (ismeretlen dámát megkérdez, ha a tagadó
válasz nem megy az 5-ös adu fölé); mind megvan: nagyszlem-kutatás az adu
dámáig és a szükséges külső királyokig.

Kivétel (2026-10-05): a kérdező ugrása (R2+) szlem-szintre (6/7) egy posszibilisen játszható színben (összeemelt, vagy 6+ lappal licitált) vagy szanban nem relé, hanem a szlem bemondása — a válaszoló passzol.

A válaszban: `meta.kibic.rule_source = "SPIRAL"`, bizonyosság 0,8; a
műhely-végponton a `spiral` mező (`role`: `kerdezo` / `valaszolo`,
`reason`). Kérésben `"spiral": false` kikapcsolja. Alert nincs (3NT fölött).

### 5.3 `POST /v1/bridge/play` ✅ (2026-10-21)

A kérés az 1.0.1 szerint (7.1), plusz a `game.systems`. A kibic ezeket
használja belőle: `actor.acting_for_seat`, `state.contract`, `declarer`,
`dummy`, `dealer`, `visible_hands`, `history.play` (ha nincs: a
`completed_tricks` + `current_trick`), `history.auction`,
`legal_actions.cards`, `game.vulnerability`, `game.systems`, `deadline_ms`.

**A döntés** (`motor/lejatszas.py`; részletesen: `rendszerek/jelzesek/README.md`):

1. **Tények → minta.** A látható kezek, a lejátszott lapok, a renonszok és a
   licitmenet kényszertára alapján lehetséges teljes leosztások — amennyi az
   időkeretbe fér (legfeljebb 400); ha a lehetséges elosztások száma ≤ 600,
   mind (kimerítő elemzés, `meta.kibic.exhaustive`). Ha a kényszertár túl
   szűk, elengedi (`meta.kibic.relaxed`).
2. **DD-szűrő.** Mintánként double dummy minden szabályos lapra; laponként:
   `JO` (a legjobb átlagától legfeljebb a tűréssel marad el: 0,2 ütés 26+
   ismeretlen lapnál, arányosan kevesebb a végjáték felé, kimerítő
   elemzésnél 0), `BIZTOSAN_ROSSZ` (a minták 75%-ában
   legalább egy ütést veszít), `TALAN`.
3. **A megállapodás a jó lapok közül.** Védőként: hívásnál színenként a
   jelzésrendszer lapja (indító kijátszás, menet közbeni hívás), a színt a DD
   dönti; színadásnál a rács jele (kérés, lapszám, Smith); dobásnál a
   preferencia. Felvevőként a DD legjobbja (azonos értékből a legkisebb).
4. **Mérlegelő elvek** (ahol a DD vak): még csak a jelzésrendszer szövegében.

Kényszerű lapnál nincs számolás — de a válasz akkor sem azonnali: a
kijátszásra a kibic legalább `KIBIC_GONDOLKODAS_MS` ideig „gondolkodik”
(alap 1,5–3 s, véletlenszerűen; legfeljebb a `deadline_ms` 30%-a; az utolsó
ütésben nem), hogy a válasz gyorsasága ne árulja el, volt-e választás. A
`meta.elapsed_ms` a döntés ideje, a várakozás nélkül. DDS nélkül a megállapodás választ a
szabályos lapok közül. Értelmezhetetlen állásnál tartalék (a legkisebb lap,
`source: fallback`).

**Válasz:**

```json
{"request_id": "…", "action": {"type": "play", "card": "SK"}, "confidence": 0.86,
 "explanation": "Indító kijátszás: a megállapodás szerinti lap a jó lapok közül (40 lehetséges leosztás double dummy elemzése alapján).",
 "meta": {"source": "model", "pipeline": "kibic_play", "elapsed_ms": 2750, "fallback_reason": null,
          "kibic": {"situation": "INDITAS", "samples": 40, "relaxed": false,
                    "rule": "INDITAS/SZAN/SOROZAT", "classes": {"JO": 3, "TALAN": 8, "BIZTOSAN_ROSSZ": 2},
                    "system": "KIBIC_STAND", "signals": "MOHA_STAND", "constraints_used": true,
                    "systems": {"…": "…"}}}}
```

| Mező | Jelentés |
|---|---|
| `meta.kibic.situation` | `INDITAS` · `HIVAS` · `SZINADAS` · `DOBAS` · `FELVEVO` · `KENYSZER` |
| `meta.kibic.rule` | a jelzésrendszer kulcsa, ha a megállapodás döntött (pl. `INDITAS/SZAN/SOROZAT`, `RACS/PARTNER_INDIT`) |
| `meta.kibic.classes` | hány szabályos lap jó / talán / biztosan rossz — lapok NÉLKÜL |
| `meta.kibic.samples`, `relaxed`, `constraints_used`, `dd_error` | a minta mérete, elengedett kényszertár, volt-e licit-kényszertár, DDS-hiba |
| `meta.kibic.bidding_adjusted` | azok az ülések, akiknek a licitjét a letett lapokhoz kellett igazítani (pl. 5 kőrt ígért, de csak 4 lehet nála): csak az ellentmondó rész igazodik, a többi ígéret és a következtetések maradnak |
| `meta.kibic.exhaustive`, `unknown_cards`, `tolerance` | az összes lehetséges elosztást nézte-e; hány lap helye ismeretlen; a JÓ tűrése ütésben (játék közben ez csak felső korlát: a minta zaja dönt, legalább 0,02) |
| `meta.kibic.scoring`, `stopped` | a pontozás (IMP / MP, a `game.scoring`-ból) és hogy miért állt meg a mintavétel: BIZTOS (eldőlt), IDO, MAX, KIMERITO (minden elosztás), ELFOGYOTT |
| `meta.kibic.inference_weighted` | kódonként hány elosztást értékelt le egy súlyozott következtetés (`PARTNER_INDITASA`, `PARTNER_DOBASA`, `LICIT_PONTHATAR`) |
| `meta.kibic.signals` | a jelzésrendszer kódja (a licitrendszer `jelzesek:` profiljából) |
| `meta.kibic.debug.cards` | **csak teszt módban**: laponként az osztály és a DD-átlag (a kéz lapjai) |
| `confidence` | 0,5 + 0,45 × (a választott lap a minták mekkora részében volt a legjobb); DD nélkül 0,3 |

Időkeret: a `deadline_ms` 40%-a, legfeljebb `KIBIC_LEJATSZAS_MS` (alap
10 000 ms); a DDS szálbiztosság miatt egy zár mögött fut (a `/v1/kibic/dd`-vel
közös). A `capabilities` válaszában: `play: {dd_sampling, signals,
deliberation_principles}`.

### 5.4 `POST /v1/bridge/explain` ✅

Egy **már elhangzott** licit jelentése a pár rendszerében — a valódi
asztalon a licitáló partnere magyaráz. Kezet nem kap és nem használ, ezért
szerkezetileg képtelen elárulni a lapot.

**Kérés:**

```json
{
  "protocol": "mohabridzs-ai/1.1",
  "request_id": "5aa92d15:17:0:1:explain:2",
  "deadline_ms": 5000,
  "game": {"match_id": "…", "board_number": 3, "table_index": 0,
           "vulnerability": "ns",
           "systems": {"NS": "KIBIC_STAND", "EW": "PRECISION"}},
  "actor": {"seat": "S", "profile_code": "kibic_stand"},
  "state": {"dealer": "N"},
  "history": {"auction": [{"seat": "N", "call": "1N"}, {"seat": "E", "call": "P"},
                          {"seat": "S", "call": "2C"}, {"seat": "W", "call": "X"},
                          {"seat": "N", "call": "2D"}]},
  "question": {"call_index": 4, "asked_by": "E"}
}
```

| Mező | Kötelező | Jelentés |
|---|---|---|
| `actor.seat` | igen | A **magyarázó** AI ülése. A kérdezett licitnek az ő vonalán kell elhangzania, különben HTTP 400. |
| `game.systems` | ajánlott | A magyarázó vonalának rendszere ez szerint; az előtte elhangzott ellenfél-licitek az ellenfél rendszere szerint (3.4). |
| `actor.profile_code` | nem | Tartalék, ha nincs `game.systems`. |
| `state.dealer` | igen | Osztó. |
| `history.auction` | igen | Legalább a kérdezett licitig. |
| `question.call_index` | igen | A kérdezett licit sorszáma, 0-tól. |
| `question.asked_by` | nem | Naplózásra. |

**Válasz:**

```json
{
  "request_id": "5aa92d15:17:0:1:explain:2",
  "explanation": {
    "index": 4, "seat": "N", "call": "2D",
    "agreed": true, "alert": true,
    "text": "Nincs 4-es nemes", "text_en": null,
    "shows": {"suits": {"S": [0, 3], "H": [0, 3]}, "described": "S: 0-3; H: 0-3",
              "understood": true},
    "forcing": null,
    "conventions": ["STAYMAN"],
    "principle": false
  },
  "meta": {"source": "model", "pipeline": "kibic_explain", "elapsed_ms": 4,
           "system": "KIBIC_STAND"}
}
```

| Mező | Jelentés |
|---|---|
| `agreed` | Van-e rá megállapodás. `false`: a `text` ezt mondja ki („Nincs rá kifejezett megállapodásunk.”). |
| `alert` | Alertálandó-e a rendszer szerint. |
| `text` | A jelentés; több illeszkedő megállapodásnál `VAGY`-gyal összefűzve. |
| `shows` | Amit a licit **biztosan** ígér: `points` [min, max], `suits` színenként [min, max], `denies`, `stoppers` (a színek, amelyekben fogást ígér — pl. a fogásmutatás), `described`. `null`, ha nem szűkít. |
| `forcing` | `EGY_MENET`, `GEMFORSZ`, `SZLEMFORSZ`, `KIZARO` vagy `null`. |
| `conventions` | Melyik rendszerből / konvencióból jön. |
| `principle` | Csak általános elv szerint értelmezhető. |

### 5.5 `POST /v1/bridge/card` ✅

A konvenciókártya, WBF-szerkezetben, nyomtatható HTML-lel. Bárki elkérheti
(partner, ellenfél): a megállapodást írja le, kezet nem tartalmaz.

| Kérés | Válasz |
|---|---|
| `system` **nélkül** — „partner, mit játszunk?” | A saját vonal rendszerének kártyája (`game.systems` + `actor.seat`; tartalékként a profilból). |
| `"system": "KOD"` — „mutasd ennek a rendszernek a kártyáját” | A kért rendszeré, ha a `capabilities.systems`-ben szerepel; különben **HTTP 404**. |

```json
{"protocol": "mohabridzs-ai/1.1", "request_id": "…",
 "actor": {"seat": "S", "profile_code": "kibic"},
 "system": "KIBIC_STAND", "format": "html"}
```

Válasz: `system`, `name`, `current_system` (amit az AI most játszik),
`current` (azé-e a kártya), `card` (adat: nyitások válaszokkal, küzdelmi
licitek, konvenciók, szlem, indulás, jelzések…), és `html`, ha a `format`
nem `json`. A kártya a rendszer következő változásáig ugyanaz; az MB
gyorsítótárazhatja `system` szerint.

---

## 6. Az MB oldaláról: mit, mikor, melyik hívásban

| Mikor | Hívás | Mit küld az MB |
|---|---|---|
| Profil mentésekor, meccs indításakor | `GET /v1/bridge/capabilities` | — (megkapja az ismert rendszereket és családokat) |
| Rendszerválasztó lista (párok beállítása) | `GET /v1/bridge/systems` | — (család → alaprendszer → rendszer) |
| Rendszer kiválasztásakor (előnézet) | `POST /v1/bridge/card` + `system` | a vizsgált rendszer kódja |
| Párok beállításakor | — | páronként: ismert rendszer kódja, vagy családja, vagy kód + család |
| Minden licitnél | `POST /v1/bridge/bid` | **`game.systems` (MUST az 1.2-ben)**; `auction[].alert` (SHOULD); a `meta.kibic.explain_requests`-re a magyarázat a következő kérésekben (SHOULD) |
| Minden lapnál | `POST /v1/bridge/play` | **`game.systems`** |
| Ha valaki megkérdez egy licitet | `POST /v1/bridge/explain` | **`game.systems`**; a licitáló vonalán ülő AI kapja |
| „Mutasd a kártyádat” | `POST /v1/bridge/card` | `system` nélkül (a saját vonal rendszere a `game.systems`-ből, ha küldik) |
| Leosztás végén (elemzés) | `POST /v1/kibic/dd-tabla` (és állásonként `/v1/kibic/dd`) | a négy kéz, kontraktus, felvevő, beli |
| Tanár kiosztássort kér | `GET /v1/kibic/kiosztas/kepessegek` (a választólistához), majd `POST /v1/kibic/kiosztas` | `target.preset` vagy saját cél, `count`, `seed`, `student.seat`, `systems` (az asztal rendszerei); szabad szövegnél előbb `dry_run` |

**Szabályok (SHOULD az MB-nek):**

* **Leosztás közben nincs váltás.** Az új rendszer a következő leosztástól
  él — különben a már elhangzott licitek jelentése megváltozna.
* **Egy pár, egy rendszer.** AI-párnál mindkét tagra ugyanaz megy. Csak
  olyan rendszer választható egy párnak, amit a pár minden AI-tagja ismer
  (a tagok `capabilities.systems[]` listájának metszete).
* **Emberi pár:** ha a rendszerüket a kibic nem ismeri, a családját akkor
  is érdemes megadni (`{"code": "…", "family": "STRONG_CLUB"}`), vagy
  legalább a családot.
* **Az ellenfél értesül.** Váltás után az ellenfél kérhesse az új kártyát.
* **Visszafelé kompatibilitás:** a régi (1.0/1.1) kérés `game.systems`
  nélkül is működik — a kibic a profilból veszi a saját rendszerét, az
  ellenfélét a sajátja szerint érti, és a napló jelzi (`warning`).

---

## 7. Ami még hiányzik

1. **Az alert-értelmező szótára** (3.6) szándékosan kicsi: a valós
   MB-alertekből érdemes bővíteni (pl. „Multi”, „Landy”, „DONT” nevek →
   jelentés).
2. **A lejátszó réteg mérlegelő elvei** (5.3, 4. lépés): ahol a DD vak (a
   DD-felvevő mindent lát), az elvek még nem lépnek be a döntésbe; a Lavinthal
   preferencia és a partner színében való indulás (PARTNER_SZINE) a
   döntésben még nincs.
3. **A családok tartalma**: a `STRONG_CLUB`, `NATURAL`, `ACOL`, `POLISH`
   első változata gépi javaslat — átnézendő (a hierarchia — család →
   alaprendszer → rendszer — 2026-10-02 óta megvan, 3.3).
4. **Mentés (sacrifice) szimuláció**: a törvény (LoTT) most gyors elv; a
   DD-mintás mérlegelés a mentésre még hátravan.
5. **Kiosztástervező**: a szabad szöveg fordítója (LLM → `target`) nincs
   bekötve; a tervezett lejátszási technikák (asztalfordítás, keresztlopás,
   eliminálás, beszorítás, adupuccs, tartás, biztonsági játék) felismerése
   hátravan (8. pont).

---

## 8. Kiosztástervező (`/v1/kibic/kiosztas`) ✅ 2026-10-03

Részletes szerződés: `doc/mohabridzs-deal-design-1.1.md`
(`mohabridzs-deal-design/1.1`). Az MB a `DEAL_DESIGN_ENDPOINT`-ra küldi, az
`AI_SHARED_SECRET`-tel.

* **Források** (`source.type`): `generate` (véletlen, `seed`-del
  újrajátszható), `pbn` (egy verseny PBN-je; szűrhető), `deals` (kész
  kiosztások ellenőrzése, annotálása).
* **Cél** (`target`, egyszerre teljesül): `preset` (előre definiált helyzet,
  `rendszerek/kiosztas/helyzetek.yaml`), `hands` (kézfeltétel ülésre vagy
  szerepre: `hcp`, `suits`, `shape`, `cards`, `no_cards`, `any_of`),
  `auction` (a kibic licitje a `systems` rendszereivel: `prefix`,
  `student_role`, `branch` páros / küzdelmi / védekező, `final`, `fallback`),
  `play` (DDS: kontraktus, `result`, `technique` impassz / expassz /
  kevés biztos ütés, `lead` egyetlen buktató szín).
* **Válasz**: `deals[]` (`hands`, `dealer`, `vulnerability`, `board`,
  `deal_id`, `source`, `tags`, `auction`, `contract`, `checks`, `dd`, `pbn`),
  `interpretation` (amit a kibic a kérésből értett — szabad szövegnél ezt
  hagyja jóvá a tanár), `stats`, `status` `ok` / `partial` / `empty`.
* **Hibák**: `invalid_request`, `unsupported_protocol`, `invalid_deal`,
  `pbn_parse_error` (400); `unknown_preset`, `unsupported_target`,
  `text_unsupported`, `no_deals_found` (422); `dds_unavailable`,
  `auction_unavailable` (503).
* **Helyzetek most**: `NT_STAYMAN`, `NT_TRANSFER`, `WEAK_TWO`, `PREEMPT_3`,
  `NEGATIVE_DOUBLE`, `OVERCALL`, `FINESSE`, `OPENING_LEAD`.
* **Próba** egy futó szolgáltatáson:
  `python -m kibic.cli.kiosztasproba --cim http://localhost:9050 --titok …`

A kiosztás maga a tartalom, ezért itt a kezek szerepelnek; a „kéz nélküli
magyarázat” szabály (13. pont) az `explain` / `card` végpontokra vonatkozik.

---

## 9. Double dummy (`/v1/kibic/dd*`) — a MohaBridzs elemző funkciói

Mindkettő a `KIBIC_SHARED_SECRET`-tel hívható; a DDS (endplay) kell hozzájuk
(nélküle HTTP 503).

### 9.1 `POST /v1/kibic/dd` ✅ — egy játékállás, laponként

Egy konkrét állásban a soron lévő játékos **minden szabályos lapjára**: mi
lenne az eredmény tökéletes folytatással, és mennyit veszít a legjobbhoz
képest.

```json
{"request_id": "…",
 "hands": {"N": ["SA","SK", "…"], "E": ["…"], "S": ["…"], "W": ["…"]},
 "contract": {"level": 4, "strain": "H", "multiplier": 1},
 "declarer": "S", "vulnerability": "ns",
 "play": [{"seat": "W", "card": "D2"}]}
```

A `hands` lehet a teljes kiosztás vagy a még kézben lévő lapok (a `play`-ből
visszaállítja). A `contract` lehet `"4H"`, a `play` sima laplista is. A
válasz `warning` mezője mindig jelzi: nyílt lapos elemzés, emberi hiba
megítélésére felső korlát.

### 9.2 `POST /v1/kibic/dd-tabla` ✅ — egy leosztás egyben

Ugyanaz a kéréstest (+ `dealer`, `declarer_tricks`). Válasz: a 20 mezős
DD-tábla, vonalankénti maximum, a legjobb kontraktus, a **par**, és ha a
kérés hozza a játszott kontraktust, az eltérés a partól pontban és IMP-ben,
licitre és játékra bontva. Leosztásonként egyszer, a lejátszás végén
érdemes hívni. Részletesen: `doc/kibic-dd-tabla.md`, sémák:
`doc/semak/kibic-dd-tabla.*.schema.json`.

---

## 10. Tanító / műhely végpontok (nem az éles asztalnak)

Ezek a **licitáló kezét is** tartalmazhatják — ellenfélnek soha.
Részletesen: `doc/kibic-tanito-api.md`.

| Végpont | Mire |
|---|---|
| `POST /v1/kibic/licit` | Mit licitálna a kibic ezzel a kézzel, és mit értett meg a menetből. Kérés: `hand`, `seat`, `dealer`, `vulnerability`, `auction` (rövid `["1N","P",…]` vagy `[{seat, call}]`), **`system`** (kötelező), `pair`, `legal_actions`, `test_mode`, `debug`, `simulate`, `samples`. Válasz: `call` (lehet `null`), `source`, `alert`, `candidates`, `to_deliberate`, `auction_understanding`, `constraints` (a kényszertár a négy kézre), `coverage`, teszt módban `debug`, szimulációnál `deliberation`. |
| `POST /v1/kibic/magyaraz` | Egy elhangzott licit: a jelentése (mint az `explain`), és ha jön a licitáló keze, mit mondott volna ott a kibic és miért (`would_bid`, `matches`). |
| `GET /v1/kibic/kartya[?system=KOD]` | A kártya HTML-ben, böngészőben (nyomtatható, PDF-be menthető). |
| `GET /v1/kibic/leiras?system=KOD[&format=html\|md][&test_mode=]` | A rendszer TELJES leírása: a feloldott rendszer minden szabálya forrás (alaprendszer / konvenció) és fejezet szerint, a jegyzetekkel. HTML (nyomtatható) vagy Markdown (letöltés). A szerkesztő „Letöltés” lapjáról is elérhető; fájlba adatbázis nélkül: `python -m kibic.cli.rendszerleiras`. |

**Teszt mód** (`KIBIC_TESZT_MOD=1`, vagy kérésenként `test_mode`): a még jóvá
nem hagyott (JAVASOLT) szabályok is élnek. **A `bridge/bid`-re is
vonatkozik**, és ott a `meta.kibic.debug` a kéz adatait is tartalmazza —
éles versenyen kapcsold ki.

---

## 11. A rendszerszerkesztő

Böngészőben: `GET /szerkeszto`. A felület a `/v1/kibic/szerk/*` végpontokat
hívja (a `KIBIC_SHARED_SECRET`-tel). Használata: `doc/szerkeszto.md`.

A felső sáv: a rendszer választója, a lapok (Rendszer · Próbakéz ·
Megjegyzések · Letöltés), jobbra a **neved** (a jóváhagyások és a
megjegyzések szerzőjeként kerül az adatbázisba) és a **titok** (a
`KIBIC_SHARED_SECRET` értéke, `Authorization: Bearer`-ként megy a
`/v1/kibic/szerk/*` hívásokkal; mindkettő csak a böngésződben tárolódik). A
**Letöltés** lapon a választott rendszer rövid (kártya) és hosszú (teljes
leírás, HTML / Markdown) alakja — ezekhez titok nem kell.

| Végpont | Paraméterek | Mit ad / mit csinál |
|---|---|---|
| `GET /v1/kibic/szerk/rendszerek` | — | az összes aktív rendszer és konvenció, szabály-állapot összesítővel |
| `GET /v1/kibic/szerk/fa` | `system`, `test_mode` | a hivatkozási (feloldási) lánc és a feloldás megjegyzései |
| `GET /v1/kibic/szerk/rendszer` | `system` | egy rendszer adatai, jegyzete és saját hivatkozásai; a hivatkozásnál `settings` (elv-sablon példány: `ervenyes`, `parameterek`, `kivalt`), elv-sablonnál `principle` (`szoveg`, `parameterek`, `terulet_szoveg`) |
| `GET /v1/kibic/szerk/fejezetek` | `system` | a rendszer fejezetei, állapotonkénti számokkal |
| `GET /v1/kibic/szerk/szabalyok` | `system`, `chapter` | egy rendszer (fejezet) saját szabályai |
| `GET /v1/kibic/szerk/feloldott` | `system`, `prefix`, `openings`, `test_mode` | a szabályok a feloldás után — amivel a kibic ténylegesen licitál; minta szerinti kereséssel |
| `POST /v1/kibic/szerk/allapot` | `{system, action: jovahagy\|jegel\|kiolvaszt\|visszavon, ids \| chapter, author}` | szabályok állapotának váltása; a gyorsítótárat üríti |
| `GET /v1/kibic/szerk/megjegyzes` | `system`, `key` | a megjegyzések |
| `POST /v1/kibic/szerk/megjegyzes` | `{system, text, chapter, key, pattern, rule_id, author}` | új megjegyzés (a `system` és a `text` kötelező) |
| `POST /v1/kibic/szerk/megjegyzes/{id}/lezar` | — | megjegyzés lezárása |
| `GET /v1/kibic/szerk/export` | — | a nyitott megjegyzések és a rendszerek (jelzésrendszerek) állapota egy JSON-ban (ezt kapja meg Claude) |
| `GET /v1/kibic/szerk/jelzes/rendszerek` | — | a jelzésrendszerek, állapot-összesítővel, ki játssza őket (Jelzések lap) |
| `GET /v1/kibic/szerk/jelzes/rendszer` | `system` | egy jelzésrendszer adatai és saját hivatkozásai (beemel / kizár) |
| `GET /v1/kibic/szerk/jelzes/fa` | `system`, `level` | a hivatkozási fa és a feloldás: felülírt, kihagyott, kizárt sorok, figyelmeztetések |
| `GET /v1/kibic/szerk/jelzes/fejezetek` | `system` | fejezetek állapotonként |
| `GET /v1/kibic/szerk/jelzes/sorok` | `system`, `chapter` | a saját sorok: fajta, terület, kulcs, mit ír felül / hagy ki |
| `GET /v1/kibic/szerk/jelzes/feloldott` | `system`, `level` (`ELES` / `TESZT`) | a feloldott sorok, forrással |
| `GET /v1/kibic/szerk/jelzes/proba` | `system`, `holding`, `situation`, `level` | „Mit hív?”: a lap szín és szan ellen, a nyertes és a mögötte álló sorok |
| `POST /v1/kibic/szerk/jelzes/allapot` | `{system, action, ids \| chapter, author}` | jóváhagyás / jegelés / kiolvasztás / visszavonás; a gyorsítótárat üríti |

---

## 12. A kibic beállításai (környezeti változók)

| Változó | Jelentés |
|---|---|
| `KIBIC_SHARED_SECRET` | a kibic titka: minden védett végpont ezt fogadja el — értéke = az MB `AI_SHARED_SECRET`-je (2.1) |
| `KIBIC_AI_SHARED_SECRET` | opcionális: külön titok az AI-végpontokra (`/v1/bridge/*`, `/v1/kibic/kiosztas*`); üresen a `KIBIC_SHARED_SECRET` érvényes |
| `KIBIC_RENDSZER` | az alaprendszer (`default_system`), pl. `KIBIC_STAND` |
| `KIBIC_PAR` | az alapértelmezett pár-paraméterek |
| `KIBIC_PROFILOK` | profilkód → rendszer leképzés: `kod=RENDSZER:pár;kod2=RENDSZER2` |
| `KIBIC_TESZT_MOD` | `1`: a JAVASOLT szabályok is élnek (éles versenyen ne) |
| `KIBIC_ATJARO_SZIMULACIO` | a mérlegelő helyzetekben szimuláció (DD-mintavétel); alap: `1` (be), `0`: ki |
| `KIBIC_ATJARO_SZIM_MS` | a szimuláció időkerete egy licitdöntésre (alap: 10000); a `deadline_ms` szűkítheti |
| `KIBIC_ATJARO_SZIM_TARTALEK_MS` | a `deadline_ms`-ből ennyi marad a licit többi részére (alap: 1500) |
| `KIBIC_SZIM_MIN_MINTA` | ha az időkeret letelik, legalább ennyi kiszámolt minta kell a szimuláció döntéséhez (alap: 12) |
| `KIBIC_ARNYEK` | árnyék mód (a terv 0. fázisa): `1` = minden regisztrált új döntéshozó, vagy nevek vesszővel; `rendszer:KOD` = ugyanaz a kérés egy MÁSIK rendszerrel is (pl. `rendszer:MOHA_STAND_ELV`); a különbség a műhely-válasz `shadow` mezőjébe és az átjáró naplójába kerül, a licit a régi marad |
| `KIBIC_INFO_KERES` | `0`: a kibic nem kér magyarázatot licitdöntés közben (alap: be, csak `mohabridzs-ai/1.1`-nél) |
| `KIBIC_ATJARO_NAPLO` | JSONL-napló útvonala (kéz nélkül: a kényszertár, a lefedettség, a döntés) |
| `KIBIC_KIOSZTAS_NAPLO` | JSONL-napló a kiosztástervezőhöz: a kérés (a PBN / kész kiosztások csak méretként), az `interpretation`, a `stats` és a `deal_id`-k. Konzolra mindig megy egy összefoglaló sor. |
| `KIBIC_KOVETKEZTETES_MS` | a kizárásos következtetés időkerete licitdöntésenként (alap 800 ms; a `bid`-nél legfeljebb a határidő negyede) |
| `KIBIC_KOVETKEZTETES_MINTA` | a kizárásos következtetés mintaszáma (alap 120) |
| `KIBIC_LEJATSZAS_MS` | a lejátszó réteg időkerete egy lapdöntésre (alap 10000; legfeljebb a `deadline_ms` 40%-a) |
| `KIBIC_LEJATSZAS_MINTA` | a lejátszó réteg legfeljebb ennyi mintát néz (alap 3000; ténylegesen a döntés biztossága és az időkeret dönti el) |
| `KIBIC_LEJATSZAS_MIN_MINTA` | legalább ennyi minta, mielőtt a döntést biztosnak veszi (alap 60) |
| `KIBIC_LEJATSZAS_KOVETKEZTETES_MS` | a licit kizárásos következtetése a lejátszásban (leosztásonként egyszer; alap 15000, legfeljebb a `deadline_ms` 30%-a; utána gyorsítótár) |
| `KIBIC_GONDOLKODAS_MS` | a kijátszás legrövidebb válaszideje: `1500-3000` (véletlen a tartományból, ez az alap), `2000` (fix), `0` (ki). Ha a döntés tovább tartott, nincs várakozás; legfeljebb a `deadline_ms` 30%-a; az utolsó ütésben nincs |
| `KIBIC_LEJATSZAS_KIS_LAP` | a kimerítő elemzésben ennél nem nagyobb rejtett lapok egyenértékűek (alap `8`; `0`: ki) |
| `KIBIC_LEJATSZAS_MINTAZAT_HATAR` | ennyi mintázatig (kis lapok összevonva) a teljes sokaságot nézi (alap 5000) |
| `KIBIC_ATJARO_NAPLO_KERES` | `1`: a napló play-sorában a teljes kérés is (a saját kéz és az asztal!) — a visszajátszáshoz: `python -m kibic.cli.jatekelemzes` |
| `KIBIC_HOST`, `KIBIC_USER`, `KIBIC_PASS`, `KIBIC_DB` | az adatbázis |

**Hogyan kell megadni.** A kibic a környezeti változókat a folyamat
környezetéből olvassa (`.env`-fájlt maga nem tölt be). Ha a szolgáltatást
shellből (vagy egy `source`-olt szkriptből) indítod, `export NEV=érték` kell,
különben az elindított `uvicorn` nem látja. Ha a változók fájlból jönnek
(systemd `EnvironmentFile=`, Docker `env_file`, dotenv), ott `NEV=érték`,
`export` NÉLKÜL. Az MB `.env`-je ilyen fájl, ezért ott nincs `export`.

Az adatbázis vagy a YAML-rendszerek módosítása után: `POST /v1/kibic/ujratolt`
(különben a kibic a gyorsítótárazott rendszerrel licitál tovább).

---

## 13. Adatvédelem összefoglalva

* Az `explain` és a `card` **kezet nem kap és nem ad**; a válasz kizárólag a
  megállapodásból készül.
* A `bid` válaszában az `alert` a megállapodás (az összes illeszkedő
  szabály szövege), nem a kéz leírása.
* A `meta.kibic.debug` (teszt mód) és a `/v1/kibic/licit`, `/magyaraz`
  válasza a kéz adatait is tartalmazhatja: csak tanításhoz.
* A kibic naplója (`KIBIC_ATJARO_NAPLO`) a kezet nem tartalmazza — kivéve, ha
  a `KIBIC_ATJARO_NAPLO_KERES=1` kifejezetten kéri (elemzéshez).
* A `play` magyarázata kéz nélküli (a helyzet és a megállapodás neve); a
  laponkénti DD-osztályok csak teszt módban, a `meta.kibic.debug`-ban.
* A `/v1/kibic/kiosztas` kiosztást ad (a kezek a tartalma): tanári,
  gyakorló felületre való, nem az ellenfélnek.

---

## 14. Változásnapló

| Dátum | Változás |
|---|---|
| 2026-10-01 | Első egyesített leírás: minden végpont; a rendszerek kezelése. |
| 2026-10-01 (2.) | A vonalak rendszere megvalósítva: a `game.systems` a saját és az ellenfél rendszerét is meghatározza (a profil csak tartalék); új rendszer-fajta: RENDSZERCSALAD (`STRONG_CLUB`, `NATURAL`, `ACOL`); `capabilities.families`, `capabilities.line_systems`; a nyelvben `ha: {ellenfel_pont}`, `ha: {ellenfel_csalad}`. |
| 2026-10-02 | Hierarchia: RENDSZERCSALÁD → ALAPRENDSZER → RENDSZER (a rendszernek pontosan egy alaprendszere és családja; az import ellenőrzi; a szerkesztő így mutatja). Új: `GET /v1/bridge/systems` (katalógus), `capabilities.systems_catalog`. POLISH család; a PRECISION nem család (→ STRONG_CLUB). Az `auction[].alert` értelmezése (az ellenfél rendszere után, a mienk előtt); `meta.kibic.explain_requests`, `understood_from_alert`. Feltételes felülírás (a `ha:`-s szabály csak a saját helyzetében ír felül). Új konvenciók: Timbuktu, Junk Stayman és a törvény (LoTT) a KIBIC_STAND-on; Rubensohl (a Lebensohl alternatívája, a KIBIC_STAND-on nincs). Nyelv: `ha: {ellenfel_szin, ellenfel_licitalt}`, `fit: {A: 9+}`. |
| 2026-10-02 (2.) | A Rubensohl és a Lebensohl két alternatív „világ”: egyik sem váltja a másikat, az a rendszer hivatkozik rá, amelyik játssza (KIBIC_STAND: Lebensohl, Junk Stayman). Új elvek a KIBIC_STAND-on: 1-re 1 kényszerít (tagadja a riverz erőt), a negyedik szín (általános elv: a vonal három igazi színe után a negyedik, F1, lapleírást kér), splinter-elv (ugrás új színben a partner nemesének 3-as szintje fölé). A passz-elv gémesélynél nem passzol (nemes fittel 25, minor fittel 27, szanban 24 FP egyenlő elosztásnál, egyenetlennél hosszú színnel). Walsh: a nyitó újralicitjei 1♣-1♦ után (1M csak nagyon egyenetlen lappal), riverz 18+, a válaszoló 1♣-1♦-1M után. Timbuktu: pontsáv helyett zónás vesztőhatár, kontra/2♣ a játékütések szerint. Új rendszer: MOHA_STAND = KIBIC_STAND + a törvény (LoTT). 3NT fölött nincs alert (szabály). Nyelv: zónás `vesztok`, `jatekutes`, `gyorsutes`, `gemeselyes`, `splinter_tamogatas`, `osszesen: {ap_biztos}`; `ha: {negyedik_szin, partner_negyedik, splinter, en_mondtam}`; a `Q` a feltételben is. |
| 2026-10-02 (3.) | **Kizárásos következtetés** (`motor/kovetkeztetes.py`): a kibic a licitáló helyébe képzeli magát — a licit előtti tudás szerint lehetséges kezeket sorsol, mindegyikkel lefuttatja az ő rendszerét, és amelyik kézzel nem ugyanezt mondta volna, azt a licit KIZÁRTA. Valószínű (nem biztos) tudás: külön rétegben (`inferred`), a gémesély és a mintavétel használja. A műhely-válaszban: `inferred` ülésenként, `auction_understanding[].inferred` licitenként („amit nem licitált”). Időkeret: `KIBIC_KOVETKEZTETES_MS` (alap 800 ms; a `bid`-nél legfeljebb a határidő negyede), kérésenként `inference`, `inference_ms`. Új: POZITIV_SZABAD_LICIT (a közbeszólás utáni nem ugró új szín SZABAD_LICIT_MIN+ FP, 5+; paraméter, migráció: `schema/025_szabad_licit.sql`; MOHA_STAND: 11), a negatív kontra „minden más” sorai (10+ FP-tal nem passzolunk). A YAML-ban pontsáv paraméterrel: `pont: {param: KOD, alap: 10, eltolas: -1}`. |
| 2026-10-02 (4.) | A nyitó a negatív kontra után (NEGATIV_KONTRA, új fejezet): a büntető passz MÉRLEGELŐ jelölt (erős, biztos aduk), a kibic szimulációval dönti el; ha a büntetés jobb, `recommended_call` = P (a mi kontránk után) vagy X. Különben: a kontra ígéretének teljesítése (a tagadott nemes), ugrás erővel (`ha: {ugras}`), a saját szín, szan/3NT fogással, új szín, felüllicit; „kínunkban” a saját szín. Gyenge ugró válasz (GYENGE_UGRO_VALASZ, KIBIC_STAND): a minor nyitásra adott 2♥/2♠ folytatásai (a nyitóé, 2NT kérdésre minimummal a szín, maximummal mellékszín alulról. A gyenge ugró közbeszólásra adott válaszok (emelés kizáró, ugró emelés, új szín 6 lappal, 2NT kérdés, felüllicit) és a közbeszóló folytatásai. Nyelv: `ha: {ugras, en_igertem}`. |
| 2026-10-02 (5.) | **A gyenge ugrás ELV** (GYENGE_UGRAS_ELV, KIBIC_STAND): nem konkrét helyzet, hanem megállapodás — ahol nem vagyunk licitálásra kényszerítve, első megszólalásként, új színben az egyszeres/dupla ugrás (amit alacsonyabban is mondhatnánk, és arra van szabály) gyenge, kizáró, nem többleterő. Ha maga az ugrás konkrétan definiált (pl. Bergen, transzfer), annak a jelentése él; splinter-helyzetben a splinter. A megértésnél a pontplafon az alacsonyabb licit minimuma alatt van. A konkrét 3-as szintű gyenge ugró válasz sorok megszűntek (az elv fedi). A párja: MÁSODIK megszólalásként az ugrás új színben erő, gémforsz (a nyitótól 17-19, mástól kb. 15+ FP; aki korábban limitálta a lapját, annál nem). Nyelv: `ha: {gyenge_ugras: 1|2, eros_ugras, en_nyitottam}`. |
| 2026-10-03 | **Kiosztástervező** (`mohabridzs-deal-design/1.1`, külön dokumentum: `doc/mohabridzs-deal-design-1.1.md`): `POST /v1/kibic/kiosztas`, `GET /v1/kibic/kiosztas/kepessegek`; a `/v1/bridge/capabilities` új `deal_design` mezője. Források: generálás (seed), verseny-PBN, kész kiosztások; cél: kézfeltételek, licithelyzet a kibic licitjével (előtag, szerep, ág, néma helyek), lejátszás / ellenjáték DD-vel (impassz, expassz csere-teszttel; egyetlen buktató indulás). Helyzetkatalógus: `rendszerek/kiosztas/helyzetek.yaml`. Próba: `python -m kibic.cli.kiosztasproba`. |
| 2026-10-03 (2.) | A dokumentum KUMULÁLT: minden végpont, felület és beállítás itt van (a fejléc szerint). A kiosztástervező bekerült (2.1 táblázat, 6., 7., 8., 12., 13. pont). A titkok tisztázva: az MB egyetlen `AI_SHARED_SECRET`-et küld mindenhová, a kibicben elég a `KIBIC_SHARED_SECRET` ugyanazzal az értékkel; a `KIBIC_AI_SHARED_SECRET` csak külön AI-titokhoz kell. Új a 12. pontban: `KIBIC_KOVETKEZTETES_MS`, `KIBIC_KOVETKEZTETES_MINTA`, és hogy mikor kell `export`. |
| 2026-10-03 (3.) | **Hézag-elv** (5.2a, `motor/hezag.py`): ha nincs szabály, a kibic a közös erő (A / F) és a kényszer alapján dönt, a hívások rendszerbeli jelentése szerint — nem vak passz. 40 véletlen leosztás teljes licitjében a szabály nélküli helyek (22) mind döntést kaptak. Javítva: a negyedik szín elve csak 3NT alatt és egyszer él (egy végtelen 4♣–5♣–6♣–7♣ kört okozott). A kiosztástervező naplója: `KIBIC_KIOSZTAS_NAPLO`. |
| 2026-10-04 | Passz-elv: a `.. (*) P` sor (az ellenfél — akár passz — hívása után) eddig gémesély-feltétel nélkül passzolt; most egyik sor sem passzol gémesélynél vagy gémforszban (YAML, import kell). Fésű: a felüllicit csak egyszer (migráció `schema/026_fesu_ismetles.sql`). Hézag-elv: 3NT csak fogással; 4-3 fit csak rövidséggel játszható; a géminvit / kényszerítő leíró licit csak gém alatti. Az átjáró naplója a `deadline_ms`-t is rögzíti. |
| 2026-10-04 (2.) | Fésű: csak akkor, ha a partner már mutatott színt (migráció `schema/027_fesu_partner_szine.sql`, a 026-ot is tartalmazza). Hézag-elv 5. pont: büntető passz a partner kontrájára (szimulációval vagy becsléssel); a partner büntető kontrája fogás a 3NT-hez; DD-mintavétel a végkontraktus-választáshoz, ha a szimuláció engedélyezett. A gémesély (passz-elv) a partner nyitott felső határával (pl. 2/1: 11+) is számol. |
| 2026-10-04 (3.) | KIBICEGY_STAND: `1♥-1♠-2♥-3NT` (leállás) csak 13-16 ponttal (YAML, import kell). Hézag-elv: a partner nem értett 3NT-je után, ha a nemes adu megállapodott (8+ lap, a partner 5+), a nemes gém (`1♥-1♠-3♥-3♠-3NT` → 4♥). |
| 2026-10-04 (4.) | **Spirál** (5.2b, `motor/spiral.py`): a kulcslap-válasz utáni relé és válasz; új `rule_source`: `SPIRAL`, a műhelyben a `spiral` mező, kérésben `"spiral": false`. (A többi változás ebben a szállításban rendszer-YAML, az interfészt nem érinti: Walsh 2♦/3♦, módosított Jacoby 3♦, MOHA_3NT_4M — import kell.) |
| 2026-10-04 (5.) | Az ELV-réteg döntésénél különválik a konvenció helyzeti alakja (megállapodás) és az általános elv: új műhely-mező `situational_agreement`, az átjáró magyarázata „Helyzeti megállapodás (KÓD) szerint.”. A KIBIC_STAND kártyán a MOHA_SZLEM (kulcslicit / ászkérdés / gém a megállapodott aduban). Rendszer-YAML (import kell): MOHA_1M: 1M-2m gémforsz (2♦ is), 1M-1NT rossz 11-gyel, a nyitó licitjei a szerkesztő szerint (a KIBICEGY alap visszaállítva); 1♥-1♠-3♥ után 3♠ = szlemérdek, 4♥ = leállás. |
| 2026-10-04 (6.) | **Információkérés** (3.6, MB AI_PLAYER_API v1.1): nem értett ellenvonali licitnél a `bid` válasza `action.type = "request_information"` a `bid_indices`-szel; a visszaküldött `auction[i].information` szövegét alertként érti; megkérdezett licitet nem kérdez újra. `capabilities.request_information: true`, új beállítás: `KIBIC_INFO_KERES`. |
| 2026-10-05 | Hézag-elv: szín-szlem a megállapodott aduban (30+: kulcslapkérdés, ha még lehet; 35+ felső határral gém fölötti kulcslicit; különben 6), a partner gém fölötti kulcslicitje nem passzolható; szan-szlem (4NT / 6NT / 5NT / 7NT). Új, opcionális bemenet: `game.scoring` (MP / BAM / IMP) — MP-n a 6M / 6NT választás DD-mintával (5.2a). |
| 2026-10-05 (2.) | Spirál: a kérdező szlem-szintű ugrása (R2+) játszható színben (vagy szanban) leállás, nem relé (5.2b). MOHA_3NT_4M: az 5m válasz definíció szerint 2 kulcslap + adu dáma, a „tetszik” előtt. Javítva: a kulcslap-válasz jelentése akkor is megmarad, ha általános elvek (kulcslicit-sorok) is illeszkednek a licitre — eddig ilyenkor a spirál el sem indult. |
| 2026-10-05 (3.) | **Aranykészlet és árnyék mód** (a terv 0. fázisa): `python -m kibic.cli.aranykeszlet rogzit / osszevet` — rögzített döntéskészlet, és minden változtatás után tételes összevetés; `KIBIC_ARNYEK` / kérésben `shadow`: új döntéshozó próbája élesben, a licit változtatása nélkül (a naplóban `shadow`). A `game.scoring` (MP / BAM / IMP) a szimulációs mérlegelést is irányítja (MP: nyerési arány, IMP: IMP-átlag). |
| 2026-10-05 (4.) | Kulcslap-válasz (RKC, ORKC): a kérdező a kétértelmű válasznál (0/3, 1/4) a rosszabb esetet tételezi fel; ha a válaszolónál a jobbik van, és a kérdező a szlem alatt állt le, a válaszoló mondja a szlemet (spirál, 5.2b). Az aranykészleten 7 szándékos eltérés (`adat/arany/elteres-2026-10-05-rosszabb-eset.jsonl`), a készlet újra rögzítve. |
| 2026-10-05 (5.) | **Rendszerleírás**: `GET /v1/kibic/leiras` (a teljes, feloldott rendszer HTML-ben vagy Markdownban), a szerkesztő új „Letöltés” lapja (kártya + teljes leírás), CLI: `python -m kibic.cli.rendszerleiras` (adatbázis nélkül, YAML-ból). |
| 2026-10-05 (6.) | **Elv-sablon** (a terv előrehozott lépése): új rendszer-fajta `ELV_SABLON` (**028-as migráció**: `rendszer.sablon`, `licitmenet.hivatkozas_beallitas`); az első: FOGASMUTATAS. A hivatkozás mondja meg, hol él (`ervenyes`) és milyen paraméterekkel; a területén a kártyán mögötte álló sorok nem élnek. Próba-rendszer: **MOHA_STAND_ELV** (a MOHA_STAND érintetlen). A magyarázat `shows` mezőjében új: `stoppers`. A szerkesztőben az „elvek” csoport, a sablon szövege és paraméterei. Árnyék mód másik rendszerrel: `KIBIC_ARNYEK=rendszer:MOHA_STAND_ELV`. A hézag-elv nem mond olyan licitet (pl. 3NT), amelynek a rendszerbeli jelentése nála nem lévő fogást ígér. |
| 2026-10-05 (7.) | **FELMENTES** elv-sablon (MOHA_STAND, MOHA_STAND_ELV): az 1./2. kézben a 8 vesztős lap 13 FP alatt és a rossz 11-12 pont nem induló erő — a kibic passzol (a passz magyarázata változatlanul „Passz”). Rossz 11 válasz: 1M-1NT (3 lapos támogatással is). FOGASMUTATAS: ha minden szín le van fedve, önálló nemes 4M / második szín / 6+ nemes ismétlése / kétség; a 3NT–4M választás szimulációval (`simulate`) a DD-mintavételből. Az aranykészlet újra rögzítve (az eltérések: `adat/arany/elteres-2026-10-05-felmentes-hezag.jsonl`). |
| 2026-10-05 (8.) | Interfész-változás nincs; a döntések változnak. A Moha-kártyákon (MOHA_STAND, MOHA_STAND_ELV) a lemaradt MOHA_2MAJOR, MOHA_NONFORCE_1NT, MOHA_FEDOKERESO és az új MOHA_2D (gyenge kettesek zónánként, a pontok fele a színben). Nem jó 11 + 3-4 lapos támogatás + 2 fedőütés: 1M-2M. Kvázi gémforsz: az 1M-2m csak 4 minorig kényszerít; a hézag-elv a gémforszban a partner nyitott sávját két licit után minimum + 4-re fékezi. FOGASMUTATAS: negyedik szín = HELP (fogást kér). Az aranykészlet újra rögzítve (`adat/arany/elteres-2026-10-05-moha-kartya.jsonl`, `…-fogasmutatas-elv-3.jsonl`); `aranykeszlet osszevet --teljes`: teljes újrajátszás a négy lappal. |
| 2026-10-05 (9.) | Interfész-változás nincs. FELMENTES: a 3./4. kézben 4-es nemes nélkül 10-11 ponttal csak 3-3 nemessel 1m (1♦ 4+ káró, 1♣ 4+ treff), rossz 12-vel 3-3 nemes nélkül passz. Gyenge kettesek „fele a színben”: a máshol álló üres dáma/bubi színenként 0,5-tel kevesebbet ér. Nem jó 11 emelése (1M-2M) 7+ lapos minorral nem (2m). Az aranykészlet újra rögzítve (`adat/arany/elteres-2026-10-05-34-minor.jsonl`). |
| 2026-10-12 | Interfész-változás nincs. Két új elv-sablon a MOHA_STAND_ELV próba-rendszerben (a MOHA_STAND változatlan, az aranykészletein 0 eltérés): **KENYSZER** (a gémforsz megszűnése: HELP-színben nincs fogás, nincs nemes fit, az 5 minorhoz kevés az erő → passz; a FOGASMUTATAS HELP-PASSZ sorát váltja) és **FORSZPASSZ_KIBIC** (kényszerítő passz, ha az ellenfél a gémünk fölé licitál: kontra / továbblicit / passz = „döntsd el”; a partner kényszerítő passza után nem passzolunk). Új nyelvi elemek: `ha: {kenyszerito_passz: elso|masodik}`, kéz: `gem_eselytelen`. A rendszerleírásban az elv szövegében a `{PARAMÉTER}` helyén az érték áll. Import kell (`rendszerimport`), migráció nem. |
| 2026-10-19 | Interfész-változás nincs. A szabálynyelvben **létezik-kötés**: a feltételben szereplő, de a mintában nem kötött színváltozó jelentése „van olyan szín, amelyre igaz” (pl. a `.. 3NT` sor `partner_szin: {M: 6}`-ja). A FOGASMUTATAS 3NT/4M választó és „kétség” sorai így egy-egy sorral írják le mindkét nemest (6 sor helyett 3). A MOHA_STAND aranykészletén 1 eltérés (#57: egy kötetlen változó miatt hibásan elfogadott 4♦ splinter helyett passz; `adat/arany/elteres-2026-10-19-letezik-kotes.jsonl`) — jóváhagyásra vár. A FOGASMUTATAS „6+ pikk mellett 3♥” sora általános lett (gémforszban a 3NT alatti szín csak fogás is lehet; biztos fogással: ász, kétszeres vagy 3+ lapos); új nyelvi elemek: `ha: {partner_nem_mondta: A}`, kéz: `eros_fogas: [A]`. A MOHA_STAND_ELV célzott készletén 3 új eltérés (♦/♣ fogásmutatás a 3M helyett) — jóváhagyásra vár. |
| 2026-10-19 (2.) | Interfész-változás nincs. Új elv-sablon: **LIMITALT_UJ_SZIN** (a limitált lap új színe lezárás; a MOHA_STAND és a MOHA_STAND_ELV az 1M-1NT után köti be). A létezik-kötés a licitek MEGÉRTÉSÉBEN is él. A MOHA_STAND aranykészlete újra rögzítve: egyetlen eltérés, a #57 (4♦ helyett 3♣; `adat/arany/elteres-2026-10-19-letezik-kotes.jsonl`). |
| 2026-10-20 | **A szimuláció alapműködés** a mérlegelő helyzetekben: `KIBIC_ATJARO_SZIMULACIO` alapértéke `1` (a `0` kapcsolja ki); `KIBIC_ATJARO_SZIM_MS` mostantól IDŐKERET (alap 10 000 ms; a `deadline_ms − KIBIC_ATJARO_SZIM_TARTALEK_MS` szűkítheti), nem küszöb. Letelt keretnél az addig kiszámolt mintán dönt (legalább `KIBIC_SZIM_MIN_MINTA` = 12), különben a szabály-alapú becslés. A műhely-kérésben új: `simulate_ms`; a `deliberation`-ben `samples_used`. |
| 2026-10-20 (2.) | **Jelzésrendszerek** a licit mintájára (**029–031-es migráció**, `rendszerek/jelzesek/`): SZEGEDI_MRAZ alaprendszer, MOHA_STAND ráépülve; sorok kulccsal, `fajta` (SZABALY / ELV / KIVETEL / KIHAGYAS) és `terulet`; a feloldás a licitével azonos. A licitmenetben a TORLES neve KIHAGYAS (a YAML `torol:` is jó). A kártya jelzés-része ebből készül (indítási táblázat, WBF-rács, módszerek). A szerkesztő új **Jelzések** lapja (`/v1/kibic/szerk/jelzes/*`, 11. pont). |
| 2026-10-21 | **A lejátszó réteg** (`/v1/bridge/play` ✅, 5.3): minta a rejtett kezekből (renonsz, licit-kényszertár), DD-szűrő (jó / talán / biztosan rossz), a jelzésrendszer a jó lapok közül választ (indítás, menet közbeni hívás, színadás: kérés / lapszám / Smith, dobás: preferencia), felvevőként a DD legjobbja. Új beállítások: `KIBIC_LEJATSZAS_MS`, `KIBIC_LEJATSZAS_MINTA`; `capabilities.play`. Jelzésnyelv: technika (névvel ellátott lapválasztás), `hivas:` a módszerben, `hezag` feltétel, menet közbeni hívás a rácsban (`VEDO_HIV`). |
| 2026-10-21 (2.) | Lejátszó réteg: a mintaszámot az időkeret dönti el (legfeljebb `KIBIC_LEJATSZAS_MINTA` = 400, keret `KIBIC_LEJATSZAS_MS` = 10 000); a végjátékban az összes lehetséges elosztás (kimerítő elemzés); a JÓ tűrése a bizonytalansággal arányos (végjátékban 0). Indításnál a lap a megállapodásé, a partner licitált színe elsőbbséget élvez (a jelzésrendszer `szinvalasztas:` sora, kivételekkel); szlem ellen nincs jelzés (`nincs_jelzes:` sor). Új meta: `exhaustive`, `unknown_cards`, `tolerance`; új beállítás: `KIBIC_ATJARO_NAPLO_KERES`; új CLI: `python -m kibic.cli.jatekelemzes`. |
| 2026-10-21 (3.) | Lejátszó réteg: a következtetés SÚLYOZHAT (`kovetkeztetes:` sor `suly:`-lyal; 0 = kizár); új következtetések: `PARTNER_INDITASA` (az indító lap a megállapodás szerinti), `PARTNER_DOBASA` (az első dobás kér / nem kér), `LICIT_PONTHATAR` (`tures:` pontig puha pontsáv). A többértelmű licit változatai a kényszertárban megmaradnak (`Igeret.alternativak`): a kéznek legalább egyet ki kell elégítenie. Játék közben a JÓ tűrése a minta zaja (párosított standard hiba). Új sorfajta: `merlegeles:` (`ATVETEL`, `PARTNER_KERESE`). Új meta: `inference_weighted`. Import kell (`rendszerimport`), migráció nem. |
| 2026-10-21 (4.) | Az információs kontra a Mohában: új konvenció **MOHA_INFO_KONTRA** (a MOHA_STAND a KIBIC_STAND elé köti): induló erő legfeljebb 17 ponttal (11-12 csak induló erős lappal: legfeljebb 7 vesztő, nem rossz lap — a FELMENTÉS szerint; újranyitóként 9-17, 2-es szinten 13-17, 3-ason 14-17), minor ellen legalább 4-3 a nemesekben, vagy 18+ bármi. A KIBIC általános konvenciójában az erős kontra 17+ (a 20+ helyett). A `merlegeles: PARTNER_KERESE` sor `tures:`-t kap (alap 0,25 ütés): a partner kért színéért ütést is veszünk (lopunk, átveszünk). Javítás: a lejátszás mintavétele csak akkor engedi el a licit kényszertárát (`relaxed`), ha 30-nál kevesebb illeszkedő minta jött — eddig már akkor is, ha a 400-as célszámot nem érte el (szinte mindig). Import kell; a MOHA_STAND aranykészletén eltérések — jóváhagyásra várnak. |
| 2026-10-21 (5.) | Licit-szál: csak licit-tudás, az interfész nem változik: természetes alap (megállapodás nélküli színlicit), Leaping Michaels és szokatlan 4NT a nemes blokkra, kétszínű közbeszólás vesztők szerint, közbeszólás = nyitás, kvázi gémforsz vége a 4m-nél, Multi-Landy válaszok, 18+ kontra, Exclusion RKC, udvariassági kulcslicit. Telepítés: `rendszerimport` + újraindítás (kódváltozás is van). |
| 2026-10-22 | **Összefésülés**: a licit- és a játék-szál közös állapota (egy fa, egy tároló: github.com/sferge/kibic). A licitmenet sor-fajtája KIHAGYAS (a 031 óta; a YAML `torol:`/`kihagy:`). A KIBIC általános információs kontrájában az erős kontra 17+, a Mohában (MOHA_INFO_KONTRA) 18+, ott a 16-19-es egyenletes lap 1NT-t mond, és a felmentés-kontra (9-11, 8-9 nemes lap) is él. A Michaels teljes válaszrendje (Michaels.pdf), exclusion RKC, udvariassági kulcslicit, kvázi gémforsz vége a 4m-nél; Leaping Michaels a minor blokkra (az ő színük a 4-es szinten = mindkét nemes); FOGÁSKÉRÉS (új elv: FOGASKERES): szan-gém csak fogással az ellenfél kimondott vagy kontrával ígért színében, fogás nélkül 3NT alatt az ő színük bemondása fogáskérés (a partner fogással / fél fogással 3NT, anélkül a fitbe). A FESU YAML-ban is (eddig csak az adatbázisban élt): mindkét színük ismert (kontra nem számít), legfeljebb a 3-as szinten; az erős ugrás új színben csak nem limitált lappal, a partner licitje után. Import: egyszer `rendszerimport rendszerek/yaml --csak FESU --kenyszer`, aztán a teljes import. |
| 2026-10-23 | Játék-szál. **Pontozás a lejátszásban**: IMP-ben (alapból) a lap értéke a pontszáma IMP-ben a mintán elérhető legjobbhoz mérve (a teljesítés / buktatás az elsődleges — biztonsági játék), MP-ben az átlagos ütés; a `game.scoring`-ból. **A minta nagysága a döntés biztosságától függ**: kötegenként, amíg el nem dől (legalább `KIBIC_LEJATSZAS_MIN_MINTA` = 60, legfeljebb `KIBIC_LEJATSZAS_MINTA` = 3000, az időkereten belül). Új meta: `scoring`, `stopped`. Új eszköz: `python -m kibic.cli.jatekmeres` (lapankénti DD-veszteség: napló, LIN, PBN, adatbázis). |
| 2026-10-23 (2.) | Játék-szál. **Építő sorsolás**: a rejtett kezek színhosszai a licit hosszígéretei szerint, pontos arányban (a hosszakra nincs eldobás; korábban szűk licitnél a próbák 90–97%-a elveszett). **Kis lapok összevonása** a kimerítő elemzésben (mintázatok, `KIBIC_LEJATSZAS_KIS_LAP`, `KIBIC_LEJATSZAS_MINTAZAT_HATAR`): a teljes elemzés a parti közepén is elérhető. A szabályon belüli `vagy:` ágai megmaradnak a kényszertárban (közös mag: `propagal.py`; a licitdöntést nem érinti). Új meta: `small_cards_merged`. |
| 2026-10-23 (3.) | Játék-szál. **A licit kizárásos következtetése a lejátszásban**: új `kovetkeztetes: LICIT_KIZARAS` sor (a SZEGEDI_MRAZ alaprendszerben, így mindenhol él): amit egy játékos a licitjével kizárt (pl. a passz 1♥-re: 0-5 pont, a licitmotor szimulációja szerint), az ennek ellentmondó elosztás 0,2 (1 pont eltérésnél fél) súllyal marad. Az ellenfél licitjét az ő rendszerük, ha ismeretlen, a miénk szerint olvassa. Aki a lapjaival már megmutatta, hogy nem a lap-megállapodás szerint játszik, arra a lapból levont következtetés nem él. Új beállítás: `KIBIC_LEJATSZAS_KOVETKEZTETES_MS`. A mérő CLI-ben: `--kovetkeztetes-ms`, `--mag`. Import kell (`rendszerimport`). |
| 2026-10-23 (4.) | Játék-szál, a mérőpad (fred-partik, 6797 döntés) tanulságai. **A licit igazítása a lapokhoz**: ha egy ígéret ellentmond a letett lapoknak, eddig az egész licitet (és a lejátszás következtetéseit) elengedte; most csak az ellentmondó rész igazodik (`meta.kibic.bidding_adjusted`). **PARTNER_KERESE**: a tűrés a pontozás egységében (IMP-ben IMP), nem ütésben — 0,16 ütés „alig rosszabb” lap IMP-ben 0,8-del rosszabb volt (a minták 19%-ában teljesült tőle a felvétel). Mérőpad: `--pbn`/`--lin` mappát is elfogad; `--mag` mellett a futás ismételhető (nem az idő állítja meg a döntést; `--idokorlat`), a `--json`-ban `megallt`, `minta`. |
| 2026-10-23 (5.) | Játék-szál, a szerkesztő döntései a fred-mérés után. **Menet közbeni hívás: a színt az elemzés választja**, a megállapodás a színen belül a lapot (színt csak a gyakorlatilag egyforma színek közül). **Smith a partner kérése**: a `PARTNER_KERESE` sor a partner Smith-jelét is követi (kicsi: váltunk, nagy: folytatjuk az indítás színét), ha az elemzés nem mond neki a tűrésnél jobban ellent; a jel nagyságát a mintákból becsüli. **Új következtetés: `FIGURA_SOROZAT`** (MOHA_STAND, súly 0,1): a nem ütésre tett figura zárt sorozat teteje vagy szingli; a kibic maga is így tesz. A megszegett lap-megállapodás csak a saját következtetését kapcsolja ki. YAML: import kell. |
| 2026-10-23 (6.) | Mérőpad: IMP-veszteség döntésenként (`imp_veszt`, `emberi_imp_veszt` a `--json`-ban; `IMP` oszlop a jelentésben), a beliállás és a kontra szerint; a `kibic+ / ember+` IMP-ben számol. |
| 2026-10-24 | Játék-szál, a szerkesztő döntései a Pavlicek-indulások után. Új mérlegelő sorok (MOHA_STAND): **`ASZ_ALOL`** — színfelvétel ellen ász alól nem indulunk (a partner színében sem); **`DUBLO_INDULAS`** — színfelvétel ellen figura nélküli dublóból nem indulunk szlem ellen, és ha a leosztás szan-jellegű (a minták többségében a felvevő szanban is ugyanannyit vinne; a mintánkénti szan-DD csak ilyenkor fut); `meta.kibic.ruff_based_share`. YAML: import kell. |
| 2026-10-24 (2.) | Játék-szál. Új következtetés: **`FELVETEL_HIHETO`** (MOHA_STAND, súly 0,6) — indulásnál az ellenfél önként licitált, kontrázatlan gémje / szleme ellen a DD szerint bukó elosztások kisebb súllyal számítanak (a kibic gém és szlem ellen kétszer annyi bukást várt, mint ahány lett). Mérőeszközök: `--suly KOD=SULY` (a súly felülírása hangoláshoz; `KIBIC_KOVETKEZTETES_SULY`), az `inditaselemzes` `--hangolas`-sal több súlyt vet össze egyszerre, és kalibrál vállalásonként. YAML: import kell. |
| 2026-10-24 (3.) | Játék-szál. **Gondolkodási idő a kijátszásban**: a kényszerű (pl. szingli) lapra se jöjjön azonnal a válasz, mert a gyorsaság elárulná, hogy nem volt választás. A `/v1/bridge/play` válasza legalább `KIBIC_GONDOLKODAS_MS` (alap 1500–3000 ms, véletlen) után érkezik; a hosszabb döntésekhez nem ad hozzá; legfeljebb a `deadline_ms` 30%-a; az utolsó ütésben nincs. A `meta.elapsed_ms` a döntés ideje. |
