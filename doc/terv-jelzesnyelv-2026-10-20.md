# Jelzésnyelv – a hat rendszer lejátszási fejezetei a nyelvvázlatra fordítva

*2026-10-20. Forrás: a projektbe feltöltött hat rendszer indítási és jelzési
fejezetei. Cél: kiderül-e, hogy a 10-20-i vázlat (helyzet + cél + lapválasztó,
ELV / SZABÁLY) elég-e, és ha nem, milyen nyelvi elem hiányzik.*

---

## 0. Röviden

* **A vázlat váza bírja**, de **öt új elem kell** hozzá (3. pont). A legfontosabb:
  a jelzésnek **állapota** van (mit jeleztünk már, és milyen jelzést kért a
  partner), és a jelzés **tárgyszíne** eltérhet a kijátszott lap színétől.
* A **római (páros/páratlan) jelzést egyik rendszer sem használja.** A nyelvben
  maradhat opcionális elemként, de nem sürgős.
* **Mind a hat rendszer kicsivel kér, és ahol a lapszám le van írva, ott
  fordított** (nagy-kicsi = páratlan). Ez jó hír: a polaritás nagyrészt közös.
* **Két rendszer hiányos:** a DP (Mezhon) csak indítást ír le, jelzést egyáltalán
  nem; az MBSZ egyéni rendszer két sorban intézi el az egészet. Ezekhez
  alapértelmezés kell (5. pont, nyitott kérdések).
* A Szegedi–Mráz rendszer **szó szerint kimondja az elvárás-elvet**:
  „Mindig azt jelezzük, amire a partnernek szüksége van.” – vagyis ez nem
  egzotikum, hanem írott megállapodás.
* A **licitben is vannak indítást irányító megállapodások** (3NT kontrája,
  szlem kontrája, lengyel kontra, splinter kontrája). Ezek a licittáblában
  élnek, de a jelentésük az indításra vonatkozik – kell egy híd (3.5 pont).

---

## 1. A rendszerek lefedettsége

| Elem | MBSZ | SA (Győr) | Syl | Heavy | DP | Sz–M |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Indítás szín ellen (kislapok) | 3./5. | Rusinow + lapszám | párat./páros | táblázat | 3./5. | párat./páros |
| Indítás szan ellen (kislapok) | kis lap = figura | Journalist (figuraszám-függő) | 4. | táblázat | 4. | 4. (T-től) |
| Figurakombinációk | sorozat | részletes | részletes, deblokk-kérés | részletes, deblokk-kérés | részletes, belső sorozat | sorozat |
| Partner színében indulás | – | külön (nincs Journ.) | külön, hossz szerint | külön | T is figura | – |
| Kérés–nem kérés | kicsi | kicsi | kicsi | kicsi | – | kicsi |
| Lapszám | UDCA (ford.) | „szokott módon” | fordított, **teljes** | fordított, maradék | – | fordított, **maradék** |
| Preferencia | Lavinthal | Lavinthal (idegen színben) | Lavinthal (spec.) | SPS, obvious | – | Lavinthal 3 értékű |
| Smith | – | – | van (kicsi = nem kér) | van (nagy = jó) | – | van (kicsi = jó) |
| Jelzés-sorrend | – | kérés, majd maradék lapszám | – | Smith után lapszám | – | – |
| Menet közbeni hívás | – | – | van | van | – | van |
| Speciális helyzetek | – | – | obvious shift | Scaniai, SPS, AK→K | – | 9 tétel + elvárás-elv |
| Indítást irányító licitek | hívásirányító kontra | – | 2 tétel | lengyel kontra, splinter | – | 3NT-kontra 5 lépcső, 4M, szlem |

Durva méret: Syl és Heavy ~40 sor, SA és Sz–M ~30, DP ~15 (csak indítás),
MBSZ ~7. Összesen nagyjából **160 szabálysor** – egy nagyságrenddel kevesebb,
mint a licit (750).

---

## 2. Fordítás a vázlatra

