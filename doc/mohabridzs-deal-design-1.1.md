# MohaBridzs – kibic kiosztástervező interfész

**Protokoll:** `mohabridzs-deal-design/1.1` · **Dokumentum:** 1.1.0 (2026-10-03)
**Kiváltja:** a `REBASE_1.1.28.md` „Kiosztástervező végpont” részét (az MB adatbázis- és felületi pontjai a 9. fejezetben, változatlan tartalommal).

A MohaBridzs (MB) ezen a végponton kér **kiosztássort** a kibictől. Három fajta igényt szolgál ki ugyanaz a kérés:

1. **Konkrét kiosztások** – egy verseny leosztásai (PBN), vagy az MB tárában lévő kiosztások újrajátszása, ellenőrzése, annotálása (a kibic licitje, DD-tábla).
2. **Licithelyzet gyakorlása** – páros, küzdelmi és védekező licit. A kiosztást **a kibic licitje válogatja** a megadott rendszerekkel: a helyzet akkor jön létre, ha a rendszer tényleg oda licitál, nem egy kézlista alapján.
3. **Lejátszás és ellenjáték gyakorlása** – kontraktus és feladat (pl. impassz, egyetlen buktató indulás), double dummy (DD) ellenőrzéssel.

---

## 1. Szereposztás

| | MohaBridzs | kibic |
|---|---|---|
| tárolás, tanári választás, felület | ✔ | |
| előre definiált egyszerű helyzetek helyi generálása (opcionális) | ✔ (delegált válasz, 6. fejezet) | |
| rendszerfüggő licithelyzet (a rendszer licitál) | | ✔ |
| verseny-PBN beolvasása, szűrése | | ✔ |
| lejátszási / ellenjátéki feladat DD-vel | | ✔ (DDS a szerveren) |
| szabad szöveg → strukturált kérés | LLM (pl. Hermes + Qwen), 7. fejezet | értelmezést visszaad, ellenőriz |

A kibic a 1.1-ben **mindig kész kiosztásokat** küld (`deals`). A delegált válaszforma (`preset_code` / `constraints`) a szerződés része marad, hogy egy másik szolgáltatás vagy az MB saját generátora is használhassa.

---

## 2. Szállítás

| Tétel | Érték |
|---|---|
| Kiosztáskérés | `POST {DEAL_DESIGN_ENDPOINT}` – a kibicnél `POST /v1/kibic/kiosztas` |
| Képességek | `GET /v1/kibic/kiosztas/kepessegek` (ugyanazzal a hitelesítéssel) |
| Felfedezés | `GET /v1/bridge/capabilities` → `deal_design: {protocol, endpoint, capabilities}` |
| Formátum | JSON, UTF-8, `Content-Type: application/json` |
| Hitelesítés | `Authorization: Bearer <titok>` – az MB ugyanazt az `AI_SHARED_SECRET`-et küldi, mint a többi kibic-hívásnál. A kibic oldalán `KIBIC_SHARED_SECRET` (vagy, ha külön AI-titkot állítottál be, `KIBIC_AI_SHARED_SECRET`) |
| Időtúllépés | az MB kliensének várakozása legyen legalább `time_budget_ms + 5000` ms |
| Méret | kérés legfeljebb 2 MiB (egy teljes verseny PBN-je belefér), válasz legfeljebb 4 MiB |
| Újrajátszhatóság | ugyanaz a kérés ugyanazzal a `seed`-del ugyanazt a sort adja (a rendszerek és a kibic verziójának változásáig) |

MB-beállítás (javított példa – a host valódi, elérhető cím legyen):

```dotenv
DEAL_DESIGN_ENDPOINT=https://kibic.example.hu/v1/kibic/kiosztas
# a titok a meglévő AI_SHARED_SECRET — új változó nem kell
```

---

## 3. A kérés

```json
{
  "protocol": "mohabridzs-deal-design/1.1",
  "request_id": "teacher-42-0007",
  "title": "Stayman gyakorlósor",
  "count": 8,
  "seed": "kedd-esti-sor",
  "first_board": 1,
  "dealer": "by_board",
  "vulnerability": "by_board",
  "student": {"seat": "S"},
  "systems": {"NS": "KIBIC_STAND", "EW": "KIBIC_STAND"},
  "source": {"type": "generate"},
  "target": {"preset": "NT_STAYMAN"},
  "include": ["auction"],
  "time_budget_ms": 20000
}
```

