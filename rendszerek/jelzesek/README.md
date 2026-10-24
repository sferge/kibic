# Jelzésrendszerek

Ez a könyvtár a kártyajelzési megállapodások **kanonikus** alakja (mint a
`rendszerek/yaml` a licitnek). Egy fájl = egy jelzésrendszer. Az adatbázis
`jelzesrendszer` / `jelzesmenet` táblái ebből **származnak**
(`schema/030_jelzesmenet.sql`, `031_jelzesmenet_szerkezet.sql`); csak a
jóváhagyás él az adatbázisban.

```
szegedi_mraz.yaml  SZEGEDI_MRAZ — ALAPRENDSZER: a Szegedi–Mráz (2008) jelzései, ahogy a leírás közli
moha_stand.yaml    MOHA_STAND   — RENDSZER: a SZEGEDI_MRAZ-ra hivatkozik, eltérésekkel
```

## Ugyanúgy, mint a licit

| Licit | Jelzés |
|---|---|
| `rendszer:` (ALAPRENDSZER, RENDSZER, KONVENCIO) | `jelzesrendszer:` (ugyanezek a fajták) |
| `hivatkozasok:` — behozza a másik összes szabályát | `hivatkozasok:` — ugyanígy |
| a hivatkozás és a kizárás SOR (`tipus = HIVATKOZAS`, BE/KI) | ugyanígy (031) |
| feloldás: szélességi bejárás, a kisebb mélység nyer, azonos mélységben az előbb hivatkozott | **ugyanaz** |
| `kihagy: true` (régen `torol`; módosított konvencióban) | `kihagy: KULCS` (régen `torol`) |
| `kizarasok: [{kod, fejezet}]` — a kizáró ALATTI fában hat | ugyanígy |
| `szabaly_fajta`: SZABALY / ELV / KIVETEL / KIHAGYAS | `fajta`: ugyanezek |
| `ag`: PAROS / KUZDELMI / VEDEKEZO / BARMELYIK | `terulet`: INDITAS / HIVAS / JELZES / MODSZER / KULONLEGES / LICIT |
| fejezetek, jegyzetek | ugyanígy |
| JAVASOLT / ELFOGADOTT / FELULVIZSGALANDO / JEGELT | ugyanígy; a szerkesztőben jóváhagyható |

**Ami eltér:** a licitnél a RENDSZER csak hivatkozásokból áll, és a pár a
módosításait egy módosított konvencióban (`alapja:`) írja; a jelzésnél a
RENDSZER-nek lehetnek saját sorai is (a MOHA_STAND így írja felül a
SZEGEDI_MRAZ néhány sorát). Kihagyni itt bármely olyan rendszerben lehet,
amelyik hivatkozik valamire. Ami csak a licitnél van: téma, elv-sablon,
feltételes (`ha:`) felülírás. A lapválasztásban a prioritás helyett a
LEGKONKRÉTABB illeszkedő sor nyer (lásd lent).

**JELZES és MODSZER.** A JELZES (rács) azt mondja meg, MIT jelzünk egy
helyzetben, milyen sorrendben (a partner indít: 1. kérés, 2. lapszám); a
MODSZER azt, HOGYAN adjuk azt a jelet (kérés: kis lap kér; preferencia:
egyenes — kicsi kéri a dobott színt; Smith: nagy lap = jó). Így egy
módszert egyszer kell kimondani, és minden rácscella, ahol az a jel szerepel,
azt használja.

A rendszer (amit egy pár játszik) a licit-YAML-jában mondja meg, melyik
jelzésrendszert játssza: `jelzesek: MOHA_STAND`.

## Sorfajták és kulcsaik

