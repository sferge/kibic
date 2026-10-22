-- =====================================================================
--  kibic — 016: a licitálás HÁROM ÁGA és az ELVEK
--
--  KÉT FELISMERÉS, mindkettő a fésű általánosításából.
--
--  1. HÁROM ÁG, NEM HÁROM RENDSZER.
--
--     A "páros licit" csak akkor érvényes, ha MI kezdünk és ők végig
--     hallgatnak. Ezen kívül van a KÜZDELMI ág (mi kezdtünk, ők
--     belelicitáltak) és a VÉDEKEZŐ ág (ők kezdtek). A valóságban a
--     páros ág a ritkább.
--
--     De ez NEM három külön rendszer, és nem is kell három `rendszer`
--     sor: ugyanannak a konvenciókártyának a három fejezete, és a
--     MINTA ALAKJA MÁR MEGMONDJA, melyikről van szó:
--
--         1NT-2C          kötőjeles          -> PAROS
--         1D (2C) 2H      mi vagyunk elöl    -> KUZDELMI
--         (1S) 2C         ők vannak elöl     -> VEDEKEZO
--         .. (*) X        `..`-vel kezdődik  -> BARMELYIK
--
--     Vagyis az ág SZÁRMAZTATOTT adat (motor/minta.py: `Minta.ag`,
--     `menet_ag()`; motor/helyzet.py: `Allas.ag`). Nem tárolni kell,
--     hanem MÉRNI vele: egy "17%-os lefedettség" semmit nem mond, ha
--     kiderül, hogy a páros ág 40%, a küzdelmi 2%, a védekező 0%.
--
--  2. AZ ELV MÁS MŰFAJ, MINT A SZABÁLY.
--
--     "Védekező rendszerben a KONTRA 4♥ magasságáig INFORMÁCIÓS."
--
--     Ez nem egy licitmenetre vonatkozik, hanem egy egész osztályra, és
--     nem azt mondja meg, MIKOR kontrázzunk, hanem azt, hogy HA kontra
--     hangzik el, az mit JELENT. Az elv tehát elsősorban a
--     jelentés-propagálásban él (motor/propagal.py), nem a
--     licitválasztásban.
--
--     Három dolog kell hozzá, és mindhárom a MŰFAJBÓL következik:

--     a) AZ ELV FALLBACK. Nem versenyez a szabályokkal, hanem MÖGÖTTÜK
--        áll: csak akkor szólal meg, ha a konkrét helyzetre nincs
--        érvényes konvenciónk. Ezt prioritással nem lehet jól megoldani,
--        mert az csak azonos `kulcs`-on belül rendez — két külön kulcsú
--        sor (egy konvenció és egy elv) így mindkettő jelölt maradna.
--        Ezért a motor KÉT RÉTEGBEN fut (motor/licital.py és
--        motor/propagal.py): előbb SZABALY+KIVETEL, és csak ha az néma
--        maradt, jönnek az ELV sorok. A `Dontes.elvre_esett` jelzi, ha
--        így dőlt el — ez a lefedettség őszinte mérőszáma, mert az
--        elvvel "lefedett" helyzet nem ugyanaz, mint amire van
--        megállapodásunk.

