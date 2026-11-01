# MohaBridzs stratégiai sématár 0.0

Dátum: 2026. október 30.

Ez a munkaváltozat azt írja le, hogyan tárolhatunk egy bridzstervet úgy, hogy az AI később felismerhesse az alkalmazási lehetőségét, előkészíthesse a szükséges állást és reagálhasson az ellenfél játékára. A javasolt szerkezet saját tervezet. Kiindulópontját a BridgeSingleDummy v0.9.13-test nyolc, szövegesen kidolgozott beszorítási feladata adta.

Az öt korábban kiemelt elem jó mag: felismerési támpont, előkészítés, megőrzendő erőforrás, sorrendi kötöttség, feltételes folytatás. Ezek a példák fontos részeit leírják, de egy alkalmazható stratégiai sémához külön cél, szerepkiosztás, célállás, újratervezési feltétel és ellenőrzési állapot is szükséges.

## A leírás szintje

A stratégiai leírás arra válaszol: milyen célállást szeretnénk elérni, miért lehet azt előállítani, és mit kell addig megőrizni? Kapcsolódik a játékfogásokhoz és az elemi műveletekhez; a teljes elemi kottanyelvet ez a dokumentum nem specifikálja.

Három külön tárgyat kezelünk:

| Tárgy | Jelentése | Példa |
|---|---|---|
| Példabejegyzés | Egy konkrét kiosztás és állapot, szakmai magyarázattal | Egy adott partiban a nyugati védő beszorítása |
| Séma | Több állásra alkalmazható szerepek, feltételek és tervszerkezet | Két színt őrző egyetlen védő beszorítása |
| Konkrét terv | Egy séma hozzárendelése az aktuális lapokhoz, választott célhoz és feltevésekhez | Ki az őrző, mely lapok a fenyegetések, melyik a beszorító lap? |

Egy séma több példában szerepelhet. Egy példa több sémát kapcsolhat össze. A nyolc forrásfeladat ezért nem jelent nyolc külön technikát.

## A stratégiai séma tíz eleme

Az első öt elem a korábbi táblázatból származik; a második öt a mostani bővítés. Az azonosító, verzió, név és forráshivatkozás ezek mellett metaadat.

| Azonosító | Elem | Kötelező tartalom |
|---|---|---|
| E1 | Felismerés és alkalmazhatóság | Megfigyelhető támpontok; szükséges feltételek; kizáró körülmények; bizonyított tények és feltevések elkülönítése |
| E2 | Előkészítő műveletek | Milyen változtatásokkal állítható elő a kívánt végállás, és mely feltételt hozza létre az egyes művelet? |
| E3 | Megőrzendő erőforrások | Fenyegetések, átmenetek, hosszúságok, tempó és szükséges nyerőlapok; mikor szabad felhasználni őket? |
| E4 | Sorrendi kötöttségek | Mely műveletnek melyiket kell megelőznie, és miért? Csak a szakmailag szükséges sorrendet rögzítjük. |
| E5 | Megfigyeléshez kötött ágak | Milyen látható eseményre milyen folytatás következik; mi történik korai őrfeladáskor vagy váratlan válasznál? |
| E6 | Cél és értékelés | Teljesítés, szűr vagy más cél; hány ütés hiányzik; a biztos teljesítés és a többletütés közötti prioritás |
| E7 | Szerepek és hozzárendelés | A részt vevő kezek, színek, lapok, őrzők, fenyegetések, átmenetek és beszorító lap szerepe |
| E8 | Célállás és sikerkritérium | A létrehozandó kapcsolatrendszer és az a feltétel, amely mellett az elágazások a kívánt eredményhez vezetnek |
| E9 | Megszakítás és újratervezés | Mi cáfolja a tervet; mi teszi végrehajthatatlanná; mikor kell másik sémára vagy alacsonyabb célra váltani? |
| E10 | Ellenőrzés és bizonyíték | Forrásállítás, saját szakmai ellenőrzés, végrehajtási teszt és DD-ellenőrzés külön; pontos vizsgálati tartománnyal |

E1 és E8 különbsége: E1 dönti el, hogy érdemes-e ezt a tervet mérlegelni a jelen állapotban. E8 határozza meg, milyen állapotban működne, illetve milyen eredmény számít sikernek. E2 köti össze a jelen állapotot a célállással.

## Tudás és feltevés

Minden érdemi feltételhez tartozzon tudásállapot. Ugyanaz a lapelhelyezési állítás nem kezelhető azonosan akkor, ha láttuk a lapot, és akkor, ha egy indulásból következtettünk rá.

