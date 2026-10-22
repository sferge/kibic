# A kibic tanító (műhely) felülete

Ez **nem** a MohaBridzs-szerződés része (az a `mohabridzs-ai-1.1.md`), hanem
a kibic saját eszköze a tanításhoz és a hibakereséshez. Ami itt van, az a
**licitáló kezét is** tartalmazhatja — ezért éles asztalon, ellenfélnek
soha nem szabad megmutatni.

| Mi | Hol | Mikor |
|---|---|---|
| Teszt mód | `KIBIC_TESZT_MOD=1` / `"test_mode": true` | a JAVASOLT szabályok is élnek |
| Tanító nyom a licitdöntéshez | `bridge/bid` → `meta.kibic.debug` | csak teszt módban |
| Tanító nyom a műhelyben | `kibic/licit` → `debug` | teszt módban, vagy `"debug": true` |
| Egy elhangzott licit elemzése | `POST /v1/kibic/magyaraz` | bármikor (titokkal) |
| Konvenciókártya böngészőben | `GET /v1/kibic/kartya` (az alaprendszeré) vagy `?system=KIBIC_STAND` | bármikor (nem titkos: a megállapodás) |
| Konvenciókártya fájlba | `python -m kibic.cli.kartya ...` | YAML-ból vagy az adatbázisból |

---

## 1. Teszt mód

A motor élesben csak az `ELFOGADOTT` szabálysorokat használja. Teszt módban a
`JAVASOLT` és `FELULVIZSGALANDO` sorokat is — így egy frissen importált
rendszer jóváhagyás előtt kipróbálható. A `JEGELT` és `ELVETETT` sort egyik
mód sem használja.

* **Az egész szolgáltatásra:** `KIBIC_TESZT_MOD=1` (a `.env`-ben vagy
  indításkor). Ez vonatkozik a `bridge/bid`-re is — a MohaBridzs-asztalodra.
* **Kérésenként** (`/v1/kibic/licit`, `/v1/kibic/magyaraz`):
  `"test_mode": true` vagy `false` — felülírja az alapértelmezést.
* A válasz `test_mode` mezője (a gateway naplójában `meta.kibic.test_mode`)
  mutatja, melyikben döntött.

A `/v1/kibic/allapot` válaszában a `teszt_mod` a szolgáltatás alapértelmezése.

---

## 2. A tanító nyom (`debug`)

Teszt módban a `bridge/bid` válaszában `meta.kibic.debug`, a
`/v1/kibic/licit` válaszában `debug` néven:

```json
{
  "hand": {"hcp": 12, "shape": {"S": 4, "H": 3, "D": 3, "C": 3}},
  "chosen": {
    "call": "2C", "rule": "1NT-2C", "system": "STAYMAN",
    "chapter": "Stayman",
    "source": "rendszerek/yaml/konvenciok/stayman.yaml: 1NT-2C",
    "rule_id": 647, "priority": 58,
    "condition": "((figurapont >= 8 és (pikk hossz >= 4 vagy kőr hossz >= 4)) ...)",
    "explanation": "Stayman: 4-es nemest kérdez"
  },
  "considered": [
    {"call": "2C", "rule": "1NT-2C", "system": "STAYMAN", "priority": 58,
     "layer": "SZABALY", "result": "IGAZ", "why_not": [],
     "explanation": "Stayman: 4-es nemest kérdez", "rule_id": 647,
     "source": "..."},
    {"call": "2D", "rule": "1NT-2D", "system": "JACOBY_TRANSZFER", "priority": 57,
     "layer": "SZABALY", "result": "HAMIS",
     "why_not": ["kőr hossz >= 5 (a kézben: 3)",
                 "kőr hossz >= pikk hossz (a kézben: 3 vs 4)"], "...": "..."}
  ],
  "considered_total": 14
}
```

