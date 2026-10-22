kibic — állapotjelentés

Frissítve: 2026-09-26. Ez a dokumentum azért van a projektben, hogy egy új beszélgetési szál is folytatható legyen belőle. A kód igazi otthona a git-repó a saját gépen (/scratch/mohAIbridzs/neuro_szimbolikus_hibrid); új szál elején a projekt zipjét egyszer fel kell tölteni a beszélgetésbe, mert .zip nem tehető projektfájllá. A teljes projektet kell feltölteni (src/ + tests/ + schema/ + eszkozok/), különben a tesztek nem követhetők.

Munkamenet: Claude a saját homokozójában tart egy projektmásolatot, abban javít és futtatja a teszteket, majd egy zipet ad, amiben csak a cserélendő és az új fájlok vannak, projektgyökérhez viszonyított útvonallal — a projektgyökérben kell kibontani.

1. Mit építünk

Egy nagyon erős bridzsjátékos MI-t kibic néven, neuro-szimbolikus hibrid architektúrával: szimbolikus mag + LLM-réteg a bizonytalan helyzetekre, double-dummy megoldóval (DDS) a mérésekhez.

Vezérelvek:

Minden legyen adat, ami csak lehet. Licitrendszerek, paraméterek, promptsablonok — és az értékelők képlete is adatbázisban.
A/B/C üzemmódok mint mérőműszer. A = tiszta algoritmus (padló), B = tiszta LLM (diagnózis), C = hibrid (a cél).
Ágensprofil: „egy bridzs pár több, mint két játékos." A kényszertár azt mondja meg, mi lehet; a párprofil azt, mi valószínű.
Kanonikus vs. származtatott. Minden származtatott adat eldobható.
Szabály kontra döntés. A szabály kapuz (hol érvényes, mit jelent); ahol ítélet kell, ott a mérlegelés dönt szimulációval. A kettő összekeverése — ítéletet küszöbnek álcázni — a legcsendesebb hibaforrás, és kétszer belesétáltunk.
2. Hol tartunk (2026-09-26)
0. fázis kész, 3502 parti validálva, 3469 pontszám egyezik.
Adatbázis: 6440 játszma, 4229+ leosztás DDS-táblával, 670 pár. A gal – korszurku pár 1707 partival a fő mérőanyag.
DD-szolgáltatás élesben a MohaBridzs apphoz (POST /v1/kibic/dd).
A licitálás is ráült a MohaBridzsre: POST /v1/bridge/bid és /v1/bridge/play, a mohabridzs-ai/1.0 szerződés szerint. Lásd a 6. pontot.
204 teszt zöld.
A 014–016 migráció lefutott. A FESU és az ALAPELVEK sorai JAVASOLT állapotban vannak — a motor csak ELFOGADOTT-at használ, tehát élesben még nem hatnak.
Az első éles fellépés és a javítása (2026-09-26)

Az első MohaBridzs-partin minden licit tartalék passz lett (rule_source: NINCS), és a kibic egyetlen LICREN_STAND licitet sem értett, a 1NT-t sem. Az adatbázis rendben volt (750 ELFOGADOTT szabály, a feloldás mind betölti) — három kódhiba okozta:

Megértés: a Propagalo kihagyja a jelentes nélküli szabályt, a LICREN-import pedig jelentes-t soha nem ír, csak feltetel-t. → Javítva: propagal.jelentes_feltetelbol() a feltételből kiolvassa, ami biztosan következik (ÉS = metszet, VAGY = alternatíva, a többi kimarad). @PONT-ból csak a felső korlát megy a HCP-re (P_HOSSZ ≥ HCP).
Licitálás: a szolgáltatás Kontextus-a metrika nélkül futott, így a @PONT üres kódra oldódott → minden nyitás ELDÖNTHETETLEN; az @INDULOERO készletét pedig senki nem töltötte be. → Javítva: Parametertar.metrika_terkep(), keszletfak_betolt(), kifejezes.rendszer_kontextus().
Kanonizálás: a nyitás előtti passzok bekerültek a mintába (P-1H), de egyetlen szabály sem kezdődik passzal (SQL-lel ellenőrizve) → 3./4. kézből soha nem nyitott, a passzolt partner nyitását nem értette. → Javítva: a kanonizal az első érdemi licittel kezd; a passzolt kéz az Allas-ból olvasható.
A fő nyitott probléma változatlanul a lefedettség

A stand.lr a licitpozíciók ~17%-ára ad szabályt, a kompetitívekre gyakorlatilag semmit (LICREN_STAND: 718 PAROS, 32 KUZDELMI, 0 VEDEKEZO). A fenti javítás után ami még NINCS, az valódi hiány a rendszerben — innen indul a standard rendszer kiegészítése (forrás: rendszerek/kibic_standard_1.0.doc és a rendszerek/konvenciok/). Az átjáró minden néma helyzetet "source": "fallback"-ként naplóz.