| Állapot | Jelentése |
|---|---|
| Megfigyelt | A saját lapokból, az asztalból vagy a szabályos játékmenetből közvetlenül ismert |
| Bizonyított | Az ismert tényekből és a szabályokból szükségszerűen következik |
| Feltételezett | Licitből, jelzésből, indulásból vagy választott ellenfélmodellből következtetett |
| Ismeretlen | A tervhez fontos lehet, de még nincs rá kellő információ |

A feltevéshez rögzítjük az alapját és a cáfoló megfigyelést. Számszerű valószínűséget csak megnevezett becslési módszer alapján adunk. A 0.0 nem ír elő kitalált százalékokat.

A teljes kiosztás ismeretében készített magyarázat lapelhelyezési tényei nem kerülhetnek automatikusan a játékos tudásállapotába. A séma működhet bizonyos lehetséges kiosztásokban anélkül, hogy a játékos tudná, melyik a tényleges kiosztás.

## A beszorítási család közös szerepei

| Szerep | Jelentés |
|---|---|
| Fenyegetés | Olyan lap vagy lapcsoport, amely az ellenfél megfelelő őrzésének megszűnése után ütéssé alakítható |
| Őrzési kötelezettség | Az ellenfélnek szükséges lap vagy lapcsoport egy fenyegetés megállításához |
| Beszorító lap | Az a nyerőlap, amelynek kijátszása a szükséges lapok egyidejű megtartását lehetetlenné teheti |
| Átmenet | A fenyegetés elérését vagy az előkészítés végrehajtását lehetővé tevő kapcsolat |
| Kijárat | Olyan ellenfél-kijátszás, amellyel elkerülhető a kívánt kényszerhelyzet |
| Teherlap | A végállás szempontjából eldobható lap; minősítése a tervtől és a lehetséges kiosztásoktól függ |

Az őrzést szükséges lapcsoportként kell kezelni: egy hosszúsági fenyegetés feltartásához több lap is kellhet. A szerepek megnevezése önmagában még nem bizonyítja a beszorítást; az ütéshelyzet, a kézgeometria, a kijátszási sorrend és az átmenetek ellenőrzése külön feladat.

## A 0.0 négy összekapcsolható modulja

Ezek tervezeti modulok. Nem állítjuk, hogy a beszorítások teljes osztályozását adják.

### S1 Egyszerű beszorítás

Cél: ugyanannak a védőnek két őrzési kötelezettségét összeegyeztethetetlenné tenni, majd a felszabaduló fenyegetést ütéssé alakítani.

Szerepek: egy célzott védő; két fenyegetés és azok őrzési igénye; beszorító lap; szükséges átmenetek.

Előkészítés: a szükséges nyerők és ütéshelyzet kialakítása, az őrzések megfelelő védőre szűkítése, szükség esetén deblokkolás. Ezek állásfüggő részfeladatok; nem minden előkészítő lehívás helyes minden állásban.

Célállás: a védő a beszorító lapra nem tud minden szükséges őrzést megtartani. A felszabaduló fenyegetés a megmaradó átmenetekkel elérhető. A saját oldalnak is van megengedett dobása.

Ágak: az első fenyegetés őrzése megszűnik; a másodiké szűnik meg; a védő valamelyiket már korábban feladja. Mindegyikhez külön ellenőrizzük az ütés bevételét és a további kézkapcsolatokat.

Újratervezés: a feltételezett védő helyett a társa is őriz; a szükséges átmenet elvész; a védőnek marad veszélytelen teherlapja; az előkészítés túl sok ütést ad ki.

### S2 Kettős beszorítás

Cél: a két védő összekapcsolódó őrzési kötelezettségeiből felszabaduló ütést létrehozni.

Szerepek: két védő; két külön őrzött oldalszín; egy közös szín, amelynek őrzésében mindkét védő részt vesz; fenyegetések, beszorító lap és átmenetek.

Előkészítés: az őrzési viszonyok kialakítása, az egyes fenyegetések megtartása és a szükséges kézkapcsolatok biztosítása.

Célállás: valamelyik oldalszín őrzésének feladása azonnal felhasználható nyerőt eredményez; ha mindkét védő megtartja a saját oldalszínét, a közös színben szabadul fel ütés. A helyes elhelyezkedés és kijátszási sorrend szükséges; a három szín és két védő puszta jelenléte nem elég.

Ágak: az egyik oldalszín felszabadul; a másik szabadul fel; a közös szín válik nyerővé. A saját dobásokat is a fennmaradó fenyegetésekhez kell igazítani.

### P1 Korai bécsi ütés mint előkészítő fogás

Cél: egy magas lap időben történő lehívásával létrehozni a később önállóan felhasználható fenyegetést és a szükséges kézkapcsolatot.

