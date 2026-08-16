# Bridzs AI — Architektúra-leírás

**Verzió:** 0.1 (vitaanyag) · **Dátum:** 2026-08-16
**Koncepció:** neuro-szimbolikus hibrid, adatvezérelt felépítéssel ("minden legyen adat, ami csak lehet")

## 1. Alapelvek

A rendszer három tervezési elvre épül. Az első a **licit és a lejátszás teljes szétválasztása**: a két modul nem hív egymást közvetlenül, kizárólag a közös kényszertáron keresztül kommunikál. A második az **adatvezéreltség**: a licitrendszerek, az állapotgép állapotai és átmenetei, valamint a dinamikus promptsablonok mind adatként (SQL-táblákban) élnek — új rendszer vagy új helyzettípus felvétele adatbővítés, nem kódmódosítás. A harmadik a **mérhetőség**: a rendszer minden komponense három üzemmódban futtatható (A: tisztán algoritmikus, B: tisztán LLM, C: hibrid), és a három mód azonos leosztásokon, azonos metrikákkal összevethető. Az A és a B mód elsődleges szerepe nem a játék, hanem a mérés: együtt jelölik ki, hogy a C módban hol éri meg LLM-et hívni.

## 2. Rendszeráttekintés

A rendszer tíz fő komponensből áll. A vezérlés gerince az episztemikus állapotgép, a tudás gerince a kényszertár és az ágensprofil-tár kettőse ("mi lehet" / "mi valószínű"), a döntéshozatal pedig helyzettípustól függően algoritmus, LLM vagy a kettő kombinációja.

```
                    ┌─────────────────────────────┐
                    │   Játékmotor (szabályok,     │
                    │   legalitás, pontszámítás)   │
                    └──────────────┬──────────────┘
                                   │ esemény (licit / hívás)
                                   ▼
┌──────────────┐   frissítés  ┌─────────────┐   olvasás   ┌──────────────┐
│ Licitrendszer │────────────▶│ KÉNYSZERTÁR │◀───────────▶│ Állapotgép   │
│ tudásbázis    │             │ (mi LEHET)  │   jellemzők │ (routing)    │
│ (SQL, adat)   │             └──────┬──────┘             └──────┬───────┘
└──────▲───────┘                     │ kényszerek                │ állapot + sablon-id
       ┆ óvatos paraméter-           ▼                           ▼
       ┆ felülbírálat         ┌─────────────┐   stílus-  ┌──────────────┐
┌──────┴────────┐   súlyok    │ Leosztás-    │   kivonat  │ Prompt-      │
│ ÁGENSPROFIL-  │────────────▶│ mintavételező│     ┌─────▶│ összeállító  │
│ TÁR           │             └──────┬──────┘      │      └──────┬───────┘
│ (mi VALÓSZÍNŰ)│───────────────────────────────────┘            │ kész prompt
└───────────────┘                    │ súlyozott minták          ▼
                              ┌──────▼──────┐            ┌──────────────┐
                              │ DDS solver + │◀──eszköz───│ LLM-réteg    │
                              │ valószínűség │───hívás───▶│ (lokális)    │
                              └─────────────┘            └──────────────┘
```

## 3. Komponensek

### 3.1 Játékmotor (szimbolikus mag)

Determinisztikus kód: a bridzs teljes szabályrendszere, a licitmenet és a lejátszás legalitás-ellenőrzése, ütésszámolás, pontszámítás (parti, gém, szlem, kontrák, beliekkel), IMP- és matchpoint-konverzió. Ez a komponens soha nem hív LLM-et, és minden más komponens erre épül. Itt dől el a rendszer megbízhatósága, ezért erre érdemes a legszigorúbb tesztlefedettséget írni.

### 3.2 Kényszertár (constraint store — az episztemikus tartalom)

