-- =====================================================================
--  kibic — 014: kompetitív helyzetek és a HELYZETI feltétel
--
--  MIÉRT: a `stand.lr` a `gal` pár licitpozícióinak 17%-ára ad szabályt,
--  és a 374 kompetitív helyzetből NULLÁRA. Nem azért, mert a rendszer
--  rossz, hanem mert a LICREN-alak csak a SAJÁT LAPRA tud feltételt
--  megfogalmazni. A kompetitív megállapodások viszont majdnem mindig a
--  HELYZETRE hivatkoznak:
--
--    "fésű: addig, ameddig a saját színünk gém alatt belicitálható"
--    "negatív kontra 2S-ig"
--    "kedvezőtlen zónában nem"
--    "csak akkor, ha a partner még nem nyilatkozott"
--
--  Ezek egyike sem a kézről szól. Ezért a `feltetel` (MILYEN LAPPAL)
--  mellé kell egy `ha_feltetel` (MILYEN HELYZETBEN). Ugyanaz a
--  kifejezésfa-gépezet (motor/kifejezes.py), új csomóponttípusokkal,
--  amiket a motor/helyzet.py értékel ki.
--
--  A MÁSODIK hiány: a szabály eddig megmondta, MIT ígér a licit
--  (`jelentes`), de nem azt, MIT VÁR a licitálótól a partner. A
--  `forsz` ezt csak részben fedi: az "erőt" mondja meg, a "műfajt"
--  nem. A Stayman és a negatív kontra egyaránt "egy menet forsz", de
--  az egyikre séma szerint kell felelni, a másikra ítélni kell.
--  Ez az `elvaras`.
--
--  A HARMADIK: kétnyelvűség. Az alert szövege a BBO-n angolul megy ki,
--  a magyarázat a promptban magyarul a legpontosabb. A meglévő
--  `magyarazat` oszlop marad a magyar; mellé jön az angol.
--
--  Futtatás: a 013 után. HeidiSQL-ből is megy (nincs DELIMITER).
-- =====================================================================

USE kibic;