Ismert apróság: a licitmenet.ag oszlop elavult (mind a 750 PAROS); az aglefedettseg a mintából számol, tehát jól mér, de az oszlopot újra kellene számolni.

3. Mit tud ma a kibic — futtatható parancsok
source .env

# A SZOLGÁLTATÁS (DD + licit + MohaBridzs-átjáró egy folyamatban)
uvicorn kibic.szolgaltatas.api:app --host 0.0.0.0 --port 9050
#   fejlesztéskor: --reload --reload-dir src/kibic   (élesben NE)
#   DB-változás után: POST /v1/kibic/ujratolt

# A SZERZŐDÉS ELLENŐRZŐLISTÁJA — a webapp nélkül, 18 tétel
python -m kibic.cli.atjaroproba --cim http://localhost:9050 --titok "…"
python -m kibic.cli.atjaroproba --kez "SK S7 S4 HA HQ H6 H3 D9 D5 D2 C8 C6 C3" \
       --menet "1S P" --ules S --oszto N --beli ns

# MIT GONDOL EGY PARTIRÓL — a teljes lánc egy leosztáson
python -m kibic.cli.elemzo --veletlen --ag VEDEKEZO --rendszer LICREN_STAND
python -m kibic.cli.elemzo --jatszma 1234 --rendszer LICREN_STAND --meddig 3

# A LICITÁLÁS HÁROM ÁGA — gyakoriság és lefedettség
python -m kibic.cli.aglefedettseg --rendszer LICREN_STAND
python -m kibic.cli.aglefedettseg --par "gal - korszurku"

# DB NÉLKÜLI ELŐTTE/UTÁNA PRÓBA a megértésre és a nyitásra
python licren_proba.py

# A DOUBLE DUMMY TORZÍTÁSA — kalibráció az eloszlással
python -m kibic.cli.ddtorzitas --reszletes --mentes kalibracio.json

# korábbról
python -m kibic.cli.ellenoriz        # parti-validálás, pontszám-ellenőrzés
python -m kibic.cli.ddsfutas --tabla # DD-táblák, par-eredmények, terítés
python -m kibic.cli.meres            # A-módú mérés: melyik metrika jósol jobban
python -m kibic.cli.licitmeres       # licitmérés
python -m kibic.cli.licrenimport     # LICREN rendszer betöltése
python -m kibic.cli.alertek          # alert-kinyerés a gyűjteményből
python -m kibic.cli.karbantartas     # hash, duplikátumok
python -m kibic.cli.ddelemzo         # lap-elemzés (a DD-szolgáltatás magja)

Csak a helyes micromamba-környezetben fut kibic. előtaggal; rossz környezetben src.kibic. kellene — ilyenkor környezetet kell váltani.

Az elemzo a legbeszédesebb: kiírja a leosztást, a menetet, licitenként azt, hogy mit értett meg a rendszer, a kényszertár állását, hogy mit licitálna a kibic (jelölthalmazzal), és ha van mérlegelendő jelölt, lefuttatja a szimulációt.