```yaml
fejezetek:
  - fejezet: "Indítás szan ellen"
    sorok:
      # SZABALY — melyik lapot hívjuk         kulcs: INDITAS/SZAN/KQ+ (vagy a `kulcs:`)
      - {felvetel: SZAN, minta: KQ+, lap: K}
      - {felvetel: SZAN, minta: [AKQ+, KQJ+, QJT+], lap: SOROZAT_TETEJE, kulcs: "INDITAS/SZAN/SOROZAT"}
      - {felvetel: SZAN, hossz: "4+", legalabb: T, lap: FELULROL(4)}
  - fejezet: "Jelzési rács"
    sorok:
      # RACS — egy cella                       kulcs: RACS/FELVEVO_HIV/SZAN/1
      - {racs: FELVEVO_HIV, felvetel: SZAN, sorrend: 1, jel: SMITH,
         mikor: "a felvevő első hívásában", kulonben: LAPSZAM}
      - {racs: DOBAS, felvetel: "*", jel: PREF}      # "*": két sor (SZIN és SZAN)
  - fejezet: "Módszerek"
    sorok:
      - {modszer: SMITH, ertek: NAGY_POZITIV}       # kulcs: MODSZER/SMITH
      # ilyen kontraktus ellen színadásnál és dobásnál nem jelzünk (kulcs: JELZES/NINCS/SZLEM)
      - {nincs_jelzes: SZLEM, szint: "6+", felvetel: "*", szoveg: "Szlem ellen nem jelzünk."}
      - {kihagy: MODSZER/LAPSZAM_ALAP}              # az örökölt sor itt nem él
      # a módszer a HÍVOTT lappal (menet közbeni hívás): esetek, mint egy technikánál
      - modszer: ATTITUD
        hivas: [{legalabb: J, lap: HARMADIK_OTODIK}, {lap: LEGNAGYOBB_NELKULOZHETO}]
      # TECHNIKA: névvel ellátott lapválasztás (kulcs: TECHNIKA/HARMADIK_OTODIK);
      # bárhol állhat a `lap:` helyén, és felülírható, mint bármely sor
      - technika: HARMADIK_OTODIK
        esetek: [{hossz: "6+", lap: FELULROL(3)}, {hossz: "5", lap: LEGKISEBB},
                 {hossz: "3-4", lap: FELULROL(3)}]
  - fejezet: "Elvek"
    sorok:
      - {elv: KERES_KORLATA, terulet: JELZES, szoveg: "…"}   # kulcs: ELV/KERES_KORLATA
      - {elv: KIRE_INDULUNK, terulet: INDITAS, merlegelo: true, kartyan: false, szoveg: "…"}
      # KIVÉTEL egy elv alól (kulcs: KIVETEL/SAJAT_HOSSZU_SZIN)
      - {kivetel: SAJAT_HOSSZU_SZIN, alol: KIRE_INDULUNK, terulet: INDITAS, szoveg: "…"}
      # lapválasztó sor is lehet kivétel: szabályként él
      - {felvetel: SZAN, minta: KQ+, hossz: "6", lap: LEGKISEBB, fajta: KIVETEL, alol: KIRE_INDULUNK}
  - fejezet: "Különleges helyzetek"
    sorok:
      - {kulonleges: SMITH, szoveg: "…"}            # kulcs: KULONLEGES/SMITH
  - fejezet: "Indítást irányító licitek"
    sorok:
      - {licit: KONTRA_3NT, szoveg: "…"}            # kulcs: LICIT/KONTRA_3NT
```

**Szabálysor mezői**

