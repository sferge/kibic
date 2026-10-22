# MohaBridzs AI Gateway interfész v1

**Protokoll:** `mohabridzs-ai/1.0`  
**Célalkalmazás:** MohaBridzs 1.1.4  
**Állapot:** implementált, jelenleg használt szerződés  
**Kódolás:** UTF-8 JSON, nem streaming válasz

## 1. Rövid összefoglaló

A MohaBridzs a játékszabályok és a teljes játékállapot kizárólagos gazdája. A gateway nem módosít állapotot: minden kérésben megkapja az adott AI-játékos számára látható információt és a pillanatnyilag szabályos lépések teljes listáját, majd pontosan egy lépést választ.

Két döntési végpont szükséges:

```text
POST {base_url}/v1/bridge/bid
POST {base_url}/v1/bridge/play
```

A gateway feladata:

1. ellenőrizni a hitelesítést és a protokollverziót;
2. idempotensen kezelni a `request_id` értéket;
3. a `legal_actions` elemei közül választani;
4. a határidőn belül HTTP 200-as JSON-választ adni;
5. változtatás nélkül visszaadni a kérés `request_id` értékét.

A modell belső felépítése szabadon cserélhető. Lehet közvetlen LLM-hívás, Hermes-pipeline, RAG, episztemikus állapotgép, szabályalapú elő- vagy utófeldolgozó, illetve ezek kombinációja.

## 2. Gateway alapcím

Az AI-profil alapcíme a `moha_club.email` mezőben található, például:

```text
http://192.168.77.70:9049
```

Az alapcím tartalmazhat útvonal-prefixet is. Például a
`https://ai.example/bridge-api` alapcímhez a MohaBridzs ezeket hívja:

```text
https://ai.example/bridge-api/v1/bridge/bid
https://ai.example/bridge-api/v1/bridge/play
```

Elfogadott alapcím:

- `https://` tetszőleges érvényes hosttal;
- `http://` csak localhosttal, loopback-, link-local- vagy privát IP-címmel;
- felhasználónév, jelszó, query string és fragment nem lehet benne;
- a teljes alapcím legfeljebb 500 karakter.

## 3. HTTP-szerződés

### 3.1 Kérés

```http
POST /v1/bridge/bid HTTP/1.1
Accept: application/json
Content-Type: application/json; charset=utf-8
X-MohaBridzs-Protocol: 1.0
Idempotency-Key: <request_id>
Authorization: Bearer <AI_SHARED_SECRET>
```

Az `Authorization` fejléc csak akkor szerepel, ha a MohaBridzs környezetében az `AI_SHARED_SECRET` nem üres. A MohaBridzs a titok elejéről és végéről levágja a whitespace-t. Gyakorlatban 64 karakteres ASCII hex titok ajánlott:

```bash
openssl rand -hex 32
```

A gateway a Bearer értéket konstans idejű, UTF-8 bájtokon végzett összehasonlítással ellenőrizze.

### 3.2 Sikeres válasz

```http
HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8
```

Csak a pontos HTTP 200 számít sikernek. A 201, 204, 3xx, 4xx és 5xx válasz egyaránt MohaBridzs-fallbacket vált ki. Átirányítás követése tiltott.

A válasz legyen legfeljebb 65 536 karakter; biztonságos implementációs határként legfeljebb 64 KiB UTF-8 JSON javasolt.

### 3.3 Időkorlát

A kérés `deadline_ms` mezője tartalmazza a MohaBridzs kemény időkorlátját. Jelenlegi alapérték:

```text
licit:       60000 ms
kijátszás:  60000 ms
```

A MohaBridzs az idő lejártakor megszakítja a HTTP-kérést. A gatewaynek célszerű saját feldolgozási határidejét néhány száz milliszekundummal rövidebbre állítania, hogy még legyen ideje JSON-választ küldeni.

### 3.4 Idempotencia

A `Idempotency-Key` fejléc értéke mindig azonos a body `request_id` mezőjével. A gateway kezelje ezt átlátszatlan kulcsként.

Azonos kulcs ismételt fogadásakor ajánlott:

