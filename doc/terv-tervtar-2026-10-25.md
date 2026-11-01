# A felvevő tervtára — tervezet (2026-10-25, játék-szál, a szerkesztővel egyeztetve)

## Cél

A kibic a lejátszás elején (és új információnál) **tervet választ**: a
lehetséges tervek közül azt, amelyik a licit, az indulás és a lejátszott lapok
szerint lehetséges elosztásokon a legtöbbet hozza. A tervek **adatok**
(`rendszerek/tervek/*.yaml` → adatbázis → szerkesztő), a fogalmak a kibic
**függvényei** (`motor/terv.py`). A nyelv nem programozási nyelv: a sorok
paraméterekkel hívják a fogalmakat (mint az elv-sablonoknál).

## A tervtípusok rendszere (a szakirodalom alapján)

Források: Wikipedia — *List of play techniques (bridge)*, *Squeeze play
(bridge)*, *Coup (bridge)*; bridge-tips.co.il — *Declarer Techniques* (a
„Recognize Patterns of Hands” fejezet: erő-, hossz-, aduütések és
technikai ütések); C. Love: *Bridge Squeezes Complete* (a B-L-U-E feltételek);
Pavlicek gyakorló partijainak „Play:” címkéi. A források két tengelyt
különböztetnek meg; a tervtár is kettős, és fölötte két külön réteg áll (a
pontozás és a tartalék stratégia).

### 1. tengely — honnan jön a hiányzó ütés (ÜTÉSFORRÁS; ezek a tervtípusok)

| Típus | Változatok (soronként egy) | Pavlicek-címke (508 partiból) |
|---|---|---|
| **ERŐ** — felső lapok | (nincs terv: lehívás) | — |
| **KIMAGASÍTÁS** — hosszból / figurából | elosztásra (kiadással, kiengedéssel), impassz, dupla impassz, mély impassz, eső figura (drop), expassz (szöktetés: hívás a figura felé), felmutató impassz (show-up), lopásos impassz (ruffing finesse), kétségbeesett impassz (desperation), lopásos kimagasítás (ruff out); több színben: az esélyek kombinálása | 144 |
| **LOPÁS** — aduval szerzett plusz ütés | lopás a rövid kézben, asztalfordítás (dummy reversal), keresztlopás, átvitt lopás (transfer ruff) | 44 |
| **VESZTŐCSERE** — vesztő eltüntetése | vesztődobás nyerőre (korai dobás), vesztő a vesztőre (loser on loser), az aduk megszöktetése (elopement) | 27 |
| **VÉGJÁTÉK** — a védő ad ütést | elimináció + bedobás (kényszerhívás), lopás-dobás (ruff and sluff), aduvégjáték (trump endplay), egyszínű bedobás, adupuccs (trump coup) | 67 |
| **BESZORÍTÁS** | egyszerű (pozíciós / automatikus), kettős, bedobásos (squeeze throw-in), lopásos (ruffout), átmenetváltó, lépcsős (stepping-stone), backwash … (Love szerinti feltételek: B-L-U-E — blokkolás nincs, a vesztők száma helyes, felső fenyegetés, átmenet) | 108 |

Egy partiban több forrás is lehet (48 partinál két típus a címkében), ezért a
kibic típusok **kombinációját** is értékeli.

### 2. tengely — KÍSÉRŐ SZEMPONTOK (minden tervhez; nem ütésforrás)

Kettős szerepük van: a **döntéshez feltétel** (mit? miért?), a
**végrehajtáshoz lépés / módszer** (hogyan? mikor?).

| Szempont | Elemek | Címke |
|---|---|---|
| **Veszélyes védő** | kihagyás (holdup), kerülő impassz / kiengedés (avoidance), a védők kapcsolatának elvágása (break communication; Merrimac-, ollócsel) | 64 |
| **Átmenetek** | átmenet teremtése / megőrzése, deblokkolás, átvétel (overtaking), lapdobás az útból (jettison), bécsi csel | 73 |
| **Adukontroll, időzítés** | a kiaduzás ideje (korán / később), a felülopás elkerülése, adukontroll megtartása, a színkontroll megtartása, a gyenge szín hívása előbb, a sorrend | 42 + 5 |
| **Lapolvasás** | számolás (a leosztás alakja), lapelhelyezés a licitből és az indulásból, korlátozott választás, az üres helyek elve | 46 |
| **Az első ütés** | hol üssünk, kihagyjunk-e, mit tegyünk hozzá | 17 |
| **Esélyek és kockázat** | az esélyek kombinálása, biztonsági játék, a legjobb / az egyetlen esély, a rossz elosztás túlélése, ütésszám-igazítás (rectify the count) | ~25 |

