# Moha-kör: licitelvek (emberi nyelven)

Ez a fájl a Moha-kör elveinek EMBERI leírása, ahogy a szerkesztő
(Sanyi) megfogalmazta. A gépi alak a `rendszerek/yaml` konvencióiban él;
ahol egy elv még nincs gépi alakban, azt itt jelöljük.

## Gémforsz (GF) helyzet — 2026-09-30

GF-ban vagyunk, ha a vonalunkon
* definiáltan gémforszt jelentő licit hangzott el, VAGY
* elfogadott géminvit után (az elfogadott invit automatikusan GF).

GI után (a szerkesztő pontosítása): gém vagy afölötti licit = elfogadás.
Ha NEM a saját összeemelt színünket mondjuk a GI szintjén (3M, 4m), és
van ez alatt licittér, az alatta mondott licit további invit (F1) — VAGY
P/C (lásd lent); a fölötte, de gém alatt mondott licit GF helyzetet
teremt.

### P/C a lezárás alatt — 2026-09-30

„1♦ - 1M - 1NT - 3♦ (GI káróban) - 3M: ez a 4♦ alatti szín, de a
válaszoló színe, 3 lapot ígér, nem F1, hanem P/C (passz vagy javíts). A
majorban levő parciális fit (7 lap) akár játszható is, és nagyobb
esélyű, mint a 4♦ leállás volna.”

Gépi alak: `konvenciok/moha_pc.yaml` (helyzeti elv: a partner GI-je után
a lezárás alatt a partner korábbi színe 3 lappal). A gép kiegészítése:
P/C-t a nem maximális lap mond (az ígért pontsáv alsó fele).

A P/C után (a szerkesztő): „a 3M teljesítéséhez csak 9 ütés kell, a
4m-hez 10 — kérdés, melyiknek nagyobb a teljesítési esélye. Nem az aduk
száma dönt alapvetően, hanem pl. hány plusz ütés szerezhető lopással,
mennyire fenyeget, hogy a mi magas lapjainkat lopja az ellenvonal.”

Gépi alak: ez ÍTÉLET, nem küszöb — a passz és a 4m MÉRLEGELŐ sor. Ha a
szimuláció engedélyezett, a gép mintát vesz a kényszertárból, és a
double dummy ütésszám + a pontozás alapján a nagyobb várható írású
végkontraktust választja (`merlegel.vegkontraktus_valasztas`); ez a
licit. Szimuláció nélkül a passz-elv marad (a 3M).

Gépi alak: a kényszertár jelöli (`ha: {gemforsz: true}`). Az invitet a
szabály jelöli (`invit: true`, vagy a szövegből: „invit”, „géminvit”).

Minor színben, csak GI helyzetben: ha 3-as szinten emeljük a partner
színét, az adu kijelölt, de a GI helyzet marad. Ha 4-es szinten emeljük,
az adut jelöl, GF-ra vált, és a 4m azonnal ORKC — de CSAK ha már
licitáltunk, és a 3-as szint szabad volt: 1♦-1M-2♦-4♦ ORKC (mondhattunk
volna 3♦-t, új színt, 2NT-t, 3NT-t), az azonnali 1♦-4♦ kizárás.
(Gépi alak: RKC.)

## Kulcslapkérdés (RKC) — 2026-09-30

* Összeemelt nemes mellett: az összeemelt színből a 4-es szint +1 lépcső
  (kőr: 4♠, pikk: 4NT).
* Összeemelt minor, GF: 4m = ORKC. Nem GF: 4m = invit.
* Összeemelt minor, bármikor: 4NT = opcionális ászkérdés és szleminvit
  (passz: nem szlem jellegű a lap — kevés ász, király, sok vesztő);
  válaszok 0-3, 1-4, 2 (nincs adu).
* Válaszok: 0-3 / 1-4 / 2 / 2+adu dáma. Utána: spirál (MOHA_SPIRAL).
* Kétértelmű válasznál (0-3, 1-4) a kérdező a ROSSZABB esetet tételezi fel
  (2026-10-05) — ezért gyakran nem mond szlemet. Ha a válaszolónál a
  JOBBIK eset van (több kulcslap), és a kérdező a szlem alatt állt le, a
  válaszoló mondja a szlemet. Minden ászkérdésre (RKC, ORKC) érvényes.
* Összeemelt kőr mellett a 4NT (a 4♠ RKC kihagyásával) = kulcslicit
  pikkben.

Gépi alak: `rendszerek/yaml/konvenciok/rkc.yaml`.

## Kulcslicit vagy ászkérdés? — a szerkesztő megfogalmazása, 2026-09-30

„Amikor egy kezet abból a szempontból vizsgálunk, hogy szlemgyanús-e —
ez kb. azonos a GF helyzettel —, akkor vagy egyértelműen igen, vagy
egyértelműen nem, vagy nem tudjuk eldönteni.

* Ha a sajátunkra egyértelmű igent mondunk, ÉS a partneré sem egyértelmű
  nem, akkor vagy mi kérdezünk ászt, vagy kulcslicitet (KL) mondunk.
  Akkor kérdezünk ászt, ha a partner lapjának erejére, jellegére nem
  vagyunk kíváncsiak, CSAK a kulcslapjaira, ÉS kedvezőtlen válasz esetén
  sem tartjuk kockázatosnak az 5M felvételét.
* Minden egyéb esetben jobb valamilyen szleminvitet adni, hogy a partner
  is nyilatkozhasson. A 4 vesztős fedőkereső GI valójában előrehozott
  szleminvit. A KL értelme is ez: szleminvit (akkor is, ha GI helyzetben
  adjuk le, és ezzel teremtünk GF helyzetet).
* Ha a mi kezünk nem feltétlenül szlem jellegű, DE nem is kizárt a
  szlem, ÉS a partner keze sem zárja ki, akkor legjobb, ha KL-t mondunk.
* Ha a partner keze kizárja, és a mienk is, akkor gémet mondunk.”

Pontosítások (2026-09-30):
* „3 vesztő a gémhez, 1-nél KEVESEBB a szlemhez”: 13 ütésből gémnél az
  1 hiányzó ütés vállalható kockázat, szlemnél nem (0 vesztőnél is
  érdemes a 13. ütésen gondolkodni, mielőtt 7-et vállalunk).
* A fedőnél nem a pont számít, csak az ász, a király, a sikén, a szingli.
* Kulcslicit: gém alatt lehet király (és szingli, sikén) is; gém fölött
  ász (legalábbis az először említett színben); ugyanabban a színben
  másodszor: ász és még valami (pl. szingli ász, ÁK).
* „Biztonságos 5M”: tudottan sok pont ((29)30 — a szlem alsó határa),
  VAGY tudottan kevés vesztő („2 vesztő a szlemhez”, vállalt kockázat).

Gépi alak: `rendszerek/yaml/konvenciok/moha_szlem.yaml` (kulcslicit, gém)
és `rkc.yaml` (ászkérdés). Maradék vesztő = saját vesztők − a partner
fedői a kényszertárból; ha a partner fedőt nem mondott, a gép a pontjából
becsül (ezt később finomítani kell); minden kulcslicit +1 fedőt mutat.

### Mikor ászkérdés, mikor kulcslicit — a kontroll

„Akkor kérdezünk ászt, ha a partner lapjára nem vagyunk kíváncsiak, CSAK
a kulcslapjaira.” Gépi alak: az RKC kérdés feltétele (`kontrollok: true`)
— minden külső színben van kontrollunk (ász, király, sikén, szingli).
Ha van egy színünk xx-szel vagy xxx-szel, két gyors vesztő lehet benne,
amit a kulcslapkérdés nem derít ki: ilyenkor kulcslicit.

