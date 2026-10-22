-- =====================================================================
--  kibic — 009: kifejezésfa a licitmenet-szabályokhoz
--
--  MIÉRT: a lapos `kriterium_keszlet` (kötelező + min_teljesul) nem tudja
--  ábrázolni az egymásba ágyazott ÉS/VAGY feltételeket, amilyeneket a
--  valódi rendszerleírások használnak:
--      1N: ((F[12,14])&(L4>1)&(5>L1)) o ((F[11,13])&(L4>1)&...)
--
--  A `feltetel` oszlop egy ÁLTALÁNOS KIFEJEZÉSFÁT tárol JSON-ban, ahol a
--  LEGALABB(m) csomópont az ÉS-t (m=n), a VAGY-ot (m=1) és a TÖBBSÉGET
--  (m=ceil(n/2)) egyaránt kifejezi.
--
--  A `kriterium_keszlet` NEM szűnik meg: az továbbra is a NEVESÍTETT,
--  ember által írt kritériumoké (pl. NYITAS_ERO), és a fából
--  hivatkozható a {"t":"KESZLET","kod":"NYITAS_ERO"} csomóponttal.
--
--  Kiértékelés: HÁROMÉRTÉKŰ (igaz / hamis / ismeretlen). Az ismeretlen
--  azért kell, mert néhány LICREN-jelző képlete még tisztázatlan
--  (P = pont, i = indulóerő, j = játékütés). Így nem rossz képlettel
--  döntünk csendben, hanem MÉRHETŐ, hány szabály nem eldönthető.
--
--  MÉRT ÁLLAPOT (a fordítás után):
--      stand.lr / stund.lr   378/747  (51%) teljesen kiértékelhető
--                            blokkolók: P=364, j=26
--      szilpre.lr            979/1180 (83%)
--                            blokkolók: P=187, i=11, j=5
-- =====================================================================

USE kibic;

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

CALL kibic_oszlop_ha_kell('licitmenet', 'feltetel',
  "JSON NULL COMMENT 'Kifejezesfa (motor/kifejezes.py). Peldaul: "
  "{\\\"t\\\":\\\"ES\\\",\\\"gy\\\":[{\\\"t\\\":\\\"OSSZE\\\",\\\"op\\\":\\\">\\\","
  "\\\"bal\\\":{\\\"t\\\":\\\"SZIN\\\",\\\"szin\\\":\\\"S\\\"},"
  "\\\"jobb\\\":{\\\"t\\\":\\\"SZAM\\\",\\\"v\\\":4}}]}'");

CALL kibic_oszlop_ha_kell('licitmenet', 'feltetel_szoveg',
  "VARCHAR(1000) NULL COMMENT 'A feltetel ember altal olvashato alakja "
  "(a motor generalja) - ez megy a promptba es az alertbe'");

CALL kibic_oszlop_ha_kell('licitmenet', 'ismeretlen_jelzok',
  "VARCHAR(120) NULL COMMENT 'Mely jelzok teszik eldonthetetlenne "
  "(P, i, j). Ha kitoltott, a szabaly HAROMERTEKU kiertekelest ad.'");

CALL kibic_oszlop_ha_kell('licitmenet', 'dontesi_mod',
  "ENUM('SORREND','SPECIFIKUSSAG','MERLEGELO') NOT NULL DEFAULT 'SORREND' "
  "COMMENT 'SORREND: elso illeszkedo nyer (LICREN-hu). "
  "SPECIFIKUSSAG: a legspecifikusabb. "
  "MERLEGELO: a jelolthalmaz tovabbi megfontolasokra megy (C mod).'");

DROP PROCEDURE kibic_oszlop_ha_kell;

-- Nézet: mely szabályok eldönthetetlenek és miért
CREATE OR REPLACE VIEW v_eldonthetetlen AS
SELECT r.kod AS rendszer, lm.minta, lm.ismeretlen_jelzok,
       lm.feltetel_szoveg, lm.allapot
FROM licitmenet lm
JOIN rendszer r ON r.id = lm.rendszer_id
WHERE lm.ismeretlen_jelzok IS NOT NULL AND lm.ismeretlen_jelzok <> '';

SELECT COUNT(*) AS licitmenet_sorok FROM licitmenet;