| Mező | Típus | Alap | Jelentés |
|---|---|---|---|
| `protocol` | string | `mohabridzs-deal-design/1.1` | más érték → `unsupported_protocol` |
| `request_id` | string | – | változatlanul visszajön |
| `title` | string | a preset neve | a sor címe |
| `count` | 1..64 (importnál 1..128) | 8 (importnál: mind) | kért kiosztások száma |
| `seed` | string / szám | a kibic sorsol | újrajátszhatóság; a válasz mindig visszaadja |
| `first_board` | egész ≥ 1 | 1 | az első tábla száma |
| `dealer` | `N E S W`, `0..3` (= N E S W), `by_board` | `by_board` | `by_board`: a táblaszámból (1→N, 2→E, 3→S, 4→W …) |
| `vulnerability` | `none ns ew both`, `by_board` | `by_board` | `by_board`: a szabványos 16-os ciklus (1 senki, 2 ÉD, 3 KNy, 4 mind, 5 ÉD …) |
| `student.seat` | `N E S W` | `S` | hol ül a gyakorló; a szerepek ehhez igazodnak |
| `systems` | `{NS, EW}` | `KIBIC_STAND` mindkettő | a licitszimuláció rendszerei (vonalanként) |
| `test_mode` | bool | szerver-alapérték | a jóvá nem hagyott szabályokkal is licitál-e |
| `source` | objektum | `{"type":"generate"}` | lásd 3.1 |
| `target` | objektum | `{}` | lásd 3.2 – 3.5 |
| `text` | string | – | szabad szöveges kérés (7. fejezet) |
| `dry_run` | bool | false | csak értelmezés + megvalósíthatóság, legfeljebb 3 példa (`examples`) |
| `include` | lista | `["auction"]` | `auction` (a kibic licitje), `dd` (20 mezős DD-tábla, DDS kell), `pbn` (PBN Deal-sor) |
| `time_budget_ms` | 500..120000 | 20000 | ennyi ideig keres; ami addig meglett, azt adja (`partial`) |

Ha az `auction.student_role` meg van adva, az osztó **ehhez** igazodik (a tanuló üljön a szerepben), a beliállás ilyenkor is a táblaszámból jön.

### 3.1 Forrás (`source`)

| `type` | Mezők | Mit csinál |
|---|---|---|
| `generate` | – | véletlen kiosztások a `seed`-ből; a `target` szűr |
| `pbn` | `pbn`: a PBN-fájl szövege; `boards`: [táblaszámok] (opcionális) | a `[Deal]` tagekből olvas (`[Board]`, `[Dealer]`, `[Vulnerable]`, `[Event]`; a `[Contract] [Declarer] [Result]` a `source.played`-be kerül); a `target` itt is szűr |
| `deals` | `deals`: [{`hands`, `board`?, `dealer`?, `vulnerability`?, `title`?}] | kész kiosztások ellenőrzése (52 lap), annotálása (licit, DD), szűrése |

### 3.2 Cél (`target`)

Minden megadott rész **egyszerre** teljesül (ÉS).

| Kulcs | Jelentés |
|---|---|
| `preset` | előre definiált helyzet kódja (lásd `kepessegek.presets`); a preset célja és a kérés többi célja összeolvad (a kérés felülír) |
| `hands` | kézfeltételek (3.3) |
| `auction` | licitcél (3.4) – a kibic licitje dönt |
| `play` | lejátszási / ellenjátéki cél (3.5) – DD |

### 3.3 Kézfeltétel (`target.hands`)

Kulcs: ülés (`N E S W`) **vagy** az osztóhoz képesti szerep: `dealer`, `lho` (az osztó bal keze), `partner`, `rho`. Érték:

| Kulcs | Példa | Jelentés |
|---|---|---|
| `hcp` | `"15-17"`, `"8+"`, `"-10"`, `[15,17]`, `12` | figurapont (A4 K3 Q2 J1) |
| `suits` | `{"S": "5+", "H": [0,3]}` | színhosszak |
| `shape` | `"balanced"` (4333 4432 5332), `"semi_balanced"` (+5422 6322), `"unbalanced"`, `["4432","5-4-3-1"]` | elosztás; kötőjel nélkül rendezett alak, kötőjellel pontos S-H-D-C |
| `cards` | `["SA","SQ"]` | ezek a lapok nála vannak |
| `no_cards` | `["SK"]` | ezek nincsenek nála |
| `any_of` | `[{"suits":{"S":"4"}}, {"suits":{"H":"4"}}]` | legalább egy ág teljesül |