- ugyanazt a már elkészült választ visszaadni;
- folyamatban lévő azonos kéréshez nem indítani új modellhívást;
- eltérő bodyval érkező azonos kulcsot naplózni és elutasítani.

## 4. Közös kérésobjektum

Az alábbi TypeScript-típus a tényleges JSON-szerződést írja le:

```ts
type Seat = "N" | "E" | "S" | "W";
type Suit = "C" | "D" | "H" | "S";
type Strain = Suit | "N";
type Rank = "2" | "3" | "4" | "5" | "6" | "7" | "8" |
            "9" | "T" | "J" | "Q" | "K" | "A";
type Card = `${Suit}${Rank}`;
type ContractCall = `${1 | 2 | 3 | 4 | 5 | 6 | 7}${Strain}`;
type Call = "P" | "X" | "XX" | ContractCall;

type Vulnerability = "none" | "ns" | "ew" | "both";

type PlayedCard = {
  seat: Seat;
  card: Card;
};

type Contract = {
  level: 1 | 2 | 3 | 4 | 5 | 6 | 7;
  strain: Strain;
  multiplier: 1 | 2 | 4;
};

type CommonRequest = {
  protocol: "mohabridzs-ai/1.0";
  request_id: string;
  decision: "bid" | "play";
  deadline_ms: number;

  game: {
    match_id: string;
    state_version: number;
    round_number: number;
    board_number: number;
    table_index: 0 | 1;
    vulnerability: Vulnerability;
  };

  actor: {
    player_index: number;
    seat: Seat;
    acting_for_seat: Seat;
    is_declarer: boolean;
    controls_dummy: boolean;
    profile_code: string;
  };

  state: {
    phase: "bidding" | "play";
    dealer: Seat;
    current_seat: Seat;
    contract: Contract | null;
    declarer: Seat | null;
    dummy: Seat | null;
    visible_hands: Partial<Record<Seat, Card[]>>;
    current_trick: PlayedCard[];
    completed_tricks: Array<{
      cards: PlayedCard[];
      winner: Seat;
    }>;
    ns_tricks: number;
  };

  history: {
    auction: Array<{
      seat: Seat;
      call: Call;
    }>;
    play: PlayedCard[];
  };
};

type BidRequest = CommonRequest & {
  decision: "bid";
  legal_actions: {
    calls: Call[];
  };
};

type PlayRequest = CommonRequest & {
  decision: "play";
  legal_actions: {
    cards: Card[];
  };
};
```

## 5. A mezők jelentése

### 5.1 Felső szint

| Mező | Jelentés |
|---|---|
| `protocol` | Mindig `mohabridzs-ai/1.0`. Ismeretlen verziót a gateway utasítson el. |
| `request_id` | Egy döntési helyzet egyedi, idempotens azonosítója. A gateway ne próbálja üzleti adatokra bontani. |
| `decision` | `bid` vagy `play`; egyezik a meghívott végponttal. |
| `deadline_ms` | A teljes HTTP-kérés kemény időkerete milliszekundumban. |

A jelenlegi azonosító alakja jellemzően:

```text
<match_id>:<state_version>:<table_index>:<controller_seat>:<bid|play>:<action_count>
```

Ez implementációs részlet; a gateway számára az egész érték átlátszatlan string.

### 5.2 `game`

| Mező | Jelentés |
|---|---|
| `match_id` | A hall/mérkőzés stabil belső azonosítója. |
| `state_version` | Optimista konkurenciakezeléshez használt, monoton növekvő állapotverzió. |
| `round_number` | Fordulós meccsnél a forduló száma; gyakorlásban jelenleg `1`. |
| `board_number` | A leosztás száma. Gyakorló módban korlátlanul növekedhet. |
| `table_index` | `0`: első/nyílt asztal; `1`: második/zárt asztal. Gyakorlásban mindig `0`. |
| `vulnerability` | `none`, `ns`, `ew` vagy `both`. |

### 5.3 `actor`

