# Licitrendszerek YAML-forrásból

Ez a könyvtár a licitrendszerek és konvenciók **kanonikus** alakja. Az
adatbázis `licitmenet` sorai ebből **származnak**: bármikor újraépíthetők,
a változások gitben követhetők.

```
kibicegy_stand/       KIBICEGY_STAND  — a Kibic egyesület standardja (kibic_standard_1.0.doc)
kibicegy_kuzdelmi/    KIBICEGY_KUZDELMI — a klub küzdelmi/védekező licitjei (KÜZDELMI & VÉDEKEZŐ licitek.doc)
konvenciok/           egy fájl = egy konvenció (STAYMAN, LEBENSOHL, DRURY, ...)
kibic_stand.yaml      KIBIC_STAND — a kibic rendszere: alaprendszer + konvenciók, SORRENDBEN
```

## Fajták

| Fajta | Mi ez | Tartalma |
|---|---|---|
| `ALAPRENDSZER` | emberi forrásból, sok szabállyal (pl. KIBICEGY_STAND) | szabályok; hivatkozhat konvenciókra („Staymant játszunk”) |
| `KONVENCIO` | egy konkrét probléma megoldása | szabályok + `tema:`; másra nem hivatkozik |
| `RENDSZER` | amit egy pár játszik (pl. KIBIC_STAND) | CSAK hivatkozások és kizárások (+ `kartya:`, paraméterek) |
| `GYUJTEMENY` | konvenciók csomagja, a kényelem kedvéért | CSAK hivatkozások és kizárások |
| `ELV_SABLON` | egy ELV általánosan leírva (`elvek/`), pl. FOGASMUTATAS | `sablon: {szoveg, parameterek, terulet}` + általános mintájú szabályok `{sablon: KOD}` helyőrzőkkel; másra nem hivatkozik |

**Elv-sablon példányosítása** (2026-10-05): a rendszer hivatkozása mondja
meg, HOL él és MILYEN paraméterekkel:

```yaml
hivatkozasok:
  - {kod: FOGASMUTATAS, ervenyes: ["1M-2m-2M"], parameterek: {FIT_SZINEK: barmely}}
```

Az `ervenyes` minták UTÁN él (a vonal licitmenete ezekkel kezdődik); a
területén a kártyán mögötte álló sorok nem élnek (`kivalt: false`: mégis).

A régi nevek (`LICITRENDSZER`, `KONVENCIOKARTYA`) is elfogadottak.

**Téma.** Az azonos `tema`-jú konvenciók egymás alternatívái (pl. DONT és
Multi-Landy: „közbeszólás az 1NT ellen”). Ha egy rendszer fájában kettő is
van, a közelebbi marad (kisebb mélység, azon belül a kártyán előbb álló); a
feloldás ezt mindig kiírja, azonos szinten figyelmeztetésként.

**Kizárás** (csak RENDSZER és GYUJTEMENY): „ezt játsszuk, ennek
kivételével”. A rendszer alatti teljes fában hat, és erősebb a beemelésnél.

```yaml
hivatkozasok:
  - {kod: MOHA_KUZDELMI, kiveve: [MULTI_LANDY]}      # konvenció vagy gyűjtemény
kizarasok:
  - {kod: KIBICEGY_STAND, fejezet: "A 2♣ indulás"}   # egy fejezet
```

Egy-egy szabályt nem lehet kizárni — lyukat hagyna, ahol a kibic nem ért
semmit. Ami nem kell, azt felül kell írni (egy saját konvencióval).

## Munkamenet

```bash
# 1. ellenőrzés import ELŐTT (adatbázis nélkül) — 0 ütközés a cél
python -m kibic.cli.rendszercheck rendszerek/yaml --rendszer KIBIC_STAND
python -m kibic.cli.rendszercheck rendszerek/yaml --rendszer KIBIC_STAND --reszletes

# 2. import (először próbafutással)
python -m kibic.cli.rendszerimport rendszerek/yaml --probafutas
python -m kibic.cli.rendszerimport rendszerek/yaml

# 3. átnézés után jóváhagyás (fejezetenként is lehet)
python -m kibic.cli.rendszerimport --jovahagy STAYMAN --ki sanyi
python -m kibic.cli.rendszerimport --jovahagy KIBICEGY_STAND --fejezet "Az 1NT indulás"

# 4. a futó szolgáltatásnak
curl -X POST http://localhost:9050/v1/kibic/ujratolt
```

Minden új sor `JAVASOLT` állapotba kerül, és a motor élesben **csak az
`ELFOGADOTT`** sorokat használja.

**Teszt mód** — jóváhagyás előtti kipróbáláshoz:

| állapot | éles mód | teszt mód |
|---|---|---|
| ELFOGADOTT | ✔ | ✔ |
| JAVASOLT, FELULVIZSGALANDO | – | ✔ |
| JEGELT | – | – |
| ELVETETT | – | – |

```bash
KIBIC_TESZT_MOD=1 uvicorn ...                    # az egész szolgáltatás
curl ... -d '{..., "test_mode": true}'           # egy /v1/kibic/licit kérés
python -m kibic.cli.elemzo --teszt ...           # a CLI-elemző
python -m kibic.cli.rendszerimport --jegel KIBICEGY_STAND --minta "1NT-4S"
python -m kibic.cli.rendszerimport --kiolvaszt KIBICEGY_STAND --minta "1NT-4S"
```