4. Az architektúra darabjai
kényszertár  ->  mintavétel  ->  DDS  ->  pontozás  ->  várható írás
(propagal)       (mintavetel)    (solver)  (pontozas)    (merlegel)
motor/minta.py — mintanyelv 0.4: változókötés, indexelt színváltozók (I1/I2/V1/V2), + szint („a legkisebb szabad licit ebben a színben"), és a három ág (PAROS / KUZDELMI / VEDEKEZO), ami a minta alakjából származtatott, nem külön adat. A kanonizal a nyitás előtti passzokat elhagyja.
motor/feloldas.py — öröklés + felülírás a memóriában; a feloldott_licitmenet táblát csak a ment() írja, és a szolgáltatás nem olvassa (üres tábla nem hiba).
motor/helyzet.py — Allas + Igeret. Helyzeti csomópontok: ULES, SZKOR, SZABAD, SZINT, GEM_ALATT, MONDVA, NYILATKOZOTT, FIT, IGERT, KONTRA_ALLAS, AG, LICIT_LEGFELJEBB, ISMERT_SZINEK.
motor/propagal.py — jelentés-propagálás. Több lehetséges jelentésnél unió, nem metszet. Méri, hány licitet nem értettünk. jelentes hiányában a feltételből származtat.
motor/mintavetel.py — leosztások a kényszertárból. Először tiszta elfogadás-elutasítással (torzítatlan), és jelzi, ha az irányított ágra kellett esni.
motor/merlegel.py — összemérés IMP-ben és MP-ben külön, mert a két versenyformában más lehet a helyes döntés.
motor/licital.py — kétrétegű: SZABALY+KIVETEL, és csak ha az néma, akkor ELV. A MERLEGELO sorok jelöltje sosem nyer szabály alapon.
motor/kriterium.py — parametertar_betolt(): a háromszintű feloldás (alap → rendszer → pár), a logikai metrikák térképe (metrika_terkep) és a kritérium-készletek kifejezésfái (keszletfak).
motor/kifejezes.py — rendszer_kontextus(paramtar): EZZEL kell a licitmotor kontextusát építeni, nem puszta Kontextus(...)-szal.
A szolgáltatási réteg
szolgaltatas/api.py      HTTP: titok, idempotencia, gyorsítótár
      ├─ /v1/kibic/dd       lapelemzés (DD)          — dd.py
      ├─ /v1/kibic/licit    MAGYARÁZÓ elemzés        — licit.py   ← műhely
      ├─ /v1/bridge/bid     mohabridzs-ai/1.0 döntés — atjaro.py  ← éles
      └─ /v1/bridge/play    ma tartalék (lejátszó még nincs)
5. Amit eddig megtanultunk

A fésű = két rendezett lista összefésülése. Az ellenfél ismert színei és a mi szabad színeink rangsorrendben párba állnak (I1→V1, I2→V2). Ezért kellett az indexelt színváltozó és a + szint; enélkül konvenciónként és nyitószínenként külön sorokat kellett volna írni. Hat adatsor, nulla kód.

A DD torzítása MEGMÉRVE (6440 játszma):

	eltolás	szórás	n	szigma
sima szín	+0.033	0.85	3551	2.3
sima szan	+0.297	1.27	1549	9.2
kontrázott szín	+0.159	0.84	422	3.9
kontrázott szan	+0.270	1.43	37	1.2

Nem a kontra a fő torzító, hanem a szan. És nem azért, mert a védelem szanban többet hibázik, hanem mert a felvevő kevesebbet: színben a két hiba majdnem kioltja egymást (21% / 24%), szanban nem (20% / 37%).

Ebből: a büntető kontra egy bukásnál várhatóan veszteséges (3♣X, nem beli: a nyers DD +100-at lát, a valóság −23-at, mert ~29% eséllyel teljesítik). Gyakorlati szabály: kettő vagy több bukástól éri meg.

Az átlagkorrekció hatástalan, mert a kerekítés elnyeli (round(8 + 0.16) = 8). Eloszlásból kell húzni. Kis cellán (n < 200) pedig a durvább modellre kell esni, mert a legszebb átlag is zaj.

Az ELV külön műfaj, és nincs benne szám. Kétszer írtam bele küszöbképletet, és mindkétszer fölösleges volt:

a magasságot az ütésszám adja (a 2-es szinthez nyolc ütés kell);
a zónát a pontozás adja — ugyanaz az áldozat mansban ŐK-bell ellen három bukásig megéri, bellben ŐK-mans ellen csak egyig, és ez tisztán a pontértékekből jön ki.

Amit az elvből adat: hol érvényes, mit jelent, és hogy nem ő dönt. Pont az, amit szövegesen is meg lehet beszélni egy partnerrel.

6. A MohaBridzs-átjáró (2026-09-25)

A mohabridzs-ai/1.0 szerződés két végpontot kér, és a kibic ezeket ugyanabban a folyamatban szolgálja ki. A szolgaltatas/atjaro.py fordító, nem bridzsmodul: a licitdöntés a licit.py-ból jön.

A két szerződés nem ugyanaz, és ez a lényeg:

	/v1/kibic/licit	/v1/bridge/bid
a fő tartalom	a magyarázat	pontosan egy Action
call lehet null?	igen, ez a mérés	nem, kötelező és legális
idő	ráér	deadline_ms a mérvadó
szan	1NT	1N

A legfontosabb tervezési döntés: ha a kibic néma, az átjáró tartalékol (P), de bevallja — meta.source: "fallback", fallback_reason, és a meta.kibic.unknown_calls-ban megnevezi, melyik licitet nem értette. Következmény: a MohaBridzs admin AI-naplója magától lefedettséget mér, élesben, valódi leosztásokon, a hiány pontos címével együtt.

A lejátszás (/v1/bridge/play) ma kényszerű lapot ad, egyébként tartalékot — és annak is jelöli magát. A lejátszó modul még nincs kész.

Beüzemelés és tesztelés webapp nélkül: doc/mohabridzs-atjaro.md. Környezeti változók: KIBIC_SHARED_SECRET, KIBIC_RENDSZER, KIBIC_PROFILOK (profilkód → rendszer, tehát két AI-profil ülhet egy folyamaton), KIBIC_ATJARO_NAPLO, KIBIC_ATJARO_SZIMULACIO.

Hibakeresés, ha tartalék jön: a KIBIC_ATJARO_NAPLO JSONL-ben a kibic.auction_understanding licitenként mutatja, mit értett, az undecidable_rules pedig azt, hány szabály maradt eldönthetetlen (feloldatlan metrika!). Közvetlen próba: POST /v1/kibic/licit.

7. Nyitott bridzsszakmai kérdések
Meddig él a fésű? A GEM_ALATT a nemesekre jó, de a minor utáni Michaels-t nem zárja ki, pedig oda a forrás szerint nem fésű való.
A válasz szerkezete az információs kontra után: passz = büntetni akarok; nem ugró licit = kényszer (bármilyen színben, az erőről nem mond semmit); ugró licit = erő. Az „ugró" pontos jelentése: nem a legalacsonyabb lehetséges licit abban a színben — tehát (1♦) X után a 2♣ NEM ugrás. A mintanyelvben a + szint már a „nem ugró"-t jelöli; az „ugró"-ra még nincs jelölés.
A „jó" és „rossz" figurapont. Négy szempont: a figura címlete (1 ász > 4 bubi > …), a helye a színben (Dxx > Dx), a kombináció (KDxx > Kx + Dx), és az üléshely (a színt ígérő ellenfél után jobb, mint előtte). Az első három az ertekelo táblában leírható kódváltás nélkül; a negyedik kontextusfüggő, arra bővítés kell.
8. Felírt, nem sürgős
A LICREN_STAND kiegészítése a hiányzó (főleg kompetitív és védekező) helyzetekre — a következő nagy munka.
A licitmenet.ag oszlop újraszámolása a mintából.
/v1/kibic/allapot mutassa a betöltött szabályok és a származtatott jelentések számát rendszerenként.
A lejátszó modul — ez a legnagyobb hiányzó darab (ma tartalék).
.env betöltése a CLI-kbe (source .env kell ma).
DDS többszálúsítás.
Diszjunkt ágak az ígéretben (a lyukas pontsáv miatt).
Súlyozott mintavétel a torzított ág helyett.
Kalibráció a lejátszó oldalára külön.
Az átjáró idempotencia-tára a memóriában él (512 döntés), újraindításkor elvész.
9. Tanulságok, amiket kár volna újra megtanulni
A PBN [Note] címkéje ismételhető — enélkül 1164 fantomrekord.
A .gitignore nem ismeri a soron belüli megjegyzést.
A DELIMITER HeidiSQL-ből nem megy (CLI-ből igen).
Hash-pótlásnál kétfázisú feldolgozás kell.
A LICREN-ben az utolsó illeszkedő szabály nyer.
Több lehetséges jelentés esetén a kényszertárba unió megy.
Mintavételnél a fix színsorrend rendszeres torzítást okoz.
Átlagkorrekciót kerekíteni értelmetlen.
Kis cellán a legszebb átlag is zaj — a szigmát kell nézni.
A propagálásnál az elhangzott licitet kell a mintára illeszteni, nem fordítva: különben a kötetlen változó (1A) miatt a legegyszerűbb szabályok is némán kimaradnak.
Ha egy INSERT oszloplistája és értéklistája elcsúszik, a MySQL csak annyit mond, hogy „Column count doesn't match".
Külső szerződésnél a tartalékot be kell vallani (source: fallback). Ha a saját hiányunkat elrejtenénk egy szabályosnak látszó passz mögé, elvesztenénk a legolcsóbb mérőműszert, amit valaha kaptunk.
A CLI-mérés zöld, a szolgáltatás néma — mert a CLI kézzel adta a metrika-t, a szolgáltatás nem. Ami a mérésben kézzel van beállítva, annak a szolgáltatásban is ott kell lennie: ezért van most egyetlen belépő (rendszer_kontextus).
A „páros" licit valójában passzokkal teli (1H (P) 1S). A mintanyelv rövidítése és a valódi menet közti fordítás (kanonizálás) külön hibaforrás; a nyitás előtti passzok nem részei a mintának.
Importált rendszernél a jelentes üres — a megértés a feltételből származtatott jelentésen múlik. Ha egy rendszer „semmit nem ért", először ezt kell nézni.
A feloldott_licitmenet táblát a licitmenet újraimportja (ON DELETE CASCADE) kiüríti — de a szolgáltatás nem is olvassa.
Kibic javitas 2026 09 26b
ZIP
Kibic javitas 2026 09 26
ZIP
kibic-licren-javitas.patch
File
Licren proba
PY
Uploads
neuro_kibic.zip, src.zip
+17