Szerepek: a lehívandó magas lap; a későbbi fenyegetés; a két kéz; megőrzendő átmenetek; a fogást igénylő szülőterv.

Ez előkészítő modul, amely például S1 részeként használható. Nem önálló, minden körülmények között alkalmazható nyerési terv. Az alkalmazhatósághoz azt is ellenőrizni kell, hogy a korai lehívás nem rontja el az időzítést vagy más szükséges esélyt.

### K1 Beszorítás eliminációval és végjátékba hozással

Cél: az ellenfél dobásával vagy közvetlenül nyerőt felszabadítani, vagy eltüntetni egy kijáratot, majd az ellenfelet kedvezőtlen kijátszásra kényszeríteni.

Szerepek: célzott védő; őrzött színek; biztonságos kijárat; a kézbe adáshoz használható lap; a visszahívás kihasználásához szükséges átmenet.

Előkészítés: a beszorító helyzet és a megfelelő elimináció összehangolása. Az ágak eltérő előkészítést és eltérő dobásokat igényelhetnek.

Ágak: közvetlenül felszabaduló fenyegetés; kijárat eltüntetése után kézbe adás; új nyerőből létrejövő második beszorítás. Az ágak különböző ütésszámot adhatnak. A terv értékelésekor az ellenfél számára legkedvezőbb szabályos választ is figyelembe kell venni.

## A nyolc forrásfeladat lefedése

Az alábbi besorolás saját értelmezés. A rövid jellemzések a forrás szövegét foglalják össze. A táblázat leírási lefedést mutat, nem önálló bridzstechnikai bizonyítást.

| Forrásbejegyzés | Tervezeti modul | Miért kevés önmagában az eredeti öt mező? |
|---|---|---|
| hand0001 | S1 | A teljesítéshez szükséges összes további ütés a cél része. |
| hand0002 | S1 | A hiányzó tizenharmadik ütést és az elérhető fenyegetéseket azonosítani kell. |
| hand0003 | S1 | A végállás őrzési viszonyait és kézkapcsolatait rögzíteni kell. |
| hand0004 | S1 és előkészítő lopások | Az előkészítés helyessége a forrásban is ellenőrizendő kérdés marad. |
| Squeeze1 | S1 vagy S2, megfigyeléstől függően | Egy válasz nemcsak lépést, hanem alkalmazandó sémát is válthat. |
| Squeeze2 | S2 | A tervhez szükséges elosztási feltételt külön kell kezelni. |
| Squeeze throw in | K1, további beszorítási ággal | A feltételezett elosztás és az áganként eltérő eredmény külön kezelendő. |
| Squeeze - vroege Vienna coup | P1 és S1 | A szűr célját és az előkészítő fogás szerepét külön kell rögzíteni. |

Az öt eredeti elem mind a nyolc feladat feldolgozásánál hasznos. Nem állítjuk, hogy minden mező minden forrásszövegben teljesen ki van dolgozva. A tízmezős vázban mindegyik elhelyezhető úgy, hogy a hiányzó ismeret vagy bizonyítás hiányként maradjon meg.

Különbséget teszünk három állítás között:

1. Leírható: van megfelelő mező a szakmai tartalomnak. Erre alkalmas kiindulópont a 0.0.
2. Helyes: a terv az adott feltételek mellett valóban működik. Ezt feladatonként kell ellenőrizni.
3. Alkalmazható: az AI önállóan felismeri, hozzárendeli és szabályosan végrehajtja. Ezt a dokumentum és a forrás nyolc feladata nem bizonyítja.

## Példa a stratégiai hozzárendelésre

A bécsi ütéses feladatból saját értelmezéssel készült részleges tervváz:

| Mező | Kitöltés |
|---|---|
| Cél | A teljesítés mellett egy további ütés megszerzése |
| Összetétel | P1 előkészítés, majd S1 |
| Szerepek | Nyugat a célzott őrző; pikk és treff a fenyegetett színek; a végső beszorító lap káró |
| Előkészítés | A treff magaslap lehívása még a végső nyerősorozat előtt |
| Megőrzés | A fenyegetések és a felszabaduló ütéshez szükséges pikk-kapcsolat |
| Sorrend | Előkészítő trefflehívás, majd utolsó adu, majd a kárónyerők |
| Megfigyelés | Melyik őrzést adja fel a védő, és mikor? |
| Folytatás | A ténylegesen felszabadult fenyegetés kihasználása |
| Tudáskorlát | A tényleges kiosztásbeli őrzést külön kezeljük a játékos által levonható következtetéstől. |
| Ellenőrzés | Forrásból származó magyarázat; ebben a munkában nem történt önálló DDS-újraellenőrzés. |