--     b) AZ ELVBEN NINCS SZÁM. Ez volt a legnagyobb tanulság, és
--        kerülőúton jutottunk el ide. Elsőre küszöbképletet írtam
--        ("a szkórhelyzetnek és a magasságnak megfelelő erő" =
--        alapkövetelmény + szintenkénti pótlék + zóna-kiigazítás), és
--        az egész fölösleges volt: a magasságot az ütésszám, a zónát a
--        pontozás adja, mindkettőt magától, a szimulációban. Amit
--        kézzel beírtam volna, az a pontos számítás durva közelítése.
--
--     c) AZ ELV NEM DÖNT. A szabály kapuz (hol érvényes, mit jelent), a
--        licitet a mérlegelés választja: lehetséges elosztások
--        generálása, DDS, valószínűségek, várható nyereség és veszteség
--        (motor/mintavetel.py + motor/merlegel.py). Ez nem a büntető
--        kontra sajátossága volt, hanem az elvek általános működése.
--
--     Új helyzeti csomópontok:
--       {"t":"AG","ertek":"VEDEKEZO"}                melyik ágban vagyunk
--       {"t":"LICIT_LEGFELJEBB","hatar":"4H"}        "4 kőr magasságáig"
--       {"t":"ISMERT_SZINEK","ki":"ok","db":2}       hány színt ígértek
--     A LICIT_LEGFELJEBB azért kell külön a `SZINT` mellett, mert a magyar
--     rendszerleírások licitmagasságban fogalmaznak, nem szintben: a
--     4♥ beleszámít, a 4♠ már nem. A `hatar` lehet paraméterkód is.
--
--  Futtatás: a 015 után.
-- =====================================================================

USE kibic;

-- ---------------------------------------------------------------------
-- 1. Szabály, elv vagy kivétel?
-- ---------------------------------------------------------------------

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'licitmenet'
                 AND COLUMN_NAME = 'szabaly_fajta');