Jelölés: `helyzet | feltétel | lapállás | cél | lapválasztó` (a cél: FIG / KER /
LSZ / PREF, az új elemekkel együtt lásd 3. pont).

### 2.1 Szegedi–Mráz (a legtömörebb teljes rendszer, ezért ez az első)

```
INDITAS      SZIN  páratlan x-ek          LSZ   LEGKISEBB
INDITAS      SZIN  páros x-ek             LSZ   FELULROL(3)
INDITAS      SZIN  xx                     LSZ   NAGYOBB
INDITAS      SZIN  ígértünk 3-at, 0 fig   FIG   LEGNAGYOBB_NELKULOZHETO   ← licitkényszer kell!
INDITAS      *     sorozat / belső sor.   FIG   SOROZAT_TETEJE
INDITAS      SZAN  T-t tartalmaz          FIG   FELULROL(4)
INDITAS      SZAN  T nélkül               FIG   LEGNAGYOBB_NELKULOZHETO
UTES2        felvevő ütött és hív         KER   Smith: KICSI = jól indultam      ← tárgyszín ≠ lapszín
UTES2        válaszoló                    LSZ   Smith count: maradék, az indított színben
*            kérés                        KER   KICSI = kér
*            lapszám                      LSZ   MARADEK, KICSI_NAGY = páros
HIVAS        attitűd                      KER   figurából FELULROL(3|5), különben LEGNAGYOBB_NELK., xx: NAGYOBB
*            preferencia                  PREF  KICSI = alsó, NAGY = felső, KOZEPES = semleges
ELV  „Mindig azt jelezzük, amire a partnernek szüksége van.”               ← elvárás-elv
SPEC AK-ból K-val: AK dubló | külső szingli | 4x kontra | 5-ös szint
SPEC Á-indulás, asztalon Dxx v. Bxxx: kicsi=xx, nagy-kicsi=3, nagy-nagy=4  ← 2 lapos, 3 értékű
SPEC Á-indulás, asztalon / tudottan kézben szingli: Lavinthal
SPEC az asztal lop vagy zárt színnel visz: Lavinthal, KOZEPES = folytasd
SPEC az asztalon D vagy kisebb üt: lapszám
SPEC adu indulásba: Lavinthal
SPEC asztalon D, parti közben K hívás: lapszámot KÉR                          ← típusválasztó
SPEC szan, asztalon szingli/dubló figura üt: lapszám, később Smith           ← sorrend
```

### 2.2 Sylstandard

```
INDITAS  SZAN  hosszú, figurás          FIG+LSZ  FELULROL(4)   (11-es szabály)
INDITAS  SZAN  ≥4, mégsem 4.            FIG      LEGKISEBB = „gyenge a szín”      ← szándékos eltérés jelentése
INDITAS  SZAN  Fxx                      FIG      LEGKISEBB
INDITAS  SZAN  Fx                       FIG      FIGURA
INDITAS  SZAN  figura nélkül            FIG      LEGNAGYOBB_NELKULOZHETO
INDITAS  SZIN  páratlan / páros / xx    LSZ      LEGKISEBB / FELULROL(3) / NAGYOBB
INDITAS  *     A: AK v. K bedobását kéri, tagadja D-t   FIG+KER(bedobás)          ← deblokk-kérés
INDITAS  *     K: (A)KD v. D bedobását kéri              FIG+KER(bedobás)
INDITAS  *     D: DB, ADB v. B bedobását kéri            FIG+KER(bedobás)
INDITAS  *     B: BT, KBT;  T: T9, DT9, ABT;  9: 98 (csak szan), KT9, AT9;  8: D98, B98
INDITAS  SZIN  AKD: Á = lapszámot kérek, K = kérést kérek               ← típusválasztó
PARTNER_SZINE SZAN (≥5 ígért): xx→NAGYOBB; 3 lap fig.v.T→LEGKISEBB, nélküle→KOZEPSO;
                               4 lap → FELULROL(3), T-vel LEGKISEBB
*        kérés                  KER   KICSI = kér
*        lapszám                LSZ   fordított, TELJES (a kézben lévő lapok)    ← ≠ Sz–M (maradék)
SPEC obvious shift (indulás után ütésben marad, asztalon szingli): KICSI = bírom a maradék szín hívását
SPEC Smith: ha az indításnál nem tudtunk jelezni, következő szabad dobás:
            KICSI = nem kérem, NAGY = kérem                                   ← polaritás ≠ Sz–M!
SPEC partner a mi kizáró színünkkel indul, az asztal üt: Lavinthal
HIVAS    SZAN  attitűd: KICSI = figurát ígér
HIVAS    SZIN  KICSI = dublóm van (ha még lopás elképzelhető)
HIVAS    *     B/T/9 hívása: 0 vagy 2 magasabb lap
LICIT→IND  kizárós partnere kontrázza a 3NT-t: „ne a színeddel indulj”
LICIT→IND  (1NT)–x–(3NT) kontra: „rövidebbik majoroddal indulj”
```

