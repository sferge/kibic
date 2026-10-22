# A kibic mint MohaBridzs AI-játékos

Igen, rá lehet ültetni. A MohaBridzs `mohabridzs-ai/1.0` szerződése két
végpontot kér (`/v1/bridge/bid`, `/v1/bridge/play`), és a kibic ezeket
mostantól kiszolgálja — **ugyanazon a folyamaton belül**, ugyanabból a
motorból, mint a `/v1/kibic/licit`.

```
MohaBridzs webapp
   │  POST /v1/bridge/bid      (mohabridzs-ai/1.0, deadline_ms, pontosan 1 Action)
   ▼
kibic/szolgaltatas/api.py   ── titok, idempotencia, HTTP
   ▼
kibic/szolgaltatas/atjaro.py ── FORDÍTÓ: kérés → belső alak, döntés → Action
   ▼
kibic/szolgaltatas/licit.py ── a licitmotor (ugyanaz, mint /v1/kibic/licit)
```

Az `atjaro.py` szándékosan nem tud bridzsezni. Fordító: a szerződés
kötelező pontjait teljesíti, a bridzs a `licit.py`-ban marad.

## EGY app, EGY port, EGY folyamat

**Nem kell két példány, és nem is szabad.** A `kibic.szolgaltatas.api:app`
egyetlen FastAPI alkalmazás, amelyben mind a négy végpont benne van:

```
uvicorn kibic.szolgaltatas.api:app --host 0.0.0.0 --port 9050
   ├─ POST /v1/kibic/dd        a DD-elemzés — VÁLTOZATLAN, ahogy eddig
   ├─ POST /v1/kibic/licit     a magyarázó elemzés (műhely)
   ├─ POST /v1/kibic/ujratolt  gyorsítótár ürítése
   ├─ GET  /v1/kibic/allapot   életjel
   ├─ POST /v1/bridge/bid      ← ide hív a MohaBridzs AI-gateway
   ├─ POST /v1/bridge/play     ← és ide
   ├─ GET  /healthz  /readyz
   └─ GET  /docs               kattintható próbafelület
```

A **port marad 9050**, ahogy eddig. A DD-elemzés beállítása a
MohaBridzsben nem változik. Ami új: az AI-profilba is ugyanez az alapcím
kerül (`http://<gép>:9050`), és a gateway maga teszi hozzá a
`/v1/bridge/bid` részt.

Ellenőrzés egy paranccsal, hogy tényleg mind ott van:

```bash
curl -sS http://localhost:9050/openapi.json | python -m json.tool | grep '"/v1'
```

(Ha valamiért mégis külön folyamatban akarnád futtatni a kettőt, az is
megy — ugyanaz az app indítható két porton, `--port 9050` és `--port 9051`
—, de semmi nem indokolja: ugyanaz a kód, ugyanaz a memóriában tartott
rendszer-gyorsítótár. Két példány csak kétszer töltené be ugyanazt.)

---

## A két szerződés nem ugyanaz

|  | `/v1/kibic/licit` | `/v1/bridge/bid` |
|---|---|---|
| a fő tartalom | a **magyarázat** | pontosan egy **Action** |
| `call` lehet `null`? | igen, ez a mérés | **nem**, kötelező és legális |
| idő | ráér | `deadline_ms` a mérvadó |
| méret | tetszőleges | ≤ 64 KiB |
| szan jelölése | `1NT` | `1N` |
| kinek szól | nekünk, fejlesztés közben | a MohaBridzsnek, élesben |

Ezért kell a fordító, és ezért **marad meg mindkettő**. A
`/v1/kibic/licit` a műhely: ott látod a kényszertárat, a jelölteket, a
lefedettséget. A `/v1/bridge/bid` az éles asztal.

---

## A legfontosabb döntés: mi legyen, ha a kibic néma?

A kibic ma a kompetitív ágakon gyakran nem tud licitálni (`call: null`).
A gateway viszont nem fogad el nemleges választ: ha nem jön szabályos
akció, a MohaBridzs a **saját** tartalékát játssza meg, és a mi
hallgatásunkból nem marad nyom.

Az adapter ezért tartalékol, de **bevallja**:

```json
"meta": {
  "source": "fallback",
  "pipeline": "kibic_bid",
  "fallback_reason": "a kibicnek nincs szabálya erre a helyzetre",
  "kibic": {"branch": "KUZDELMI", "rule_source": "NINCS",
            "understood": 1, "unknown": 1, "unknown_calls": ["E:2NT"]}
}
```

Ennek következménye, hogy **a MohaBridzs admin AI-naplója magától
lefedettséget mér**: ahány döntés `fallback`-ként jelenik meg, annyiszor
volt néma a tudásbázis — élesben, valódi leosztásokon. Pontosan az a
szám, amit az `aglefedettseg` CLI-vel statikusan mérnénk, csak most a
gyakorlat adja, és melléteszi, hogy **melyik licitet nem értette**.

A tartaléklétra:

1. a kibic javaslata, ha szerepel a `legal_actions.calls`-ban;
2. `P`, ha szabályos;
3. a felsorolás első eleme.

Akciót sosem talál ki.

---

## A lejátszás

A `/v1/bridge/play` **kötelező**, hogy létezzen, különben a szolgáltatás
nem kompatibilis. A kibic lejátszó modulja viszont még nincs kész, ezért
ma két dolgot tud: kényszerű lapot ad (ha egy szabályos lap van), egyébként
a legkisebb lapot — és `meta.source: "fallback"`-kal jelöli. **Nem teszünk
úgy, mintha játszanánk.** Amikor a lejátszó elkészül, csak ez az egy
függvény cserélődik.

---

## Beállítás

Környezeti változók (a meglévők mellé):

| változó | mit csinál | alap |
|---|---|---|
| `KIBIC_SHARED_SECRET` | titok a `/v1/kibic/...` végpontokra | nincs |
| `KIBIC_AI_SHARED_SECRET` | titok a `/v1/bridge/...` végpontokra (= a MohaBridzs `AI_SHARED_SECRET`-je) | a fenti |
| `KIBIC_RENDSZER` | melyik rendszer szerint licitáljon | `LICREN_STAND` |
| `KIBIC_PAR` | paraméter-felülírások forrása | nincs |
| `KIBIC_PROFILOK` | profilkód → rendszer leképzés | nincs |
| `KIBIC_ATJARO_NAPLO` | JSONL napló a teljes elemzésről | nincs |
| `KIBIC_ATJARO_SZIMULACIO` | `1`, ha a mérlegelés engedélyezett | ki |
| `KIBIC_ATJARO_SZIM_MS` | ennyi `deadline_ms` fölött szimulál | 6000 |

A `KIBIC_PROFILOK` alakja `profilkod=RENDSZER:pár;masik=RENDSZER2`, például:

```
KIBIC_PROFILOK="kibic_stand=LICREN_STAND;kibic_gal=LICREN_STAND:gal - korszurku"
```

Így **ugyanaz a folyamat** kiszolgálhat két AI-profilt, más-más
licitrendszerrel — és egymás ellen is leültetheted őket.

### Indítás

**Vigyázat a titokkal.** A két végpontcsaládnak külön titka van, mert nem
egyszerre állnak be. A DD-hívások ma valószínűleg titok nélkül mennek: ha
csak a `KIBIC_SHARED_SECRET`-et állítanád be a gateway kedvéért, azzal a
**működő DD-integráció kezdene 401-et kapni**. Ezért a gateway titkát a
`KIBIC_AI_SHARED_SECRET`-be tedd — az csak a `/v1/bridge/...` végpontokra
vonatkozik, a DD marad, ahogy volt.

```bash
export KIBIC_AI_SHARED_SECRET="…"       # = a MohaBridzs AI_SHARED_SECRET-je
export KIBIC_RENDSZER=LICREN_STAND
export KIBIC_ATJARO_NAPLO=/var/log/kibic-atjaro.jsonl
uvicorn kibic.szolgaltatas.api:app --host 0.0.0.0 --port 9050
```

A MohaBridzs AI-profiljába az **alapcím** kerül (`http://192.168.77.70:9050`),
nem a teljes útvonal — a `/v1/bridge/bid` és `/v1/bridge/play` részt a
MohaBridzs teszi hozzá.

---

## Tesztelés a webapp NÉLKÜL

Három út, növekvő hűséggel.

### 1. A szerződés ellenőrzőlistája — ez a leggyorsabb

A szerződés 14. pontja egy 11 tételes átadás előtti listát ad. Futtatható
alakban:

```bash
python -m kibic.cli.atjaroproba --cim http://localhost:9050 --titok "…"
```

```
[  OK  ] 1a. POST /v1/bridge/bid elérhető  — HTTP 200
[  OK  ] 2. hibás titokkal nem dönt  — HTTP 401
[  OK  ] 4b. a licit a calls tömbből való  — 2S
[  OK  ] 5b. ugyanaz a kulcs más törzzsel ütközés  — HTTP 409
[  OK  ] 9a. a válasz a deadline_ms alatt érkezett  — 8 ms / 20000 ms
[  OK  ] 10b. nincs 'NT' és nincs 'PASS' a dróton  — 2S
…
18 tétel, 0 hibás.
```

Ha ez zöld, a MohaBridzs oldaláról nem lehet baj: ami marad, az már
bridzskérdés, nem integrációs.

### 2. Egyetlen kézzel írt helyzet, teljes kéréssel-válasszal

```bash
python -m kibic.cli.atjaroproba --cim http://localhost:9050 --titok "…" \
    --kez "SK S7 S4 HA HQ H6 H3 D9 D5 D2 C8 C6 C3" \
    --menet "1S P" --ules S --oszto N --beli ns
```

Kiírja a teljes `mohabridzs-ai/1.0` kérést (ezt küldené a webapp) és a
teljes választ. A `--helyben` kapcsolóval HTTP nélkül, közvetlen
importtal is megy — akkor a szállítóréteg marad ki a képből.

### 3. Nyers curl

```bash
curl -sS http://localhost:9050/v1/bridge/bid \
  -H 'Content-Type: application/json; charset=utf-8' \
  -H 'X-MohaBridzs-Protocol: 1.0' \
  -H 'Idempotency-Key: proba:1' \
  -H "Authorization: Bearer $KIBIC_SHARED_SECRET" \
  -d @keres.json | python -m json.tool
```

A `keres.json`-t az `atjaroproba` kiírja, tehát nem kézzel kell megírni.

### És a műhely

Amikor a válasz meglepő, **ne a gateway-en debugolj**: ugyanarra a
helyzetre kérd el a teljes elemzést.

```bash
curl -sS http://localhost:9050/v1/kibic/licit -H 'Content-Type: application/json' \
  -d '{"hand":["SK","S7","S4","HA","HQ","H6","H3","D9","D5","D2","C8","C6","C3"],
       "seat":"S","dealer":"N","vulnerability":"ns",
       "auction":["1S","P"],"system":"LICREN_STAND"}' | python -m json.tool
```

Vagy a FastAPI saját felületén, böngészőből: `http://localhost:9050/docs`
— ott kattintgatva is kipróbálható mindkét végpont.

Vagy CLI-ből, adatbázissal együtt: `python -m kibic.cli.elemzo --veletlen`.

---

## Napló

Ha a `KIBIC_ATJARO_NAPLO` be van állítva, minden döntés egy JSONL sort ír:
a `request_id`, a munkamenetkulcs
(`bridge:{match_id}:{table_index}:{board_number}:{seat}`), az akció, a
meta, és **a teljes elemzés** — kényszertár, licitenkénti megértés,
lefedettség.

A kéz és a `visible_hands` szándékosan **nem** kerül bele: a szerződés 12.
pontja tiltja. A kényszertár viszont igen, mert az nem titok — abból
derül ki, mit gondolt a gép a többi kézről.

Ebből a naplóból lesz a következő konvenció, amit érdemes beírni a
tudásbázisba: minden `"source": "fallback"` sor egy címzett hiánylista.

---

## Ami még nincs kész

* **A lejátszás.** Ma tartalék. Ez a legnagyobb hiányzó darab.
* **A szimuláció alapból ki van kapcsolva.** A büntető kontra
  mérlegelése (`to_deliberate`) csak a `KIBIC_ATJARO_SZIMULACIO=1`
  mellett fut, és csak ha a `deadline_ms` elég nagy. A DDS 60 leosztásra
  másodperces nagyságrend; a 20 000 ms bőven elég, de érdemes mérni,
  mielőtt élesben bekapcsolod.
* **Az idempotencia-tár a memóriában él** (512 döntés). Újraindításkor
  elvész; a MohaBridzs ilyenkor újraküld, és új döntés születik. Ez
  megengedett, csak nem ideális.