A kísérő szempontok a változatok **feltételei és lépései** közé kerülnek (pl.
a KIMAGASÍTÁS / ELOSZTÁSRA változat egy kiengedéses alváltozata: „a veszélyes
védő ne jusson ütéshez”), nem külön tervek.

### A pontozás — az értékelés mércéje (nem terv; „additív”)

Nem tervtípus, hanem az, amivel a kibic a terveket ÖSSZEMÉRI (IMP / MP / BAM —
a `game.scoring` szerint; a kibic ma is így pontoz).

- **IMP:** a teljesítés biztonsága az első (a felülütés legfeljebb 1 IMP, a
  bukás 10+). Kivétel lehet a csapatmérkőzés utolsó partija adott állásnál —
  ritka, nem kezeljük.
- **MP / BAM:** stratégiai döntés a biztonsági játék és a plusz ütés között; a
  mérce a „normál eredmény” (amit a terem többsége elér) megverése. (~20 parti)
- **Opcionális plusz:** a teljesítés biztosítása után terítés helyett a
  kockázatmentes plusz ütés keresése. A kibic részleges terítése ma is csak
  akkor terít, ha egyik lehetséges elosztásban sem lenne több ütés.

### Megtévesztés — tartalék stratégia (7 parti)

Akkor lép be, ha egyetlen terv sem célravezető (egyiknek sem teljesülnek a
feltételei, vagy a mintákban egyik sem teljesít): olyan játékmód, amelyben a
védőknek a legtöbb lehetőségük van hibázni (hamis lap, a terv elrejtése,
„ameddig az ellenjátékosok nem hibáznak”). Feltétele egy **védőmodell**,
amely nem tökéletes (a mostani DD-védő mindig mindent lát, ezért ellene a
megtévesztésnek nincs értéke) — ez külön, későbbi munka.

**Lefedettség:** a Pavlicek-partik 508-ából 88-nak nincs címkéje; a többi
minden címkéje a fenti tengelyek vagy rétegek valamelyikére esik (a címke-sorok
folytatásai — pl. „vs 3-3 diamonds (36%)”, „West passed S A-Q C A so” — a
szerző indoklásai, nem címkék; a „Reused deals” technikai megjegyzés).

## Szerkezet

- **Tervtípus** (absztrakt sor): a szűrő és a közös rész.
- **Szűrő** — olcsó, a látott lapokból számolt belépési feltétel; ha hamis, a
  típus egyik változatát sem értékeli a kibic. Pl. KIMAGASÍTÁS: `hiany` =
  szükséges − biztos ütés; a kimagasításhoz kiadandó ütések ≤ a kiadható ütések
  (a védők ellenünk futó ütéseivel együtt). BESZORÍTÁS: legfeljebb egy vesztő,
  legalább két fenyegetés.
- **Változat** — soronként egy (utólag bármikor bővíthető). **Hivatkozik** a
  típusra (vagy egy másik változatra), és csak az ELTÉRÉST írja le: `kivon`
  (szükségtelen feltétel), `ha` (új feltétel), `felulir` (más paraméter). Mint
  a licitrendszer hivatkozásai és a jelzésrendszer `kihagy:` sorai.

```yaml
- tipus: KIMAGASITAS                     # absztrakt sor: csak a szűrő és a közös rész
  nev: "Hiányzó ütés(ek) kimagasítása"
  szuro:
    hiany: "1-3"                         # szükséges − biztos
    kiadhato_eleg: igen                  # kiadandó ≤ kiadható
  szinenkent: igen                       # minden alkalmas színre és ezek sorrendjére

- valtozat: ELOSZTASRA_KIADASSAL
  alap: KIMAGASITAS
  ha: {szin_hossz_egyutt: "7+"}
  technika: {elosztasra: igen, modszer: KIADAS}

- valtozat: ELOSZTASRA_KIENGEDESSEL
  alap: ELOSZTASRA_KIADASSAL
  felulir: {technika: {modszer: KIENGEDES}}
  ha: {atmenet_a_hosszu_kezben: "0-1"}

- valtozat: IMPASSZ
  alap: KIMAGASITAS
  ha: {figura_hianyzik: 1}
  technika: {impassz: igen}

- valtozat: DUPLA_IMPASSZ
  alap: IMPASSZ
  felulir: {ha: {figura_hianyzik: 2}}
  technika: {impassz: 2}

- valtozat: EXPASSZ                      # szöktetés: hívás a figura felé
  alap: KIMAGASITAS
  ha: {figura_hianyzik: 1, figura_a_hivo_elott: igen}
  technika: {expassz: igen}

- valtozat: ESO_FIGURA
  alap: KIMAGASITAS
  ha: {leutheto_figura: igen}
  kivon: [kiadhato_eleg]                 # nem ad ki ütést
```

