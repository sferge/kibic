# Terv: az elvek adattá tétele — elv-sablonok és paraméterek

*2026-10-04 · állapot: TERV (még nincs kód) · a szerkesztő kérdésére: „lehet-e
az emberi nyelven elmondott elvi megállapodásokat úgy a kibic nyelvére
fordítani, hogy a szerkesztőben is megjelenjenek, paraméterezhetők legyenek,
és sok rendszerben felhasználhatók?”*

---

## 0. Röviden

* **Igen, nagyrészt megvalósítható** — és meglepően sok alapja már megvan
  (helyzeti ELV-sorok, színváltozók, háromszintű paramétertár, „legalább m a
  n-ből” csomópont, mérlegelő jelöltek).
* **A fő adósság** két kézzel írt algoritmus: a hézag-elv (`motor/hezag.py`,
  536 sor) és a spirál (`motor/spiral.py`, 329 sor). Ezekben a szerkesztő
  elvei Pythonként élnek, beégetett számokkal; a szerkesztőben nem látszanak.
* **A határvonal, amit javaslok:** a KÓD azt tudja, *mit kell kiszámolni*
  (alapfüggvények: kényszertár, gém, fit, fogás, kulcslap, lépcső, DD,
  várható érték). Az ADAT mondja meg, *mikor, milyen paraméterrel és melyik
  licitet* (elv-sablonok és példányaik). Így a szabálynyelv nem lesz
  programozási nyelv, és az elvek mégis láthatók, állíthatók.
* **A biztosíték:** semmi nem élesedik, amíg egy rögzített „arany” döntés-
  készleten ugyanazt nem licitálja, mint a mai kibic — vagy a különbséget
  tételesen jóvá nem hagyod. Az új mechanizmus előbb **árnyékban** fut: dönt,
  naplóz, de nem licitál.
* **Sorrend:** előbb ami nem változtat semmit (biztosíték, paraméterek), aztán
  a spirál mint minta, aztán a hézag-elv pontonként; a fokozatos relevancia
  („hasonló helyzet”) a végén, kísérletként.

---

## 1. Hol tartunk ma — őszintén

### 1.1 A döntés négy mechanizmusa

| # | Mechanizmus | Hol él | Látszik a szerkesztőben? |
|---|---|---|---|
| 1 | **Szabálymotor**: konkrét sorok (SZABÁLY/KIVÉTEL), utána a helyzeti ELV-sorok | YAML → adatbázis | ✅ igen |
| 2 | **Mérlegelés**: a `MERLEGELO` sor jelöltjeit szimuláció (DD-minta) dönti el | kód, de adat indítja | 🟡 a sor igen, a döntés módja nem |
| 3 | **Hézag-elv**: ha egyetlen sor sem illik — közös erő, kényszer | kód | ❌ nem |
| 4 | **Spirál**: a kulcslap-válasz után relé és válasz | kód | ❌ nem |

Mellettük két *információforrás* (nem döntenek, tudást adnak): a
**kényszertár** (amit a licitekből a négy kézről biztosan tudunk) és a
**kizárásos következtetés** (ami valószínű).

### 1.2 Beégetett számok (a „minden legyen adat” elv megsértései)

* Hézag-elv: gémküszöb nemes fittel 25, minor fittel 27, szanban 24 FP; a
  partner sávjának súlyozása 0,8^lépés; a gém várható értékének küszöbe
  mansban 45%, bellben 37%; az egy körös kényszerítő licit küszöbe 25%; a
  büntető passz becslésében a partner ~2 védőütése és a saját gém
  értékének 0,7-es szorzója; a „játszható” fit definíciója (8+ lap; 5-2;
  4-3 csak rövidséggel a három lapos adu mellett).
* Spirál: a tételsor (adu dáma, külső királyok ♠♥♦♣, dámák, bubik), a relé-
  és leállás-szabály (az adu szín és a 4NT nem lépcső), a kérdező döntési
  elve (2+ hiányzó kulcslap → 5m; 1 → dáma kell; 0 → nagyszlem-kutatás).
* Elszórtan a YAML-ban: a „plusz erő” 15+ FP (MOHA_1M), a slam-küszöbök
  (30+ / 33+ / 35+ / 37+) még sehol.