Ez a kitöltés még nem elemi kotta: a konkrét kártyaparancsok, a szabályosság vizsgálata és az elágazások teljes végrehajtása külön réteg feladata.

## Kapcsolódás a végrehajtáshoz

A javasolt munkafolyamat:

1. Rögzítsük a látható állapotot, az ismert tényeket és a feltevéseket.
2. Keressünk alkalmazhatónak látszó sémákat, és rendeljük hozzájuk a konkrét szerepeket.
3. Vizsgáljuk meg a célállás elérhetőségét, a szükséges erőforrásokat és az alternatív terveket.
4. Állítsuk elő az előkészítés és végrehajtás megfigyelésekhez kötött kottáját.
5. Csak szabályos, a játékos rendelkezésére álló információra támaszkodó lépést hajtsunk végre.
6. Minden új információ után frissítsük a feltételeket, és szükség esetén tervezzünk újra.

Egy végrehajtási ág feltétele látható eseményre vagy megnevezett következtetésre épüljön. Rejtett lap birtoklását közvetlenül vizsgáló feltétel nem kerülhet a játékos végrehajtási kottájába. Több egyszerre lehetséges feltétel esetén egyértelművé kell tenni, hogy prioritásos ágakról vagy egymással összehasonlítandó tervjelöltekről van szó. A stratégiai tervjelöltek kiválasztását nem bízzuk a tárolási sorrendre.

## A 0.0 adatváza

Az alábbi JSON csak a tízmezős adatszerkezetet szemlélteti. Nem JSON Schema, nem feltételnyelv és nem futtatható algoritmus. Az üres listák még kitöltendő részeket jelentenek.

```json
{
  "format": "mohabridzs-strategiai-sema/0.0",
  "id": "squeeze.simple",
  "name": "Egyszerű beszorítás",
  "status": "draft",
  "provenance": [],
  "recognition_and_applicability": {
    "cues": [],
    "required_conditions": [],
    "exclusions": [],
    "assumptions": []
  },
  "preparation": [],
  "preserve": [],
  "ordering_constraints": [],
  "observation_branches": [],
  "goal_and_evaluation": {},
  "roles": [],
  "target_state_and_success": {},
  "abort_and_replan": [],
  "validation": {
    "source_claims": [],
    "independent_checks": [],
    "scope": null,
    "unresolved": []
  }
}
```

Egy feltétel minimális rekordja később tartalmazza az állítást, a szerephivatkozásokat, a tudásállapotot, az indoklást és a cáfoló megfigyelést. Egy ág minimális rekordja tartalmazza a kiváltó megfigyelést, a további célt, a használható erőforrásokat és az utófeltételt. E rekordok pontos nyelve következő tervezési feladat.

## Ellenőrzési határ és következő lépés

Ez a változat a nyolc forrásszöveg elolvasásán és stratégiai feldolgozásán alapul. Nem futtattuk a BridgeSingleDummy alkalmazást, nem ellenőriztük újra a nyolc kiosztást DDS-sel, és nincs implementált sémafelismerő vagy kottavégrehajtó.

A forrás DDS-ellenőrzésre vonatkozó állításai forrásállítások maradnak. Különösen a hand0004 esetében a szöveg maga is ellenőrzéshez köti a tervezett végállás működését. Egy konkrét kiosztás DD-ellenőrzése önmagában nem igazolja a rejtett lapok mellett alkalmazott teljes stratégiát.

A következő munkaváltozatban egyetlen egyszerű beszorítást célszerű teljesen kidolgozni: pontos alkalmazhatósági feltételekkel, szerephozzárendeléssel, célállással, elemi kottával, összes releváns ággal és olyan ellenpéldákkal, ahol egy szükséges feltétel hiányzik. Ezután érdemes az egyszerű beszorítás modulját a kettős beszorítással és az összetett végjátékokkal bővíteni.

## Forrás és szerzőség

Forrás: Koen Grauwels, BridgeSingleDummy, v0.9.13-test, a Linux kiadási csomag library.json fájljának nyolc bejegyzése, az angol tippek és megoldások alapján.

- [Repo](https://github.com/kgrauwel/BridgeSingleDummy)
- [Vizsgált kiadás](https://github.com/kgrauwel/BridgeSingleDummy/releases/tag/v0.9.13-test)

A tízmezős szerkezet, a modulok, a besorolás és a stratégiai hozzárendelés ebben a dokumentumban készült tervezet. A forrás nem tartalmazza ezt a formális felbontást. A dokumentum nem másolja a nyolc teljes feladatmegoldást.