### 2.3 Heavy Club

```
INDITAS  *  Á: ígéri K-t, tagadja D-t, v. K deblokkot kér; D birtokában kérés
INDITAS  *  K: nem tagadja Á-t, ígéri D-t v. D deblokkot kér; Á v. B birtokában kérés kicsivel
INDITAS  *  D: sorozat teteje, ÁDB, KDT(9), szan ellen KDBx (de nem KDBxx+); B deblokkolandó
INDITAS  *  B: BTx, KBTx;  T: T9x, DT9x, ÁBTx, ÁDT9, ÁKT9 („felülről 3. erős”)
INDITAS  *  9: 98x (szan), ÁT9x, KT9x, KB98, ÁB98, ÁK98;  8: 8xx, B98x, D98x, ÁKT8, ÁDT8
INDITAS  *  x: Bxxx, Fxx, xxxx, xxx, xx, x (szan ellen legnagyobb nélkülözhető)
PARTNER_SZINE SZAN: Bxx, Txx, Txxx, xx, xxx, xxxxx – külön kódolás
HIVAS    *  B: KBTx;  T: DT9x;  9: 0 v. 2;  8: B98x, D98x
*        kérés                  KER  KICSI = kér (szan és szín)
*        lapszám                LSZ  NAGY_KICSI = páratlan
*        maradék, ha MI hívjuk  LSZ  NAGY_KICSI = páratlan („P-nél fordítva” – ?)    ← nyitott kérdés
*        maradék, ha ŐK hívják  LSZ  NAGY_KICSI = páratlan                           ← „ki hív” is helyzet
SPEC Smith szan ellen: NAGY = pozitív;  változat: NAGY = páratlan maradék az indított színben
SPEC ugyanígy, ha húzós szín van az asztalon, arra vonatkoztatva                 ← tárgyszín
SPEC obvious: asztalon szingli a megtámadott színben → KICSI kéri az obviousot
SPEC AK-ból K (fordított) kontrázott 4-es és nem kontrázott 5-ös felvétel ellen
SPEC második helyen figura: két érintkezőből a kisebb, háromból a legnagyobb     ← egyenértékű lapok közti választás
SPEC Scaniai: szanban NAGGYAL kér, ha partner figurával indul, asztalon nincs elfogni
     való figura (T nem figura!), és nem ígértünk 4-es színt. Színjátékban is, ha három kicsi terül.
SPEC asztalon szingli → SPS
LICIT→IND  lengyel kontra: „fontold meg, mivel indulsz”; passz = ne gondolkodj
LICIT→IND  ellenfél splinterének kontrája: fragmentben, ha nincs: magasabb kimaradóban kér indulást
```

### 2.4 Standard American (Győr 2002)