Lapjelölés: szín + érték, `SA`, `HT` (tízes: `T`), mint az AI-gateway protokollban.

A kézfeltétel **gyorsít** (előszűr). A licithelyzetet nem ez dönti el, hanem a 3.4.

### 3.4 Licitcél (`target.auction`)

| Kulcs | Példa | Jelentés |
|---|---|---|
| `prefix` | `["1N","P","2C"]` | a kibic licitje (vonalanként a `systems` szerint) az osztótól így indul |
| `student_role` | `partner` | a tanuló melyik szerepben ül az osztóhoz képest (`dealer lho partner rho`) |
| `branch` | `competitive` | a tanuló vonala szemszögéből: `uncontested` (csak mi licitálunk), `competitive` (mi nyitottunk, ők is szóltak), `defensive` (ők nyitottak) |
| `final` | `{"contract": "3N", "side": "student", "min_level": 3}` | a kibic licitjének végső kontraktusa: `contract` (tokenek, mint az előtagban, pl. `"3N"`, `"3N|4H"`; a kontra nem számít), `side` (`student` / `opponents`: melyik vonal a felvevő), `min_level` |
| `fallback` | `exclude` | `allow` (alap) / `exclude` / `only`: ahol a kibicnek nem volt szabálya (passzra esett vissza, vagy a hézag-elv döntött) – az `only` a kibic fejlesztéséhez: a szabály nélküli helyek keresése |

Előtag-tokenek: konkrét hívás (`1N`, `2D`, `X`, `P`), alternatívák (`2D|2H`), `*` (bármi), `BID` (szintes licit), `!P` (nem passz). A szan jelölése `N` (a `NT` is elfogadott).

### 3.5 Lejátszási / ellenjátéki cél (`target.play`) – DDS kell

| Kulcs | Érték | Jelentés |
|---|---|---|
| `contract` | `auto` / `"4S"`, `"3NX"` | `auto`: a kibic licitjének végső kontraktusa; különben a megadott |
| `declarer` | `N E S W` | a megadott kontraktus felvevője (alap: `student.seat`) |
| `student` | `declarer` / `leader` | a tanuló a felvevő, vagy az induló védő. `auto` kontraktusnál a kibic két üléssel elforgatja az asztalt, hogy a tanuló a helyén üljön (csak generálásnál és azonos rendszereknél; a licit és a beli ettől nem változik) |
| `min_level` | 2 | a kontraktus legalább ilyen szintű |
| `result` | `makes` / `fails` / `exact` | DD szerint teljesül / bukik / pontosan teljesül |
| `technique` | `finesse`, `expassz`, `sure_tricks_short` (lista is lehet) | 8. fejezet |
| `lead` | `single_suit` / `any_beating` | `single_suit`: csak egy színből induló lap buktat (és van nem buktató indulás) |

---

## 4. A válasz

```json
{
  "protocol": "mohabridzs-deal-design/1.1",
  "request_id": "teacher-42-0007",
  "status": "ok",
  "title": "1NT – Stayman",
  "interpretation": {"preset": "NT_STAYMAN", "source": "generate", "count": 8,
                     "seed": "kedd-esti-sor", "student_seat": "S",
                     "systems": {"NS": "KIBIC_STAND", "EW": "KIBIC_STAND"},
                     "dealer": "by_board", "vulnerability": "by_board",
                     "hands": {"dealer": {"hcp": [15,17], "shape": "balanced"}, "...": "..."},
                     "auction": {"prefix": ["1N","P","2C"], "student_role": "partner"}},
  "deals": [
    {
      "board": 1,
      "deal_id": "3f2a9c1d0b7e4a55",
      "hands": {"N": ["SA","SK","..."], "E": ["..."], "S": ["..."], "W": ["..."]},
      "dealer": "N",
      "vulnerability": "none",
      "tags": ["Stayman", "páros licit"],
      "source": {"type": "generate", "seed": "kedd-esti-sor", "index": 17},
      "auction": [{"seat":"N","call":"1N"}, {"seat":"E","call":"P"},
                  {"seat":"S","call":"2C","alert":"Stayman"}, "..."],
      "contract": {"level": 3, "strain": "N", "multiplier": 1, "declarer": "N"},
      "checks": {"needed_tricks": 9, "dd_tricks": 9}
    }
  ],
  "stats": {"requested": 8, "returned": 8, "tried": 1630, "elapsed_ms": 4210,
            "source_exhausted": false},
  "warnings": []
}
```