| Mező | Jelentés |
|---|---|
| `player_index` | A hall játékoslistájának 0–7 közötti indexe. |
| `seat` | A döntést hozó AI aktuális égtája. |
| `acting_for_seat` | Annak a kéznek az égtája, amelyből ténylegesen licitál/játszik. |
| `is_declarer` | Igaz, ha a döntést hozó AI a felvevő. |
| `controls_dummy` | Igaz, amikor a felvevő AI éppen az asztal kezéből játszik. |
| `profile_code` | Az AI klubprofil rövid kódja/nickje; pipeline-, licitrendszer- vagy RAG-profil választására használható. |

Licitnél `seat === acting_for_seat`, `is_declarer === false` és `controls_dummy === false`.

Kijátszásnál felvevői asztalvezérlés esetén például:

```json
{
  "seat": "N",
  "acting_for_seat": "S",
  "is_declarer": true,
  "controls_dummy": true
}
```

### 5.4 `state`

- `dealer`: az osztó;
- `current_seat`: az a kéz, amelyből most licitálni vagy lapot tenni kell;
- `contract`: a végleges felvétel, licit közben `null`;
- `multiplier`: `1` alap, `2` kontra, `4` rekontra;
- `declarer`, `dummy`: licit közben `null`, lejátszásban égtáj;
- `visible_hands`: kizárólag a döntéshozó számára szabályosan látható kezek;
- `current_trick`: az aktuális ütés eddig kijátszott 0–3 lapja;
- `completed_tricks`: a már lezárt ütések teljes tartalma és nyertese;
- `ns_tricks`: az É–D vonal eddig megszerzett ütéseinek száma.

### 5.5 `history`

Az `auction` a teljes licittörténet időrendben. A `play` minden eddig kijátszott lapot tartalmaz időrendben, beleértve az aktuális ütés lapjait is.

### 5.6 `legal_actions`

Ez a szabálymotor által kiszámított, teljes és autoritatív választék:

- licitnél `legal_actions.calls`;
- kijátszásnál `legal_actions.cards`.

A gateway kizárólag ebből a tömbből választhat. Nem szükséges és nem ajánlott a teljes bridzsszabály-motort a gatewayben megismételni, de egy végső tagsági ellenőrzés erősen ajánlott.

## 6. Kártya- és licitkódolás

### 6.1 Kártyák

A kártyakód pontosan két karakter:

```text
C2  DA  HT  SQ
```

Első karakter a szín:

| Kód | Szín |
|---|---|
| `C` | treff |
| `D` | káró |
| `H` | kőr |
| `S` | pikk |

A második karakter a rang: `2 3 4 5 6 7 8 9 T J Q K A`. A tízes `T`, nem `10`.

### 6.2 Licitek

```text
P    passz
X    kontra
XX   rekontra
1C   egy treff
4H   négy kőr
3N   három szan
```

## 7. Licitkérés és -válasz

### 7.1 Példakérés

```json
{
  "protocol": "mohabridzs-ai/1.0",
  "request_id": "5aa92d15:17:0:1:bid:6",
  "decision": "bid",
  "deadline_ms": 60000,
  "game": {
    "match_id": "5aa92d15-3a5b-4fa3-88c1-45dd3a32c701",
    "state_version": 17,
    "round_number": 1,
    "board_number": 3,
    "table_index": 0,
    "vulnerability": "ns"
  },
  "actor": {
    "player_index": 1,
    "seat": "E",
    "acting_for_seat": "E",
    "is_declarer": false,
    "controls_dummy": false,
    "profile_code": "qwen"
  },
  "state": {
    "phase": "bidding",
    "dealer": "S",
    "current_seat": "E",
    "contract": null,
    "declarer": null,
    "dummy": null,
    "visible_hands": {
      "E": ["SA", "SJ", "S7", "H9", "H4", "DA", "DQ", "D8", "D3", "CK", "CJ", "C6", "C2"]
    },
    "current_trick": [],
    "completed_tricks": [],
    "ns_tricks": 0
  },
  "history": {
    "auction": [
      {"seat": "S", "call": "1H"},
      {"seat": "W", "call": "P"},
      {"seat": "N", "call": "2H"}
    ],
    "play": []
  },
  "legal_actions": {
    "calls": ["P", "X", "2S", "2N", "3C", "3D", "3H", "3S", "3N", "4C"]
  }
}
```