| Mező | Jelentés |
|---|---|
| `helyzet` | `INDITAS` (alap), `PARTNER_SZINE` (ha nincs rá sor, az INDITAS él), `HIVAS` (menet közbeni hívás) |
| `felvetel` | `SZIN`, `SZAN`, `*` |
| `minta` | lapállás vagy lista: `AK+` (AK és utána bármi), `KQx`, `KJT(x)`, `xxx+`, `*` |
| `hossz` | `"3+"`, `"2"`, `"4-"`, `"3-5"` |
| `legalabb` | van-e legalább ilyen magas lap (`T`: "ha van legalább tízes") |
| `hezag` | hány rang hiányzik a 2. és a 3. lap között: `"1-"` legfeljebb 1 (KD10x igen, KD9x nem), `"2+"`, `"0"` |
| `kontextus` | licitbeli tény, pl. `IGERT_HAROM` |
| `lap` | `K`, `D`, `10`, `LEGKISEBB`, `LEGNAGYOBB`, `NAGYOBB`, `FELULROL(n)`, `LEGNAGYOBB_NELKULOZHETO`, `PARATLAN_PAROS(A;B)`, `SOROZAT_TETEJE` |
| `cel` | `FIG`, `KER`, `LSZ`, `PREF`, `TIPUS`, `NINCS` |
| `kulcs` | kézzel adott kulcs (több mintás sornál hasznos) |
| `fajta` | `KIVETEL` (az `alol: ELVKOD`-dal) — alapból SZABALY |
| `terulet` | felülírja a magától adódót (lapválasztó: INDITAS vagy HIVAS, rács: JELZES …) |
| `allapot` | ha kimondod, felülírja a rendszer `alap_allapot`-ját és az adatbázis jóváhagyását |

**Menet közbeni hívás** (mi hívunk, nem az indítás): a rács `VEDO_HIV` sora
mondja meg, mit jelez a hívott lap (`hossz:`-szal: pl. 3+ lapból attitűd),
a MODSZER/<jel> sor `hivas:` esetei, hogy melyik lapot hívjuk; a dubló és a
szingli lehet külön lapválasztó sor (`helyzet: HIVAS`). A motor ebből a
hármasból rakja össze a lapválasztást; a „Mit hív?” megmutatja a láncot
(RACS/VEDO_HIV/… › MODSZER/ATTITUD › TECHNIKA/HARMADIK_OTODIK).

**A legnagyobb nélkülözhető** (beépített): indító kijátszásnál a legnagyobb
nem figura lap. JÁTÉK KÖZBENI hívásnál (`helyzet: HIVAS`) finomabb: a
magában álló (nem sorozatbeli) 10-es vagy 9-es helyett a második legnagyobb;
a 8-as mérlegelés (elv). **A legnagyobb kis lap** (`LEGNAGYOBB_KISLAP`):
egyszerűen a legnagyobb 10-es vagy kisebb lap (a Moha lapszám-hívása).

**Melyik sor dönt?** A LEGKONKRÉTABB illeszkedő: konkrét lapok a mintában
(lapként 10 pont), kis lapok, kontextus, `legalabb`, pontos hossz. Egyenlőség
esetén a közelebbi rendszer (a ráépülő), azon belül a sorszám. Ez a
megállapodás, amit a partner olvas; hogy egy partiban érdemes-e eltérni tőle
(kire induljunk, saját hosszú szín …), azt a **mérlegelő** elvek és a
lejátszó modul (szimuláció, DD) döntik el.

**Állapot.** Élesben csak az ELFOGADOTT sor él, teszt módban a JAVASOLT és
a FELULVIZSGALANDO is, a JEGELT soha. Ami élesben nem él, az nem is ír felül
semmit. A kártya a jóvá nem hagyott sorokat kérdőjellel mutatja.

## A lejátszó réteg (a jelzésrendszer használata játék közben)

A `/v1/bridge/play` döntése (`src/kibic/motor/lejatszas.py`) négy lépés:

1. **Tények → minta.** A látható kezek, a lejátszott lapok, a renonszok és a
   licit kényszertára alapján lehetséges teljes leosztásokat vesz,
   KÖTEGENKÉNT (40), és addig, amíg a döntés el nem dől: a legjobb lap minden
   mástól biztosan jobb (a különbség három standard hibán túl) vagy biztosan
   alig különbözik tőle (0,05 alatt) — legalább 60 (`KIBIC_LEJATSZAS_MIN_MINTA`),
   legfeljebb `KIBIC_LEJATSZAS_MINTA` (alap 3000), az időkereten belül.
   Egyértelmű helyzetben 60–200 minta, szorosban az időkeret végéig
   (`meta.kibic.stopped`: BIZTOS / IDO / MAX / KIMERITO). A sorsolás ÉPÍTŐ
   (2026-10-23): a rejtett kezek színhosszait a licit hosszígéretei, a
   renonszok és a letett lapok szerint, pontosan az elosztások számának
   arányában sorsolja, utána a lapokat — a hosszakra nincs eldobás (a pontsávot
   és a többértelmű licit változatait az elfogadás kezeli). A KIS LAPOK (a
   8-as és alatta, ha nincs köztük látható lap; `KIBIC_LEJATSZAS_KIS_LAP`)
   a kimerítő elemzésben egyenértékűek: egy „mintázat” (a számító lapok helye
   + a kis lapok száma kezenként) képviseli mindet, a súlya az általa
   képviselt elosztások száma; legfeljebb 5000 mintázatig
   (`KIBIC_LEJATSZAS_MINTAZAT_HATAR`) a teljes sokaságot nézi, véletlen
   sorrendben (ha a döntés eldől, megállhat) — így a kimerítő elemzés a
   parti közepén is elérhető (`meta.kibic.small_cards_merged`). Ha a
   lehetséges elosztások száma legfeljebb 600, MINDET megnézi
   (kimerítő elemzés: a végjátékban pontos). Ha a kényszertár túl szűk (a
   próbák első felében 30-nál kevesebb illeszkedő minta), a második félidőben
   elengedi (`meta.kibic.relaxed`); ha van elég, inkább kevesebb mintával
   dolgozik, de a licitnek megfelelőkkel. Ha egy ígéret a letett lapoknak
   mond ellent (a 2♥ közbeszólás 5 kőrt ígér, de csak 4 lehet nála), előbb
   csak azt a részt igazítja a lehetségeshez (`meta.kibic.bidding_adjusted`),
   a pontsáv és a többiek ígéretei maradnak. A TÖBBÉRTELMŰ licitnél (pl. információs
   kontra: rövid káró + 3+ a többiben 12+-szal, VAGY 18+ bármi) a kéznek
   legalább egy változatot ki kell elégítenie — nem csak az uniót („12+”);
   a szabályon BELÜLI `vagy:` ágai is (Michaels: pikk és treff VAGY káró).
   Az elosztások SÚLYT kapnak a következtetésekből (lent): ami a partner
   jelzésének vagy a licit pontsávjának kicsit ellentmond, az kevesebbet ér.
2. **DD-szűrő.** Mintánként double dummy kiértékeli a szabályos lapokat, a
   PONTOZÁS szerint (`game.scoring`, `meta.kibic.scoring`): **IMP**-ben
   (csapat, összpont, alapból) mintánként a lap pontszáma IMP-ben, a mintán
   elérhető legjobbhoz mérve — így a teljesítés / buktatás sokkal többet ér,
   mint egy többletütés (biztonsági játék); **MP**-ben (párosverseny) az
   átlagos ütés. Laponként: **JO** (a legjobb átlagától legfeljebb a TŰRÉSSEL marad el —
   *indításnál* 0,2 ütés, ha 26+ lap helye ismeretlen, és vele arányosan
   kisebb; *játék közben* csak a minta zaja: a párosított különbség kétszeres
   standard hibája, legalább 0,02 ütés — „játék közben a szabályok
   leértékelődnek”, egy tizedütésnyi valódi különbség már nem mindegy),
   **BIZTOSAN_ROSSZ** (a minták 75%-ában legalább egy ütést veszít),
   **TALAN** (a kettő között). Időkeret: a határidő 40%-a, legfeljebb
   `KIBIC_LEJATSZAS_MS` (10000).