| Mező | Jelentés |
|---|---|
| `status` | `ok` (megvan a kért szám, vagy az import forrása elfogyott), `partial` (az időkeret lejárt, kevesebb jött), `empty` (egy sem – ilyenkor HTTP 422, `error.code = no_deals_found`) |
| `interpretation` | amit a kibic a kérésből értett: a preset feloldva, a sávok `[lo, hi]` alakban. **Ezt kell megmutatni** a tanárnak szabad szöveges kérésnél |
| `deals[].hands` | négy kéz, kezenként pontosan 13 lap, összesen 52 különböző; színenként S H D C, értéken belül csökkenő |
| `deals[].deal_id` | a kiosztás lenyomata (16 hex); ugyanaz a kiosztás mindig ugyanazt adja – duplikátumszűréshez |
| `deals[].source` | honnan jött: `generate` (`seed`, `index`: a `seed` + `index` egyértelműen visszaállítja a kezeket), `pbn` (`event`, `board`, `played`), `deals` (`index`) |
| `deals[].auction` | a kibic licitje (ha kérték, vagy licitcél volt); az elemek `alert` szövege a rendszer magyarázata. **Javaslat, nem kötelező menet**: a játékban a játékosok licitálnak |
| `deals[].auction_fallback` | true, ha a menetben volt hely, ahol a kibicnek nem volt szabálya (passz lett) |
| `deals[].auction_gap` | true, ha a menetben volt hely, ahol szabály helyett a hézag-elv döntött (az elem `gap: true`) |
| `deals[].contract` | a kibic licitjének vagy a megadott célnak a kontraktusa |
| `deals[].checks` | a lejátszási ellenőrzés: `needed_tricks`, `dd_tricks`, `techniques` [{`type`, `suit`, `card`, `seat`}], `beating_leads`, `leader`, `sure_tricks` |
| `deals[].dd` | `{N:{S,H,D,C,NT}, ...}` ütésszámok (ha `include: dd`) |
| `deals[].pbn` | `"N:AKQ2.KQ2.A32.432 ..."` (ha `include: pbn`), az osztótól |
| `stats` | `requested`, `returned`, `tried` (megvizsgált jelöltek), `elapsed_ms`, `source_exhausted` |

Az MB tárolás előtt ellenőrzi az 52 lapot (ahogy az 1.1.28 leírja); a kibic is ellenőriz, a hibás bemenetet `invalid_deal` hibával utasítja el.

A kiosztás és a menet **nem titkos**: ez a végpont kiosztást ad, nem döntést. A „kéz nélküli magyarázat” szabály a `/v1/bridge/explain` és a kártya-végpontokra vonatkozik, erre nem.

---

## 5. Hibák

Hiba esetén a test:

```json
{"protocol": "mohabridzs-deal-design/1.1", "request_id": "…", "status": "error",
 "error": {"code": "unsupported_target", "message": "…"}}
```

| HTTP | `error.code` | Mikor |
|---|---|---|
| 400 | `invalid_request` | hibás mező, sáv, kulcs |
| 400 | `unsupported_protocol` | ismeretlen `protocol` |
| 400 | `invalid_deal` | nem 4×13 / 52 különböző szabályos lap |
| 400 | `pbn_parse_error` | olvashatatlan PBN |
| 401 | – | rossz vagy hiányzó titok |
| 422 | `unknown_preset` | ismeretlen `target.preset` |
| 422 | `unsupported_target` | a kibic ezt a célt (még) nem tudja – pl. tervezett technika |
| 422 | `text_unsupported` | szabad szöveg, de nincs fordító beállítva |
| 422 | `no_deals_found` | az időkereten belül egy sem akadt (a válaszban `stats`) |
| 503 | `dds_unavailable` | lejátszási cél / DD-tábla, de a szerveren nincs DDS |
| 503 | `auction_unavailable` | a licitcélhoz a rendszerek nem tölthetők be |

Hiba esetén az MB a tanárnak az `error.message`-et mutatja; a parti nem indul a hibás sorral.

---

## 6. Delegált válasz (szolgáltatás → MB helyi generálás)

Egy kiosztástervező szolgáltatás válaszolhat úgy is, hogy **nem** küld kiosztást, hanem megmondja, mit generáljon az MB helyben:

```json
{"protocol": "mohabridzs-deal-design/1.1", "request_id": "…", "status": "ok",
 "preset_code": "NT_STAYMAN",
 "constraints": {"N": {"hcp": "15-17", "shape": "balanced"},
                 "S": {"hcp": "8+", "any_of": [{"suits": {"S": "4"}}, {"suits": {"H": "4"}}]}},
 "count": 8, "seed": "kedd-esti-sor"}
```

- A `constraints` **ugyanaz a nyelv**, mint a `target.hands` (3.3), csak üléskulcsokkal. Az MB generátorának legalább a `hcp`, `suits`, `shape` (`balanced`) kulcsokat kell tudnia; amit nem tud, arra ne generáljon (`unsupported` a tanárnak), mert csendes elhagyással rossz sor készülne.
- A `boards` kulcs a `deals` régi neve: az MB elfogadja, a szolgáltatások a `deals`-t küldjék.
- A kibic 1.1 mindig `deals`-szel válaszol.

---

## 7. Szabad szöveges kérés

**Javaslat: vállaljuk, de mindig jóváhagyással.**

```
tanár szövege ──▶ LLM (Hermes pipeline, Qwen) ──▶ target (JSON) ──▶ kibic dry_run
                         ▲  response_schema = a target sémája        │
                         │  + a kepessegek.presets listája           ▼
                         └──────────── javítás ◀──────── interpretation + példák
                                                         (a tanár jóváhagyja)
                                                                     │
                                                                     ▼
                                                        a valódi kérés ugyanazzal a target-tel
```

- **Az LLM nem talál ki kiosztást**, csak a `target`-et tölti ki. A legjobb, ha elsősorban **presetet választ** a `kepessegek.presets` listából, és csak kevés paramétert ad hozzá (sávok, ki a tanuló). A `kepessegek` válasza ehhez minden felsorolást tartalmaz.
- **Qwen alkalmassága:** a Hermes `llm_call` lépése tud `response_schema`-t (kikényszerített JSON-alak), a `request_schema`-val a Qwen3 „thinking” módja kikapcsolható. Ezzel egy 14B-s Qwen megbízhatóan **választ** a felsorolt értékek közül és tölt ki sávokat. Szabad kézfeltételt vagy licitelőtagot kitalálni viszont már bizonytalanabb, ezért a jóváhagyás (`interpretation`) nem hagyható ki.
- Ha a kérés `text` mellett `target`-et is hoz, a `target` számít (a szöveg csak megjegyzés).
- A kibic 1.1-ben fordító **nincs bekötve**: `text` önmagában → `text_unsupported`. A bekötés helye a kibicben `kiosztas.SZOVEG_FORDITO`; ha a fordítás az MB-ben történik, a kibic oldalán nincs teendő.

---

## 8. Lejátszási technikák – mit lehet felismerni

A felismerés **double dummy**: nyílt lapokkal számol. Egy technikára a kiosztást úgy válogatjuk, hogy **csak azzal** teljesüljön a kontraktus.

| Technika | Kód | Állapot | Hogyan |
|---|---|---|---|
| impassz | `finesse` | ✔ | **csere-teszt**: a kontraktus DD szerint teljesül, de ha egy védőfigurát (A K Q J) a másik védőhöz teszünk (a legkisebb lapjával cserélve, a hosszak nem változnak), bukik. Impassz, ha a felvevő oldalnak van e figuránál magasabb lapja (villa). |
| expassz | `expassz` | ✔ | ugyanaz a csere-teszt, de a felvevő oldalnak nincs a kulcsfiguránál magasabb lapja (pl. Kx a hiányzó ász ellen: a K felé kell játszani) |
| kevés biztos ütés | `sure_tricks_short` | kísérleti | DD szerint teljesül, de a felső biztos ütések száma kevesebb a szükségesnél – „valamit ki kell dolgozni” (szín kifejlesztése, lopás…) |
| egyetlen buktató indulás | `lead: single_suit` | ✔ | az induló minden lapját kiértékeljük (DD): buktat-e |
| asztalfordítás | `dummy_reversal` | tervezett | sablon + DD-ellenőrzés |
| keresztlopás | `crossruff` | tervezett | sablon + DD |
| eliminálás, bedobás | `elimination` | tervezett | sablon + DD |
| beszorítás | `squeeze` | tervezett | sablon + DD |
| adupuccs | `trump_coup` | tervezett | sablon + DD |
| tartás | `hold_up` | tervezett | sablon + DD |
| biztonsági játék | `safety_play` | tervezett | több ellenfél-elosztáson mért teljesülési arány |