### 1.3 Ami a jövőképhez már megvan

| A szerkesztő elképzelése | Ami ma megvan | Ami hiányzik |
|---|---|---|
| Az elv bármikor előszedhető, a helyzet dönti el, releváns-e | Helyzeti ELV-sor: `..` minta + `ha:` feltétel; színváltozók (M, m, oM, om, A, B) a licitből kötődnek | — |
| Állítható paraméterek, sok rendszerben más értékkel | Háromszintű paramétertár: alapérték → rendszer → pár (`parameter`, `rendszer_parameter`, `par_parameter`); a YAML-ban `pont: {param: KOD, alap: 10}` | Paraméter csak néhány számmezőben; nincs „a konvenció saját paraméterei” fogalom; szín- vagy listaparaméter nincs |
| Jelöltet ad, ami nem feltétlenül győz | Jelöltlista, prioritás, mérlegelendő jelöltek | — |
| Nem kell minden feltételnek teljesülnie | A kifejezésnyelvben van `LEGALABB` (m a n-ből); a régi `kriterium_keszlet` (kötelező + min_teljesül) | A YAML-ban nincs rá kényelmes kulcs; súly nincs |
| Relevancia mint % („hasonló helyzet”) | Háromértékű logika (igaz / hamis / eldönthetetlen) | A fokozatosság |
| Egyszer megírt elv, sok rendszerben | Hivatkozás (`hivatkozasok`), kiváltás (`kivalt`), feltételes felülírás | Példányosítás paraméter-felülírással |
| Látszik a szerkesztőben | A sorok, jóváhagyással | A kódba írt elvek és a paraméterek |

---

## 2. A javasolt modell

### 2.1 A határvonal: alapfüggvény (kód) és elv (adat)

**Alapfüggvény** — kód, mert számolás, és nem bridzs-megállapodás:

* kényszertár-lekérdezés (a partner ígért sávja, hossza, fedője; ki forszolt);
* közös erő: A (saját + partner minimuma) és F (saját + partner valószínű
  maximuma);
* gém(adu) és gémküszöb(fit-fajta); fit és biztos fit; játszható(fit);
* fogás(szín), többszörös fogás; kulcslapok, adu dáma; vesztő, fedő,
  gyorsütés, lapminőség;
* lépcső(licit, n): az n-edik lépcső egy licit fölött, kihagyási szabállyal;
* szimuláció: DD-minta, várható érték, büntetés kontra saját kontraktus.

**Elv** — adat (YAML → adatbázis → szerkesztő):

* *mikor* érvényes (licithelyzet-minta + helyzeti feltétel);
* *milyen paraméterekkel* (alapérték, rendszer- és párszintű felülírás);
* *milyen feltételek mellett* (kötelezők és súlyozottak);
* *milyen licitet javasol* (jelölt), és *mit jelent* a licit (ígéret);
* az **emberi szöveg** — a szerkesztő saját megfogalmazása, szó szerint.

A szabálynyelv így nem válik programozási nyelvvé (nincs ciklus, változó-
értékadás): az alapfüggvényeket *hívja*, paraméterekkel.

### 2.2 Elv-sablon

Egy konvenció-YAML, amelynek **saját paraméterei** vannak. Vázlat:

```yaml
rendszer:
  kod: HEZAG_GEMKERESES
  fajta: ELV_SABLON                 # új rendszer-fajta (vagy KONVENCIO + jelző)
  nev: A hézag-elv 1. pontja — gém a közös erőből
  szoveg: >-                        # a szerkesztő megfogalmazása, szó szerint
    Ha a saját pontom és a partner ígért minimuma együtt eléri a gémet…
parameterek:
  GEMKUSZOB_NEMES:   {alap: 25, tartomany: 23-27, fajta: allithato,
                      leiras: "Gémküszöb nemes fittel (FP)"}
  GEMKUSZOB_MINOR:   {alap: 27, tartomany: 25-29, fajta: allithato}
  GEMKUSZOB_SZAN:    {alap: 24, tartomany: 23-26, fajta: allithato}
  SAV_SULY:          {alap: 0.8, fajta: konstans}
szabalyok:
  - minta: ".. +A"                  # gém a fitben
    fajta: ELV
    ha: {kozos_also: {gem: A, op: ">=", param: GEMKUSZOB_NEMES}}
    licit: gem(A)
    prioritas: 1
```