```
INDITAS  SZIN  Rusinow: Á: Á, ÁK(!), Áx, Áxx…;  K: ÁKx, ÁKxx, ÁKDx, KD, Kx;
               D: KDx, KDBx, DB, Dx;  B: DBx, DBT, KBTx, BT, Bx;  T: BTx, KT9x, DT9x, T9, Tx;  9: T9x, T98x
INDITAS  SZIN  ÁKD: K majd D = semmi extra; Á majd D = felső szín; D majd Á = alsó szín  ← 2 lap SORRENDJE = PREF
INDITAS  SZIN  kislapok: lapszám szerint, NAGY_KICSI = páratlan
ELV      Rusinow NINCS aduszínben; VAN szlem ellen, partner színében, összeemelt színben
INDITAS  SZAN  Journalist: Á: ÁK(x)(x) v. ÁKB → kérés;  ÁDBT → K bedobását kéri
               K: KD → kérés;  ÁKBT → D bedobását kéri
               D: erős (KDBxx, DBT9x…) → deblokk T-ig, különben lapszám             ← típusválasztó
               B: BT v. DB → kérés;  T, 9: 0 v. 2 magasabb figura → kérés
               kislapok: 0 figura → LEGNAGYOBB_NELK.; 1 figura → FELULROL(3|5); 2 figura → FELULROL(4|6)  ← figuraszám
ELV      Journalist NINCS szlem ellen és partner színében (partner színe = ≥5-öt ígért:
         1M, színközbeszólás, Ghestem, hívásirányító kontra)                         ← fogalom-definíció
*        saját vonal által bontott szín: KICSI = kér
*        idegen szín: Lavinthal
ELV      kérés az elsődleges, második tevésnél MARADÉK lapszám                        ← sorrend
```

### 2.5 DP (Mezhon 2011) – csak indítás

```
INDITAS  SZAN  figurás szín             FIG  FELULROL(4)   (11-es szabály)
INDITAS  SZAN  figura nélkül            FIG  LEGNAGYOBB_NELKULOZHETO   (10843→8, 1097→T, 952→5)
INDITAS  SZAN  3 lap: figurás → LEGKISEBB, figura nélkül → LEGNAGYOBB_NELK.
INDITAS  *     sorozat teteje; figura ígéri az alatta lévőt
INDITAS  *     érintkező figurákból az ALACSONYABB = deblokkot kér (ÁKBT9 → K)
INDITAS  *     B/T/9: sorozat teteje, v. belső sorozat: 1 lyuk → 1. lap (KBT→B), 2 lyuk → 2. lap (KT9→T)  ← lyukszám
PARTNER_SZINE (≥4 ígért): a T is figura                                              ← fogalom kontextusfüggő
INDITAS  *     ha MI ígértünk ≥5-öt: a 2-es = nincs figurám                          ← licitkényszer kell
INDITAS  SZIN  3./5., xx: NAGYOBB, 6 lapból 3.;  érintkező figurákból a nagyobb
INDITAS  SZIN  ÁK-ból K, ha ÁK dubló, vagy sikén van máshol (lopni akar)              ← saját kéz más színe!
```

### 2.6 MBSZ egyéni

```
INDITAS  SZIN  3./5.; sorozat teteje, belső sorozat teteje; xx: NAGYOBB
INDITAS  SZAN  KICSI = figurát ígér; sorozat teteje, belső sorozat teteje
*        UDCA: fordított lapszám, KICSI = kér;  preferencia: Lavinthal
```

---

## 3. Mi hiányzik a nyelvből – az öt új elem

### 3.1 Jelzési állapot (a legfontosabb)

A vázlat minden lapot önállóan kezelt. A rendszerek viszont **sorrendet és
emlékezetet** írnak elő:

* „kérés az elsődleges, a második tevésnél maradék lapszám” (SA);
* „Smith után is jöhet lapszám” (Heavy);
* „szanban, ha szingli figura üt az asztalon: lapszám, **később** Smith” (Sz–M);
* Smith csak akkor, „ha az indításnál nem tudtunk jelezni” (Syl).

