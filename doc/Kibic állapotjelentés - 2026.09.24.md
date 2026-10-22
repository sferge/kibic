kibic — állapotjelentés

Frissítve: 2026-09-23 este. Ez a dokumentum azért van a projektben, hogy egy új beszélgetési szál is folytatható legyen belőle. A kód igazi otthona a git-repó a saját gépen (/scratch/mohAIbridzs/neuro_szimbolikus_hibrid); új szál elején a projekt zipjét egyszer fel kell tölteni a beszélgetésbe, mert .zip nem tehető projektfájllá.

1. Mit építünk

Egy nagyon erős bridzsjátékos MI-t kibic néven, neuro-szimbolikus hibrid architektúrával: szimbolikus mag + LLM-réteg a bizonytalan helyzetekre, double-dummy megoldóval (DDS) a mérésekhez.

Vezérelvek:

Minden legyen adat, ami csak lehet. Licitrendszerek, paraméterek, promptsablonok — és az értékelők képlete is adatbázisban.
A/B/C üzemmódok mint mérőműszer. A = tiszta algoritmus (padló), B = tiszta LLM (diagnózis), C = hibrid (a cél).
Ágensprofil: „egy bridzs pár több, mint két játékos." A kényszertár azt mondja meg, mi lehet; a párprofil azt, mi valószínű.
Kanonikus vs. származtatott. Minden származtatott adat eldobható.
Szabály kontra döntés. A szabály kapuz (hol érvényes, mit jelent); ahol ítélet kell, ott a mérlegelés dönt szimulációval. A kettő összekeverése — ítéletet küszöbnek álcázni — a legcsendesebb hibaforrás, és kétszer belesétáltunk.
2. Hol tartunk (2026-09-23)
0. fázis kész, 3502 parti validálva, 3469 pontszám egyezik.
Adatbázis: 6440 játszma, 4229+ leosztás DDS-táblával, 670 pár. A gal – korszurku pár 1707 partival a fő mérőanyag.
DD-szolgáltatás élesben a MohaBridzs apphoz (POST /v1/kibic/dd).
174 teszt zöld (integrációsakkal együtt).
A 014–016 migráció lefutott. A FESU és az ALAPELVEK sorai JAVASOLT állapotban vannak — a motor csak ELFOGADOTT-at használ, tehát élesben még nem hatnak.
A fő nyitott probléma változatlanul a lefedettség

A stand.lr a licitpozíciók ~17%-ára ad szabályt, a kompetitívekre gyakorlatilag semmit. Az aglefedettseg mérő most ezt ágakra bontja — ez a szám még nincs megmérve, ez a következő lépés.

3. Mit tud ma a kibic — futtatható parancsok
source .env

# MIT GONDOL EGY PARTIRÓL — a teljes lánc egy leosztáson
python -m kibic.cli.elemzo --veletlen --ag VEDEKEZO --rendszer LICREN_STAND
python -m kibic.cli.elemzo --jatszma 1234 --rendszer LICREN_STAND --meddig 3

# A LICITÁLÁS HÁROM ÁGA — gyakoriság és lefedettség
python -m kibic.cli.aglefedettseg --rendszer LICREN_STAND
python -m kibic.cli.aglefedettseg --par "gal - korszurku"

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

Az elemzo a legújabb és a legbeszédesebb: kiírja a leosztást, a menetet, licitenként azt, hogy mit értett meg a rendszer, a kényszertár állását, hogy mit licitálna a kibic (jelölthalmazzal), és ha van mérlegelendő jelölt, lefuttatja a szimulációt.

4. Az architektúra darabjai
kényszertár  ->  mintavétel  ->  DDS  ->  pontozás  ->  várható írás
(propagal)       (mintavetel)    (solver)  (pontozas)    (merlegel)
motor/minta.py — mintanyelv 0.4: változókötés, indexelt színváltozók (I1/I2/V1/V2), + szint („a legkisebb szabad licit ebben a színben"), és a három ág (PAROS / KUZDELMI / VEDEKEZO), ami a minta alakjából származtatott, nem külön adat.
motor/helyzet.py — Allas + Igeret. Helyzeti csomópontok: ULES, SZKOR, SZABAD, SZINT, GEM_ALATT, MONDVA, NYILATKOZOTT, FIT, IGERT, KONTRA_ALLAS, AG, LICIT_LEGFELJEBB, ISMERT_SZINEK.
motor/propagal.py — jelentés-propagálás. Több lehetséges jelentésnél unió, nem metszet. Méri, hány licitet nem értettünk.
motor/mintavetel.py — leosztások a kényszertárból. Először tiszta elfogadás-elutasítással (torzítatlan), és jelzi, ha az irányított ágra kellett esni.
motor/merlegel.py — összemérés IMP-ben és MP-ben külön, mert a két versenyformában más lehet a helyes döntés.
motor/licital.py — kétrétegű: SZABALY+KIVETEL, és csak ha az néma, akkor ELV. A MERLEGELO sorok jelöltje sosem nyer szabály alapon.
motor/kriterium.py — parametertar_betolt(): a háromszintű feloldás (alap → rendszer → pár). Eddig hiányzott, és emiatt minden paraméterre hivatkozó szabály csendben eldönthetetlen volt.
5. Amit ebben a körben megtanultunk

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

Ami az elvből adat: hol érvényes, mit jelent, és hogy nem ő dönt. Pont az, amit szövegesen is meg lehet beszélni egy partnerrel.

6. Nyitott bridzsszakmai kérdések
Meddig él a fésű? A GEM_ALATT a nemesekre jó, de a minor utáni Michaels-t nem zárja ki, pedig oda a forrás szerint nem fésű való.
A válasz szerkezete az információs kontra után: passz = büntetni akarok; nem ugró licit = kényszer (bármilyen színben, az erőről nem mond semmit); ugró licit = erő. Az „ugró" pontos jelentése: nem a legalacsonyabb lehetséges licit abban a színben — tehát (1♦) X után a 2♣ NEM ugrás. A mintanyelvben a + szint már a „nem ugró"-t jelöli; az „ugró"-ra még nincs jelölés.
A „jó" és „rossz" figurapont. Négy szempont: a figura címlete (1 ász > 4 bubi > …), a helye a színben (Dxx > Dx), a kombináció (KDxx > Kx + Dx), és az üléshely (a színt ígérő ellenfél után jobb, mint előtte). Az első három az ertekelo táblában leírható kódváltás nélkül; a negyedik kontextusfüggő, arra bővítés kell.
7. Felírt, nem sürgős
.env betöltése a CLI-kbe (source .env kell ma).
DDS többszálúsítás.
Diszjunkt ágak az ígéretben (a lyukas pontsáv miatt).
Súlyozott mintavétel a torzított ág helyett.
Kalibráció a lejátszó oldalára külön.
A doc/ és eszkozok/ mappa nem volt benne a zipben.
8. Tanulságok, amiket kár volna újra megtanulni
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
Ha egy INSERT oszloplistája és értéklistája elcsúszik, a MySQL csak annyit mond, hogy „Column count doesn't match" — érdemes a migrációkat oszlopszám-ellenőrzéssel átnézni kiadás előtt.