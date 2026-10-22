# Bridzs AI — 0. fázis, első komponensek

## Tartalom

| Fájl | Szerep |
|---|---|
| `schema.sql` | MariaDB séma (fej-tétel szerkezet, értékelő-regiszter) |
| `bridzs/domain.py` | Domain-mag: lap, kéz, leosztás, lapértékelők |
| `bridzs/pontozas.py` | Eredménypontozás (scoring) + IMP-átváltás |
| `bridzs/pbn.py` | PBN-olvasó (rotáció-visszafejtéssel, claim-kezeléssel) |
| `bridzs/importalo.py` | Importáló CLI, dry-run móddal |

## Indulás

```bash
mysql -u root -p < schema.sql

# Elemzés adatbázis nélkül — ezzel kezdd:
python -m bridzs.importalo "partik/*.pbn" --dry-run

# Tényleges betöltés:
pip install pymysql
python -m bridzs.importalo "partik/*.pbn" --db bridzs --user root --jelszo TITKOS

# Az arany készlet megjelölése regressziós tesztnek:
python -m bridzs.importalo "arany/*.pbn" --db bridzs --cimke arany_keszlet
```

A CLI kilépési kódja 1, ha bármely pontszám eltért vagy kiosztás hibás volt —
így CI-ben is használható regressziós tesztként.

## Amit a `--dry-run` megválaszol

Hány leosztás, hány egyedi, hány claim, hány hiányos rekord, kik a játékosok,
és a legfontosabb: **egyezik-e a saját pontszámításunk a jegyzőkönyvvel**.
Ez a 0. fázis kilépési feltételének fele.

## Mi következik

1. LIN-olvasó (`bridzs/lin.py`) — ugyanaz az interfész, `PbnJatszma`-kompatibilis
   kimenettel. Kereszt-ellenőrzés: ugyanaz a parti mindkét formátumból
   azonos `leosztas_hash`-t és azonos lapsorrendet kell adjon.
2. Visszajátszó (`bridzs/visszajatszo.py`) — a lejátszás szabályossági
   ellenőrzése ütésről ütésre (színkötelezettség, ütésgyőztes, ütésszám),
   és az eredmény egyeztetése a jegyzőkönyvvel.
3. DDS-kötés + a `leosztas.dds_utesek` gyorsítótár feltöltése.

#BridzsAI 0-1. fázis átmenet ("kibic" — állapotjelentés: 2026.09.09.)

1. Projekt: neuro-szimbolikus hibrid bridzs ágens Gyökér: /scratch/mohAIbridzs/neuro_szimbolikus_hibrid Környezet: micromamba kibic, MySQL 5.7 (kibic adatbázis), 48 GB GPU + Threadripper Utolsó állapot: a 0. fázis kész és validált; az 1. fázis alapozása folyik
A szimbolikus mag elkészült és valódi adaton igazolt; a licitrendszer-tudásbázis sémája megvan, a feltöltése még nem kezdődött el.

2. Ami KÉSZ (0. fázis — minden kilépési feltétel teljesült)
Kód
    modul					mit csinál
domain/kartya.py		Lap, Kéz, Leosztás, PBN oda-vissza, hash, alapértékelők
domain/pontozas.py		eredménypontozás (scoring), IMP-átváltás
domain/ertekelo.py		NANO, AP_321, AP_531, GYORSUTES, EGYENLETES, F1–F4
impex/pbn.py			PBN-olvasó: rotáció-visszafejtés, claim, Note/alert kezelés
impex/importalo.py		idempotens importáló, dry-run, környezeti változók
impex/rendszerdoc.py		docx rendszerleírás-kinyerő (a színszimbólumok KÉPEK!)
impex/licren.py			a LICREN .lr formális nyelv értelmezője
motor/visszajatszo.py		licit- és lejátszás-ellenőrzés ütésről ütésre
motor/kriterium.py		paraméterezett, összetett lapkritériumok kiértékelése
solver/dds.py			DDS-kötés (endplay), öntesztelt
cli/ellenoriz.py		visszajátszó CLI (fájl vagy DB)
cli/ddsfutas.py			--tabla / --par / --claim
cli/alertek.py			alert-bányász: --konvenciok, --nyitas, --pontok

Minden nagyobb modulnak van öntesztje (python -m kibic.<modul>).

Adat (a kibic adatbázisban)
3389 leosztás, 3502 játszma, 81 336 kézérték (4 ülés × 6 metrika), 1022 játékos
DDS-tábla mind a 3389 leosztásra kiszámolva (63 leosztás/mp egyszálon, ≈ 4,4 óra/millió — a többszálúsítás még nem történt meg)
2885 alertelt licit (a tudásbázis nyersanyaga)
Mérési eredmények
Pontszámítás: 3469/3469 egyezik a jegyzőkönyvvel, 0 eltérés
Visszajátszás: 3499/3502 parti hibátlan (a 3 hiba: [Declarer] nélküli feladványok)
Licitből levezetett kontraktus + felvevő: 3468/3468 egyezik
Terítések: 2324-ből 2302 pontosan egyezik a double dummy maximummal, 4 „több" (a védők adtak fel ütést), 18 „kevesebb" (a felvevő biztosra ment)
3. Ami FOLYAMATBAN — az első teendő

Az SQL-migrációk lefuttatása. A 003 fájl elejére a bővített DROP blokk kell (mert egy félig lefutott állapot maradt), és a par / par_rendszer szakaszt ki kell venni belőle — az 005 hatásköre.

