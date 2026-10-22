# kibic — menetrend

**Dátum:** 2026-09-17 · Az 1. fázis zárása és a 2. fázis előkészítése

---

## Hol tartunk

**A 0. fázis kész és validált.** Szimbolikus mag, importálók, visszajátszó,
DDS-kötés, 3389 leosztás, 3502 parti, 121+ teszt.

**Az 1. fázis nagyrészt kész.** Tudásbázis-séma, kifejezésfa, mintaillesztő,
feloldó, licitmotor, mérőeszköz. Három rendszer betöltve (`LICREN_STAND`
750 sor, `LICREN_STUND` 4 sor örökléssel, `LICREN_SZILPRE` 1186 sor),
plusz az `mbsz.lr` nyitásai.

**Mérési eredmények (nyitások, 6395 helyzet):**

| rendszer | egyezés | megjegyzés |
|---|---|---|
| MBSZ (erős szan) | **83,0%** | passz 91,9%, nyitás 75,4% |
| `stand.lr` (gyenge szan) | 64,7% | a gyűjtemény erős szant játszik |

**Eldöntött kérdés:** a LICREN `P` jelzője = **figurapont + hosszúsági
pont** (`P_HOSSZ`). Két független rendszeren is ez nyert.

---

## A fő akadály: a körte-alma probléma

A gyűjtemény játékosai **nem azt a rendszert játsszák**, amit mérünk.
Az MBSZ 83%-a és a `stand.lr` 64,7%-a közti különbség nagyrészt nem a
rendszerek minőségéből jött, hanem abból, melyikük illett jobban.

Amíg ez így van, a mérés **nem tudja megmondani, jó-e a kibic** — csak
azt, hogy melyik rendszerleírás hasonlít a mezőnyre.

---

## Menetrend

### 1. lépés — Rendszerfelismerés *(fél nap, futtatás: Te)*

A `rendszerfelismeres.py` script az alertek alapján megmondja:
hány parti van **gépi magyarázattal** (BBO-robot), és páronként milyen
**szan-tartományt** és milyen **1♣-ot** mutatnak.

```bash
source .env
python rendszerfelismeres.py
```

**Amit eldönt:** van-e elég robotparti tiszta mérőanyagnak, és
szétválaszthatók-e a párok családra (natúr-erős szan / natúr-gyenge szan
/ erős treff).

### 2. lépés — Szűrt mérés *(fél nap, kód: én)*

A mérőeszköz kiegészítése pár-szűréssel: az MBSZ-t csak a natúr-erős
szanos párokon mérjük, a `szilpre`-t az erős treffeseken.

**Amit eldönt:** működik-e egyáltalán a mérés. Ha a szűrt számok
érdemben jobbak a kevertnél, akkor minden további munka mérhető.

### 3. lépés — Teljes licitmenet-mérés *(1 nap, kód: én)*

Nem csak a nyitások: minden licit, kétféleképp. **Pozíciónkénti**
(minden döntés önálló, a menet a valódi licitekkel megy tovább) és
**szimulációs** (a motor végiglicitál, a végén a kontraktust
hasonlítjuk — és a DDS-táblából a **par-hoz mért IMP-veszteséget** is).

**Amit ad:** a kibic első teljes licitminősítése, és a bizonytalan
helyzetek térképe (ahol egynél több szabály illeszkedik).

### 4. lépés — Rendszerbővítés *(néhány nap, forrás: Te, fordítás: én)*

Az MBSZ-nek jelenleg **csak a nyitásai** vannak meg. A válaszok és
folytatások hiányoznak — enélkül a teljes licitmenet-mérés csak a
`stand.lr`-en és a `szilpre.lr`-en értelmes.

**Amivel a legtöbbet segítesz:** eldönteni, melyik rendszert fordítsuk
teljesen. A jelöltek a projektmappában: MBSZ egyéni (rövid, kanonikus),
Standard American (26 oldal, definíciókkal), Sylstandard, DP, Heavy Club.

### 5. lépés — Az 1. fázis zárása *(fél nap)*

Roadmap-frissítés a mért számokkal, állapotjelentés, és a 2. fázis
(LLM-ág) előkészítése: a bizonytalan helyzetek listája lesz a
kiindulópont.

---

## Amivel a legtöbbet segítesz

**1. Futtasd a rendszerfelismerést** — ez dönti el, van-e tiszta mérőanyag.

**2. Döntsd el, melyik rendszert fordítsuk teljesen.** A fordítás gyors
(az MBSZ nyitásai fél óra alatt megvoltak), de a **szakmai ellenőrzés
csak Te tudod elvégezni**. Ebben a beszélgetésben többször tévedtem
bridzs-alapkérdésekben — a fordítás javaslat, a jóváhagyás a Tiéd.

**3. Ha van rá mód, szerezz olyan partikat, ahol ismered a rendszert.**
Akár a saját partijaid: ha tudjuk, hogy Heavy Clubot játszottál, az a
legtisztább mérőanyag. Nem kell sok — pár száz parti egyetlen ismert
rendszerrel többet ér, mint 3500 ismeretlen.

---

## Felírt, de nem sürgős teendők

* **A `.env` betöltése a CLI-kbe** — most `source .env` kell minden
  parancs előtt; egy közös `env_betolt()` megszüntetné.
* **A DDS többszálúsítása** — a 63 leosztás/mp egyszálú szám; az
  `endplay`-ben nincs `set_max_threads`, de `multiprocessing`-gel a
  kötegek függetlenül futtathatók.
* **A `stand.lr` küszöbeinek paraméterezése** — a `P>11` beégetett
  szám; ha paraméterhivatkozás lenne, a `NYITAS_MIN` söpörhető volna
  10-től 14-ig.
* **Relé/lépcső tokenek a mintanyelvbe** (`R`, `L1..L9`) — a Heavy Club
  kódolásához kell, de az a lista végén van.