* **konstans**: nem változik (a szerkesztőben csak olvasható);
* **szigorú összefüggés**: más paraméterből számolt (pl. `GEMKUSZOB_MINOR =
  GEMKUSZOB_NEMES + 2`);
* **állítható**: rendszerenként és páronként felülírható.

A paraméterek a meglévő `parameter` táblába kerülnek (`csoport` = a sablon
kódja); a felülírás a meglévő `rendszer_parameter` / `par_parameter` táblán
megy. Új tábla legfeljebb a sablon–rendszer kapcsolathoz kell.

### 2.3 Példányosítás

```yaml
rendszer: {kod: MOHA_STAND, fajta: RENDSZER}
hivatkozasok:
  - KIBIC_STAND
  - {kod: HEZAG_GEMKERESES, parameterek: {GEMKUSZOB_NEMES: 24}}   # pl. agresszívebb pár
```

Ugyanaz az elv így a KIBICEGY, a MOHA és bármely más rendszer alatt
használható, eltérő számokkal — nem kell szabálykészletet másolni.

### 2.4 A szerkesztőben

* Új lap: **Elvek** — a sablonok listája, az emberi szövegük, a paramétereik
  (alapérték, a rendszer felülírása, tartomány), és hogy mely rendszerek
  használják.
* A paraméter-felülírás ugyanúgy JAVASOLT → ELFOGADOTT, mint a sor.
* **Nyomkövetés**: egy konkrét leosztásnál látszik, melyik elv „ébredt fel”,
  mivel kötődtek a változói (pl. A = ♥), milyen paraméterértékkel, mely
  feltételei teljesültek, és miért nyert vagy nem nyert. (A teszt módú
  `debug` nyom ennek az alapja már ma is.)

### 2.5 Fokozatos relevancia — csak a döntés rétegében

* **A jelentés éles marad.** Amit egy licit *jelent* (amiből a kibic a
  partnert érti, és amit alertál), az nem lehet „78%-ban igaz” — a partnernek
  számítania kell rá.
* **A döntés lehet fokozatos.** Amikor több jelölt van, vagy egyetlen sor sem
  illik pontosan: a feltételek súlyozott teljesülése egy 0–1 közötti
  pontszám. Ez rendezi a jelölteket, és ezt méri össze a szimuláció.
* **„Hasonló helyzet”**: ha semmi sem illik, a hézag-elv *előtt* a gép
  megkeresheti a legjobban illeszkedő, `hasonlithato: true`-val megjelölt
  (természetes jelentésű) sort, és jelöltként felhozhatja: „hasonló helyzet:
  1M-2♣-3NT (82%)”. Konvencionális (mesterséges) sort soha nem alkalmaz
  hasonlóság alapján.

### 2.6 Determinizmus (a szerkesztő pontosítása, 2026-10-04)

Szándékos véletlen és blöff NINCS. A „nem mechanikus” viselkedés magától
jön: ahol a döntést DD-elemzés vagy várható érték befolyásolja, ott egy kis
lapkülönbség (8-as helyett 3-as) is eltolhat egy valószínűséget annyira,
hogy nagyon hasonló lapokkal más licit szülessen. A leadott licit jelentése
ettől ugyanúgy megbízható. A mintavétel leosztásonként rögzített maggal
megy, hogy egy döntés visszajátszható és hibakereshető maradjon.

---

## 3. Ütemezés — minden lépés után ugyanúgy licitál a kibic

### 0. fázis — Biztosíték (viselkedés nem változik) — ✅ KÉSZ 2026-10-05

*Megvalósítva:* `python -m kibic.cli.aranykeszlet rogzit | osszevet`
(`src/kibic/cli/aranykeszlet.py`); az alap: `adat/arany/MOHA_STAND.jsonl` —
300 leosztás (mag: 1), 2885 döntéspont (SZABÁLY 1044, ELV 1387, HÉZAG 422,
SPIRÁL 32), önmagával összevetve 0 eltérés (determinisztikus). A
tesztkészletben az első 25 leosztás (`tests/adat/arany_mini.jsonl`, 241
pont) minden futáskor ellenőrződik. Árnyék mód: `motor/arnyek.py`
(`KIBIC_ARNYEK`, kérésben `shadow`); az összevető `--arnyek NÉV`-vel az
árnyék-döntéshozót méri az alaphoz. A kizárásos következtetés a készletben
alapból KI van kapcsolva (időkeretes, így nem determinisztikus).