A **tervezett** technikák terve: a kulcsszín(ek) **sablonból** jönnek (pl. beszorításnál a fenyegető lapok és a beszorított védő tartásai), a többi lap véletlen, és a DD igazolja, hogy a kontraktus teljesül, a „naiv” játékkal (pl. impasszal) viszont nem. Amíg egy technika nincs kész, a kérés `unsupported_target` hibát kap. Csendes, rossz sort a kibic nem ad.

A DD **felső korlát**: azt mutatja, mi lett volna a legjobb nyílt lapokkal. Egy emberi lejátszásnál a helyes technika valószínűségi döntés is lehet. A `checks` ezért azt írja le, **amin a kontraktus múlik**, nem azt, hogy „ezt kell játszani”.

---

## 9. MB oldal (az 1.1.28 leírásból, pontosítva)

**Adatbázis** – az 1.1.27 migráció után:

```sql
SOURCE database/migrations/1.1.28_deal_context.sql;
```

A két új, opcionális mező a kiosztással együtt őrzi az **osztót** és a **beliállást**. A futó alkalmazás a hiányzó oszlopokat is létrehozza, de a kézi migráció ajánlott. Javaslat a következő migrációba (a protokoll már küldi): `deal_id` (egyediség, duplikátumszűrés), `source` (JSON: seed+index / PBN event+board), `auction` (a kibic javasolt menete, JSON), `tags`.

**Felület**
- Az admin kiosztástára önálló blokk a hallban, nem a Hall beállításain belül.
- A tanár játék közben a bal oldali sávból kiválaszthatja a következő kiosztást.
- A felső sávban az É–D és a K–Ny rendszere egymás mellett jelenik meg; a rendszer neve megnyitja a kártyát.
- Megszűntek a játékosnevek melletti kártyaikonok és a rendszernevek melletti négyzetek.
- A konvenciókártya nem modális, húzható és átméretezhető ablakban nyílik meg.

**Javaslat a kérőfelületre:** preset-lista (a `kepessegek.presets`-ből), darabszám, seed (megjeleníteni, hogy egy sort újra lehessen kérni), tanuló ülése; haladó módban szabad szöveg → `dry_run` → jóváhagyás.

---

## 10. Példák

**Verseny kiosztásai, csak ahol a kibic 1NT-Stayman menetet licitálna:**

```json
{"source": {"type": "pbn", "pbn": "[Event \"OB 2026\"]\n[Board \"1\"] …"},
 "target": {"auction": {"prefix": ["1N", "P", "2C"]}},
 "include": ["auction", "dd"]}
```

**Küzdelmi licit – negatív kontra, a tanuló Dél:**

```json
{"count": 6, "target": {"preset": "NEGATIVE_DOUBLE"}, "student": {"seat": "S"}}
```

**Lejátszás – impassz, legalább 2-es szintű kontraktus, a tanuló a felvevő:**

```json
{"count": 4, "target": {"preset": "FINESSE"}, "include": ["auction", "dd"], "time_budget_ms": 60000}
```

**Ellenjáték – az indulás dönt, a tanuló indul:**

```json
{"count": 4, "target": {"preset": "OPENING_LEAD"}}
```

**Saját feltételek, rendszer nélkül (csak kézfeltétel):**

```json
{"count": 10, "seed": 7,
 "target": {"hands": {"N": {"hcp": "20-21", "shape": "balanced"},
                      "S": {"hcp": "4-8", "suits": {"H": "5+"}}}}}
```

**Kibic-fejlesztés – ahol a kibic néma volt:**

```json
{"count": 20, "target": {"auction": {"prefix": ["1C|1D", "BID"], "fallback": "only"}},
 "include": ["auction"]}
```

---

## 11. Átadás előtti ellenőrzés

```bash
python -m kibic.cli.kiosztasproba --cim http://localhost:9050 --titok <AI-gateway titok>
```

A próba végigméri:
- a képességeket;
- a generálást és az újrajátszhatóságot;
- minden licites presetet;
- a PBN-importot;
- a hibakódokat;
- DDS esetén a lejátszási és ellenjátéki presetet.

---

## Változásnapló

| Dátum | Változás |
|---|---|
| 2026-10-03 | 1.1.0 – az MB 1.1.28 leírásának pontosítása és kiegészítése: teljes kérés- és válaszséma, források (generálás, PBN, kész kiosztások), cél (kéz, licit a kibic rendszerével, lejátszás, ellenjáték), értelmezés, szabad szöveg folyamata, hibakódok, képességek-végpont, delegált válasz pontosítása. |
