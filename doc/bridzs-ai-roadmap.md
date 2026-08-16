# Bridzs AI — Roadmap

**Verzió:** 0.1 · **Dátum:** 2026-08-16
**Vezérelv:** minden fázis önállóan mérhető eredménnyel zárul; a következő fázis csak teljesült kilépési feltétel után indul. Az időbecslések egyszemélyes, részmunkaidős fejlesztésre szólnak, és inkább arányokat jeleznek, mint határidőket.

## 0. fázis — Alapzat: motor és eszköztár (kb. 3–5 hét)

Cél a szimbolikus mag: játékmotor (teljes szabályrendszer, legalitás, pontszámítás, IMP), DDS-integráció (endplay vagy python-dds, teljesítményteszttel a Threadripperen), leosztás-generátor és -mintavételező (először kényszerek nélkül, majd egyszerű kényszerekkel), valamint a napló- és visszajátszó-infrastruktúra. Ebben a fázisban LLM egyáltalán nincs.

**Kilépési feltétel:** 10 000 véletlen leosztás double dummy kiértékelése lefut mérhető, dokumentált sebességgel; egy kézzel felírt híres parti visszajátszható és a pontszámítás egyezik a hivatalossal; a mintavételező egyszerű kényszereket (pl. "észak 15–17 pont, kiegyensúlyozott") helyesen tart be, statisztikai teszttel igazolva.

## 1. fázis — Függőleges szelet, A mód (kb. 4–6 hét)

Egyetlen licitrendszer (javaslat: SAYC vagy a saját preferált rendszered), egyetlen helyzetcsalád: az 1 szan nyitás utáni, kompetíció nélküli licitmenet (Stayman és transzferek), plusz a hozzá tartozó szan-felvevőjáték. Ebben a szeletben megépül minden réteg csírája: a licitrendszer-tudásbázis első bejegyzései (feltétel + kényszerfrissítés párban), a kényszertár a frissítési szabályokkal, az állapotgép első 5–8 állapota adattáblából töltve, és az A módú döntéshozó (tudásbázis-vezérelt licit, solver-vezérelt lejátszás terv nélkül, mintavétel + DDS aggregálással).

**Kilépési feltétel:** 500 szűrt leosztáson (ahol a rendszer szerint 1 szan a nyitás) az A mód végiglicitál és végigjátszik emberi beavatkozás nélkül; licitminőség a par-hoz mért IMP-veszteségben, lejátszás a DD-optimumhoz mért ütésveszteségben dokumentálva. Ezek a számok lesznek a projekt origója — az abszolút értékük másodlagos, a mérhetőségük az eredmény.

## 2. fázis — B és C mód ugyanazon a szeleten (kb. 4–6 hét)

Lokális LLM üzembe állítása (első körben egy 30 mrd körüli kvantált modell; a 70 mrd-os osztály később, ha a minőség indokolja), a prompt-összeállító és a sablontábla megépítése, strukturált JSON-kimenet legalitás-ellenőrzéssel és A-módú fallbackkel. Előbb a B mód: tiszta LLM-döntések ugyanazon az 500 leosztáson, állapotonként bontott kimutatással. Utána a C mód első változata: a routing-tábla feltöltése az A–B összehasonlításból, és az eszközhívásos minta bevezetése ott, ahol B gyenge volt.

**Kilépési feltétel:** háromoszlopos eredménytábla (A/B/C) ugyanazon az 500 leosztáson, helyzettípusonként bontva; a C mód legalább nem rosszabb A-nál összesítve, és van legalább egy helyzettípus, ahol mérhetően jobb. Mellékterméke egy dokumentált lista a B mód tipikus hibamintáiról — ez hajtja a 3. fázis sablonfejlesztését.

## 3. fázis — Licitbővítés és belief-finomítás (kb. 6–10 hét)

A licittér kiterjesztése: színnyitások és válaszok, majd az első kompetitív helyzetek (közbeszólás, kontra), az állapotgép bővítésével és a "bizonytalan" állapot + routing-osztályozó élesítésével. Párhuzamosan a mintavételező okosítása: a kényszertár teljes tartalmának betartása, súlyozott mintavétel, és a mintavételező önálló minőségmérése visszajátszott, ismert lapelosztású partikon. Itt lép be az **ágensprofil-réteg első foka, a mezőnyprofil**: a kényszertár tól-ig határain belüli valószínűségi súlyozás mezőnyszintű hajlamokból (helyzettípusonként), a mintavételező súlyfüggvényeként — egyedi párprofilok még nélkül. A profilhatás külön kapcsolható, hogy a mérésben profil nélküli kontrollfutással legyen összevethető. Itt érdemes bevezetni a sablonverziónkénti mérést is (a benchmark-tapasztalat szerint a célzott, hibapéldás promptok hozzák a legnagyobb ugrást).