Kell tehát **színenkénti jelzési állapot**: mit jelzett már a pár ebben a
színben, és mi következik. Ez egy kis állapotgép, és pontosan illeszkedik a
korábban felvetett episztemikus állapotgéphez: a helyzet nem csak a lapokból,
hanem a **már elhangzott jelzésekből** is áll.

### 3.2 Típusválasztó jel (meta-jelzés)

Több helyen **a lap nem információt ad, hanem kiválasztja, milyen jelzést adjon
a partner**:

* ÁKD-ból Á = „lapszámot kérek”, K = „kérést kérek” (Syl);
* Journalist D: deblokkot vagy lapszámot kér (SA);
* asztalon D, parti közben K hívás lapszámot kér (Sz–M);
* deblokk-kérések (Á/K/D „bedobását kéri”) – Syl, Heavy, DP.

Új cél kell: **`TIPUS`** – a kijátszott lap beállítja a partner következő
lapjának kapuját. Ez a 3.1-es állapotba ír.

### 3.3 Tárgyszín ≠ lapszín

Smith, Lavinthal, obvious shift, SPS: a lap az egyik színből megy, de **egy másik
színről** szól. A szabálynak tehát külön mezője kell: **`targy`** (az indított
szín / a magasabb kimaradó / „a fennmaradó szín” / a húzós asztali szín).

### 3.4 Többértékű és sorozatos kódolás

A kétértékű nagy/kicsi nem elég:

* **három szint**: KICSI / KOZEPES / NAGY (Sz–M Lavinthal: közepes = semleges,
  vagy „folytasd”);
* **kétlapos döntési fa**: Á-indulásba Dxx-asztallal kicsi = 2, nagy-kicsi = 3,
  nagy-nagy = 4 (Sz–M);
* **két kijátszás sorrendje**: Rusinow ÁKD – K-D, Á-D, D-Á (SA);
* **figuraszám- és lyukszám-függő választó**: Journalist 1 figura → 3./5.,
  2 figura → 4./6.; DP belső sorozat 1 lyuk → 1. lap, 2 lyuk → 2. lap.

A lapválasztó tehát egy kis kifejezés kell legyen (feltétel → kiválasztás), nem
egy szó. A lapállás-mintának pedig tudnia kell a figurák számát és a lyukakat.

### 3.5 Kapcsolat a licittel – két irányban

**a) A jelzés a licitkényszertárt olvassa.** Számos szabály kapuja licitbeli tény:
„ha már ígértünk három lapot” (Sz–M), „ha legalább öt darabot ígértem” (DP),
„a mi kizáró színünk” (Syl), „partner színe = ≥4 / ≥5-öt ígért” (rendszerenként
más!), „tudottan szingli a kézben” (Sz–M). Ez a meglévő kényszertár
újrafelhasználása – nem kell új gép, csak lekérdezés.

**b) A licit indítást irányít.** A 3NT kontrája (Sz–M öt lépcsős sorrendje), a
szlem kontrája („lopni szeretnék”), a 4M kontrája, a lengyel kontra, a splinter
kontrája, „rövidebbik majoroddal indulj”. Ezek a **licittáblában** élnek, de a
jelentésük nem kéztulajdonság, hanem **indítási utasítás**. A licit
jelentés-nyelvébe kell egy új jelentéstípus (`INDITAS_KERES: szín-kifejezés`),
amit az indító modul kényszerként vagy erős előzetes súlyként olvas.

### 3.6 Rendszerenkénti fogalom-definíciók

Ugyanaz a szó rendszerenként mást jelent: **„partner színe”** (≥4 vs ≥5,
felsorolt licitekkel), **„figura”** (a T partner színében figura – DP; a Scaniai
jelzésnél a T *nem* figura – Heavy), **„lapszám”** (teljes vs maradék). Ezek
adatsorok egy `jelzes_fogalom` táblában, nem kódban – ugyanúgy, ahogy a licitnél
az ágak.

---

## 4. A javított nyelv (v0.2)