A négy kézről felhalmozott tudás egzakt, szimbolikus reprezentációja, játékosonként: figurapont-intervallum (min–max), lapszám-intervallum mind a négy színben (min–max), megmutatott és letagadott figurák, valamint megjátszott lapok. Minden licit és minden hívás egy frissítési szabályt vált ki; a licitek frissítési szabályai a licitrendszer-tudásbázisból jönnek (tehát rendszerfüggőek és adatvezéreltek), a hívások frissítési szabályai játéklogikaiak (pl. színre nem tett szolgálás → az adott szín kizárása). A kényszertár a licit- és a lejátszásmodul közös nyelve: a licit során felépült tudás ezen keresztül öröklődik át a lejátszásba. Fontos tervezési döntés, hogy a kényszertár szándékosan konzervatív: csak azt rögzíti, ami a deklarált rendszer szerint biztosan következik — ez a "mi lehet" rétege. A "mi valószínű" réteg az ágensprofil-tár (3.10), és a kettő nem keveredik: a profil sosem írja a kényszertárat közvetlenül, hanem a mintavételező súlyain és — szigorúan kapuzott esetben — a rendszerbejegyzések paraméterein keresztül hat. Így egy téves profilfeltevés soha nem zárhatja ki logikailag a valódi kezet, legfeljebb alulsúlyozza.

### 3.3 Licitrendszer-tudásbázis (adat)

Deklaratív leírás rendszerről rendszerre: nyitási követelmények, válaszok és viszonválaszok jelentése, konvenciók, kompetitív megállapodások. Szerkezetileg a konvenciókártya kiterjesztett, géppel olvasható változata. Minden bejegyzés két dolgot ad meg: (a) mikor licitálható (feltétel a saját kézre és a licitmenetre), és (b) mit jelent (a kényszertár-frissítési szabály a partner és az ellenfelek szemszögéből). Az (a) hajtja az A mód licitálóját, a (b) hajtja a kényszertárat — a kettő ugyanabból a bejegyzésből származik, így definíció szerint konzisztens.

### 3.4 Episztemikus állapotgép (routing, adat)

Állapotai helyzettípusok (pl. gémforsz kialakult, kompetitív licit, szlemkutatás, indító kijátszás, felvevő-tervezés, ellenjáték-jelzéshelyzet), átmenetei a kényszertár és a játékállás **jellemzőire** kötött feltételek — nem merev licitmintákra. Az állapotokhoz tartoznak: a dinamikus promptsablon(ok) azonosítói, az adott állapotban engedélyezett eszközök listája, és az üzemmód-preferencia (A/B/C routing-tábla, lásd 5. pont). Tartalmaz egy explicit "bizonytalan" állapotot: ha az átmeneti feltételek nem döntenek egyértelműen, egy olcsó osztályozó hívás (rövid routing-prompt) sorol be, és az eset naplózásra kerül. Az állapotgép szándékosan karcsú: episztemikus tartalmat nem tárol, azt a kényszertárból olvassa.

### 3.5 Prompt-összeállító

Sablonmotor, amely az állapothoz tartozó makrózott szövegsablonba beépíti: a saját kezet, a licitmenetet/játékmenetet, a kényszertár emberi nyelvű összefoglalóját ("a partner eddig 12–14 pontot és pontosan 5 pikket mutatott…"), és a licitrendszer-tudásbázis **releváns kivonatát**. A generált kontextus garantálja, hogy a prompt sosem csúszik szét a szimbolikus állapottól. A sablonok adatok (SQL), verziózottak, és a kiértékelő keretrendszer sablonverziónként tud mérni — ez teszi lehetővé a szisztematikus prompt-optimalizálást.

### 3.6 LLM-réteg

Lokálisan futó nyílt modell (a 48 GB VRAM kb. 30–70 mrd paraméteres kvantált modellt enged; inferencia llama.cpp-vel vagy vLLM-mel). Három szerepben hívható: (1) routing-osztályozó a bizonytalan állapotokhoz, (2) döntéshozó a B és C módban (licitválasztás, játéktervválasztás), (3) értelmező (az ellenfél nem-standard licitjének/viselkedésének magyarázata). A kimenet mindig strukturált (JSON: döntés + indoklás + megbízhatóság), és a játékmotor legalitás-ellenőrzésén megy át; illegális vagy parse-olhatatlan kimenetnél determinisztikus fallback az A mód döntésére. Későbbi fázisban a modell QLoRA-val finomhangolható szakértői annotált anyagon.

### 3.7 Solver-eszköztár

