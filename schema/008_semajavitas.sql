-- =====================================================================
--  kibic — 008: SÉMA-ÖSSZEHANGOLÁS
--
--  A teljes séma átvizsgálása után talált eltérések javítása.
--  A 007 után futtatandó. Adatvesztés nélkül, idempotensen.
--
--  MEGTALÁLT ELTÉRÉSEK:
--
--  (a) VALÓDI TERVEZÉSI HIBA — par_parameter elsődleges kulcsa
--      Jelenleg: PRIMARY KEY (par_id, parameter_id)
--      Helyesen: PRIMARY KEY (par_id, parameter_id, forras)
--      Enélkül egy párnak NEM lehet egyszerre DEKLARALT és MERT sora
--      ugyanarra a paraméterre — pedig épp a kettő KÜLÖNBSÉGE
--      az ágensprofil lényege ("15-17-et deklarálnak, de 14-gyel is
--      nyitnak"). Ez a hiba csendben elnyelte volna a profilt.
--
--  (b) Hiányzó oszlopok: parameter.csoport, kriterium.sorrend/param_id2/
--      leiras, kriterium_keszlet.leiras, par_parameter.megbizhatosag/
--      frissitve, rendszer_parameter.megjegyzes    -> a 007 pótolja
--
--  (c) Hiányzó idegen kulcsok a par_parameter és rendszer_parameter
--      táblákon (a korai, beszélgetésből futtatott változatból)
--
--  RENDBEN VOLT: leosztas (22 oszlop, alak VARCHAR(9)), jatszma,
--  licit_akcio, rendszer, licitmenet (25 oszlop), kez_ertek,
--  forras_fajl, esemeny, jatekos, licitmenet_index, feloldott_licitmenet
-- =====================================================================

USE kibic;

-- ---------------------------------------------------------------------
-- 1. Hiányzó oszlopok (a 007 migrációs blokkja már pótolhatta)
-- ---------------------------------------------------------------------

DROP PROCEDURE IF EXISTS kibic_oszlop_ha_kell;
DELIMITER $$
CREATE PROCEDURE kibic_oszlop_ha_kell(IN t VARCHAR(64), IN o VARCHAR(64),
                                      IN meghat TEXT)
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.TABLES
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = t)
     AND NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                      WHERE TABLE_SCHEMA = DATABASE()
                        AND TABLE_NAME = t AND COLUMN_NAME = o) THEN
    SET @sql = CONCAT('ALTER TABLE `', t, '` ADD COLUMN `', o, '` ', meghat);
    PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;
    SELECT CONCAT('Hozzaadva: ', t, '.', o) AS migracio;
  END IF;
END$$
DELIMITER ;

CALL kibic_oszlop_ha_kell('par_parameter', 'megbizhatosag',
  'TINYINT UNSIGNED NULL');
CALL kibic_oszlop_ha_kell('par_parameter', 'frissitve',
  'DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP');
CALL kibic_oszlop_ha_kell('rendszer_parameter', 'megjegyzes',
  'VARCHAR(255) NULL');

DROP PROCEDURE kibic_oszlop_ha_kell;

-- ---------------------------------------------------------------------
-- 2. A par_parameter elsődleges kulcsának javítása  (a) pont
--    Az `id` szintén hiányzott: enélkül a hármas kulcs kényelmetlen.
-- ---------------------------------------------------------------------

DROP PROCEDURE IF EXISTS kibic_pk_javitas;
DELIMITER $$
CREATE PROCEDURE kibic_pk_javitas()
BEGIN
  DECLARE oszlopok INT;
  SELECT COUNT(*) INTO oszlopok
    FROM information_schema.KEY_COLUMN_USAGE
   WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'par_parameter'
     AND CONSTRAINT_NAME = 'PRIMARY';
  IF oszlopok = 2 THEN
    ALTER TABLE par_parameter
      DROP PRIMARY KEY,
      ADD PRIMARY KEY (par_id, parameter_id, forras);
    SELECT 'par_parameter elsodleges kulcsa kiegeszitve a forras mezovel'
           AS migracio;
  END IF;
