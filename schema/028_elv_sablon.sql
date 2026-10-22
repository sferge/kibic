-- =====================================================================
--  kibic — 028: ELV-SABLON (2026-10-05)
--
--  Új rendszer-fajta: ELV_SABLON — egy elv ÁLTALÁNOSAN leírva (`.. +A`,
--  `.. 3NT`), saját paraméterekkel; egy rendszer úgy játssza, hogy
--  hivatkozik rá, és a hivatkozás mondja meg, HOL él (`ervenyes`: minták,
--  amelyek után) és MILYEN paraméterekkel (doc/terv-elvsablonok-2026-10-04.md).
--  Az első: FOGASMUTATAS (rendszerek/yaml/elvek/fogasmutatas.yaml).
--
--    rendszer.fajta            + 'ELV_SABLON'
--    rendszer.sablon           JSON: {szoveg, parameterek, terulet} — a
--                              szerkesztő megfogalmazása, a paraméterek
--                              alapértéke, és az elv területe (ahol a
--                              kártyán mögötte álló sorokat kiváltja)
--    licitmenet.hivatkozas_beallitas
--                              JSON a HIVATKOZAS soron: {ervenyes: [...],
--                              parameterek: {...}, kivalt: false}
--
--  Futtatás: a 027 után, a rendszerimport ELŐTT. Újrafuttatható.
-- =====================================================================

USE kibic;

ALTER TABLE rendszer
  MODIFY fajta ENUM('ALAPRENDSZER','KONVENCIO','RENDSZER','GYUJTEMENY',
                    'RENDSZERCSALAD','ELV_SABLON') NOT NULL;

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'rendszer' AND COLUMN_NAME = 'sablon');
SET @sql := IF(@kell,
  'ALTER TABLE rendszer ADD COLUMN sablon JSON NULL COMMENT ''ELV_SABLON: {szoveg, parameterek, terulet}''',
  'SELECT ''A rendszer.sablon oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

SET @kell := (SELECT COUNT(*) = 0 FROM information_schema.COLUMNS
               WHERE TABLE_SCHEMA = DATABASE()
                 AND TABLE_NAME = 'licitmenet' AND COLUMN_NAME = 'hivatkozas_beallitas');
SET @sql := IF(@kell,
  'ALTER TABLE licitmenet ADD COLUMN hivatkozas_beallitas JSON NULL COMMENT ''HIVATKOZAS egy ELV_SABLON-ra: {ervenyes, parameterek, kivalt}'' AFTER kizart_fejezet',
  'SELECT ''A licitmenet.hivatkozas_beallitas oszlop mar letezik'' AS migracio');
PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;

SELECT COLUMN_TYPE FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rendszer' AND COLUMN_NAME = 'fajta';