A valódi `calls` lista nem rövidített: minden pillanatnyilag szabályos licitet tartalmaz.

### 7.2 Minimális sikeres válasz

```json
{
  "request_id": "5aa92d15:17:0:1:bid:6",
  "action": {
    "type": "bid",
    "call": "2S"
  }
}
```

## 8. Kijátszáskérés és -válasz

### 8.1 Példakérés

```json
{
  "protocol": "mohabridzs-ai/1.0",
  "request_id": "5aa92d15:24:0:0:play:9",
  "decision": "play",
  "deadline_ms": 60000,
  "game": {
    "match_id": "5aa92d15-3a5b-4fa3-88c1-45dd3a32c701",
    "state_version": 24,
    "round_number": 1,
    "board_number": 3,
    "table_index": 0,
    "vulnerability": "ns"
  },
  "actor": {
    "player_index": 0,
    "seat": "N",
    "acting_for_seat": "S",
    "is_declarer": true,
    "controls_dummy": true,
    "profile_code": "qwen"
  },
  "state": {
    "phase": "play",
    "dealer": "S",
    "current_seat": "S",
    "contract": {"level": 4, "strain": "H", "multiplier": 1},
    "declarer": "N",
    "dummy": "S",
    "visible_hands": {
      "N": ["SA", "S7", "H9", "H4", "DA", "CK", "C6"],
      "S": ["SK", "S9", "HA", "HK", "H7", "D6", "C8", "C3"]
    },
    "current_trick": [
      {"seat": "W", "card": "D2"},
      {"seat": "N", "card": "D8"},
      {"seat": "E", "card": "D5"}
    ],
    "completed_tricks": [
      {
        "cards": [
          {"seat": "S", "card": "S2"},
          {"seat": "W", "card": "SQ"},
          {"seat": "N", "card": "S5"},
          {"seat": "E", "card": "S4"}
        ],
        "winner": "W"
      }
    ],
    "ns_tricks": 0
  },
  "history": {
    "auction": [
      {"seat": "S", "call": "P"},
      {"seat": "W", "call": "P"},
      {"seat": "N", "call": "1H"},
      {"seat": "E", "call": "P"},
      {"seat": "S", "call": "4H"},
      {"seat": "W", "call": "P"},
      {"seat": "N", "call": "P"},
      {"seat": "E", "call": "P"}
    ],
    "play": [
      {"seat": "S", "card": "S2"},
      {"seat": "W", "card": "SQ"},
      {"seat": "N", "card": "SA"},
      {"seat": "E", "card": "S4"},
      {"seat": "W", "card": "D2"},
      {"seat": "N", "card": "D8"},
      {"seat": "E", "card": "D5"}
    ]
  },
  "legal_actions": {
    "cards": ["D6"]
  }
}
```

### 8.2 Minimális sikeres válasz

```json
{
  "request_id": "5aa92d15:24:0:0:play:9",
  "action": {
    "type": "play",
    "card": "D6"
  }
}
```

## 9. Válaszséma és diagnosztika

### 9.1 Teljes válasz

```ts
type GatewayResponse = {
  request_id: string;
  action:
    | { type: "bid"; call: Call }
    | { type: "play"; card: Card };

  confidence?: number;
  explanation?: string;
  meta?: {
    source?: string;
    pipeline?: string;
    elapsed_ms?: number;
    fallback_reason?: string | null;
  };
};
```

### 9.2 Kötelező mezők

- `request_id`: karakterre pontosan egyezzen a kérésével;
- `action.type`: egyezzen a kért döntéstípussal;
- licitnél `action.call`: szerepeljen a `legal_actions.calls` tömbben;
- kijátszásnál `action.card`: szerepeljen a `legal_actions.cards` tömbben.

### 9.3 Opcionális diagnosztika