-- ---------------------------------------------------------------------
-- 1. Helyzeti feltétel a licitmenet-szabályokhoz
-- ---------------------------------------------------------------------
--  A fa ugyanolyan JSON, mint a `feltetel`, de a KONTEXTUSRA kérdez.
--  Új csomóponttípusok (motor/helyzet.py):
--
--   {"t":"ULES","ertek":[1,2]}           hányadik ülésben licitálunk
--   {"t":"SZKOR","ertek":"O"}            zóna (már a 009-ben is volt)
--   {"t":"SZABAD"}                       jobbról passz jött: szabad licit
--   {"t":"SZINT","op":"<=","v":2}        a pillanatnyi licitszint
--   {"t":"GEM_ALATT","szin":"@M"}        a szín még gém alatt mondható
--   {"t":"MONDVA","szin":"S","ki":"ok"}  mondta-e már valaki a színt
--   {"t":"NYILATKOZOTT","ki":"p"}        a partner mondott-e már bármit
--   {"t":"FIT","szin":"@M","min":8}      ismert össz-hossz a kényszertárból
--   {"t":"IGERT","ki":"p","mit":"HOSSZ","szin":"S","op":">=","v":5}
--   {"t":"IGERT","ki":"p","mit":"PONT","op":">=","v":12}
--   {"t":"KONTRA_ALLAS","ertek":"MI"}    van-e élő kontra, és kié
--
--  A `ki` szerepváltozó értékei — mindig a LICITÁLÓHOZ képest:
--     "en"   a licitáló maga
--     "p"    a partner
--     "bal"  a balkéz felőli ellenfél (LHO)
--     "jobb" a jobbkéz felőli ellenfél (RHO)
--     "mi"   a vonalunk (bármelyikünk)
--     "ok"   az ellenfelek (bármelyikük)
--
--  A `szin` lehet konkrét (S/H/D/C/N) vagy VÁLTOZÓ (@M, @m, @X, @Q),
--  amit a minta illesztése köt meg — ugyanaz a kötés, mint a mintában.
-- ---------------------------------------------------------------------

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'licitmenet' AND COLUMN_NAME = 'ha_feltetel');
SET @sql := IF(@kell,
  'ALTER TABLE licitmenet ADD COLUMN ha_feltetel JSON NULL COMMENT ''HELYZETI feltetel (motor/helyzet.py). A `feltetel` a kezrol szol, ez a licitallasrol: zona, ules, mit mondtak eddig, gem alatt van-e meg a szinunk.''',
  'SELECT ''A ha_feltetel oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'licitmenet' AND COLUMN_NAME = 'ha_feltetel_szoveg');
SET @sql := IF(@kell,
  'ALTER TABLE licitmenet ADD COLUMN ha_feltetel_szoveg VARCHAR(500) NULL COMMENT ''A ha_feltetel ember altal olvashato alakja (a motor generalja).''',
  'SELECT ''A ha_feltetel_szoveg oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- ---------------------------------------------------------------------
-- 2. ELVÁRÁS — mit vár a licitáló a partnertől
-- ---------------------------------------------------------------------
--  A `forsz` az ERŐT mondja meg (meddig nem szabad passzolni), az
--  `elvaras` a MŰFAJT (mit kell csinálni). A kettő független:
--
--    Stayman          forsz=EGY_MENET   elvaras=VALASZ
--    negatív kontra   forsz=EGY_MENET   elvaras=DONTS
--    Jacoby transzfer forsz=NEM         elvaras=KORRIGALJ
--    5NT pick-a-slam  forsz=GEMFORSZ    elvaras=VALASSZ
--    gyenge 2         forsz=NEM         elvaras=PASSZOLJ
--    forsz passz      forsz=EGY_MENET   elvaras=DONTS
--
--  A forsz passz miatt fontos, hogy az elvárás a PASSZ-szabályokra is
--  rátehető legyen: "passzolok, de te ne hagyd bent" nem ugyanaz, mint
--  "passzolok, mert nincs mondanivalóm".
-- ---------------------------------------------------------------------

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'licitmenet' AND COLUMN_NAME = 'elvaras');
SET @sql := IF(@kell,
  'ALTER TABLE licitmenet ADD COLUMN elvaras ENUM(''SEMMI'',''VALASZ'',''VALASSZ'',''KORRIGALJ'',''DONTS'',''PASSZOLJ'') NOT NULL DEFAULT ''SEMMI'' COMMENT ''Mit var a licitalo a partnertol. SEMMI: leiro licit. VALASZ: kerdes, sema szerint kell felelni. VALASSZ: a felkinaltak kozul valasszon. KORRIGALJ: mondja meg az altalam kert szint / javitson. DONTS: itelje meg o, hova megyunk. PASSZOLJ: hagyja bent, ha nincs le nem irt extraja.''',
  'SELECT ''Az elvaras oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- ---------------------------------------------------------------------
-- 3. Kétnyelvűség
-- ---------------------------------------------------------------------
--  A meglévő `magyarazat` MARAD a magyar szöveg (nem nevezzük át, hogy
--  a betöltött 2000+ sor ne sérüljön). Mellé jön az angol, ami az
--  online alert szövege lesz.
-- ---------------------------------------------------------------------

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'licitmenet' AND COLUMN_NAME = 'magyarazat_en');
SET @sql := IF(@kell,
  'ALTER TABLE licitmenet ADD COLUMN magyarazat_en VARCHAR(500) NULL COMMENT ''Az alert angol szovege. A `magyarazat` a magyar.''',
  'SELECT ''A magyarazat_en oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'rendszer' AND COLUMN_NAME = 'leiras_en');
SET @sql := IF(@kell,
  'ALTER TABLE rendszer ADD COLUMN leiras_en VARCHAR(1000) NULL COMMENT ''A rendszer/konvencio angol leirasa.''',
  'SELECT ''A rendszer.leiras_en oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- A konvenciónak lehet közismert angol neve is (Negative Double):
SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'rendszer' AND COLUMN_NAME = 'nev_en');
SET @sql := IF(@kell,
  'ALTER TABLE rendszer ADD COLUMN nev_en VARCHAR(255) NULL COMMENT ''A konvencio bevett angol neve, ha van.''',
  'SELECT ''A rendszer.nev_en oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- ---------------------------------------------------------------------
-- 4. Forrás-URL a dokumentumkatalógusban
-- ---------------------------------------------------------------------
--  A PDF-ek egy részének van nyilvános forrása. Ha a fordítást később
--  vitatni kell, az `eredeti_utvonal` (a saját gépen) kevés — kell az,
--  ahonnan bárki ellenőrizheti.
-- ---------------------------------------------------------------------

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'forras_dokumentum' AND COLUMN_NAME = 'forras_url');
SET @sql := IF(@kell,
  'ALTER TABLE forras_dokumentum ADD COLUMN forras_url VARCHAR(500) NULL COMMENT ''Nyilvanos hivatkozas, ha van - a forditas ellenorizhetosegehez.''',
  'SELECT ''A forras_url oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- ---------------------------------------------------------------------
-- 5. Kompetitív paraméterek
-- ---------------------------------------------------------------------
--  MINDEN küszöb paraméter, egy sem beégetett. A `csoport='kompetitiv'`
--  azért kell, hogy a söprés (eszkozok/valasz_kuszobok.py mintájára)
--  EGYÜTT tudja mozgatni őket: ha a fésű alsó határa feljebb megy, a
--  belicitálás küszöbe is feljebb kell menjen, különben lyuk támad.
-- ---------------------------------------------------------------------

INSERT IGNORE INTO parameter (kod, nev, ertekelo_id, alapertek,
                              min_ertek, max_ertek, csoport, leiras) VALUES
 ('FESU_MIN', 'Fésű alsó határa (figurapont)',
  (SELECT id FROM ertekelo WHERE kod='HCP'), '6', 4, 10, 'kompetitiv',
  'Ennyi alatt nincs mondanivalonk: passz.'),
 ('FESU_MAX_SZINT', 'A legmagasabb szint, ameddig a fésű él',
  NULL, '3', 2, 5, 'kompetitiv',
  'Fix felso korlat. A GEM_ALATT feltetel ennel eletszerubb, ezert ez '
  'csak vegso vago - aki fix hataru fesut jatszik, ezt hasznalja.'),
 ('FESU_NEMES_HOSSZ', 'A fésű által ígért nemes hossza',
  NULL, '4', 4, 5, 'kompetitiv',
  'A negativ kontra tipikusan pontosan negyest iger - otossel szint '
  'mondanank.'),
 ('BELICIT_MIN', 'Belicitálás alsó határa (figurapont)',
  (SELECT id FROM ertekelo WHERE kod='HCP'), '8', 5, 12, 'kompetitiv', NULL),
 ('BELICIT_HOSSZ', 'Belicitálás minimális színhossza',
  NULL, '5', 4, 6, 'kompetitiv', NULL),
 ('BUNTETO_MIN', 'Büntető kontra alsó határa (figurapont)',
  (SELECT id FROM ertekelo WHERE kod='HCP'), '10', 8, 14, 'kompetitiv',
  'Kompetitiv helyzetben a buntetes sajat eronkbol - a partner mar '
  'nyilatkozott.'),
 ('BUNTETO_ADU', 'Büntető kontrához szükséges adufogás',
  NULL, '4', 3, 5, 'kompetitiv',
  'Hany lap az ellenfel szineben - ez a "onalloan meg tudja buntetni" '
  'merheto alakja.');

-- ---------------------------------------------------------------------
-- 6. A konvenciók angol neve (a meglévő 14 sorhoz)
-- ---------------------------------------------------------------------

UPDATE rendszer SET nev_en = 'Stayman'              WHERE kod = 'STAYMAN'       AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Jacoby transfer'      WHERE kod = 'JACOBY_TRF'    AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Texas transfer'       WHERE kod = 'TEXAS_TRF'     AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Fourth suit forcing'  WHERE kod = 'NEGYEDIK_SZIN' AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Bergen raises'        WHERE kod = 'BERGEN'        AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Reverse Bergen'       WHERE kod = 'FORD_BERGEN'   AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Jacoby 2NT'           WHERE kod = 'JACOBY_2NT'    AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Splinter'             WHERE kod = 'SPLINTER'      AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Negative double'      WHERE kod = 'NEG_DBL'       AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Inverted minor raise' WHERE kod = 'FORD_EMELES'   AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Multi 2D'             WHERE kod = 'MULTI'         AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Lebensohl'            WHERE kod = 'LEBENSOHL'     AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Roman Key Card Blackwood' WHERE kod = 'RKC'       AND nev_en IS NULL;
UPDATE rendszer SET nev_en = 'Four-way transfers'   WHERE kod = 'NEGY_SZIN_TRF' AND nev_en IS NULL;

-- ---------------------------------------------------------------------
-- 7. Nézetek
-- ---------------------------------------------------------------------

-- Mely szabályok kompetitívek, és van-e helyzeti feltételük?
CREATE OR REPLACE VIEW v_kompetitiv AS
SELECT r.kod AS rendszer, r.fajta, lm.id, lm.minta, lm.kulcs,
       lm.elvaras, lm.forsz,
       lm.feltetel_szoveg    AS kez_feltetel,
       lm.ha_feltetel_szoveg AS helyzet_feltetel,
       lm.magyarazat, lm.magyarazat_en, lm.allapot
FROM licitmenet lm
JOIN rendszer r ON r.id = lm.rendszer_id
WHERE lm.minta LIKE '%(%';   -- a zárójel a mintanyelvben = ellenfél licitje

-- A lefedettség mérőszáma: hány szabálynak van helyzeti feltétele
SELECT
  COUNT(*)                                        AS licitmenet_sorok,
  SUM(minta LIKE '%(%')                           AS kompetitiv_minta,
  SUM(ha_feltetel IS NOT NULL)                    AS van_helyzeti_feltetel,
  SUM(elvaras <> 'SEMMI')                         AS van_elvaras,
  SUM(magyarazat_en IS NOT NULL)                  AS van_angol_szoveg
FROM licitmenet;