### Fedő a rövidségből (splinter) — 2026-09-30

„Nem a pont számít. A splinter = rövidség. Ha olyan színünkben van a
szingli, amiből nálunk xxx van, akkor ez 2 fedő (nem 3 pont, nem 5,
hanem 7!). Ezért nem jó szingli ászt szinglinek licitálni, mert könnyen
lesz 11 pont abban a színben.”

Gépi alak: a partner tudott rövidsége (a kényszertárban legfeljebb 1
lap) mellett a saját vesztőimből annyi fedő, amennyi a rövidségén túl
van (xxx a szingli mellett: 2, a sikén mellett: 3). A SPLINTER
konvencióban szingli ásszal nincs splinter (`nincs: [CA]` stb.).

## Gyors-lassú elv (erővel lassú) — 2026-09-30

„1♥-2♣-2♥-3♥ — ÚJABB ELV: »gyors-lassú«: erővel lassú, azaz alacsonyan
kell tartani a licitet (Bánky Zoli szabály). A 4♥ bemondás leállás
volna: 5+ treff, 3 kőr és minimális gémerő. A 3♥ tehát plusz erő,
szleminvit.”

Gépi alak: `konvenciok/gyors_lassu.yaml` (helyzeti elv: gémforszban a
partner 5+ lapos színének első támogatása) és az alaprendszerben az
1M-2♣-2M-3M / 4M. „Minimális gémerő” a gépben: az ígért sáv alja + 2
pont (2♣ 12+ után: legfeljebb 14) ÉS legalább 7 vesztő; minden más plusz
erő.

A lassú emelésből a nyitó azt is tudja (a szerkesztő): „ha az új szín
után lassú módon 3M-t (sőt, néha 2M-t) mond, akkor az első színe NAGYON
JÓ, egy, de inkább 2 fedő lesz benne. Ha a nyitónak xxx van a válaszoló
első színében, azt a biztonságos 5M szempontjából ne tekintse 3
vesztőnek: a 2, de akár az 1 vesztő sem irracionális.”

Gépi alak: az 1M-2♣-2M-3M a treffben két felső honőrt kér (AK, AD, KD),
és a jelentése: a treffben legalább 1, valószínűleg 2 fedő
(`jelentes: {szin_fedo: {C: {min: 1, valoszinu: 2}}}`). A szlemjelleg a
biztos (1), a biztonságos 5-ös szint a valószínű (2) fedővel számol. A
„plusz erő” határa (15+ pont vagy legfeljebb 6 vesztő) a szerkesztő
szerint a válaszoló oldalán rendben; a nyitó oldalán a lassú emelés
fedőszáma nyitott (FP-ből és AP-ből más jön ki).

A dilemma (a 3♥ után a nyitó: ászkérdés vagy KL?) a fenti szlem-elvből
dől el: ászkérdés csak egyértelmű szlemjelleggel, biztonságos 5-ös
szinttel ÉS minden külső színben kontrollal; különben kulcslicit.

## A 2♣ indulás: kuka-válasz — 2026-09-30

* 2♣-2♥ = KUKA: NINCS 3 nano-pont (A = 3, K = 2, D = 1, B = 0), vagyis
  legfeljebb egy király vagy két dáma. Nem gémforsz. A kuka lap 7+ lapos
  színnel az alaprendszer 2♣-4♥ / 4♠ licitjét mondja.
* 2♣-2♦ = várakozó, pozitív (3+ nano-pont): gémforsz.
* 2♣-3♥ = ugyanaz, mint eddig a 2♣-2♥ (természetes kőr); ebben benne van
  az eddigi 3♥ (zárt szín) is.
* Nincs második negatív: 2♣-2♦-2M után a 3♣ is ugyanaz, mint bármelyik
  más szín bemondása.
* A kuka után a felvevő: a szan-bemondások végkontraktusok. „A színből
  mondhat gém alatt is 3M-t vagy minorból 4-et: ezek ERŐS INVITEK a
  vesztőütések alapján, egy bukással. A gémbemondás a vesztők alapján
  (az 1 ütés bizonytalansággal) önállóan gémerős — ehhez önállóan
  játszható adu kell, vagyis a partner sikénjével szemben is játszható
  (a többi bemondásra ez nem igaz). A 6 lapos adu ehhez kevés.”

* A kuka után a 2NT NEM végkontraktus (a szerkesztő, 2026-10-01): „ez
  ugyanaz a helyzet, ami az 1NT indulás után van, csak néhány ponttal
  feljebb. Az ottani ökölszabály az, hogy 7 pont alatt passzolunk — itt a
  pontfeltételt a kuka lap már elmondta —, de a kivétel még állhat: 5-ös
  nemes vagy 6-os minor színnel transzferrel álljunk le.”
  A káró-transzfer a 4♣, a teljesítése 4♦ (nem 5♦).
* 2♣-2♥-2♠ = F1, lapleírást kér: „a válaszolónak a leghosszabb színét
  kellene bemondania (4+). Ez jó, ha az indulónak 4-4-4-1, esetleg
  5-4-4-0 (minorral) lapja van: így megtalálhatja a jó adut; kényszerből
  persze lehet a végén 3 szan is. Hátránya: lehet, hogy a gyenge kéz lesz
  a felvevő.”
  Minor fitnél a 3NT és az 5m közül a szimuláció dönt (a várható írás).

Gépi alak: `konvenciok/moha_2c_kuka.yaml` (csak az eltérő sorok). Gém:
4M legfeljebb 3, 5m legfeljebb 2 vesztővel ÉS önállóan játszható aduval;
invit (3M / 4m): egy vesztővel több. Az invitre a válaszoló 1 fedővel
gémet mond (gépi kiegészítés).

### Önállóan játszható adu — kiszámolva

Legfeljebb 1 aduvesztő esélye a partner SIKÉNJÉVEL szemben (impassz
nincs, felülről húzzuk, az ellenfél a legjobban véd; az elosztások a
valódi valószínűségükkel):

| 6 lap | | 7 lap | | 8 lap | | 9 lap | |
|---|---|---|---|---|---|---|---|
| AKQJxx | 93% | AKQJxxx | 99% | AKQxxxxx | 96% | AKxxxxxxx | 90% |
| AKQTxx | 71% | AKJTxxx | 86% | AKJxxxxx | 74% | AQJxxxxxx | 90% |
| AKQxxx | 62% | AQJTxxx | 86% | AQJxxxxx | 74% | | |
| | | KQJTxxx | 86% | AKxxxxxx | 68% | | |
| | | AKQxxxx | 84% | AQxxxxxx | 27% | | |
| | | AKJxxxx | 52% | | | | |

A gép küszöbe: legalább 2/3 (ez épp a „8 lapos AK” szintje). A „7 lapos
3 figurás” nem egyforma: AKQxxxx 84%, de AKJxxxx csak 52% (a 10-es, 9-es
számít); a 6 lapos AKQJxx viszont 93%. A szerkesztő: „a 6 lapos színnél
kritikus, hogy az ellenfél kirövidíti a felvevőt — de maradjon a 6+.”
(A számítás a kirövidítést nem látja: csak a húzást számolja.)

## Folytatás „mint X után” — 2026-09-30