* **Arany döntéskészlet**: rögzített magú generált leosztások (pl. 2000
  leosztás × minden licitpozíció) és a beküldött naplók licitpozíciói; a mai
  kibic döntése mindegyikre, fájlban.
* **Döntés-összevető** eszköz: egy változtatás után újra lefut, és tételesen
  kiírja, hol és miért licitál mást.
* **Árnyék mód**: az új mechanizmus kiszámolja a saját döntését, a naplóba
  írja a különbséget, de a licit a régi marad (`KIBIC_ARNYEK=1`).
* Elfogadási szabály: egy fázis akkor élesedik, ha az aranykészleten a
  különbség **nulla**, vagy minden eltérés szándékos és jóváhagyott.

### Előrehozott lépés — az első ELV-SABLON: FOGASMUTATAS — ✅ KÉSZ 2026-10-05 (próbában)

*A szerkesztő kérése (2026-10-05):* az 1♠-2♣-2♠-3♦ leosztás után a régi
módszer (soronkénti szabályok) 23 sort adott két mondatra — „elbarokkosodott”.
„Haladjunk a tervvel”: az elv legyen EGY általános leírás.

*Megvalósítva:*

* Új rendszer-fajta: **ELV_SABLON** (`rendszerek/yaml/elvek/`, 028-as
  migráció). A sablon: `sablon: {szoveg, parameterek, terulet}` + általános
  mintájú szabályok (`.. +A`, `.. 2NT`, `.. 3NT`), a paraméterek helyén
  `{sablon: KOD}` helyőrzővel.
* **Példányosítás** a hivatkozásban (`motor/sablon.py`, a feloldásban):
  `- {kod: FOGASMUTATAS, ervenyes: ["1M-2m-2M"], parameterek: {...}}`. A
  helyőrzők helyére az érték kerül, a helyzeti feltételbe az érvényességi
  helyzet (`ELV_KONTEXTUS`). Ugyanaz a sablon több helyen, más paraméterrel
  is beköthető. Az adatbázisban: `licitmenet.hivatkozas_beallitas`.
* **Terület (kiváltás)**: ahol az elv él, ott a kártyán MÖGÖTTE álló régi
  sorok nem élnek (a meglévő feltételes felülírás, `elnyomo`). Így pl. a
  KIBICEGY „1M-2♣-2M-3NT: leállás” fogás nélkül nem jön elő. A hivatkozásban
  `kivalt: false`-szal kikapcsolható.
* Új alapfüggvények: a kényszertár FOGÁS-ígérete (`Igeret.fogas`, a
  `fogas:` feltételből futás közben kiolvasva — a tárolt jelentés, így a
  jóváhagyások sem változnak), „le nem fedett színek” (a vonal természetes
  színei + a megmutatott fogások), `FOGASMUTATAS` helyzet, `FOGAS_MARADEK`
  és `NINCS_FIT` kéz-feltétel.
* A szerkesztőben: az „elvek” csoport a rendszerválasztóban; a sablon
  szövege, paraméterei, területe; a hivatkozásnál, hol él. A teljes
  leírásban („Letöltés”) ugyanez.
* **Próba-rendszer: MOHA_STAND_ELV** = a MOHA_STAND, de a MOHA_1M
  fogásmutató fejezete helyett az elv. A régi MOHA_STAND érintetlen.
* Mérés: `aranykeszlet rogzit --elotag "1H|1S,P,2C|2D,P,2H|2S,P" --egyezo 0,4`
  (célzott készlet, 2732 döntéspont), és az árnyék mód más rendszerrel:
  `KIBIC_ARNYEK=rendszer:MOHA_STAND_ELV`.

