# A kibic mintanyelve — 0.4

Ez a nyelv írja le, MELYIK licithelyzetre vonatkozik egy szabály. A
`licitmenet.minta` oszlopban él, és a `motor/minta.py` értelmezi.

A 0.4 két új eszközt hoz, mindkettőt a **fésű** kényszerítette ki:
az *indexelt színváltozókat* (`I1/I2/V1/V2`) és a `+` *szintjelölést*.
A fejezet végén leírom, miért nem volt elég nélkülük a nyelv.

---

## 1. A két alak

**Pároslicit** — kötőjellel. Azt jelenti, hogy az ellenfelek végig
passzoltak; csak a mi licitjeinket írjuk le.

```
1NT-2C          Stayman
1M-2M           egyszerű nemes emelés
1D-1H-1S        fordított licit
```

**Kompetitív** — szóközzel, az ellenfél licitje zárójelben.

```
1D (2C) 2H      közbeszólás után új szín
1S (X) 2S       információs kontra után emelés
.. (*) X        bármilyen előzmény, az ellenfél licitje, majd kontra
```

A kettő nem keverhető egy mintában. Az illesztés előtt a valódi
licitmenetet **kanonizáljuk** ugyanebbe a jelölésbe, a licitáló vonalának
szemszögéből — onnantól az illesztés token-token összevetés, azonos
ábécén.

---

## 2. Tokenek

| Token | Jelentés |
|---|---|
| `P`, `X`, `XX` | passz, kontra, rekontra |
| `1C` … `7NT` | konkrét licit (`N` = `NT` elfogadott rövidítés) |
| `(2H)` | az ellenfél licitje |
| `(*)` | az ellenfél **bármilyen** licitje |
| `(?)` | az ellenfél bármilyen **szín**-licitje (nem passz/kontra) |
| `..` | tetszőleges számú akció kihagyása |

### Színváltozók

| Változó | Amit jelölhet | Kötés |
|---|---|---|
| `M` | nemes (H/S) | a minta köti meg, illesztéskor |
| `m` | minor (C/D) | ugyanaz |
| `A`, `B`, `E` | bármelyik szín | ugyanaz |
| `oM` | a *másik* nemes | `M`-ből származik |
| `om` | a másik minor | `m`-ből |
| `Q` | a negyedik szín (amit még senki nem mondott) | a menetből |
| `I1`, `I2`, … | az **ellenfél ígért színei**, rangsorban | a **kényszertárból** |
| `V1`, `V2`, … | a **szabad színek**, rangsorban | ugyanonnan |

Az **ismételt változó ugyanazt a színt jelenti**: az `1M-2M` mintában a
két `M` szükségképpen egy szín.

### Szintjelölések

| Jelölés | Jelentés |
|---|---|
| `1`–`7` | konkrét szint |
| `n` | bármilyen szint (illesztésnél megengedő; feloldásnál nem elég) |
| `+` | **a legkisebb szabad licit ebben a színben** |

---

## 3. Mit hozott a 0.4, és miért

A fésű kódolásakor derült ki, hogy a nyelv nem tud két dolgot kimondani.

### 3.1 Indexelt színváltozók — `I1/I2` és `V1/V2`

A fésű megállapodása így szól: *az ellenfél ismert színeinek
felüllicitjei a mi szabad színeinket kódolják rangsorrendben.*

```
1S – (2NT = minorok) – ?
    ismert színeik, rangsorban:   I1 = ♣   I2 = ♦
    a mi szabad színeink:         V1 = ♥   V2 = ♠
    a megállapodás:               3♣ → ♥        3♦ → ♠
                                  (I1 → V1)     (I2 → V2)
```

Két rendezett listát fésülünk össze — innen a konvenció neve. A nyelvnek
eddig nem volt erre szava, ezért a fésűt csak úgy lehetett volna leírni,
hogy minden kétszínű konvencióra (Michaels, Ghestem, Szokatlan 2NT) és
minden nyitószínre külön sort írunk: több tucat sor **ugyanarról az egy
gondolatról**. Indexelt változókkal hat sor elég.

Fontos különbség a többi változóhoz képest: **az `I`/`V` kötését nem a
minta adja, hanem a kényszertár.** Az `1S (2NT)` menetből a nyelv
magától nem látja, hogy a 2NT minorokat ígér — ezt a `2NT` szabályának
`jelentes` mezője propagálta be az ellenfél ígéretébe. A kötés ebből áll
elő (`helyzet.Allas.fesu_kotesek`), az illesztés *előtt*.