* 2♣-2♦-2NT: a válaszok mint a 2NT nyitás után, csak a ponthatárok
  különböznek (az alaprendszer szövege). Gépi alak: a sorban
  `folytatas: {mint: 2NT, pont: 2}` — a 2NT-ág szabályai élnek, a
  válaszoló pontjához 2-t hozzáadva.
* 2NT után Puppet Stayman (a KIBICEGY_STAND Stayman-szerű 3♣-ja helyett);
  így a 2♣-2♦-2NT után is. 3♦ = nincs 5-ös, de van (legalább egy) 4-es
  nemes; 3NT = legfeljebb 3-as nemesek. A 3♦ után TAGADÁS:
  „3♥ = NINCS 4 kőr, de nem biztos, hogy van négy pikk! Ezért a szanos NE
  ugorjon gémre, hanem mondja be a pikkjét, ha 4-es pikkje van. A
  válaszoló vagy 3 szant mond — ha nincs 4 pikkje —, vagy gémre emel. 3♠ =
  NINCS 4 pikk ÉS VAN 4 kőr (a szanos 4♥ vagy 3NT). 3NT = mindkettő.”
  (A 3NT-re a szanosnak mindig van fitje: gémet mond a 4-es nemesében.)
* Módosított Jacoby: 1M-2NT és 2M-2NT — minden ugyanaz, csak a „minimum”
  és a „nem minimális” az addig ígérthez mérve (az ígért sáv alsó fele a
  minimum). Gépi alak: `konvenciok/moha_jacoby.yaml`; a 2M-2NT
  `folytatas: {mint: 1M-2NT}`, az alaprendszer Ogust-válaszai helyett.
* A „minimum” a széles sávban (a szerkesztő: „a 16 pont túlzás; ilyen
  nagy sávnál a közepe helyett 35-40% jobb határ”): 7+ pontos sávnál a gép
  a 35%-nál vág (1M 11-21: 11-14 a minimum); keskenyebb sávnál a közepén
  (1M-2M 6-10: legfeljebb 8). Szabályonként felülírható (`hatar`).

### 2M-2NT: a szkórhelyzet dönt — 2026-09-30

„Itt sem a pontok számítanak elsősorban. Nagyon függ a szkórhelyzettől.
Mivel a 2M mansban »terrorista«, különösen igaz, hogy nem feltétlenül a
gém megtalálása a cél. Bellben viszont az. Mansban mérlegelni kell, hogy
a várható bukás kontrázva megéri-e az ellenfél gémjével szemben. A 2NT
»kérdés« arra is vonatkozhat, hogy érdemes-e az ellenfél gémjét később
lementeni: ha a válaszolónak sok M lapja van ÉS van saját rövid színe
(szingli, esetleg dubló), érdemes megkérdezni az indulót. Ha neki is van
rövidsége, akár gémet is mondhatunk nagyon kevés FP, sok AP és »jó fit«
esetén (»jó fit«: a partnernek rövidsége van a mi xxx színünkben). A
kérdező ponthatárait a szkórhelyzethez (az induló követelményeihez) kell
igazítani, de AP-ben érdemes meghatározni. És a szlemhelyzethez hasonlóan
mérlegelni kell a mentés lehetőségét (tudatosan vállalt kontrázott bukás
a várható nyereség érdekében).”

Gépi alak (`moha_jacoby.yaml`): 2NT, ha a saját AP + az induló ígért
MAXIMUMA legalább 25 (a zóna így magától számít: mans bell ellen az
induló 0-8, bellben 10-11); mansban ezen felül 4+ aduval és saját
szinglivel/sikénnel pontra való tekintet nélkül. A válasz után gém, ha a
maradék vesztő (saját vesztők − az induló biztos fedői, köztük a
rövidsége a mi xxx színünkkel szemben) legfeljebb 3; különben 3M. A
MENTÉS mérlegelése (szimulációval) még nincs meg.

## MOHA_SPIRAL — 2026-09-30

A Sylstandard spirálja (SYL_SPIRAL) tökéletes, de átlagos játékosoknak
nagyon nehéz, mert a színek sorrendje a licittől függően átrendeződik
(ott a tudott sikén kimarad, és a partner tudott 5-ös színe kerül az adu
után). A MOHA_SPIRAL-ban a színek sorrendje ÁLLANDÓ, nem rendeződik át,
és nem marad ki semmi: első helyen az adu, utána csökkenő sorrendben a
többi (külső) szín. A tudott sikén is benne van, és ásznak is, királynak
is számít.

A spirál (megerősítve): 1. adu dáma; 2. királyok a külső színekben
csökkenő sorrendben; 3. dámák ugyanígy; 4. bubik: adu bubi, majd a külső
színek. A kérdezés és a válasz ugyanaz, mint a Sylstandardban (lépcső:
1. „nincs nálam”, 2. „nálam van, de a következő nincs”, …).
Relék: L1 = relé (a következő tétel), L2 = szuper-relé (a következő
réteg elejére ugrik); a 4NT és az 5m (reléként is) = LEÁLLÁS (válaszként
persze nem).

Gépi alak (2026-10-04): `src/kibic/motor/spiral.py` — a kulcslap-válasz
után a menetből számolja a reléket és a válaszokat (a kulcslap-válasz
sorainak `jelentes.kulcslap` mezője jelöli a kiindulópontot). A kérdező
döntése a gépben: 2+ hiányzó kulcslap → leállás az 5-ös aduban; 1 hiányzó
→ kis szlem, ha az adu dáma megvan (ismeretlen dámát az L1 megkérdez, ha
a tagadó válasz nem megy az 5-ös adu fölé); 0 hiányzó → relé / szuper-relé
az adu dámáig és a szükséges külső királyokig (ahol nekem nincs, és nem
vagyok sikén): mind megvan → 7, valamelyik hiányzik → 6. A nagyszlem-ítélet
egyelőre csak a lapokat nézi (ütésszámolás nincs).

### Kivétel: ugrás a szlembe (a szerkesztő, 2026-10-05)

A kérdező ugrása (R2 vagy több relé-lépcső) alapértelmezésben a következő héj elejére
visz (R3: egy héj kihagyásával a második következőre — pl. a király-sor
folytatása helyett a bubik héjának eleje). DE ha az ugrás szlem-szintre
(6/7) történik egy POSSZIBILISEN JÁTSZHATÓ színben — összeemelt szín, vagy
amit valaki önállóan játszhatóként licitált —, az a szlem bemondása:
passzolandó. Példa: 1♦-1♥-3♣-3♦-3♠(4. szín, GF)-3NT-4♣(ORKC treffben)-5♣
(2 kulcslap + adu dáma)-6♦: passz. Értelme: az ORKC a minor K/D-jét deríti
ki (fedőütés, ami a kényszertárból hiányzik a szlemhez); utána a szlem
ugrással bemondható a "tényleges" színben (nemesben is). A gépben
játszható szín: a vonal ismert össz-hossza 7+, vagy valamelyikünk 6+
lappal licitálta; a 6NT/7NT ugrás is leállás. Az R1 ilyenkor is relé.

## MOHA_3NT_4M — 3NT után 4m ORKC — 2026-10-04