```
jelzes_fogalom   (rendszer, fogalom, definíció)
                 pl. PARTNER_SZINE: ígért hossz ≥ 5 | licitek: 1M, színközbeszólás, Ghestem, hívásirányító X
jelzes_helyzet   mozzanat:  INDITAS | INDITASRA_TESZ | HIVAS | SZINADAS | DOBAS | UTES2
                 feltétel:  felvétel (SZAN/SZIN, szint, kontra), szín státusza (adu, partneré, sajátunk,
                            összeemelt, ellenfélé, ígért hossz), asztal (szingli, Dxx/Bxxx, három kicsi,
                            elfogható figura, ki üt és mivel, lop-e), ki hív (mi/ők), jelzési állapot
jelzes_elv       helyzetenként: célok sorrendje, kivételek (pl. Rusinow nincs aduban), NINCS (szlem),
                 ELVARAS (profilparaméter)
jelzes_szabaly   lapállás-minta (figuraszám, lyukak, sorozat) → lapválasztó-kifejezés
                 cél: FIG | KER(folytat|bedob|lop) | LSZ(teljes|maradék) | PREF(2|3 értékű) | TIPUS | NINCS
                 tárgy: a lap színe | indított szín | magasabb/alacsonyabb kimaradó | ...
                 polaritás, prioritás, állapot (JAVASOLT/ELFOGADOTT)
jelzes_allapot   futásidőben, színenként: kiadott/kért jelzéstípusok (ezt NEM tároljuk, a játék számolja)
licit jelentés   + INDITAS_KERES  (a licit-jelentésnyelv bővítése)
```

Lapválasztók (zárt készlet, a hat rendszer alapján): `LEGKISEBB`, `FELULROL(n)`,
`FELULROL(n|m)` (hossz szerint), `NAGYOBB`, `KOZEPSO`, `SOROZAT_TETEJE`,
`BELSO_SOROZAT(lyukszám)`, `ALACSONYABB_ERINTKEZO` (deblokk-kérés),
`LEGNAGYOBB_NELKULOZHETO`, `FIGURA`, `KICSI/KOZEPES/NAGY`, `NAGY_KICSI`,
`KICSI_NAGY`, `KETLAPOS_FA(...)`, `SEMLEGES`. Opcionális: `PAROS/PARATLAN`.

---

## 5. Nyitott bridzsszakmai kérdések

1. **Heavy Club, „P-nél fordítva”:** a maradék lapszám, ha mi hívjuk. A „P”
   partnert jelent (ha a partner hívja, fordított), vagy pikket?
2. **Smith polaritása:** a Sylstandardban a kicsi = *nem* kérem, a Szegedi–Mráz és
   a Heavy Club szerint a kicsi / a nagy = jó indítás. Valódi eltérés, vagy
   elírás a Sylstandardban?
3. **DP (Mezhon):** nincs jelzési fejezet. Mi legyen az alapértelmezés – a
   Szegedi–Mráz jelzései (a két rendszer licitje is szoros rokon)?
4. **MBSZ és SA:** a „szokott módon” jelzett maradék lapszám és az UDCA mellett
   mi a menet közbeni hívás és a dobás? Elég, ha ezekre egy közös alapértelmezés
   lép életbe?
5. **Teljes vs maradék lapszám** (Syl vs Sz–M): ez valódi különbség, vagy a
   Sylstandard „mindig a kézben lévő lapok száma” is maradékot ért?

---

## 6. Javasolt sorrend

1. A `jelzes_fogalom` és a `jelzes_szabaly` **indítási része** (2. pont INDITAS
   sorai) – ez kell az első modulhoz, és a hat rendszer itt a legteljesebb.
2. A licit-jelentésnyelv bővítése `INDITAS_KERES`-sel (3.5 b) – kicsi munka,
   és az indításnál azonnal hasznos.
3. Utána a menet közbeni jelzések a jelzési állapottal (3.1–3.3), a felvevőjáték
   és az ellenjáték moduljával együtt.