*Finomítás (2026-10-05 este, a szerkesztő megjegyzései után):* a
FOGASMUTATAS kiegészül arra az esetre, ha már minden szín le van fedve
(önálló nemes 4M, második szín, 6+ nemes ismétlése, kétség; a 6+ ismétlés
után 2 lappal a 3NT és a 4M közül a DD-mintavétel választ —
`dontesi_mod: MERLEGELO`). Második elv-sablon: **FELMENTES** (nem induló
erő az 1./2. kézben) — a sablon itt PASSZT ad a nyitási sorok előtt, és a
sora nem ad jelentést (`jelentes: {csak_dontes: true}`), hogy a passz az
ellenfélnek ne „rossz 11-12”-t jelentsen. Új alapfüggvények: üres figura
(`URES_FIGURA`), korrigált pont (`KORR_PONT`), kétszeres fogás, kétség.
A FELMENTES második fejezete (23:12): a 3./4. kéz minorja induló erő
nélkül — 10-11 ponttal csak 3-3 nemessel, rossz 12-vel 3-3 nélkül passz.

*Második finomítás (2026-10-05 késő este):* a FOGASMUTATAS-ban a fogás
mutatása csak 2+ le nem fedett szín mellett; egy le nem fedett szín: HELP
(negyedik szín), a válasz fogással 3NT, különben 4m — arra passz is lehet
(kvázi gémforsz: az 1M-2m csak 4 minorig kényszerít, `gf_hatar`). 6+ pikk
és kőrfogás: 3♥ (FOGAS-KOR); kétes fogás és 2 lap a partner 5-ösében: 3M.
A hézag-elvben gémforsznál a partner nyitott sávja két licit után
minimum + 4. Az összevetés `--teljes` módban teljes leosztásokat játszik
újra (a régi előtag okozta „lehetetlen” helyzetek eltűntek): a MOHA_STAND_ELV
és az új MOHA_STAND a 300 leosztásból 2-ben licitál másként
(`doc/elv-sablon-osszevetes-3-2026-10-05.md`).

*Paraméterezhető elvek (2026-10-12):* a szerkesztővel közösen írt
szótár és elv-lapok („A licithelyzet szótára”) alapján két új elv-sablon a
MOHA_STAND_ELV-ben: KENYSZER (a gémforsz megszűnése) és FORSZPASSZ_KIBIC
(kényszerítő passz). A szótár szabálya: a fogalom tény vagy tulajdonság,
kivétel nélkül — a jelentést elv mondja meg. Következő kör: invitkényszer, a
„határ alatti közbeszólás” közös mintája, szlemkényszer, kérés (transzfer),
kitérő licit; utána a licitstratégia.

*Döntés a szerkesztőé:* a MOHA_STAND-ot nyessük vissza (a fejezet helyett
a hivatkozás), vagy a mostani legyen MOHA_STAND_OLDSCHOOL, és a
MOHA_STAND_ELV-ből legyen az új MOHA_STAND.

### 1. fázis — A beégetett számok paraméterbe (viselkedés nem változik)

* A 1.2 pont minden száma paraméter lesz, alapértéke a mai érték, emberi
  leírással; a szerkesztő Elvek lapján olvasható és felülírható.
* A hézag-elv és a spirál „beépített elvként” megjelenik a szerkesztőben: a
  szövegük (a te megfogalmazásod) és a paramétereik — a logikájuk még kód.
* Ellenőrzés: aranykészlet-különbség = 0 (alapértékkel definíció szerint az).

### 2. fázis — A nyelv bővítése (viselkedés nem változik)

* `{param: …}` minden számmezőben (hossz, vesztő, összesen, gyorsütés,
  küszöbök), nem csak a pontnál.
* A konvenció-YAML `parameterek:` szakasza (2.2), az importban és a
  szerkesztőben.
* Súlyozott feltétel kényelmes YAML-alakja (`legalabb: {m: 2, felt: […]}`) a
  meglévő `LEGALABB` csomópontra.

### 3. fázis — A spirál adatként (az első valódi átköltözés)

* Új alapfüggvény: **lépcső-válasz táblázat** (tételsor, relé-kihagyás,
  leállás-licitek, a lépcső jelentése). Ugyanez szolgálja ki a kulcslap-
  válaszokat (0/3, 1/4, 2, 2+D), a Jacoby rövidség-válaszait és az Ogust-
  féle lépcsőket.