```json
{
  "request_id": "5aa92d15:17:0:1:bid:6",
  "action": {
    "type": "bid",
    "call": "2S"
  },
  "confidence": 0.78,
  "explanation": "Természetes, versengő pikk licit.",
  "meta": {
    "source": "model",
    "pipeline": "bridge_bid_v2",
    "elapsed_ms": 10827,
    "fallback_reason": null
  }
}
```

Feldolgozási szabályok:

- `confidence`: véges szám; a MohaBridzs a naplóban 0–1 közé szorítja;
- `explanation`: nem üres string, legfeljebb 1000 karakter kerül a naplóba;
- `meta.source`: legfeljebb 80 karakter kerül a naplóba;
- `meta.pipeline`: legfeljebb 80 karakter kerül a naplóba;
- `meta.elapsed_ms`: véges szám, a MohaBridzs nemnegatív egészre alakítja;
- `meta.fallback_reason`: legfeljebb 240 karakter kerül a naplóba;
- ismeretlen extra response mezők jelenleg figyelmen kívül maradnak.

### 9.4 Gateway-szintű fallback

Ha a gateway nem kapott használható modellválaszt, de maga választ egy szabályos tartalék lépést, továbbra is HTTP 200-at adhat:

```json
{
  "request_id": "5aa92d15:17:0:1:bid:6",
  "action": {
    "type": "bid",
    "call": "P"
  },
  "confidence": 0,
  "explanation": "Biztonságos tartalék lépés.",
  "meta": {
    "source": "fallback",
    "pipeline": "bridge_bid_v2",
    "elapsed_ms": 59000,
    "fallback_reason": "a modell nem adott választ a belső határidőig"
  }
}
```

Ha `meta.source === "fallback"` vagy a `fallback_reason` nem üres, a MohaBridzs adminnaplója **gateway fallbackként** jelöli a döntést, de a szabályos Actiont végrehajtja.

## 10. MohaBridzs-oldali validáció és fallback

A MohaBridzs saját fallbacket használ, ha:

- a végpont érvénytelen;
- hálózati hiba történik;
- lejár a `deadline_ms`;
- a státusz nem pontosan 200;
- a body nem érvényes JSON;
- a body 65 536 karakternél hosszabb;
- eltér a `request_id`;
- hibás vagy hiányzik az `action.type`;
- a választott licit/lap nincs a megfelelő `legal_actions` listában.

MohaBridzs fallback:

- licit: `P`, ha szabályos; különben a lista első eleme;
- kijátszás: a legalacsonyabb rangú szabályos lap; azonos rangnál `C < D < H < S`.

A hibás gateway-válasz tehát nem állítja meg a partit, de az adminnaplóban fallbackként jelenik meg.

## 11. Látható és rejtett információ

A gateway megkapja:

- az AI saját kezét;
- az asztalt az indító kijátszás után;
- AI felvevő esetén az AI által vezérelt asztalt is;
- elutasított terítés után a nyitott felvevői kezet;
- a teljes licit- és kijátszástörténetet;
- a felvételt, osztót, szkórhelyzetet és ütésállást;
- a szabályos lépések teljes listáját.

A gateway nem kapja meg:

- a még rejtett ellenfél- vagy partnerkezet;
- a párhuzamos asztal állapotát vagy eredményét;
- meghívó-, játékos-, admin- vagy kibictokeneket;
- személyes belépőkódokat;
- adatbázis-hozzáférést vagy más játékos privát profiladatait.

### 11.1 Ember–AI felvevőpár az 1.1.4-ben

Ha az AI lesz a felvevő és a párja ember, akkor az ember vezérli az AI felvevő kezét és a saját, asztalként leterített kezét is. Ilyenkor a gateway:

- továbbra is megkapja az AI licitkéréseit;
- **nem kap kijátszáskérést** sem az AI felvevő, sem az emberi asztal kezéhez;
- nem dönt a felvevővonal terítéséről vagy az ellenfél kártya-undójáról.

Ha a felvevő és az asztal is AI, a felvevő AI profilja kapja mindkét kéz kijátszáskéréseit. Az asztalként ülő AI profil önálló kijátszáskérést nem kap.

Ha az ember a felvevő és az AI a párja/asztal, az ember vezérli az asztalt, tehát az AI pár szintén nem kap kijátszáskérést a felvevővonalon.