## A kibic menete

1. A típusok szűrője (egyszer, a látott lapokból; a közös számokat — biztos
   ütés, hiány, kiadható, veszélyes védő, átmenetek — a változatok közösen
   használják).
2. Az alkalmas típusok változatai (és több színnél / több típusnál ezek
   sorrendje: az esélyek kombinálása) a lehetséges elosztásokon: teljesülnek-e
   az igényei, hány ütést hoz. A fogalom értéke tervfüggő (pl. a lopással
   szerezhető ütés más, ha előtte két kör adut hívunk).
3. Összehasonlítás a pontozás szerint (IMP / MP várható érték) → választás. A
   terv megmarad a partira; új információnál újraértékelés, váltás csak
   jelentős előnyért. Ha egyik sem célravezető: a tartalék stratégia.
4. A lapot a terv célja mellett a mostani elemzés keresi (a terv megmondja,
   MIT akarunk; az időzítést, átmeneteket kezdetben a DD). A terv neve és
   szövege megy a magyarázatba és a terítésbe.

## Mérés

- Felismerés: egyezik-e a választott típus / változat a Pavlicek-címkével
  (508 parti, „Play:” sor; 88 partinak nincs címkéje).
- Hatás: teljes lejátszás (`jatekmeres --teljes`). Kiinduló állapot (PR #29
  után): 374/508 teljesült (tökéletes felvevővel 489), 1431 IMP. Az
  „ugyanaz a lap” előrelátással (αμ, 120 világ): 362/508, 1578 IMP —
  rosszabb, kikapcsolva marad.

## Első szelet

KIMAGASÍTÁS (a változataival) — a legtöbb parti ilyen; utána a nagy
veszteségű családok: a veszélyes védő (kihagyás, kerülő játék), VÉGJÁTÉK.

## Elnevezések

A magyar nevek a kibic javaslatai, zárójelben az angol; a szerkesztő jelzi, ha
egy név szokatlan.

- **színhiány / sikén** (void) — NEM „renonsz”: a renonsz a szabálytalan
  színadás (revoke). (A kód belső nevei — pl. `renonszok()` — még a régi
  szót használják; a kifelé menő szövegekben színhiány.)
- **expassz / szöktetés** — hívás a figura felé (az impassz ellentéte).

## Mérés: a „lehetséges” szint (2026-10-25 este, PR #31)

A **LEHETSÉGES** jelzés azt jelenti, hogy a típus feltételei igazak, vagyis a
típus alkalmazható. A jelzés akkor is megjelenik, ha az így szerezhető ütés
egymagában nem elég. A kombinációk ebből a halmazból épülnek.

A sorok külön készültek szanra és színre. A beszorításnak fajtánként van sora:
egyszerű, kettős, bedobásos, bécsi csel, lopásos.

Új fogalmak:

- hosszfenyegetés;
- a fenyegetések kezei;
- osztott fenyegetés / bécsi csel;
- lopással kimagasítható szín;
- kitett figura;
- villás színek;
- `hiany_terv`, a hiány a könnyű források (felső, hossz, lopás) után.

| | lefedés (első mérés) | lefedés most |
|---|---|---|
| végjáték | 37% | 90% |
| beszorítás | 14% | 73% |
| veszélyes védő | 23% | 69% |
| összesen | 44% | 73% |

**Tanulság.** A beszorítás-fajták pontossága a kézből számolt fogalmakkal
nem jobb a véletlennél: kb. 25%, ennyi a beszorítás-címkés partik aránya.
A kettős beszorítás 12 partijából 1-et talál meg. Hogy van-e beszorítás, és
milyen fajta, az a védők lapjain múlik: ki őriz mit, és jó-e az ütésszám a
terv után. Ezt a két kéz egyedül nem dönti el.

A következő lépés ezért a dinamikus felismerés. A sorsolt világok DD
lejátszásában figyelni kell, mikor kényszerül egy védő őrzőlapot dobni. A
végállásból adódik a fajta. Ez egyúttal a címke nélküli partik automatikus
címkézése is.