A partner 3NT-je után a 4m GF + ORKC (nem invit, nem leállás). A-ág: a
minort a vonalunk 4+ lappal ígérte, VAGY a 3NT előtt SZÍNKÉNT licitálta (nem kérdés, relé,
transzfer, lépcsőválasz — a licit jelentése legalább 2 lapot ígér benne) (indirekt
ígéret: 1♠-2♣-3NT-4♣ — a 2♣ lehet rövid is, de az ismétlés hosszú treff;
a megállapodás a GF és az ORKC) → ORKC abban. B-ág: 4♦ = ORKC káró; 4♣
(5+ treff) kétirányú: 4♦ treff tetszik, 4♥ káró tetszik, 4♠-tól kulcslap
treff aduval (a káró dáma nem számít: 4♠ 0/3, 4NT 1/4, 5♣ 2 dáma nélkül,
5♦ 2 + treff dáma). Az A-ágon és a 4♦-re az 5m definíció szerint 2 kulcslap
+ adu dáma, a „tetszik” előtt. Válasz: 1. lépcső „tetszik” (utána a relé — pl. 4♥ — kérdezi
a kulcslapokat), majd 0/3, 1/4, 2, 2+D; utána spirál. Megállapodott nemes
adu mellett nem él. Gépi alak: `rendszerek/yaml/konvenciok/moha_3nt_4m.yaml`.

## Az alert a megállapodást mondja, nem a lapot — 2026-10-01

A szerkesztő (a Walsh 1♣-1♦ két sora kapcsán): „az alert a konkrét lapot
mondja el, nem a rendszer (konvenció) leírását.” Javítva kétféleképpen:
a Walsh 1♣-1♦ egy sor lett (gyenge VAGY erős ág, egy közös alerttel), és
a gép általában is az adott menetben az adott licitre vonatkozó ÖSSZES
szabály szövegét mondja el alertként — így a győztes sor szövege nem
árulhatja el, melyik ágba esik a kéz.

## 1M-2m gémforsz — 2026-10-04

A Moha-körben az 1M-2m EGYÉRTELMŰ gémforsz (2♣: lehet dubló; 2♦: 5+ káró),
a 3m viszontválasz után is. Ezért az 1M-1NT lehet rossz 11 FP is, a nem
rossz 11 már 2m. (A KIBICEGY-ben az 1M-2♦ 11+, egy körre kényszerít —
"GI+", 4m-ig; ott a nyitó 3m-je redukálja GI-re. A Moha-kártyán a MOHA_1M
írja felül.)

A nyitó: 2M = semmit nem ígér (többlethosszt sem; ezért a válaszoló
emelése utána 3+ lapot ígér); 3NT = fogás a nem licitált színekben (a
partner 5-ös színe felér egy fogással), nincs plusz erő; 2NT = ugyanez
plusz erővel; 2♥ (1♠ után) = 4-es kőr, nincs plusz erő (plusz erővel 3♥);
2♠ (1♥ után) = riverz: 4-es pikk és plusz erő; 3m = plusz erő, 4+ a
színben; 3♠ (1♥ után) = önsplinter: 0-1 pikk, valószínűleg 6+ kőr — nem
elsősorban a minorra (minor találkozásnál nincs splinter), nyitva hagyja a
3NT-t. Erre a válaszoló: sok ponttal és több fogással a pikkben 3NT; kőr
fittel 4♥; különben 4m (természetes, nem ORKC: nincs összeemelt minor).
Plusz erő a gépben: 15+ FP. Gépi alak: `konvenciok/moha_1m.yaml`.

### A várakozó 2M után — 2026-10-05

A szerkesztő leosztása: 1♠-2♣-2♠-3♦. A válaszoló új színe a várakozó 2M
után TERMÉSZETES, és FOGÁST mutat a színben — nem ígér plusz erőt, négy
lapot sem (a szerkesztő javítása: plusz erő nélkül, gyenge negyedik
színnel különben nem lenne licit). Gémforsz marad; nincs színtalálkozás,
az irány a 3NT. Ugyanígy: 1♠-2m-2♠-3♥, 1M-2♦-2M-3♣, 1♥-2m-2♥-2♠ (0-2 lap
a nyitó nemesében — 3 lappal az emelés jön). Mindkét nem licitált színben
fogással a válaszoló rögtön 3NT (nincs plusz erő) vagy 2NT (plusz erő),
mint a nyitó. A minor ismétlése: 1M-2♣-2M-3♣ = 5+ treff, 1M-2♦-2M-3♦ = 6+.

A nyitó: fogással a még nem licitált színben 3NT („adja magát”); fogás
nélkül 6+ nemessel 3M (a 2♦ mellé 3+ káróval 3♦). A 3M után a válaszoló:
fogással a kőrben is 3NT, nemes fittel (2+) 4M, hosszú treffel 4♣ (a
treff hosszabb a kárónál).

**Elv-sablonként (2026-10-05, próba):** a fogásmutatás a FOGASMUTATAS
elv-sablon (`rendszerek/yaml/elvek/fogasmutatas.yaml`): egyetlen általános
leírás, a MOHA_STAND_ELV próba-rendszer `1M-2m-2M` után köti be. Ott a
MOHA_1M fogásmutató fejezete ki van zárva; a „saját szín és fit” fejezet
(a kibic javaslata) mindkét rendszerben él. A sablon a szerkesztő szavain
túl egyet tesz hozzá: plusz erővel (15+) a lassú 2NT (gyors-lassú elv).

Miért licitált a kibic 3♠-t 3NT helyett: a 3♦-re nem volt sora, és a
nem értett partner-licitre a hézag-elv (4. pont) a sávja alsó felében a
legolcsóbb fit-licitet adja (gémforszban ez kényszerítő, teret hagy). A
magyarázatkérő ablakot nem a partner-kibic nyitotta (a saját vonal
licitjére sosem kérdez), hanem az ellenfél kibicjei — ők sem értették.

### Rossz 11 a válaszban — 2026-10-05 (este)

A szerkesztő: a rossz 11 pont nem 2/1, hanem 1NT (1M-1NT), és ilyenkor 3
lapos nemes támogatás is lehet (szingli, sőt sikén is). „Rossz”: üres dáma
vagy bubi (ász és király nélkül, legfeljebb 3 lapos színben — Dxx, Bxx,
Dx, D, DBx), vagy rossz lapminőség. A jó 11 marad 2♣/2♦. (A tíz példából
kilenc így egyezik a szerkesztő ítéletével; a ♠DB5 ♥9 ♦K932 ♣AB1054-ot a
szerkesztő jónak tartotta, a szabály rossznak — a DBx üres figura.)

A 2M után 3 lapos nemes támogatással emelés (a gyors-lassú elv szerint),
nem a minor ismétlése: a 3♣ / 3♦ ismétlés 0-2 lapot ígér a nyitó nemesében.

### Ha már minden szín le van fedve — 2026-10-05 (este)

A várakozó 2M csak a plusz erőt tagadja, a többlethosszt és a két színű
lapot nem. Ezért ha a partner már minden színt lefedett (pl. a lassú 2NT),
a 3NT előtt még elmondható (FOGASMUTATAS elv-sablon):

* önállóan játszható nemes szín: 4M;
* második szín (4+) szinglivel vagy sikénnel mellette: 3 a második színben
  (a 6-4 is — a szerkesztő: ♠KB10872 ♥10 ♦75 ♣AK75 után 3♣);
* 6+ lapos nemes: még egy nemes licit (3M) — a partner 2 lappal a DD-
  mintavétel szerint választ 3NT és 4M között (szimuláció nélkül: 4M);
* később (ha már leírtam a lapom) rövid szín, amit csak a partner fogása
  fed: „kétség” — a színt licitálom; a partner kétszeres fogással 3NT
  (pl. ÁDB), különben a nemes gém az 5-2 fitben.

Ha még van le nem fedett szín, és nálam a fogás, marad a 3NT (az eredeti
1♠-2♣-2♠-3♦ leosztás: ♥ÁK10-zel 3NT).