Ennek két jó következménye van:

* **Rendszerfüggetlen.** Ugyanaz a hat sor működik Michaels, Ghestem és
  Szokatlan 2NT ellen is, mert nem a konvenció *nevére* hivatkozik,
  hanem arra, amit az mutat.
* **Csendben nem téved.** Ha az ellenfél licitje nem mutat konkrét
  színeket — vagy ha az ismert és a szabad színek száma nem egyezik,
  tehát a párosítás nem egyértelmű —, a kötés elmarad, és a szabály
  egyszerűen **nem illeszkedik**. Nem fésűzünk ott, ahol nincs mit
  összefésülni.

### 3.2 A `+` szint — „menj fel a színére"

A fésű cue-bidje nem konkrét licit. Hogy `3♣` vagy `4♣`, az a
licitállástól függ, nem a megállapodástól:

```
1S (2NT) 3C       a 2NT után a legkisebb treff a 3C
1S (3NT) 4C       ugyanaz a szabály, magasabb állásból
```

A `+I1` token ezt mondja ki: *a legkisebb szabad licit az `I1` színben.*
A feloldás a `helyzet.Allas.kovetkezo_licit()`-tel történik, tehát a
szabály a szintről **nem tud és nem is kell tudnia** semmit.

---

## 4. Ütközésfeloldás

Ha több minta illeszkedik, a `licitmenet.dontesi_mod` dönt:

* `SORREND` — a legmagasabb prioritású nyer (ez reprodukálja a LICREN
  viselkedését, és ez a viszonyítási alap);
* `SPECIFIKUSSAG` — a legspecifikusabb minta nyer;
* `MERLEGELO` — a jelölthalmaz **döntés nélkül** megy tovább; a C mód
  további megfontolásokkal dönt.

A specifikusság számítása tokenenként: konkrét szín 4, változó vagy
származtatott 2, helyettesítő 0; a konkrét szint +2, a `+` +1, az `n` 0.

---

## 5. Ami a mintán kívül van

A minta csak azt mondja meg, **melyik helyzetre** vonatkozik a szabály.
Három másik oszlop mondja meg a többit:

| Oszlop | Kérdés | Motor |
|---|---|---|
| `feltetel` | **milyen lappal?** | `motor/kifejezes.py` |
| `ha_feltetel` | **milyen helyzetben?** | `motor/helyzet.py` |
| `jelentes` | **mit ígér vele?** | `motor/propagal.py` |

Mindhárom ugyanolyan JSON-kifejezésfa, háromértékű (igaz / hamis /
**ismeretlen**) kiértékeléssel. A `@V1` alakú hivatkozás mindháromban
ugyanazt a színt jelenti: a mintaillesztés kötéseit.

A `ha_feltetel` csomóponttípusai (a 014_kompetitiv.sql fejlécében
teljes listával): `ULES`, `SZKOR`, `SZABAD`, `SZINT`, `GEM_ALATT`,
`MONDVA`, `NYILATKOZOTT`, `FIT`, `IGERT`, `KONTRA_ALLAS`.

A `jelentes`-ben a `"vagy"` kulcs **alternatívákat** jelöl. A fésű
cue-bidje „gyenge **vagy** gémforsz" — ilyenkor a kényszertárba a
változatok **uniója** kerül, nem a metszete. Ez az episztemikusan helyes
irány: ha a licit jelenthet A-t vagy B-t, a kényszernek mindkettőt
engednie kell.

---

## 6. Ismert korlát

A kényszertár intervallumokból áll, ezért **lyukas sávot nem tud
ábrázolni**. A „gyenge vagy gémforsz" 0–8 és 13+ sávjából 0–40 lesz.

Ez a fésűnél nem véletlen és nem is baj: a köztes (invit) sávnak megvan
a saját licitje — a szín természetes megmondása —, tehát a lyukat a
szomszédos szabály tölti ki. De más konvencióknál (Multi 2♦) ez valódi
veszteség. A `Propagalo` ezért **megszámolja**, hányszor fordul elő, hogy
tudjuk, mennyit veszítünk vele; a javítás (több diszjunkt ág ígéretenként)
a következő kör feladata.