3. **A megállapodás a jó lapok között.** Védőként:
   *indító kijátszásnál* a lap MINDIG a megállapodásé, a DD csak a színt
   választja (a megállapodás lapjainak értéke szerint), és csak a biztosan
   rossz lapot vétózza meg — itt még nincs igazi információ;
   a SZÍN elsőbbsége (`szinvalasztas: PARTNER_SZINE` sor): ha a partner
   licitált (a kényszertár szerint 4+ lapot ígért), az ő színe megy — a
   kivételek: `NINCS_LAP`, `KIS_SZINGLI` (egyetlen 9-es vagy kisebb),
   `SAJAT_EROS_SZIN` (szan ellen 5+ lap, 2+ figura, köztük Á vagy K),
   `LOPAS` (szín ellen saját szingli, 1-3 aduval); a lap a színen belül a
   megállapodásé, a DD csak a biztosan rosszat vétózza;
   *menet közbeni hívásnál* a SZÍNT az elemzés választja (2026-10-23, a
   szerkesztő döntése): a színek a legjobb lapjuk értéke szerint; a
   megállapodás csak a színen belül dönt a lapról (ha az jó lap; ha nem, a
   szín legjobb lapja), és színt csak a gyakorlatilag egyforma (0,05-ön
   belüli) színek közül választhat. *Színadásnál* a rács első jele: kérés (van-e figuránk a
   színben), lapszám / maradék lapszám (a módszer szerint páros-páratlan),
   Smith (a felvevő első hívásában; tetszik-e az indulás) — magas vagy
   alacsony lap a jók közül. A „magas” a legnagyobb NÉLKÜLÖZHETŐ (figura nem,
   a magában álló 10-es / 9-es sem: az játszó lap lehet; „nem a legkisebb”
   elég). Ahol a jelzésrendszer `nincs_jelzes:` sora él (pl. szlem ellen),
   színadásnál és dobásnál nincs jelzés: a legkisebb jó lap. *Dobásnál* egyenes preferencia:
   nagy lap a nem kért színből, kis lap a kértből. Felvevőként: a DD
   legjobbja, azonos értékűekből a legkisebb.
4. **Mérlegelő elvek** (ahol a DD vak) — a jelzésrendszer `merlegeles:` sora
   kapcsolja be őket, sor nélkül nem élnek:
   `ASZ_ALOL` (2026-10-24) — színfelvétel ellen ász alól nem indulunk, a
   partner színében sem: az ásszal (merev szabály; a partner nem számít az
   aláhívásra); az aduszínben nem él;
   `DUBLO_INDULAS` (2026-10-24) — színfelvétel ellen figura nélküli dublóból
   (a felső lap nem Á, K, D, és nem B10) nem indulunk szlem ellen (a lopáshoz
   előbb két ütés kell — az már a bukás), és szan-jellegű leosztásban sem.
   A JELLEG a mintákból: minden mintában a felvevő DD-ütése a színfelvételben
   és ugyanazon a szinten szanban; ha a minták legalább felében a szín
   legalább 2-vel többet ér, a felvétel lopásra épül (ott marad az elemzés),
   különben szan-jellegű (`meta.kibic.ruff_based_share`). A partner licitált
   színe kivétel. A Pavlicek-partikon a kibic 127-szer indult dublóból (az
   ember 81-szer); ahol a dubló nem volt figurás, a szan-jellegű leosztásokban
   62 IMP-t vesztett (az ember 15-öt), a lopásra épülőkben ugyanannyit, mint az ember;
   `ATVETEL` — a DD a partnert is mindentudónak hiszi, ezért ha mindegy, ki
   viszi az ütést, a folytatást rábízza; mi a partner ütését nyerő lappal
   átvesszük (ha ez semmibe sem kerül), és mi folytatunk;
   `PARTNER_KERESE` (`tures: 0.25`) — a partnerség kedvéért: a partner első
   dobással kért színét hívjuk menet közben, és ütést is veszünk érte
   (lopunk, átvesszük az ütését), hogy mi hívhassuk; a partner SMITH-jele
   szerint (a felvevő első hívásában, ha nem ütni próbált; hogy a lapja kicsi
   vagy nagy volt, a mintákból becsüljük — a minták 65%-ában) váltunk, illetve
   folytatjuk az indítás színét — akkor is, ha az elemzés
   átlaga szerint ez legfeljebb a tűréssel rosszabb — a pontozás egységében:
   IMP-ben 0,25 IMP, MP-ben negyed ütés (egy „alig” kevesebb ütés is
   elbuktathatja a felvételt); a biztosan rossz lapot soha. A többi mérlegelő elv még csak szöveg.