## FELMENTÉS — nem induló erő az 1./2. kézben — 2026-10-05 (este)

A szerkesztő: „a 8 vesztős lapok csak 13 FP-tal indíthatók, a 4-4-3-2
elosztásnál nem számítható fel hosszúsági pont. Az üres Dxx és Bxx kapjon
-0.5 vagy -0.25 pont büntetést; rossz 11-12 pont se legyen induló erő — az
első és második helyen! 3.-4. helyen viszont — ennek fejében, kihasználva a
Drury helyzetet — gyengébb lappal is induljunk el.”

Gépi alak: a FELMENTES elv-sablon (`rendszerek/yaml/elvek/felmentes.yaml`),
a MOHA_STAND és a MOHA_STAND_ELV is hivatkozik rá. Az 1./2. kézben passz:

* 8+ vesztővel (a Moha-féle vesztőszámítás) 13 FP alatt (`VESZTO8_MIN_FP`);
* 11-12 FP-tal, ha rossz a lapminőség, vagy van üres figura (levonás:
  `URES_LEVONAS`, alap 0.5) és a korrigált pont (FP + hosszúsági pont az
  5+ lapos színekért − levonás) a küszöb alatt van (`KORR_KUSZOB`, alap 13).
  A hosszúsági pont így a 4-4-3-2-nél magától nulla; a 6-4-es 12 pontos lap
  egy üres bubival is indul.

A passz az ellenfélnek továbbra is csak passz (a sor nem ad jelentést). A
3./4. kézben a nemes nyitás csökkentett erejű (MOHA_1M, 4 lappal is).

**A 3./4. kéz minorja (2026-10-05, 23:12):** „ha nincs induló erő, max rossz
11-12, és nem lehet 2 minorral indulni — mert nincs 6 db —, akkor 4-es
major hiányában 10 pont alatt ne, 10+ ponttal is csak akkor, ha van 3-3
major.” Gépi alak (FELMENTES, új fejezet): 10-11 ponttal 3-3 nemessel 1♦
(4+ káró) vagy 1♣ (4+ treff); rossz 12-vel 3-3 nemes nélkül passz. Ha
gyenge 2♦ lehet, az nyer.

## Késő esti finomítások — 2026-10-05 (21:31 után)

**A Moha-kártya hiányzó konvenciói.** A 09-29/30-án eldöntött MOHA_2MAJOR,
MOHA_NONFORCE_1NT és MOHA_FEDOKERESO egyik kártyán sem szerepelt; most a
MOHA_STAND és a MOHA_STAND_ELV is hivatkozik rájuk, és az új MOHA_2D-re is.
Ez az aranykészlet eltéréseinek fő forrása: a „figurapontok legalább fele a
színben” szabály miatt 28 gyenge kettes lett passz.

**Gyenge kettesek zónánként** (MOHA_2MAJOR, MOHA_2D — azonos táblázat):

| zóna | pont | szín |
|---|---|---|
| csak ők beliben (mans-bell) | 0-8 | 5-7 (káró: 5-7) |
| senki (mans-mans) | 5-10, nem jó lappal 11 | 5-7 |
| mindkét vonal beliben | 8-10, nem jó lappal 11 | 6-7 |
| csak mi beliben | 10-11, nem jó lappal 12 | 6-7 |

„Nem jó”: rossz lapminőség, vagy üres figura és a korrigált pont 12,9
alatt. **A „fele a színben” számolásakor** a máshol álló üres dáma/bubi
(legfeljebb 3 lapos színben, ász és király nélkül) színenként 0,5 ponttal
kevesebbet ér — a szerkesztő: a színben lévő Á, ÁB vagy KD 4-5 pontját ne
„üsse ki” három Dxx, vagy egy Kxx és két Bxx. A szerkesztő példái: ♠ÁKDB104 ♥943 ♦1063 ♣B → 2♠ mindenhol, kivéve
mans-bellben; ♠D107 ♥ÁDB743 ♦8 ♣D93 → 2♥ ugyanígy; ♠D86 ♥D ♦ÁDB942
♣B104 (12) → 2♦ (csak mi beliben, mert 12 pont csak ott fér bele).

**Rossz / nem jó 11 a válaszban.** „Nem jó”: rossz lapminőség, vagy üres
figura és a korrigált pont 11,5 alatt. A nem jó 11:
* 3-4 lapos támogatással és 2+ fedőütéssel: **1M-2M** (az invitet
  elfogadja; a partnernek ez maximális egyszerű emelés, 6-10) — de 7+ lapos
  minorral 2m (♠B53 ♥— ♦DB108653 ♣ÁK9: „túl hosszú a káró”);
* különben 1M-1NT (3 lapos támogatással is, ha nincs 2 fedőütés).

**FOGASMUTATAS (MOHA_STAND_ELV).** A fogásmutató licit csak akkor jön, ha
legalább két szín még nincs lefedve; ha csak egy, az a negyedik szín:
**HELP** (fogást kér abban a színben). A partner fogással 3NT, fogás nélkül
a legolcsóbb minor-fit (4m), és arra a HELP-kérő passzolhat (15 pontig).
6+ pikkel és fogással a kőrben (1♠-2♣-2♠-2NT-3♥: a 2♠ tagadta a 4-es kőrt,
tehát a 3♥ fogás); erre a partner kétes káró-fogással és dubló pikkel 3♠-t
mondhat. Kőr és pikk felcserélve ez nem működik: ott 3M.

**Kvázi gémforsz.** Az 1M-2♣/2♦ gémforsz csak 4 minorig kényszerít: ha a
licit eljutott a 4♣-ig, a hézag-elv már nem tekinti kényszerítőnek a
helyzetet (passz is lehet). Ezen felül a hézag-elv a gémforszban fékez: ha a
partner sávjának nincs felső határa, de már legalább kétszer licitált, a
felső határ legfeljebb a minimum + 4 (`GF_FEKEZES`) — a 37 pontos „F” így
nem jön ki, ha a partner a harmadik körben fékezett.

**Újrajátszás.** Az összevetés eddig pontonként, a RÉGI menet-előtagon
dolgozott, ezért olyan helyzeteket is mutatott, amelyekbe az új rendszer el
sem jut (pl. 5♦ után 5♥). Mostantól az `osszevet --teljes` az eltérő
leosztásokat végiglicitálja, és a két teljes menetet a négy lappal mutatja.

## 1♥-1♠-3♥ után — 2026-10-04

A forrás „3♠ | GF és fit!” sora a KŐR fitet jelenti (2+ kőr a 6+ mellé).
A gyors-lassú elv szerint: 3♠ = szlemérdek (13+ FP vagy legfeljebb 6,5
vesztő), kulcslicitet kér; 4♥ = leállás.

## Szlem a hézag-elvben, kulcslicitre kulcslicit — 2026-10-04 (este)

* Megállapodott adu nélkül, ha a hézag-elv 3NT-t mondana, de a közös erő
  szlemet ígér (szanban 33+, nagyszlem 37+): a felső határral 4NT
  (kvantitatív szleminvit), az alsóval 6NT, alsóval szlem + felsővel
  nagyszlem: 5NT, alsóval nagyszlem: 7NT. Invitálni csak a partner
  limitált (legfeljebb 6 pont széles) sávjával. A kvantitatív 4NT-re a
  sávja felső felével 6NT, az alsóval passz (MOHA_SZLEM).
* Kőr adu mellett a pikk-kulcslicit a 4NT (a 4♠ az RKC); gém fölött ász
  kell, és a szlem ne legyen kizárt (a vesztő-elv szerint). Ha kizárt: 4♥.