* A MOHA_SPIRAL egy paraméterkészlet; a Sylstandard és a HeavyClub spirálja
  csak más tételsor és kihagyási szabály — külön rendszerekben választható.
* Árnyékban fut, amíg az aranykészleten azonos; utána a `spiral.py` csak az
  alapfüggvényt tartalmazza.

### 4. fázis — A hézag-elv pontonként ELV-sablonba

* Új alapfüggvény-csomópontok: közös erő (A/F), gém(adu), játszható(fit),
  kényszer, partner-sáv-pozíció.
* Pontonként (0–5) költözik, mindegyik külön árnyékkal és aranykészlet-
  összevetéssel. A Python-hézag a végső tartalék marad, amíg minden pont át
  nem költözött.
* A szimulációs részek (DD-mintás végkontraktus-választás, büntető passz)
  alapfüggvények maradnak; az elv csak *hívja* őket (mint a mai MERLEGELO).

### 5. fázis — Fokozatos relevancia (kísérlet)

* Pontszám a jelöltekre; „hasonló helyzet” keresés a hézag-elv előtt.
* Csak árnyékban, és **mérve**: generált leosztásokon DD-vel összevetve a
  régi és az új licit eredményét (IMP-ben). Csak akkor élesedik, ha jobb.

---

## 4. Amit NEM javaslok

* A jelentés réteg fokozatossá tétele (lásd 2.5).
* A kényszertár, a propagálás, a DD és a szimuláció „adattá” tétele — ezek
  alapfüggvények; adatként leírva csak lassabbak és nehezebben ellenőrizhetők
  lennének.
* Általános programozási nyelv a YAML-ban (ciklus, értékadás). Ha egy elvhez
  az kellene, az új alapfüggvényt jelent, nem nyelvi bővítést.
* „Nagy újraírás”: minden fázis önállóan szállítható, és a kibic közben
  ugyanúgy játszik.

---

## 5. Kockázatok és ellenszereik

| Kockázat | Ellenszer |
|---|---|
| Az átköltözés közben megváltozik a licit | Aranykészlet + árnyék mód; élesítés csak nulla vagy jóváhagyott különbséggel |
| A sablonnyelv túl bonyolult lesz | A határvonal (2.1): ami számolás, az alapfüggvény |
| A paraméter-felülírás összekuszálja a rendszereket | Jóváhagyás (JAVASOLT → ELFOGADOTT); a szerkesztő megmutatja, melyik érték honnan jön (alap / rendszer / pár) |
| A „hasonló helyzet” félrevisz | Csak természetes sorokra; csak jelölt, nem győztes; csak mérés után |
| Lassulás | Az alapfüggvények ugyanazok; a sablonok előre feloldódnak (mint ma a rendszerek); a tempónorma (15–20 s) bőven elég |

---

## 6. Becsült méret

| Fázis | Méret | Viselkedés |
|---|---|---|
| 0. Biztosíték | 1 munkamenet | nem változik |
| 1. Számok paraméterbe + megjelenítés | 1 munkamenet | nem változik |
| 2. Nyelvbővítés | 1 munkamenet | nem változik |
| 3. Spirál adatként | 1–2 munkamenet | azonos (ellenőrizve) |
| 4. Hézag-elv pontonként | 3–5 munkamenet | azonos, vagy jóváhagyott különbség |
| 5. Fokozatos relevancia | nyitott | csak mérés után |

---

## 7. Döntések, amik a tieid

1. **Jóváhagyás**: a paraméter-felülírás is menjen JAVASOLT → ELFOGADOTT
   úton, mint a sorok? (Javaslat: igen.)
2. **Párszintű paraméter**: ki állítja — a pár maga, vagy csak a szerkesztő?
3. **Hasonló helyzet**: elfogadható-e, hogy a kibic néha „analógia alapján”
   licitál, ha a magyarázatban ez látszik („hasonló helyzet: … 82%”)?
4. **Kezdés**: indulhat a 0–1. fázis (a viselkedést nem érinti), vagy előbb
   a rendszer-tartalommal (licithelyzetek javítása) haladjunk tovább?