| Mező | Jelentés |
|---|---|
| `hand` | A licitáló figurapontja és elosztása. |
| `chosen` | A győztes szabály: minta, rendszer/konvenció, fejezet, **forrásfájl**, prioritás, a teljes feltétel és a magyarázat. Innen tudod, hol javíts. |
| `considered` | Minden szabály, amelyik ebben a helyzetben **szóba jött** (a minta illett), legfeljebb 25; előbb a teljesültek, azon belül prioritás szerint. |
| `considered[].result` | `IGAZ` — teljesült (ha mégsem ez lett a licit, nagyobb prioritás verte meg); `HAMIS` — nem teljesült; `ISMERETLEN` — nem eldönthető; `HELYZET_NEM` — a helyzeti feltétel (ülés, zóna, forsz) bukott; `NEM_LEGALIS` — a licit nem volt szabályos. |
| `considered[].why_not` | Miért nem teljesült, **a kéz tényleges értékeivel**. VAGY-feltételnél ágankénti okkal. |
| `considered[].layer` | `SZABALY` vagy `ELV` (az elvek csak akkor jönnek szóba, ha konkrét szabály nem illett). |

A tanító nyom **nem kerül a naplóba** (a gateway kiveszi): a kéz adatait
tartalmazza, az 1.0.1 12. pontja szerint ez nem naplózható.

---

## 3. `POST /v1/kibic/magyaraz`

Egy **elhangzott** licit elemzése utólag: mit jelent a rendszerben, és — ha
megadod a licitáló kezét — mit licitált volna ott a kibic, és miért.
A MohaBridzs teszt-asztalán jó arra, hogy egy licitre kattintva lásd a
teljes gondolatmenetet.

Fejléc: `Authorization: Bearer <KIBIC_SHARED_SECRET>` (a `/v1/kibic/*` titka).

### Kérés

```json
{
  "system": "KIBIC_STAND",
  "dealer": "N",
  "vulnerability": "none",
  "auction": ["1N", "P", "2C", "X", "2D"],
  "call_index": 2,
  "hand": ["SK","SQ","S8","S2","HJ","H7","H3","DA","D9","D2","CQ","C6","C4"],
  "test_mode": true
}
```

| Mező | Kötelező | Jelentés |
|---|---|---|
| `system` | igen | A licitáló rendszere. |
| `dealer` | igen | Osztó. |
| `auction` | igen | A licitmenet (rövid alak `["1N","P",...]` vagy `[{seat, call}]`). |
| `call_index` | igen | A vizsgált licit sorszáma, 0-tól. |
| `hand` | nem | A licitáló keze. Nélküle csak a `meaning` jön. |
| `vulnerability` | nem | `none` / `ns` / `ew` / `both`. |
| `test_mode` | nem | Mint fent. |

### Válasz

```json
{
  "system": "KIBIC_STAND",
  "meaning": { "...": "ugyanaz, mint a bridge/explain explanation-je" },
  "would_bid": {
    "call": "2C", "source": "SZABALY",
    "explanation": "2C — Stayman: 4-es nemest kérdez",
    "alert": {"alert": true, "text": "Stayman: 4-es nemest kérdez"},
    "debug": { "...": "a 2. pont szerinti tanító nyom" },
    "constraints": { "...": "mit gondolt a kibic a négy kézről addig" },
    "auction_understanding": [ "...": "licitenként: értette-e" ]
  },
  "matches": true
}
```

`matches`: egyezik-e a kibic licitje az elhangzottal — emberi licitnél így
látszik, hol tér el a kibic tőled, kibic-licitnél pedig, hogy a mostani
szabályokkal is ugyanezt mondaná-e.

---

## 4. A MohaBridzs teszt-asztalán ajánlott megjelenítés

1. **Minden licit mellett:** az `alert` jele és szövege (ez élesben is jár).
2. **Kibic-licit, teszt módban:** a licitre kattintva a `meta.kibic.debug`
   — fent a `chosen` (mi és honnan), alatta a `considered` lista, a
   `why_not` okokkal. Érdemes színezni: IGAZ zöld, HAMIS szürke,
   HELYZET_NEM sárga.
3. **Bármely korábbi licit** (emberi is): `POST /v1/kibic/magyaraz` a
   licitáló kezével → „mit mondott volna a kibic” + `matches`.
4. **Nem értett licitek:** a `meta.kibic.unknown_calls` — ezek a rendszer
   hiányai; a tanításhoz ezek a legértékesebbek.