* A P/C utáni passz / javítás csak GI-helyzetben (gémforszban nem).
* Negatív kontra erős lappal (15+): külön változat, hogy a magyarázat ne
  "minor szín(ek)" legyen.

## Szín-szlem a gém fölött — 2026-10-05

1♥-1♠-3♥-3♠-4♦-4NT(pikk-kulcslicit)-5♥ után a válaszoló nem passzolhat,
ha a kényszertár szerint a közös erő alsó határa is 30+ (szín-szlem):
ha a felső határ 35+ (nagyszlem nem kizárt), újabb kulcslicit (pl. 6♣ a
treff ásszal), különben 6♥. A 6♥ vagy 6NT dilemmája csak párosversenyen
(MP, esetleg BAM) jön elő: ha nem kell lopás a teljesítéshez, a szan +10
ponttal nyerő — ezt a kényszertárból vett minta DD-elemzése dönti el.
A partner gém fölötti, nem adu-színű licitje (kulcslicit) nem passzolható.

## Paraméterezhető elvek: kényszer és kényszerítő passz — 2026-10-12

A szerkesztővel közösen írt szótár („A licithelyzet szótára”) és két
elv-lap alapján, a MOHA_STAND_ELV próba-rendszerben (a MOHA_STAND
változatlan). A szótár szabálya: a fogalom egyszerű tény vagy tulajdonság,
kivétel nélkül; hogy „ilyenkor mit jelent”, azt egy elv mondja meg.

**KENYSZER** (`elvek/kenyszer.yaml`) — kényszer alatt nem passzolunk. A
gémforsz megszűnik, ha a licitből közösen kiderül, hogy nincs esélyes gém:
fogást kértem (HELP), a partner nem mutatott benne fogást, nemes fit nincs
(4-3 sem: mindkettőnknél 3+, együtt `NEMES_FIT_MIN` = 7), és a pontom + a
partner ígért minimuma `MINOR_GEM_ERO` (27) alatt van → passz. Ez váltja a
FOGASMUTATAS régi „HELP-PASSZ” sorát (egy fogalom — egy hely).

**FORSZPASSZ_KIBIC** (`elvek/forszpassz_kibic.yaml`) — kényszerítő passz:
az ellenfél a gémünk fölé licitál, és (a) csak mi vagyunk beliben, vagy (b)
elfogadott invit, vagy (c) gémforsz volt a vonalunkon. Elsőként: kontra
`X_GYORS_MIN` (2) gyorsütéstől; továbblicit `LICIT_ADU_MIN` (10) közös
aduval és kevés védőütéssel; különben passz = „döntsd el”. A partner
kényszerítő passza után nem passzolunk: továbblicit (ugyanígy), különben
kontra.

Közös minta (megerősítve): ha az ellenfél a kényszer határa alá szól be, a
passzunk kényszerítő (erősebb), a határ szintjén tett licit a minimum.
Következő kör: invitkényszer, a közös minta, a szlemkényszer határa, a kérés
(transzfer) és a kitérő licit, a kényszerítő passz két változata
(szlemzóna; indulást kérő új szín, ha már mentettek).

### Egy elv — egy sor mindkét nemesre (2026-10-19)

A szerkesztő észrevétele: a FOGASMUTATAS-ban a „3NT vagy 4M” és a „kétség
után 4M” sorok külön 4♥ és 4♠ alakban álltak — ez ellentmond az elv
céljának. Az ok a nyelv hiánya volt: a 3NT sorában az M nem kötődhetett a
licitből. Új nyelvi elem: ha egy színváltozó csak a feltételben szerepel,
jelentése „van olyan szín, amelyre igaz”. Így a sorok 4M alakúak (6 helyett
3).

**A „6+ pikk mellett 3♥” sor is általános lett** (a szerkesztő, 10-19,
visszavonva a korábbi aszimmetriát): gémforszban (vagy kvázi gémforszban)
a 3NT alatti szín CSAK FOGÁS is lehet — természetes, de nem feltétlenül
4-es. Ezért 6+ lapos nemes mellett, ha minden szín le van fedve, az új szín
biztos fogást mutat (ász, kétszeres, vagy 3+ lapos: Kxx, KB3; a Kx nem —
így a 10-05-i ♠ÁB9432 ♥432 ♦K7 ♣KB után a 3♠ marad), olyan színben, amit
sem én, sem a partner nem mondott. A partner kétes fogással és 2 lappal a
nemesben visszaválaszthatja a nemest.

## A limitált lap új színe — lezárás (2026-10-19)

A szerkesztő: „az 1 szanos 2. megszólalása gyenge lapot, de hosszú
(általában 7+) színt ígér” — jó minőségű 6-os (ÁKD vezetésű) is elég,
legfeljebb dubló a partner nemeséből. Gépi alak: a LIMITALT_UJ_SZIN
elv-sablon (`elvek/limitalt_uj_szin.yaml`), a MOHA_STAND és a MOHA_STAND_ELV
az 1M-1NT után köti be (`ervenyes: ["1M-1NT"]`); más helyre ugyanez a leírás
köthető (a fedőkeresőbe nem: ott a limitált kéz új színe kérdésre felel).
Paraméterek: HOSSZ_MIN 7, HOSSZ_MIN_JO 6, JO_FOHONOR 2, LEGFELJEBB 3♠,
SZAN_GYORS 3. A partner passzol, kivéve, ha a 3NT-hez meg tudja számolni a
9 ütést: figura a színben (pl. szingli K), fogás minden más le nem fedett
színben, legalább 3 gyorsütés. Az aranykészlet #57: ♠103 ♥B4 ♦10
♣ÁDB109872, 1♥-1NT-2♥ után 3♣ (eddig: 4♦ „splinter”).

## Természetes alap, szan a blokkra, kétszínű licitek, exclusion — 2026-10-21

A szerkesztővel közösen, a 13:25–17:44 közötti leosztások alapján.

- **Természetes alap (TERMESZETES_ALAP, elv):** a megállapodás nélküli
  színlicit természetes: az első szín 5+, a később mondott új szín 4+. A
  kétszínű partner mellett a jobb fitbe igazítunk; egyforma fitnél az első
  színbe — nemes, majd minor sorrendnél a minorban maradunk (a minor
  hosszabb is lehet). A sorok csak a megértést szolgálják.
- **Leaping Michaels** a (2M)-P-(3M) és a (3M) után is (4m = a minor és a
  másik nemes). **Szokatlan 4NT**: az ugró szan a két legalacsonyabb nem
  licitált szín (a nemes blokkra: a két minor). A **nem ugró szan**
  természetes: a (2M) után 2NT 16–19 (mint az 1NT-közbeszólás); a (2M)-P-(3M)
  és a (3M) után 3NT 16+ fogással; kontra, majd szan: 19+ egyenletes.
- **Kétszínű licit vesztők szerint** (Michaels, Leaping Michaels, szokatlan
  szan): 5-5 lappal legfeljebb 6,5 (mi mansban, ők bellben) · 5,5 (senki) ·
  5 (mindenki) · 4 (mi bellben, ők mansban); a minorra adott Michaels 5-4-gyel
  eggyel kevesebb. A 6-4 és a 7-4 NEM Michaels. A Michaelsre az ugró választás
  BLOKK (4 lap, a törvény szerint) — a Michaels-licitáló passzol (a teljes
  válaszrend lent, a Michaels.pdf szerint).