END$$
DELIMITER ;

CALL kibic_pk_javitas();
DROP PROCEDURE kibic_pk_javitas;

-- ---------------------------------------------------------------------
-- 3. Hiányzó idegen kulcsok  (c) pont
--    Csak akkor, ha a hivatkozott tábla létezik (a `par`-t a 007 hozza).
-- ---------------------------------------------------------------------

DROP PROCEDURE IF EXISTS kibic_fk_ha_kell;
DELIMITER $$
CREATE PROCEDURE kibic_fk_ha_kell(IN t VARCHAR(64), IN fk VARCHAR(64),
                                  IN oszlop VARCHAR(64),
                                  IN cel_tabla VARCHAR(64),
                                  IN cel_oszlop VARCHAR(64),
                                  IN vege VARCHAR(40))
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.TABLES
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = cel_tabla)
     AND NOT EXISTS (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS
                      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = t
                        AND CONSTRAINT_NAME = fk) THEN
    SET @sql = CONCAT('ALTER TABLE `', t, '` ADD CONSTRAINT `', fk,
                      '` FOREIGN KEY (`', oszlop, '`) REFERENCES `',
                      cel_tabla, '` (`', cel_oszlop, '`) ', vege);
    PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;
    SELECT CONCAT('Idegen kulcs: ', t, '.', oszlop, ' -> ', cel_tabla)
           AS migracio;
  END IF;
END$$
DELIMITER ;

CALL kibic_fk_ha_kell('par_parameter','fk_pp_par','par_id',
                      'par','id','ON DELETE CASCADE');
CALL kibic_fk_ha_kell('par_parameter','fk_pp_p','parameter_id',
                      'parameter','id','');
CALL kibic_fk_ha_kell('rendszer_parameter','fk_rp_r','rendszer_id',
                      'rendszer','id','ON DELETE CASCADE');
CALL kibic_fk_ha_kell('rendszer_parameter','fk_rp_p','parameter_id',
                      'parameter','id','');
CALL kibic_fk_ha_kell('kriterium','fk_k_param','param_id',
                      'parameter','id','');
CALL kibic_fk_ha_kell('kriterium','fk_k_param2','param_id2',
                      'parameter','id','');

DROP PROCEDURE kibic_fk_ha_kell;

-- ---------------------------------------------------------------------
-- 4. A hiányzó nézet
-- ---------------------------------------------------------------------

CREATE OR REPLACE VIEW v_par_elteres AS
SELECT p.id AS par_id, p.nev, pa.kod AS parameter,
       d.ertek AS deklaralt, m.ertek AS mert, m.megfigyeles
FROM par p
JOIN par_parameter d ON d.par_id = p.id AND d.forras = 'DEKLARALT'
LEFT JOIN par_parameter m ON m.par_id = p.id
     AND m.parameter_id = d.parameter_id AND m.forras = 'MERT'
JOIN parameter pa ON pa.id = d.parameter_id;

-- ---------------------------------------------------------------------
-- 5. ÖNDIAGNÓZIS
-- ---------------------------------------------------------------------

SELECT TABLE_NAME AS tabla, COUNT(*) AS oszlopok
  FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE()
   AND TABLE_NAME IN ('parameter','kriterium','kriterium_keszlet',
                      'par','par_parameter','rendszer_parameter')
 GROUP BY TABLE_NAME
 ORDER BY TABLE_NAME;

SELECT 'par_parameter PK oszlopai' AS ellenorzes,
       GROUP_CONCAT(COLUMN_NAME ORDER BY ORDINAL_POSITION) AS ertek
  FROM information_schema.KEY_COLUMN_USAGE
 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'par_parameter'
   AND CONSTRAINT_NAME = 'PRIMARY';