A válasz `test_mode` mezője (és az átjáró naplójában a `meta.kibic.test_mode`)
mutatja, melyik módban döntött a kibic. A JEGELT állapothoz egyszer le kell
futtatni a `schema/017_jegelt.sql`-t. Újraimportnál a jóváhagyás megmarad, ha
a sor tartalma nem változott; ha egy elfogadott sor megváltozott,
`FELULVIZSGALANDO` lesz.

## Egy szabály

```yaml
- minta: 1NT-2C            # mintanyelv: 1NT-2C, 1M-2M, "1D (2C) X", "(1S) 2NT"
  pont: 8+                 # figurapont: 15-17, 12+, 0-7, 5
  vagy:                    # alternatívák
    - {hossz: {S: 4+}}
    - {hossz: {H: 4+}}
  forsz: EGY_MENET         # NEM / EGY_MENET / GEMFORSZ / SZLEMFORSZ / KIZARO
  prioritas: 58            # ha egy kézre több licit illik, a nagyobb nyer
  alert: "Stayman: 4-es nemest kérdez"
```

Egyetlen leírásból áll elő a **feltétel** (mikor licitálható) és a
**jelentés** (mit ígér, ha a partner mondja). A teljes kulcslista az
`src/kibic/impex/rendszer_yaml.py` elején van: `hossz`, `rel` (színviszony),
`elosztas` (BAL / alakok), `szkor` (zóna), `fogas`, `lapok`, `nincs`,
`fohonor`, `figura`, `aszok`, `ha` (helyzet: ülés, zóna, forsz), `tagad`,
`elvaras`, `kulcs`, `fajta` (SZABALY/ELV/KIVETEL), `allapot`.

A `nyers:` mező a forrásdokumentum eredeti sora; a `# kieg.` megjegyzés
jelzi, ahol a pontsáv vagy a feltétel **kiegészítés** (a dokumentum nem
mondta meg) — átnézéskor ezekre érdemes figyelni.

## Módosított konvenció, változat

A legtöbb „saját” konvenció egy ismert konvenció **változata** (ismert,
névvel bíró eltérés) vagy **módosítása** (saját eltérés):

```yaml
rendszer: {kod: MOHA_LEBENSOHL, fajta: KONVENCIO, alapja: LEBENSOHL, viszony: MODOSITAS}
szabalyok:
  - {minta: "1NT (2H) X", pont: "7+", magyarazat: "értéket mutat"}   # felülírja az alapét
  - {minta: "1NT (2H) 3NT", torol: true}                             # ebben nincs ilyen
```

Az alap minden más szabálya él; a téma az alapé. Kivenni (`torol`) csak
módosításban lehet.

## Pont, asztali pont, lehetőség

* `pont: {O: "8+", A: "9+", M: "10+", S: "11+"}` — zónánként (O: csak ők
  bellben, A: senki, M: mindkét vonal, S: csak mi).
* `ap: "7-9"` — asztali pont a fit utáni emeléshez: figurapont + rövidségpont
  (4+ adunál 5-3-1, 3 adunál 3-2-1).
* `hossz: {H: "(4)5+"}` + `lehetoseg: {...}` — a zárójeles érték nem a
  rendszer, hanem **lehetőség**: az 5+ rendes szabály, a 4 lapos csak a
  `lehetoseg` feltételével (`lehetoseg: {}` = feltétel nélkül); ha nincs
  `lehetoseg` (vagy benne `merlegelo: true`), a 4 lapos jelöltet a
  mérlegelés dönti el.
* `pont: "8-10(11)"` vagy `pont: "(11)12-21"` — ugyanez a pontra: a
  zárójeles pontszám lehetőség (pl. „rossz 11”), saját lehetőség-sorral.
* `minoseg: jo | rossz | nem_jo | nem_rossz` — a lap minősége a LAPMINOSEG
  metrika szerint (jó jelek − rossz jelek; jó >= 2, rossz <= -2; lásd
  `schema/023_lapminoseg.sql`). Pl. `lehetoseg: {minoseg: rossz}`.
* `fele_a_szinben: H` — a figurapontok legalább fele ebben a színben van (a máshol álló üres dáma/bubi — legfeljebb 3 lapos színben, ász és király nélkül — színenként 0,5 ponttal leértékelve számít)
  (változóval is: `M`).
* Fedőütés, vesztőütés, mellékszín, „gém alatt”, „alulról”, az ígért sáv
  alsó/felső fele, megállapodott adu, kulcslap: lásd
  `doc/kibic-nyelv-bovites-2026-09-30.md`.

**Jegyzet:** `jegyzet:` a rendszer-, a fejezet- és a szabályszinten —
tartós magyarázat, MIÉRT ilyen; a szerkesztő mindig megmutatja.

**Bánky-szabály:** ha több jelölt egyformán jó (azonos prioritás), a
legalacsonyabb licit nyer.

## Ellentmondás

Két szabály ellentmond, ha ugyanabban a helyzetben ugyanarra a kézre
különböző licitet adnak, és a prioritás sem dönt. A `rendszercheck`
mintavétellel keresi ezeket (a helyzetenkénti kezek a korábbi licitjeinkhez
igazodnak), és kiírja az **árnyékolt** (sosem nyerő) szabályokat is.

## Kártya-sorrend

Ha két hivatkozott rendszer ugyanarra a kulcsra ad szabályt, a kártyán
**előrébb álló nyer**. Egy közvetlenül hivatkozott konvenció kikapcsolása:
`{kod: PUPPET_STAYMAN, aktiv: false}`; mélyebben lévőé: kizárás (fent).