Három eszköz, amelyet az algoritmikus döntéshozó közvetlenül, az LLM pedig eszközhívásként használ. A **leosztás-mintavételező** a kényszertárral konzisztens véletlen lapelosztásokat generál (elutasításos mintavétel), majd az ágensprofil-tár hajlamfüggvényeivel súlyozza őket: a kényszertár dönti el, mely elosztások megengedettek, a profil azt, melyik mennyire valószínű az adott pártól látott licitek és hívások fényében. Maga a DDS profil-független marad — a profil a DDS *előtt* (mintasúlyok) és *után* (az aggregált eredmények döntéssé alakításakor) lép be, soha a solveren belül. A **double dummy solver** (Bo Haglund DDS könyvtára, python-dds vagy endplay kötéssel) egy adott elosztáson kiszámítja az elérhető ütésszámot; a mintákon aggregálva ad ütésvárakozást licitekhez és hívásokhoz. A **pontszám/valószínűség-kalkulátor** kontraktus-kiértékelést (IMP a par-eredményhez képest) és színeloszlás-valószínűségeket számol. Elv: minden számszerű állítást, amit az LLM tesz, ez a réteg ellenőriz — a nyelvi érvelés sosem forrása számnak, csak felhasználója.

### 3.8 Lejátszásmodul

Emberi mester mintájára terv-alapú: az indító kijátszás, illetve felvevőként az asztal leterülése után **egyszer** készül játékterv (C módban: LLM javasol tervváltozatokat, a solver-eszköztár kiértékeli, a legjobb megy tovább), a végrehajtás ütésről ütésre algoritmikus. Újratervezés csak "meglepetéskor" történik: amikor egy hívás ellentmond a kényszertárnak vagy a terv feltevéseinek. Így az LLM-hívások száma lejátszásonként tipikusan 1–3, nem 13.

### 3.9 Kiértékelő keretrendszer

Duplikált mérés: azonos leosztás-készlet minden összehasonlított konfigurációnak, IMP-alapú pontozás, licitre a par-hoz mért veszteség (ellenfél-független), lejátszásra a double dummy optimumhoz mért ütésveszteség. Minden futás rögzíti: állapotgép-útvonal, sablonverzió, üzemmód, LLM-kimenet és indoklás, fallback-események, félreroutolás-gyanús esetek. Ez a napló a fejlesztés elsődleges nyersanyaga.

### 3.10 Ágensprofil-tár (a "mi valószínű" réteg, adat)

A világban lévő ágensek — ellenfélpárok, a saját partner, és önmagunk két ülése — helyzettípusonként bontott hajlamainak tára. A tétel, amire épül: egy pár közös tudása több, mint a két játékos tudásának átlaga; a licitrendszer tól-ig határain belül a párok szignifikánsan és mérhetően eltérően döntenek, és ez az eltérés maga is tudás a világról — tehát adat, nem kód.

**Szerkezete hierarchikus.** Az alap a *mezőnyprofil*: hogyan viselkedik egy átlagos pár az adott helyzettípusban (nagy mintából építve, akár külső archívumokból). Az egyedi *párprofil* ettől való eltérésként tárolódik, és kevés megfigyelésnél erősen a mezőnyátlag felé zsugorítva érvényesül — csak felgyűlő adattal távolodhat tőle. Ismeretlen pár = mezőnyprofil. Ez a zsugorítás a védelem a "babona" ellen (két megfigyelésből levont örök ítélet).

**Tartalma helyzettípus-kulcsú hajlamfüggvény.** Példák: invit-küszöb eltérése a rendszerminimumtól, gátlási agresszivitás beliállás szerint, közbeszólási hajlandóság, indítókijátszási preferenciák, jelzésrendszer-megbízhatóság (mennyire fegyelmezetten adnak számjelzést/attitűdjelzést — ez a lejátszásbeli hívás-alapú kényszerfrissítések súlyát hangolja). A kulcsolást az állapotgép taxonómiája adja ingyen.