**Következtetés a lejátszásból — a jelzésrendszer sora, nem rejtett tudás.**

```yaml
- kovetkeztetes: LEGKISEBB_EGYENERTEKU   # 3./4. kézben, ha ütni próbál: az egyenértékűek legkisebbike
  kitol: [ELLENJATEKOSOK]                # PARTNER / ELLENJATEKOSOK / FELVEVO
  sajat: true                            # a kibic maga is így játszik
- kovetkeztetes: LEGOLCSOBB_NYERO        # 4. kézben a legolcsóbb nyerő lap
  kitol: [ELLENJATEKOSOK]
  sajat: true
- kovetkeztetes: FIGURA_SOROZAT          # a nem ütésre tett (dobott) Á/K/D/B zárt sorozat
  kitol: [ELLENJATEKOSOK]                # teteje (nála a következő kint lévő lap), vagy szingli:
  sajat: true                            # a partner ászára a D: DB vagy szingli D
  suly: 0.1
```

A `FIGURA_SOROZAT` (2026-10-23) súlyoz (alapból 0,1): a jelzés téves is
lehet. A kibic maga is így tesz: ha nem ütésre tesz figurát, a sorozata
tetejét (ha az elemzés szerint ugyanannyit ér). Aki egy lap-megállapodást
már megszegett, arra csak az a következtetés nem él.

Akinek a lapjaiból következtetünk, annak az ennek ellentmondó elosztásai
kiesnek a mintából (ha marad elosztás). A Moha a felvevőéből nem következtet
(a hamis lap az ő trükkje); ha mégis kellene, a `kitol`-ba kerül a `FELVEVO`.
Sor nélkül nincs következtetés. A kizárt elosztások száma:
`meta.kibic.play_inference_excluded`.

A következtetés lehet SÚLYOZOTT is (`suly:` 0–1; 0 = kizárás): az
ellentmondó elosztás ennyit ér a mintában (a véletlen mintában ekkora
eséllyel marad benne). A jelzésekből és a licitből levontak alapból súlyoznak:

```yaml
- kovetkeztetes: PARTNER_INDITASA   # az indító lap a mi megállapodásunk szerinti
  kitol: [PARTNER]                  # (KB952-ből a 2-es: ha a ♠5 jött, nincs 5 pikkje)
  suly: 0.2
- kovetkeztetes: PARTNER_DOBASA     # az ELSŐ dobás a dobási jel szerint kér / nem kér
  kitol: [PARTNER]                  # kért: van benne Á, K vagy D; nem kért: nincs Á, K
  suly: 0.25
- kovetkeztetes: LICIT_PONTHATAR    # a pontsáv nem éles: 12+ mellett a 11 fél, a 10
  kitol: [ELLENJATEKOSOK, FELVEVO]  # negyed súllyal él (a hossz marad éles)
  tures: 2
  suly: 0.5
- kovetkeztetes: LICIT_KIZARAS     # amit a licitjével KIZÁRT (2026-10-23, az alaprendszerben)
  kitol: [ELLENJATEKOSOK, FELVEVO]  # pl. passz 1♥-re: a licitmotor szimulációja
  suly: 0.2                         # szerint 0-5 pont; 1 pont eltérés fél súly
```