sql
USE kibic;
SET FOREIGN_KEY_CHECKS = 0;
DROP VIEW  IF EXISTS v_bejegyzes, v_licitmenet, v_feloldott, v_par;
DROP TABLE IF EXISTS feloldott_licitmenet, licitmenet_index, licitmenet,
                     bejegyzes_index, bejegyzes, rendszer_dokumentum,
                     par_rendszer, par_konvencio, rendszer_konvencio,
                     konvencio, rendszer, forras_dokumentum;
SET FOREIGN_KEY_CHECKS = 1;

Utána sorban: 003 → 004 → 005. (Az 005 fel is tölti a par táblát a játszmákból, és megválaszolja, mely pároknál van elég adat egyedi profilhoz.)

4. Ami KÖVETKEZIK (1. fázis)
Mintaillesztő (motor/minta.py) — a doc/mintanyelv.md szerinti minták illesztése valódi licitmenetekre: változókötés, Q (negyedik szín) relációs számítás, specifikusság-alapú ütközésfeloldás. Azonnal tesztelhető: a 3502 parti licitmenetein megnézhető, melyik minta milyen gyakran fordul elő.
Feloldó (motor/feloldas.py) — a rekurzív rendszer-hivatkozások feloldása körfigyeléssel, az eredmény a feloldott_licitmenet táblába.
Tudásbázis-feltöltés — kézzel, egy szűk szeleten (10–15 bejegyzés), hogy a séma kiforrjon; utána LLM-es javaslatgenerálás emberi jóváhagyással.
A módú licitáló és az első mérés a par-hoz viszonyított IMP-veszteséggel.
5. NYITOTT KÉRDÉSEK — ezekre válasz kell a folytatáshoz

a) A LICREN P, i, j képlete. A stand.lr 396-szor használja a P („pont") jelzőt — gyakrabban, mint a figurapontot (F, 92×). A súgófájl a képletet nem adja meg. Enélkül a LICREN-rendszerek (747 + 1180 szabály!) nem importálhatók helyesen. Három út: emlékezet, dokumentáció/forráskód, vagy visszafejtés a szabályokból.

b) A relé/lépcső tokenek beépítése a mintanyelvbe. Megbeszéltük, de a doc/mintanyelv.md MÉG NEM tartalmazza: R (relé, a legolcsóbb licit), R2/R3 (szuper relé), L1..L9 (lépcső). A Heavy Club relézős rendszer, enélkül nem kódolható. Tisztázandó: a lépcsőszámítás kihagy-e színeket (a dokumentumban van egy „Mi van, ha a relé az aduszínre esik? Kimarad!" megjegyzés).

c) Melyik rendszert kódoljuk először? A javaslat: az MBSZ egyéni (3 oldal, kanonikus, tartalmazza az 1 szan szeletet) legyen a tanulóterep, a Heavy Club (a te rendszered, már markdownban, 63 fejezet) a cél.

d) A Sylstandard rövidségi pontja. A nano-pont (A=3, K=2, D=1) megvan a dokumentumból, de a rövidségi pontokat nem találtam benne — ellenőrizendő.

6. Fontos tervezési döntések (hogy ne kelljen újra levezetni)
Minden legyen adat: licitrendszer, állapotgép, promptsablonok, paraméterek mind SQL-táblákban. Ha egy bővítés kódmódosítást kényszerít ott, ahol adatbővítésnek elég kellene lennie → architektúra-hibajel.
Kanonikus vs. származtatott: a minta a kanonikus, a kibontott index származtatott és bármikor újraépíthető. Ugyanez a DDS-gyorsítótárnál, a licit_akcio táblánál és a feloldott_licitmenet-nél.
Kényszertár = „mi lehet", ágensprofil = „mi valószínű". A profil sosem írja közvetlenül a kényszertárat; a mintavételező súlyain és — szigorúan evidencia-kapuzva — a rendszerparamétereken keresztül hat.
A/B/C üzemmód nem termék, hanem MÉRŐMŰSZER: A (tiszta algoritmus) a padló, B (tiszta LLM) a diagnózis, a kettő különbsége helyzettípusonként tölti fel a C mód routing-tábláját.
Egyetlen rendszer tábla fajta enummal (LICITRENDSZER / KONVENCIO / KONVENCIOKARTYA) → rekurzív modell. A hivatkozó saját sorai felülírják a behivatkozottak azonos kulcs-ú sorait, sorrendtől függetlenül.
A lapértékelés nem egy szám: értékelő-regiszter, és a rendszerbejegyzés nevezi meg, melyik metrikára hivatkozik (kiderült: két AP-iskola is van).
A terítés (claim) szabálya: a lapok BÁRMELY elhelyezkedése ellen állnia kell — a licitből származó következtetések NEM számítanak. Ezért a claim-ellenőrző szűkebb, tisztán fizikai kényszerhalmazból dolgozik, nem a kényszertárból.
7. Praktikus emlékeztetők
Importálás: python -m kibic.impex.importalo "tanpartik/**/*.pbn" --dry-run
A .gitignore-ban nincs soron belüli megjegyzés (a git nem ismeri!)
A tanpartik/ nem verziózott; a tests/arany/ és a schema/ igen
Kapcsolat: KIBIC_DB, KIBIC_HOST, KIBIC_USER, KIBIC_PASS környezeti változók
A .pbn és .lin fájlok sorvégeit a .gitattributes védi (fájl-hash!)