**Három belépési pontja van, szigorúan elkülönítve.** (1) *Mintasúlyozás* — az elsődleges és alapértelmezett út: a kényszertár által megengedett elosztásokon belül a profil valószínűségi súlyokat ad a mintavételezőnek. (2) *Prompt-kivonat*: a prompt-összeállító emberi nyelvű stílusösszefoglalót injektál ("az ellenfélpár stílusa: agresszív gátlások, könnyű nyitások"), ugyanúgy, ahogy a rendszertudás-kivonatot. (3) *Paraméter-felülbírálat a rendszerbejegyzéseken* — a legóvatosabban kezelendő út: ha egy pár deklarált és tényleges gyakorlata dokumentáltan eltér (pl. rendszeresen 10 ponttal nyitnak 12+ helyett), a profil felülbírálhatja a kényszertár-frissítési szabály paramétereit. Ez kemény kényszert módosít, ezért evidencia-kapuzott: csak statisztikailag megalapozott, naplózott eltérésnél aktiválódhat, mert egy téves kemény kényszer kizárja a valódi kezet a mintatérből — ez a legdrágább hibafajta.

**Az adatforrás beépített.** Minden parti végén a lapok kiterülnek, így minden megfigyelt döntéshez utólag ingyen megvan a valódi kéz — címkézett tanítóadat a profilépítéshez. A profil tehát a játszmanaplóból inkrementálisan frissül, emberi kézimunka nélkül.

## 4. Adatmodell (vázlat)

Fő táblák: `rendszer` (licitrendszerek), `rendszer_bejegyzes` (licit-jelentések: feltétel + kényszerfrissítés, rendszer-hivatkozással), `allapot` (állapotgép-állapotok), `atmenet` (feltételek a kényszertár-jellemzőkre), `sablon` (makrózott promptsablonok, verziózva, állapot-hivatkozással), `routing_tabla` (állapot × üzemmód-döntés, a 5. pont mérési eredményeiből töltve), `mezony_profil` (helyzettípus × hajlamjellemző, mezőnyszintű alapértékek), `par_profil` (pár × helyzettípus × hajlamjellemző, eltérésként a mezőnytől, megfigyelésszámmal a zsugorításhoz), `leosztas`, `jatszma_naplo`, `meres`. A kényszertár futásidejű objektum, de minden döntési pontban szerializálva a naplóba kerül (visszajátszhatóság).

## 5. Az A/B/C üzemmódok mint mérőműszer

Az A mód (tiszta algoritmus: tudásbázis-vezérelt licit + solver-vezérelt lejátszás) adja a padlót. A B mód (tiszta LLM, minimális kerettel) adja a diagnózist. A kettőt az állapotgép miatt **helyzettípusonként** lehet összevetni, és a különbség tölti fel a routing-táblát: a C mód ott hív LLM-et, ahol B mérhetően jobb A-nál, vagy ahol mindkettő gyenge és az LLM+eszköz kombináció ígéretes. A várható (de mérendő!) kimenet: legalitás, kényszertár-frissítés, valószínűségszámítás, végjáték → algoritmus; szokatlan kompetitív helyzetek értelmezése, játéktervválasztás, ellenfél-modellezés → LLM eszközökkel.

## 6. Ismert kockázatok

A legnagyobb kockázat a **félreroutolás** (rossz állapot → rossz prompt → magabiztos rossz döntés); ellenszere a jellemző-alapú átmenetek, a "bizonytalan" állapot és a kötelező naplózás. A második az **LLM-indoklások látszat-megalapozottsága**; ellenszere, hogy számszerű állítás csak eszközhívásból származhat, és a strukturált kimenet ellenőrzésen megy át. A harmadik a **mintavételező torzítása** (a kényszertárral konzisztens, de a valósággal nem reprezentatív minták); ellenszere a mintavételező külön tesztelése ismert lapelosztású, visszajátszott partikon. A negyedik a **profil-túlilleszkedés** (kevés megfigyelésből levont túl erős párjellemzés, ami rossz mintasúlyokat vagy — a legrosszabb esetben — téves kemény kényszert szül); ellenszere a hierarchikus zsugorítás a mezőnyprofil felé, a paraméter-felülbírálat evidencia-kapuzása, és a profilhatás külön ki-be kapcsolhatósága a mérésekben (profil nélküli kontrollfutás).