**Kilépési feltétel:** a rendszer a leosztások legalább ~80%-át (nem szűrt, véletlen leosztásokon, egy rendszeren belül) képes végiglicitálni; a félreroutolási napló heti szinten átnézhető méretű; a par-hoz mért IMP-veszteség a 2. fázishoz képest javul; a mezőnyprofillal súlyozott mintavételező mérhetően pontosabb rejtettkéz-becslést ad, mint az egyenletes (visszajátszott, ismert lapelosztású partikon mérve).

## 4. fázis — Terv-alapú lejátszás és ellenjáték (kb. 6–10 hét)

A lejátszásmodul teljes kiépítése: indító kijátszás (kényszertár-alapú), felvevő-játékterv (C módban: LLM-tervváltozatok + solver-kiértékelés, egyszeri tervezés + meglepetés-alapú újratervezés), és az ellenjáték alapjai. Az ellenjátéknál jelentkezik először élesen a determinizáció stratégiafúzió-problémája — itt elég a tudatos kompromisszum: dokumentálni, mit ront el szisztematikusan, és csak akkor nyúlni fejlettebb (belief-alapú keresési) módszerhez, ha a mérés indokolja. Ebben a fázisban bővül az ágensprofil a lejátszás-oldali jellemzőkkel: indítókijátszási preferenciák és jelzésrendszer-megbízhatóság, amelyek a hívás-alapú kényszertár-frissítések és mintasúlyok hangolását adják.

**Kilépési feltétel:** teljes partik (licit + lejátszás mindkét vonalon) duplikált mérése; felvevőjátékban a DD-optimumhoz mért veszteség dokumentáltan kisebb, mint az 1. fázis terv nélküli megoldásáé; LLM-hívások száma lejátszásonként átlagosan 3 alatt.

## 5. fázis — Finomhangolás és külső mérce (nyitott végű)

QLoRA-finomhangolás szakértői annotált anyagon (kommentált partik, szakértői paneldöntések indoklással — az adatgyűjtés és -tisztítás önmagában is jelentős munka, érdemes már a 3. fázistól gyűjteni), sablon-optimalizálás a felhalmozott hibanaplókra építve, és külső viszonyítás: mérés a nyílt referenciák (pl. Ben, WBridge5) ellen, illetve a nyílt LLM-licit-benchmarkon. Ide tartozik az ágensprofil második foka is: **egyedi párprofilok** a felhalmozott játszmanaplókból, hierarchikus zsugorítással a mezőnyprofil felé, és — kizárólag erős evidencia mellett — a rendszerbejegyzés-paraméterek pár-specifikus felülbírálata. Opcionális kutatási irányok innen: RL-finomhangolás DD-jutalommal, második licitrendszer felvétele (az adatvezéreltség éles próbája — elvileg kód nélkül), emberi játékosokkal való tesztjáték, ahol ugyanez a profilréteg az emberi partner hajlamait tanulja.

**Kilépési feltétel (első kör):** dokumentált, reprodukálható összehasonlítás legalább egy külső referenciával, néhány ezer duplikált leosztáson.

## Átfogó elvek

Minden fázisban érvényes: (1) az adatvezéreltség nem sérülhet — ha egy bővítés kódmódosítást kényszerít ki ott, ahol adatbővítésnek kellene elégnek lennie, az architektúra-hibajel; (2) minden LLM-hívás naplózva, minden döntés visszajátszható; (3) a mérés mindig duplikált és helyzettípusonként bontott; (4) a fázisok végén rövid írásos összegzés készül (mi működött, mi nem, mit mérünk másképp) — fél év múlva ez lesz a legértékesebb dokumentum.

## Első konkrét lépések (jövő hétre)

Fejlesztői környezet és repó felállítása; endplay/python-dds telepítése és egy 1000 leosztásos DDS-sebességteszt a gépeden; a játékmotor licit-legalitás részének megírása tesztekkel; és egy 20 soros döntésnapló-séma megtervezése — mert minden későbbi tanulság ezen fog múlni.