- **Közbeszólás = nyitás (KOZBESZOLAS_NYITAS):** a közbeszóló partnerének nem
  ugró új színe azt jelenti, amit a nyitás után ugyanaz a válasz: a magasabb
  szín ugyanazon a szinten F1; a 2-es közbeszólás után a 3-as szintű
  alacsonyabb szín (a 2/1 megfelelője) kvázi gémforsz 4m-ig; az 1-es
  közbeszólás után a 2-es szintű alacsonyabb szín („1-re 2”) enyhébb kvázi
  gémforsz: a saját színe 3-as szintjéig kötelez. A közbeszóló viszontválasza
  a saját színében várakozó (mint az 1M-2m-2M).
- **A kvázi gémforsz a 4m-nél megszűnik** (ha az adu nem nemes): minimális
  lappal passz. A gémforsz megszűnésének elve (KENYSZER) a kvázi gémforsz
  határán túl is él.
- **Multi-Landy 2♣-ra:** 2♦ = egyforma nemesek (mondd az 5-öst), 2♥/2♠ = a
  hosszabb nemes, 2NT = erős kérdés, 3m = természetes.
- **Információs kontra a minorra:** legalább 4-3 a nemesekben. **18+ ponttal**
  bármilyen elosztással kontra (az egyenletes 16–19 fogással 1NT marad);
  kontra, majd saját szín: 18–21, 5+; a kontrázó emelése az 1-es szintű
  válaszra: 2M 16–18, 3M 19–21, 4M 22+.
  **Felmentés:** induló erő nélkül (9–11) is kontra a minorra 8-9 nemes
  lappal (4-4, 5-4, 4-5), ha a kontrázott színben legfeljebb 2 lap van és
  legalább 2 kontroll (rossz pontokkal nem).
- **A Michaels teljes válaszrendje** (a szerkesztő feltöltött leírása):
  minorra adott Michaels után 2M lezárás (0–11), 3M blokk (4 lap), 4M
  játékra, az ő színük gém- vagy szlemérdekeltség (16+), az új minor 6+
  természetes, 3NT játékra; nemesre adott Michaels után a másik nemes a
  legolcsóbban lezárás, 4M játékra (10+ és 4 adu, 12+ és 3 adu), **az ő
  színük gémforsz és szleminvit** (13+), 2NT = mondd a minorod, 3m 6+
  természetes. A Michaels-licitáló az ő színükre 0–10 ponttal a legolcsóbb
  színét mondja, minden más 11+ és gémforsz; a blokkra passzol.
- **A kvázi gémforsz határán** (4m) a partner megállt: minimális lappal passz.
- **Exclusion RKC:** megállapodott nemes adu mellett az ugrás az 5-ös szintre
  a sikén színben = kulcslapkérdés az ott levő ász nélkül (a partner színében
  is); 0/3, 1/4, 2, 2+D. Feltétel: a szlem nem kizárt, és az 5-ös szint nem
  kockázatos (a két kéz vesztőinek összege legfeljebb 13).
- **„Udvariassági” kulcslicit:** a partner kulcslicitjére gém fölött, az adu
  5-ös szintje alatt ász mutatása = szlem-HAJLANDÓSÁG (helyet hagy a
  partnernek az ászkérdésre). A gém bemondása kétséget, az ászkérdés
  bizonyosságot fejez ki. Megállapodott adu mellett a negyedik szín elve nem
  él (ott az új szín kulcslicit).

## Fogáskérés és a szan-gém fogás nélkül — 2026-10-22

- Szan-gémet (3NT) a kibic csak fogással mond az ellenfél színében: a
  kimondottban, és abban a nemesben is, amit a kontrájuk ígért („1♥-ünk
  kontrája pikket ígér”). A partner szanja vagy büntető kontrája is fogás.
- Fogás nélkül, ha 3NT alatt van hely (2-es szinttől), az ő színük bemondása
  FOGÁSKÉRÉS (elv: FOGASKERES): a partner fogással vagy fél fogással (Dx,
  Bxx, xxxx) 3NT-t mond, anélkül a közös fitbe megy (menekülőút, pl. 4♦ a
  dubló ásszal). Ahol a licitnek más megállapodott jelentése van (pl. a
  felüllicites emelés, Lebensohl), ott nem fogáskérés.
- Ha a kérésre nincs hely: 3NT fogás nélkül is, ha együtt valószínűleg 5+
  lapunk van a színükben, gémerősek vagyunk (24+), nincs 8 lapos nemes fit,
  és az 5m sem jobb (8 lapos minor fit 27+ ponttal).
- Leaping Michaels a minor blokkra is: (2♦)/(3♦) után 4♦, (3♣) után 4♣ =
  mindkét nemes 5-5 (a vesztő-határral); a partner a jobb nemesét mondja.

## Minor ORKC: leállás 4NT-ben — 2026-10-23

A 3NT utáni 4m definíció szerint ORKC marad (nem kap pont- vagy fitfeltételt).

A negatív kulcslap-válasz után:

- **A kérdező:** ha a minorban legfeljebb 8 lapos fitről tud (a saját lapjai és a partner ígért minimuma együtt), és a vonal már licitált szant (a 4NT reális alternatíva), akkor 4NT-vel áll le, különben 5m-mel.
- **A válaszoló a 4NT-re:**
  - ha van még nem mondott többlethossza a minorban, és a lapja nem szan jellegű (van 0-1 lapos színe), 5m-re javít;
  - ha a kétértelmű válaszának (0/3, 1/4) a jobbik esete igaz, szlemet mond (ez a 2026-10-05-i szabály).

Gépben: `motor/spiral.py`, teszt: `tests/test_spiral_4nt.py`.

### NYITOTT ötlet: kérdezés minorban, szlem nemesben

Néha hasznos a minorban kérdezni ászt, és a végén nemes szlemet játszani, például ha a kérdező lapjánál a ♣K vagy a ♦K különösen fontos. Ehhez a kulcslap-kérdés után a végső színt külön lépésnek kellene választania: a legjobb ismert fitet (8+ lapos nemes fit esetén a nemest), nem automatikusan a kérdezett minort. A szerkesztő példákat keres rá.

## Ki kérdezhet a 3NT után, a nyitó második licitje, a negyedik színre adott szan — 2026-10-23

