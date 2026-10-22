-- =====================================================================
--  kibic — 013: duplikáció-védelem a játszmákra
--
--  A LIN-ben NINCS parti-azonosító: se verseny-ID, se asztalszám.
--  A meglévő védelmek egyike sem elég:
--    * forras_fajl.fajl_hash  csak ugyanazt a FÁJLT fogja meg
--      (ugyanaz a verseny más exporttal más bájtokat ad)
--    * leosztas_hash          csak a LAPOKAT (egy leosztást sok asztal
--      játszik ugyanazon a versenyen)
--    * a jatszma táblán       SEMMI
--
--  A `jatszma_hash` a leosztásból, a négy játékosból és a licitmenetből
--  számítódik. Ugyanaz a parti kétszer letöltve azonos hasht ad; két
--  külön asztal ugyanazon a leosztáson nem.
-- =====================================================================

USE kibic;

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'jatszma' AND COLUMN_NAME = 'jatszma_hash');
SET @sql := IF(@kell,
  'ALTER TABLE jatszma ADD COLUMN jatszma_hash CHAR(64) NULL COMMENT ''SHA-256: leosztas_hash + a negy jatekos + a licitmenet. Duplikacio-vedelem.''',
  'SELECT ''A jatszma_hash oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

-- Az index CSAK akkor tehető egyedivé, ha nincs duplikátum.
-- Előbb megnézzük, van-e:
SELECT COUNT(*) AS duplikalt_hash FROM (
  SELECT jatszma_hash FROM jatszma
   WHERE jatszma_hash IS NOT NULL
   GROUP BY jatszma_hash HAVING COUNT(*) > 1) x;

SET @van_index := (SELECT COUNT(*) FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'jatszma'
                      AND INDEX_NAME = 'uq_jatszma_hash');
SET @sql2 := IF(@van_index = 0,
  'ALTER TABLE jatszma ADD UNIQUE KEY uq_jatszma_hash (jatszma_hash)',
  'SELECT ''Az egyedi index mar letezik'' AS migracio');
PREPARE st2 FROM @sql2; EXECUTE st2; DEALLOCATE PREPARE st2;

-- Az `ember` jelző a robotokra (a BBO `~~M` elotagja)
UPDATE jatekos SET ember = 0 WHERE azonosito LIKE '~~%';

SELECT COUNT(*) AS jatszma,
       SUM(jatszma_hash IS NOT NULL) AS hasheles_kesz
  FROM jatszma;
SELECT COUNT(*) AS robot_jatekos FROM jatekos WHERE ember = 0;