A `LICIT_KIZARAS` a licit-szál kizárásos következtetését (`motor/kovetkeztetes.py`:
a licitmotor szimulálja, milyen lappal licitált volna így) adja át a
lejátszásnak; leosztásonként egyszer drága (`KIBIC_LEJATSZAS_KOVETKEZTETES_MS`,
alap 15 000, legfeljebb a határidő 30%-a), utána gyorsítótárból jön.
Aki a lapjaival már MEGMUTATTA, hogy nem a lap-megállapodás szerint játszik
(pl. QJT-ből a D-vel ütött, és a B-t később letette), arra a lapból levont
következtetés nem él — különben minden elosztást kizárna.

A leértékelt elosztások száma kódonként: `meta.kibic.inference_weighted`.
Így lesz a következő lépés is ELV: a felvevő lapjaiból levont, súlyozott
következtetés (pl. az ellenfél erőssége szerint, a RAG-ból) ugyanilyen sor
lesz, `kitol: [FELVEVO]`-vel és `suly`-lyal.

**Ahol a DD vak: második kéz.** A `helyzet: MASODIK_KEZ` lapválasztó sor
(terület: SZINADAS) a színadást írja le második kézben — pl. a Mohában „dubló
figurából a figura” (K, D, B; ászra nem). Feltételei az asztalról: `asztal:
ELOTTUNK` (az asztal hívott, jobbra ül) / `UTANUNK`; `kozbenso: "2+"` (az
asztal lapjai a 10-es és a figuránk között, a hívottal együtt — B10xx a Dx
előtt: várunk); `hivott: NAGY / KICSI` (Bxxx-ből a B-t hívták: fedünk; kicsit:
nem kell). Nyílt lapokkal az információnak nincs ára,
ezért a DD ilyenkor a két lapot egyformának látja; a szabály nyer, ha a lap
nem biztosan rossz.

**Visszajátszás.** `KIBIC_ATJARO_NAPLO_KERES=1` mellett a napló a play-döntés
teljes kérését is tartalmazza (a saját kéz és az asztal — csak elemzéshez),
és egy döntés laponként újra megnézhető:
`python -m kibic.cli.jatekelemzes --naplo kibic-atjaro.jsonl [--sor N]`.

DDS nélkül a 3. lépés a szabályos lapok közül választ (a leghosszabb színből
a megállapodás lapja). A válasz magyarázata kéz nélküli; a laponkénti
osztályok csak teszt módban mennek ki (`meta.kibic.debug`).

## Mérés: lapankénti DD-veszteség (2026-10-23)

`python -m kibic.cli.jatekmeres` (`motor/lejatszas_meres.py`) minden
kijátszott lapról megmondja, hány ütést adott el a lehető legjobbhoz
képest a valódi lapokkal (double dummy), és hogy elrontotta-e az eredményt
(teljesítés / bukás — IMP-ben ez fáj).

- **A kibic saját partijai** (a napló, `KIBIC_ATJARO_NAPLO_KERES=1`-gyel):
  `--naplo kibic-atjaro.jsonl`. Egy leosztás kéréseiből az osztás
  visszaállítható; ha a napló a parti vége előtt ér véget, a hiányzó lapokat
  a renonszok szerint minden lehetséges módon kiegészíti, és csak azt
  számolja, ami mindegyikben ugyanaz (a többi „bizonytalan”, tól–ig).