SET @sql := IF(@kell,
  'ALTER TABLE licitmenet ADD COLUMN szabaly_fajta ENUM(''SZABALY'',''ELV'',''KIVETEL'') NOT NULL DEFAULT ''SZABALY'' COMMENT ''SZABALY: egy konkret licithelyzetre. ELV: egesz osztalyra ervenyes alapertelmezes, amit a specifikusabb sorok felulirnak - tipikusan JELENTEST ad, nem licitet javasol. KIVETEL: egy elv alol kivesz egy esetet.''',
  'SELECT ''A szabaly_fajta oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- Az ág SZÁRMAZTATOTT, de érdemes tárolni a gyors csoportosításhoz.
-- A motor számolja ki és írja be (mint a `specifikussag`-ot).
SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'licitmenet' AND COLUMN_NAME = 'ag');
SET @sql := IF(@kell,
  'ALTER TABLE licitmenet ADD COLUMN ag ENUM(''PAROS'',''KUZDELMI'',''VEDEKEZO'',''BARMELYIK'') NULL COMMENT ''SZARMAZTATOTT a mintabol (motor/minta.py Minta.ag). Eldobhato es ujraszamolhato.''',
  'SELECT ''Az ag oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

SET @van := (SELECT COUNT(*) FROM information_schema.STATISTICS
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'licitmenet'
                AND INDEX_NAME = 'ix_ag');
SET @sql := IF(@van = 0,
  'ALTER TABLE licitmenet ADD INDEX ix_ag (rendszer_id, ag, szabaly_fajta)',
  'SELECT ''Az ix_ag index mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- ---------------------------------------------------------------------
-- 2. Az ág feltöltése a meglévő sorokra (a motor pontosabban csinálja,
--    ez csak a gyors, mintaalapú közelítés)
-- ---------------------------------------------------------------------

UPDATE licitmenet SET ag =
  CASE
    WHEN minta IS NULL                THEN NULL
    WHEN minta LIKE '..%'             THEN 'BARMELYIK'
    WHEN minta NOT LIKE '%(%'         THEN 'PAROS'
    WHEN minta LIKE '(%'              THEN 'VEDEKEZO'
    ELSE 'KUZDELMI'
  END
WHERE tipus = 'SZABALY';

-- ---------------------------------------------------------------------
-- 3. Paraméterek az elvekhez
-- ---------------------------------------------------------------------

INSERT IGNORE INTO parameter (kod, nev, ertekelo_id, alapertek,
                              min_ertek, max_ertek, csoport, leiras) VALUES
 ('INFO_KONTRA_HATAR', 'Meddig információs a kontra (védekező ágban)',
  NULL, '4H', NULL, NULL, 'kompetitiv',
  'LICITMAGASSAG, nem szint: a 4H meg bele, a 4S mar nem. Van, aki 3S-ig, '
  'van, aki 4S-ig jatssza - ezert parameter.'),
 ('INFO_KONTRA_HATAR_KUZD', 'Ugyanez küzdelmi ágban',
  NULL, '3S', NULL, NULL, 'kompetitiv',
  'Sajat nyitas utan a partner kontraja tipikusan alacsonyabbig informacios.');

-- ---------------------------------------------------------------------
-- 4. ELVEK — a védekező ág kontra-megállapodása
-- ---------------------------------------------------------------------
--  Az elv FALLBACK: a motor csak akkor jut el ide, ha a konkrét réteg
--  (SZABALY + KIVETEL) néma maradt. A `prioritas` ezen belül rendez.
-- ---------------------------------------------------------------------

INSERT IGNORE INTO rendszer (kod, nev, nev_en, fajta, csalad, leiras, leiras_en)
VALUES ('ALAPELVEK', 'Alapelvek', 'General principles', 'KONVENCIO', 'EGYEB',
        'Egesz osztalyokra ervenyes alapertelmezesek, amiket a konkretabb '
        'szabalyok felulirnak. Nem licitet javasolnak, hanem jelentest adnak.',
        'Class-wide defaults that more specific rules override. They do not '
        'suggest a bid; they give meaning to one.');

SET @elv := (SELECT id FROM rendszer WHERE kod = 'ALAPELVEK');
DELETE FROM licitmenet WHERE rendszer_id = @elv;

INSERT INTO licitmenet
  (rendszer_id, fejezet, alfejezet, seq, tipus, szabaly_fajta, ag,
   minta, kulcs, prioritas, feltetel, feltetel_szoveg,
   ha_feltetel, ha_feltetel_szoveg, jelentes,
   magyarazat, magyarazat_en, alert, forsz, elvaras, allapot, megbizhatosag)
VALUES

-- 4.1 A védekező ág alapelve: a kontra információs, egy magasságig.
--
--     NINCS BENNE SZÁM, ÉS EZ SZÁNDÉKOS. Korábban ide egy küszöbképlet
--     került ("alapkövetelmény + szintenkénti pótlék + zóna-kiigazítás"),
--     és az egész fölösleges volt:
--
--       * A MAGASSÁG nem pótlék kérdése. A 2-es magassághoz nyolc ütés
--         kell hét helyett — ez a szimulációban magától megjelenik,
--         mert a magasabb kontraktus ritkábban jön be.
--       * A ZÓNA szintén nem. Ugyanaz az áldozat mansban ŐK-bell ellen
--         három bukásig megéri, bellben ŐK-mans ellen csak egyig — és
--         ez tisztán a bukások és a gémek pontértékéből jön ki, egyetlen
--         szabály nélkül. (Számolás: doc/elvek.md)
--
--     Ami marad, az pont az, amit szövegesen is meg lehet beszélni egy
--     partnerrel: HOL érvényes, MIT jelent, és hogy NEM Ő DÖNT.
--
--     A `feltetel` ezért NULL: a kontra a hatókörben mindig szóba jön,
--     és a `dontesi_mod='MERLEGELO'` miatt sosem nyer szabály alapon —
--     a döntést a mérlegelő hozza (motor/merlegel.py), a kényszertárból
--     vett mintán, DDS-sel és pontozással.
 (@elv, 'Védekező vonal', 'Kontra', 10, 'SZABALY', 'ELV', 'BARMELYIK',
  '.. (?) X', 'ELV_INFO_KONTRA', 1, NULL, NULL,
  '{"t":"ES","gy":[{"t":"AG","ertek":"VEDEKEZO"},{"t":"ISMERT_SZINEK","ki":"ok","op":">=","db":1},{"t":"LICIT_LEGFELJEBB","hatar":"INFO_KONTRA_HATAR"},{"t":"NEM","gy":[{"t":"NYILATKOZOTT","ki":"p"}]}]}',
  'védekező vonalon, ismert színük ellen, a {INFO_KONTRA_HATAR} magasságáig, a partner még nem nyilatkozott',
  '{"forsz":"EGY_MENET","tagad":["BUNTETO"]}',
  'Információs kontra. NEM büntető, és a partner válaszát kéri. Az erőről önmagában nem mond semmit: lehet 18+, lehet szerény lap jó elosztással — a válasz szerkezete tisztázza (passz = büntetni akarok; nem ugró licit = kényszer; ugró licit = erő).',
  'Takeout double. NOT for penalty; asks partner to respond. It says nothing definite about strength on its own — the shape of the reply clarifies it.',
  0, 'EGY_MENET', 'DONTS', 'JAVASOLT', 90),

-- 4.2 A komplementere: a határ fölött büntető. KIVETEL, mert ugyanannak
--     a megállapodásnak a másik fele — és mert a kivétel MEGELŐZI az
--     elvet: a motor előbb a SZABALY/KIVETEL réteget futtatja.
 (@elv, 'Védekező vonal', 'Kontra', 20, 'SZABALY', 'KIVETEL', 'BARMELYIK',
  '.. (?) X', 'ELV_BUNTETO_KONTRA', 5, NULL, NULL,
  '{"t":"ES","gy":[{"t":"AG","ertek":"VEDEKEZO"},{"t":"NEM","gy":[{"t":"LICIT_LEGFELJEBB","hatar":"INFO_KONTRA_HATAR"}]}]}',
  'védekező vonalon, a {INFO_KONTRA_HATAR} határ fölött',
  '{"tagad":["INFORMACIOS"]}',
  'Büntető kontra. A határ fölött a kontra már nem információs — nincs hova kivenni.',
  'Penalty double. Above the takeout ceiling there is no room to respond.',
  0, 'NEM', 'DONTS', 'JAVASOLT', 90);

-- MINDKETTŐ mérlegelendő: a szabály kapuz, a szimuláció dönt.
UPDATE licitmenet SET dontesi_mod = 'MERLEGELO'
 WHERE rendszer_id = @elv;

-- ---------------------------------------------------------------------
-- 5. Nézetek: ÁGANKÉNTI lefedettség
-- ---------------------------------------------------------------------
--  Ez a jelentés adja meg a valódi képet arról, hol tart egy rendszer.
--  A páros ág könnyen leírható és általában jól fedett; a másik kettő
--  zömmel konvenciókból és elvekből áll, és ott szokott kiderülni,
--  hogy a rendszer valójában mennyit tud.
-- ---------------------------------------------------------------------

CREATE OR REPLACE VIEW v_ag AS
SELECT r.kod AS rendszer, r.fajta, lm.ag, lm.szabaly_fajta,
       COUNT(*)                          AS sorok,
       SUM(lm.allapot = 'ELFOGADOTT')    AS elfogadott,
       SUM(lm.ha_feltetel IS NOT NULL)   AS helyzetfuggo,
       SUM(lm.jelentes IS NOT NULL)      AS van_jelentes,
       SUM(lm.feltetel IS NULL)          AS nincs_kez_feltetel
FROM licitmenet lm
JOIN rendszer r ON r.id = lm.rendszer_id
WHERE lm.tipus = 'SZABALY'
GROUP BY r.kod, r.fajta, lm.ag, lm.szabaly_fajta;

SELECT * FROM v_ag ORDER BY rendszer, ag, szabaly_fajta;

-- Az ELVEK külön: ezek adják a "mindig érvényes" alapréteget
SELECT lm.ag, lm.szabaly_fajta, lm.minta, lm.ha_feltetel_szoveg,
       lm.magyarazat
  FROM licitmenet lm
  JOIN rendszer r ON r.id = lm.rendszer_id
 WHERE r.kod = 'ALAPELVEK'
 ORDER BY lm.seq;