- **A hézag-elv** (a tartalék döntés, amikor egyik szabály sem illik a lapra) nem választ mesterséges (alertos) licitet. Ilyet csak a szabály adhat, a teljes feltételével, mert a partner a megállapodás szerint érti (#48: a 4♦ ORKC volt, #138: a 4♣ splinter).
- **3NT után 4m (ORKC):** az kérdezhet, akinek a saját pontjaival a partner ígért *alsó* határával számolva sem kockázatos az 5m (27+), a *felső* határával számolva pedig szlemerő jön ki (31+); VAGY a vesztői szerint: legfeljebb 4,5 vesztő, misfitnél (0–1 lap a partner tudottan 5+ lapos színében) legfeljebb 4.
- **A negyedik szín kvázi gémforsz** (4 minorig kényszerít; eddig F1 volt).
- **Lassan szlemeséllyel:** gémforszban, ha a partner felső határával szlem lehet (30+), a hézag-elv nem ugrik gémbe, hanem a legolcsóbb természetes licitet mondja (a saját 6+ lapos szín vagy a partner 5+ lapos színének támogatása).
- **A nyitó egyszerű új színe** (nem riverz) 1-re 1 vagy 1NT válasz után: 12–16 pont (rossz 17). (A saját szín egyszerű ismétlésének sávja nem változott: NYITOTT.)
- **A nyitó ugró új színe** (nem riverz), ahol az egyszerű új szín nem kényszerítene: 17–19 pont, limitált. 5-5-tel jó 16 is, ha legfeljebb 5 vesztő van.
- **A nyitó ugrása a saját színében** (második licitként): 17–19 pont, limitált, jó 6+ színnel (szinglivel is játszható: legfeljebb 1 vesztő a színben).
- **A negyedik színre a válaszoló a teljes laperejét mutatja:**
  - Ha a legolcsóbb szan 3NT alatt van, és gémforszban vagyunk: a 2NT plusz erő (lassú), az ugrás a 3NT-be minimum (gyors).
  - Ha a legolcsóbb szan a 3NT: a 3NT az ígért sáv alja (12–15, rossz 16), a 4NT a teteje (16, rossz 17), limitemelés, nem kényszerít.
  - Színnel az ugrás a minimum (szlemérdek nélkül), de csak tudott 8+ lapos fittel (minorban 9+); különben a legolcsóbb színlicit jön.

Teszt: `tests/test_szerkeszto_2026_10_23.py`.
- **Fedőkereső megfelelő mellékszín nélkül:** ha nincs 3+ lapos, 2,5–3 vesztős mellékszín, a fedőt a legolcsóbb 2 vesztős dublóban keressük (1M-2M és 1m-1M-2M után is).
- **Passz az 1NT-re:** 0–7 ponttal és rossz 8-cal. Rossz 8: rossz lapminőség (üres figurák, nincs 10-es/9-es), vagy egyenletes lap 4-es nemes nélkül. Kivétel: Junk Stayman, transzfer és leállás; 6+ lapos minorral marad a 3m invit (DD: mansban +0,8, bellben +1,8 IMP a passzhoz képest).
- **A 4-4 fit jobb az 5-3-nál** (a hosszú színre dobni lehet): a saját 4+ lapos nemesünket akkor is megmutatjuk, ha a partner nemesét 3 lappal támogathatnánk. Pl. (1♣) 1♥ (P): 4–5 pikkel és 3 kőrrel 1♠, nem felüllicit; a felüllicites emelés 4 lapos támogatással vagy pikk nélkül jön. A nyitó 1♠-2m után gyenge lappal is mondja a 4-es kőrt (1♠-2m-2♥, már megvolt).
- **A misfit-határ** (3NT utáni 4m vesztős ága): 4 vesztő, egyelőre.
- **Walsh:** az 1♣-1NT (8–10, rossz 11) kiváltja az alaprendszer 1m-1NT-jét (6–9); az 1♦-1NT marad 6–9.

### DD-mérés (2026-10-23, véletlen leosztások, a nyitó 1NT 15–17 egyenletes)

- **Gyenge lap (0–7) AK-s 5 lapos színnel, 3NT a passz helyett:** a 3NT 24%-ban teljesül; a passzhoz képest mansban −2,0, bellben −2,2 IMP leosztásonként. Nemes színnel a transzfer és passz (2M) 2,2 IMP-vel jobb a 3NT-nél. A DD tehát nem támasztja alá; ez tapasztalati („C módú”) döntés maradna.
- **5332, gyenge 5 lapos nemes (A és K nélkül), 10–14 pont, a nyitónál 3+ lap:** a 3NT 83%-ban, a 4M 82%-ban teljesül; a 3NT a 4M-hez képest −0,36 IMP. Szinte azonos; a DD nem méri a lap „eltitkolását”.
- **11–12 pontos egyenletes lapok vesztői:** 7 vesztő 22%, 8 vesztő 60%, 9 vesztő 18%. A 7 vesztőhöz 5 fedő figura kell az első 3 lapban, ami 11–12 ponttal csak sok dámával jön ki. A FELMENTÉS után (11–12 ponttal csak legfeljebb 7 vesztővel nyitunk) a nyitó egyenletes lapjai közül a pontok: 11: 3%, 12: 9%, 13: 48%, 14: 40% (11–14 között). NYITOTT: ezt a következtetést a partner sávjába bevinni.

## MOHA_1NT — az 1NT-válaszok — 2026-10-24

`konvenciok/moha_1nt.yaml`, a kártyán az alaprendszer előtt; kiváltja a kártya 1NT-2♠, 1NT-2NT, 1NT-3♣/3♦ és 1NT-3♥/3♠ sorát.

- **Minor-transzfer:** 2♠ = treff, 2NT = káró. Jellemzően 6+ lap; invit vagy gémerővel 5+ is (nem egyenletes lappal). 5-5 minorral invit+ erővel előbb 2♠, majd 3♦ (gémforsz).
  - Az induló: 2♠ után 2NT = maximális (16–17, és a treffhez jó: 3+ lap vagy dubló magasfigura), 3♣ = nem maximális; 2NT után 3♣ = maximális, 3♦ = nem.
  - A válaszoló: gyengén a „nem max”-ra passz, a „max” után 3m; invittel a „nem max”-ra passz, a „max” után egyenletes lappal 3NT, 3M = szingli; gémerővel a „nem max” után ugyanígy (3NT / 3M szingli).
- **1NT-3♣:** 5-5 minor, 0–7 (8) pont, leállás; az induló passzol vagy 3♦-ra javít.
- **4441, 9+ (gémforsz):** 3♦ = minor szingli (3♥ relé: 3♠ = káró, 3NT = treff szingli), 3♥ = kőr szingli, 3♠ = pikk szingli. Az induló: 3NT passzkérő (16+ ponttal 4NT), 4M passzkérő.
- **Az egyenletes invit 4-es nemes nélkül a Staymanen** megy (1NT-2♣, bármi a válasz, 2NT). 8 ponttal 4-es nemes nélkül passz (rossz 8), így ez 9 pont.
- **NYITOTT:** ugyanez a közbeszóló 1NT-je (16–19) után, a határok egy ponttal lejjebb (invit 8+ helyett 7+, gémforsz 15+); ehhez a minta-nyelvbe a „rendszer él” kell. A rövidség után a 4m ORKC és az 5m passzkérő még nincs a gépben.

## Menekülő rekontra — 2026-10-24

`elvek/menekulo_rekontra.yaml`. Ha a mi felvételünket megkontrázták, és a kontrát büntetőre passzolták (a sor végén ülünk: kontra – passz – passz), a rekontra menekülő: várhatóan van jobb felvétel a kontrázottnál. Bármilyen szinten, és mondhatja a felvevő is, a partnere is.

- **A partner (aki már passzolt) rekontrája:** a kontrázott színben 0–1 lap (5-5-tel 2 is), és legalább két másik 4+ lapos szín. Pontot nem ígér.
- **A felvevő saját rekontrája:** „van jobb ötletem, nem is egy, és nem egyértelmű, melyik”: a kontrázott (saját) színe legfeljebb 5 lapos, és van két másik 4+ lapos vagy egy másik 5+ lapos színe (5440, 5530; mögötte ül a hosszú adu).
- **Szan elől:** legalább két 4+ lapos szín (nem 4333).
- **Egyszínű lappal** (6+) nem rekontra: a színt mondjuk be.
- **A válasz:** a legolcsóbb 4+ lapos másik szín (alulról fölfelé), ha nincs, a legolcsóbb 3 lapos. Bent is lehet maradni: a felvevő 6+ lapos színével, illetve a felvevő rekontrájára a partner 4+ lapos támogatással.
- **NYITOTT:** a közvetlen kontra utáni rekontra (ma csak a büntetőre passzolt után).