## 12. Munkamenet, RAG és memória

A `profile_code` használható licitrendszer, modell, prompt vagy RAG-korpusz kiválasztására.

Ajánlott döntési munkamenetkulcs:

```text
(match_id, table_index, board_number, actor.seat, profile_code)
```

Ajánlott szabályok:

- új `board_number` esetén a kézhez kötött episztemikus állapot induljon újra;
- a játékos- és licitrendszerprofil megmaradhat a mérkőzésen belül;
- az `history` legyen az autoritatív előzmény, a gateway memóriája csak gyorsítótár;
- eltérés esetén mindig a friss request body nyerjen;
- külön licit- és kijátszási pipeline használható;
- RAG-lekérdezésnél a kéz, aktuális aukció, szkórhelyzet, égtáj és szerep legyen a keresési kontextus;
- a végső kimenetet determinisztikusan ellenőrizni kell a `legal_actions` ellen.

## 13. Nem támogatott műveletek v1-ben

A gateway v1-ben nem kezdeményezhet:

- terítést;
- undo-kérést;
- chatüzenetet;
- ültetést vagy hallműveletet;
- következő leosztást/fordulót;
- egyszerre több licitet vagy lapot.

AI-védő esetén a MohaBridzs az ellenfél terítését és az AI-ra váró undo-döntést alapértelmezetten elutasítja. Külön claim/undo AI-végpont jelenleg nincs.

## 14. Ajánlott gateway-feldolgozás

```text
1. HTTP-metódus és Content-Type ellenőrzése
2. X-MohaBridzs-Protocol === "1.0"
3. Bearer hitelesítés
4. JSON parse és sémaellenőrzés
5. Idempotency-Key === request_id
6. Azonos request_id cache/single-flight ellenőrzése
7. Pipeline és RAG-profil kiválasztása profile_code alapján
8. Modell/RAG/állapotgép futtatása belső határidővel
9. Modellválasz normalizálása egyetlen kódra
10. Tagsági ellenőrzés a legal_actions tömbben
11. Sikeres vagy gateway-fallback JSON elküldése
12. Rövid idejű idempotencia-cache frissítése
```

## 15. Minimális kompatibilitási ellenőrzőlista

- [ ] Mindkét POST végpont létezik.
- [ ] JSON UTF-8 request és response támogatott.
- [ ] `X-MohaBridzs-Protocol: 1.0` ellenőrzött.
- [ ] Bearer secret helyesen ellenőrzött.
- [ ] `Idempotency-Key` és `request_id` egyezése ellenőrzött.
- [ ] Azonos kérés nem indít párhuzamos modellhívásokat.
- [ ] A válasz `request_id` értéke változatlan.
- [ ] A válasz Action típusa egyezik a végponttal.
- [ ] A választott Action szerepel a `legal_actions` listában.
- [ ] A gateway a MohaBridzs határideje előtt válaszol.
- [ ] Nincs redirect és nincs streaming response.
- [ ] A válasz 64 KiB alatt marad.
- [ ] Belső modellhiba esetén szabályos, jelölt gateway-fallback készül.
- [ ] A napló nem tartalmaz shared secretet vagy teljes, rejtett információt hordozó request bodyt.

## 16. Konfiguráció a MohaBridzs oldalán

```dotenv
AI_SHARED_SECRET=64_KARAKTERES_ASCII_HEX_TITOK
AI_BID_TIMEOUT_MS=60000
AI_PLAY_TIMEOUT_MS=60000
```

A Compose-konténernek mindhárom változót meg kell kapnia. Az AI klubprofil `email` mezőjében a gateway alapcíme szerepeljen.

## 17. Kompatibilitási megjegyzés

A gateway implementációja függhet további belső mezőktől, de a nyilvános v1 szerződéshez új kötelező request- vagy response-mezőt nem szabad egyoldalúan hozzáadnia. Ismeretlen opcionális mezőket érdemes tolerálni. Törő változtatáshoz új protokollverzió és új `X-MohaBridzs-Protocol` érték szükséges.