- **Mérőpad valódi partikon**: `--lin fájlok/mappák…`, `--pbn fájlok/mappák…` (mappánál a benne és almappáiban lévő összes `.lin`/`.pbn`) vagy `--db`
  (a `jatszma` tábla). A lejátszás minden pontján a kibic ugyanazt látja, mint az ember
  (ugyanaz az előzmény, a saját keze és az asztal), és a két lapot DD-ben
  összevetjük: kibic–ember döntésenként. Szűrők: `--jatekos gal` (csak az
  ő lapjai, felvevőként az asztaléi is), `--oldal felvevo|vedo`,
  `--max-parti`, `--max-dontes`; sebesség: `--minta` (alap 200), `--ido`,
  `--parhuzamos N` (N folyamat; legfeljebb a valódi magok száma).
- **Ismételhetőség**: `--mag 1`-gyel két futás lapra pontosan ugyanazt adja,
  akárhány folyamattal. Ilyenkor a döntés a minta számán (`--minta`) és a
  biztonságon áll meg, nem az időn: az idő a gép terhelésétől függne. Az
  időkorlát (`--ido` legalább 120 mp, a licit-következtetés 300 mp) csak
  biztonsági határ; `--idokorlat` visszaállítja az élő asztal korlátait.
  A `--json` soraiban a `megallt` (BIZTOS / MAX / KIMERITO / IDO …) és a
  `minta` mutatja, mi állította meg a mintavételt.
- Kimenet: összesen / felvevő / védő / helyzetenként (INDITAS, HIVAS,
  SZINADAS, DOBAS, FELVEVO); `--reszletes`: a legrosszabb döntések;
  `--json`: minden mérés soronként. Az `IMP` oszlop (2026-10-23): az összes
  IMP-veszteség a DD legjobb lapjához képest, beliállással és kontrával — a
  kibic IMP-ben játszik (a teljesítés sokat, a felülütés alig ér), ezért
  ütésben mérve a biztonsági játéka „hibának” látszhat; a `kibic+ / ember+`
  is IMP-ben számol (egyenlőségnél ütésben).

A DD-veszteség FELSŐ korlát (nyílt lapokkal a találgatás is „hiba”), ezért a
kibic és az ember EGYMÁSHOZ mért eredménye a beszédes.

**Az indulások kimutatása** (`python -m kibic.cli.inditaselemzes`, 2026-10-24):
a mérés `--json`-jából azokra az indulásokra, ahol a kibic IMP-t vesztett
(`--mind`: mind, `--rosszabb`: ahol az ember jobban indult), minden induló
lapra a kibic becslése az indulás pillanatában (a mintákból: átlagos
védőütés, hány %-ban buktat, IMP) és a valódi osztás DD-je; és a leosztás
JELLEGE — hány induló lap buktat: nem buktatható / aktív (≤ ⅓) / vegyes /
passzív (> ⅔) / mindig bukik —, a mintákban és a valóságban. `--html`:
böngészőben olvasható kimutatás, `--ki`: JSON.

## Munkamenet

```bash
# megnézni (YAML-ból vagy --db): mit hoz be, mit ír felül, mit töröl
python -m kibic.cli.jelzes --rendszer MOHA_STAND
python -m kibic.cli.jelzes --rendszer MOHA_STAND --lap KQ72        # mit hív, melyik sor miatt
python -m kibic.cli.jelzes --rendszer MOHA_STAND --lap KQ72 --szint ELES

# kártya YAML-ból
python -m kibic.cli.kartya rendszerek/yaml --rendszer KIBIC_STAND --ki kartya.html

# import (a jelzésrendszereket a rendszerek/jelzesek-ből magától betölti)
mysql kibic < schema/030_jelzesmenet.sql     # egyszer (a 029 után)
mysql kibic < schema/031_jelzesmenet_szerkezet.sql
mysql kibic < schema/032_jelzes_szinadas.sql
python -m kibic.cli.rendszerimport rendszerek/yaml/ --csak KIBIC_STAND
curl -X POST http://localhost:9050/v1/kibic/ujratolt
```

A jóváhagyás és a jegelés a szerkesztőben (`/szerkeszto`, Jelzések lap);
az import megőrzi, amíg a sor tartalma nem változik.
