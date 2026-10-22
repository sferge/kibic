-- =====================================================================
--  kibic — 007: hiányzó adatok pótlása + ÖNDIAGNÓZIS
--
--  Ha a 002/004/005 részben lefutott, ez a fájl pótolja a hiányt.
--  TELJESEN IDEMPOTENS: bármikor újrafuttatható.
--  A végén kiírja, mi hiányzik még.
-- =====================================================================

USE kibic;


-- ---------------------------------------------------------------------
-- 0. SÉMA-MIGRÁCIÓ: hiányzó oszlopok pótlása ADATVESZTÉS NÉLKÜL.
--
--    A `parameter` és `kriterium` táblák egy KORÁBBI változatból
--    származhatnak (a beszélgetésből futtatva), amelyben még nem volt
--    `csoport`, `sorrend`, `param_id2`, `ertek2`, `leiras` oszlop.
--    A MySQL 5.7 nem ismeri az "ADD COLUMN IF NOT EXISTS" szerkezetet,
--    ezért information_schema-vizsgálat + dinamikus SQL.
-- ---------------------------------------------------------------------

DROP PROCEDURE IF EXISTS kibic_oszlop_ha_kell;
DELIMITER $$
CREATE PROCEDURE kibic_oszlop_ha_kell(IN t VARCHAR(64), IN o VARCHAR(64),
                                      IN meghat TEXT)
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                  WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = t AND COLUMN_NAME = o) THEN
    SET @sql = CONCAT('ALTER TABLE `', t, '` ADD COLUMN `', o, '` ', meghat);
    PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;
    SELECT CONCAT('Hozzaadva: ', t, '.', o) AS migracio;
  END IF;
END$$
DELIMITER ;

CALL kibic_oszlop_ha_kell('parameter', 'csoport',
  "VARCHAR(40) NULL COMMENT 'Egyutt mozgo parameterek'");
CALL kibic_oszlop_ha_kell('parameter', 'min_ertek',
  "DECIMAL(6,2) NULL COMMENT 'A sopreshez: also hatar'");
CALL kibic_oszlop_ha_kell('parameter', 'max_ertek',
  "DECIMAL(6,2) NULL COMMENT 'A sopreshez: felso hatar'");
CALL kibic_oszlop_ha_kell('parameter', 'leiras', 'VARCHAR(500) NULL');
CALL kibic_oszlop_ha_kell('parameter', 'tipus',
  "ENUM('EGESZ','TIZEDES','LOGIKAI','FELSOROLAS') NOT NULL DEFAULT 'EGESZ'");

CALL kibic_oszlop_ha_kell('kriterium', 'sorrend',
  'SMALLINT UNSIGNED NOT NULL DEFAULT 0');
CALL kibic_oszlop_ha_kell('kriterium', 'param_id2',
  "SMALLINT UNSIGNED NULL COMMENT 'A KOZOTT felso hatara parameterkent'");
CALL kibic_oszlop_ha_kell('kriterium', 'ertek2', 'DECIMAL(6,2) NULL');
CALL kibic_oszlop_ha_kell('kriterium', 'leiras', 'VARCHAR(255) NULL');

CALL kibic_oszlop_ha_kell('kriterium_keszlet', 'leiras', 'VARCHAR(500) NULL');
CALL kibic_oszlop_ha_kell('kriterium_keszlet', 'min_teljesul',
  'TINYINT UNSIGNED NOT NULL DEFAULT 1');

DROP PROCEDURE kibic_oszlop_ha_kell;

-- ---------------------------------------------------------------------
-- 1. Értékelők (a 004-ből)
-- ---------------------------------------------------------------------
UPDATE ertekelo SET kod='AP_321', nev='Asztali pont (3-2-1)',
       leiras='HCP + renonsz 3 / szingli 2 / dubló 1'
 WHERE kod='AP';

INSERT IGNORE INTO ertekelo (kod, nev, leiras, kontextus) VALUES
 ('AP_531','Asztali pont (5-3-1)','HCP + siken 5 / szingli 3 / dublo 1','SZINTALALKOZAS'),
 ('NANO','Nano-pont','A=3, K=2, D=1','ABSZOLUT'),
 ('GYORSUTES','Gyorsutes','AK=2, AQ=1,5, A=1, KQ=1, Kx=0,5','ABSZOLUT'),
 ('EGYENLETES','Egyenletes (LICREN b)','Legalabb ket lap minden szinben','ABSZOLUT'),
 ('F1','Figurapont a leghosszabb szinben','LICREN f1','ABSZOLUT'),
 ('F2','Figurapont a 2. leghosszabb szinben','LICREN f2','ABSZOLUT'),
 ('F3','Figurapont a 3. leghosszabb szinben','LICREN f3','ABSZOLUT'),
 ('F4','Figurapont a legrovidebb szinben','LICREN f4','ABSZOLUT');

-- ---------------------------------------------------------------------
-- 2. Forrásdokumentumok (a 004-ből)
-- ---------------------------------------------------------------------
INSERT IGNORE INTO forras_dokumentum (kod, cim, szerzo, ev, formatum) VALUES
 ('MBSZ_EGYENI','Egyeni verseny licitrendszere - Standard','MBSZ',NULL,'PDF'),
 ('STD_AMERICAN','Standard American','Gyor',2002,'PDF'),
 ('SYLSTANDARD','Sylstandard',NULL,2009,'PDF'),
 ('MEZHON_DP','DP Licitrendszer',NULL,2011,'PDF'),
 ('SZEGEDI_MRAZ','Szegedi-Mraz licitrendszer','Szegedi Balazs & Mraz Mate',2008,'PDF'),
 ('HEAVYCLUB_2004','Heavy Club','Hajdu Peter',2004,'DOC'),
 ('LICREN_STAND','LICREN stand.lr',NULL,2013,'EGYEB'),
 ('LICREN_SZILPRE','LICREN szilpre.lr',NULL,2013,'EGYEB');

-- ---------------------------------------------------------------------
-- 3. Paraméterek (a 002-ből) — egyesével, hogy egy hiba ne vigye el a többit
-- ---------------------------------------------------------------------
INSERT IGNORE INTO parameter (kod,nev,ertekelo_id,alapertek,min_ertek,max_ertek,csoport,leiras)
 VALUES ('NYITAS_MIN','Nyitasi minimum (figurapont)',
         (SELECT id FROM ertekelo WHERE kod='HCP'),'12',10,14,'nyitas',
         'Van, aki 11-gyel, van, aki 13-mal nyit.');
INSERT IGNORE INTO parameter (kod,nev,ertekelo_id,alapertek,min_ertek,max_ertek,csoport)
 VALUES ('NYITAS_ZAR','Nyitasi kuszob Zar-pontban',
         (SELECT id FROM ertekelo WHERE kod='ZAR'),'26',24,30,'nyitas');
INSERT IGNORE INTO parameter (kod,nev,ertekelo_id,alapertek,min_ertek,max_ertek,csoport)
 VALUES ('NYITAS_LTC','Nyitasi kuszob vesztoutesben',
         (SELECT id FROM ertekelo WHERE kod='LTC'),'7',6,8,'nyitas');
INSERT IGNORE INTO parameter (kod,nev,ertekelo_id,alapertek,min_ertek,max_ertek,csoport)
 VALUES ('1NT_MIN','1 szan nyitas minimuma',
         (SELECT id FROM ertekelo WHERE kod='HCP'),'15',12,16,'szan');
INSERT IGNORE INTO parameter (kod,nev,ertekelo_id,alapertek,min_ertek,max_ertek,csoport)
 VALUES ('1NT_MAX','1 szan nyitas maximuma',
         (SELECT id FROM ertekelo WHERE kod='HCP'),'17',14,19,'szan');
INSERT IGNORE INTO parameter (kod,nev,ertekelo_id,alapertek,min_ertek,max_ertek,csoport)
 VALUES ('INVIT_MIN','Invit minimuma',
         (SELECT id FROM ertekelo WHERE kod='HCP'),'10',8,12,'valasz');
INSERT IGNORE INTO parameter (kod,nev,ertekelo_id,alapertek,min_ertek,max_ertek,csoport)
 VALUES ('GEM_MIN','Gemero minimuma (a par egyutt)',
         (SELECT id FROM ertekelo WHERE kod='HCP'),'25',23,27,'gem');
INSERT IGNORE INTO parameter (kod,nev,ertekelo_id,alapertek,min_ertek,max_ertek,csoport)
 VALUES ('SZLEM_MIN','Kisszlem-ero minimuma (a par egyutt)',
         (SELECT id FROM ertekelo WHERE kod='HCP'),'33',30,34,'szlem');
INSERT IGNORE INTO parameter (kod,nev,ertekelo_id,alapertek,min_ertek,max_ertek,csoport,leiras)
 VALUES ('MAJOR_MIN_HOSSZ','Nemes nyitas minimalis szinhossza',
         NULL,'5',4,5,'nyitas','Standard American: 5, Acol: 4');

-- ---------------------------------------------------------------------
-- 4. Kritérium-készlet: az INDULÓERŐ több értékelés alapján
-- ---------------------------------------------------------------------
INSERT IGNORE INTO kriterium_keszlet (kod,nev,min_teljesul,leiras) VALUES
 ('NYITAS_ERO','Nyitasi (indulo) ero',1,
  'HCP kotelezo; a Zar-pont es a vesztoutes kozul legalabb az egyik.');

INSERT IGNORE INTO kriterium (keszlet_id,sorrend,ertekelo_id,operator,param_id,kotelezo,leiras)
 VALUES ((SELECT id FROM kriterium_keszlet WHERE kod='NYITAS_ERO'),10,
         (SELECT id FROM ertekelo WHERE kod='HCP'),'>=',
         (SELECT id FROM parameter WHERE kod='NYITAS_MIN'),1,'Figurapont - kotelezo');
INSERT IGNORE INTO kriterium (keszlet_id,sorrend,ertekelo_id,operator,param_id,kotelezo,leiras)
 VALUES ((SELECT id FROM kriterium_keszlet WHERE kod='NYITAS_ERO'),20,
         (SELECT id FROM ertekelo WHERE kod='ZAR'),'>=',
         (SELECT id FROM parameter WHERE kod='NYITAS_ZAR'),0,'Zar-pont - valaszthato');
INSERT IGNORE INTO kriterium (keszlet_id,sorrend,ertekelo_id,operator,param_id,kotelezo,leiras)
 VALUES ((SELECT id FROM kriterium_keszlet WHERE kod='NYITAS_ERO'),30,
         (SELECT id FROM ertekelo WHERE kod='LTC'),'<=',
         (SELECT id FROM parameter WHERE kod='NYITAS_LTC'),0,'Vesztoutes - valaszthato');

-- ---------------------------------------------------------------------
-- 5. `par` tábla (az 005-ből) — csak ha még nincs
-- ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS par (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  jatekos_a     INT UNSIGNED NOT NULL,
  jatekos_b     INT UNSIGNED NOT NULL,
  nev           VARCHAR(120) NULL,
  rendszer_id   INT UNSIGNED NULL,
  rendszer_forras ENUM('DEKLARALT','FELTETELEZETT','ISMERETLEN') NOT NULL DEFAULT 'ISMERETLEN',
  rendszer_tol  DATE NULL,
  partik        INT UNSIGNED NOT NULL DEFAULT 0,
  elso_parti    DATE NULL,
  utolso_parti  DATE NULL,
  ember         TINYINT(1) NOT NULL DEFAULT 1,
  aktiv         TINYINT(1) NOT NULL DEFAULT 1,
  megjegyzes    VARCHAR(500) NULL,
  letrehozva    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_par (jatekos_a, jatekos_b),
  KEY ix_rendszer (rendszer_id),
  KEY ix_partik (partik),
  CONSTRAINT fk_par_a FOREIGN KEY (jatekos_a) REFERENCES jatekos(id),
  CONSTRAINT fk_par_b FOREIGN KEY (jatekos_b) REFERENCES jatekos(id),
  CONSTRAINT fk_par_r FOREIGN KEY (rendszer_id) REFERENCES rendszer(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO par (jatekos_a, jatekos_b)
SELECT DISTINCT LEAST(n_jatekos_id,s_jatekos_id), GREATEST(n_jatekos_id,s_jatekos_id)
  FROM jatszma WHERE n_jatekos_id IS NOT NULL AND s_jatekos_id IS NOT NULL
   AND n_jatekos_id <> s_jatekos_id;
INSERT IGNORE INTO par (jatekos_a, jatekos_b)
SELECT DISTINCT LEAST(e_jatekos_id,w_jatekos_id), GREATEST(e_jatekos_id,w_jatekos_id)
  FROM jatszma WHERE e_jatekos_id IS NOT NULL AND w_jatekos_id IS NOT NULL
   AND e_jatekos_id <> w_jatekos_id;

UPDATE par p SET partik = (
  SELECT COUNT(*) FROM jatszma j
   WHERE (LEAST(j.n_jatekos_id,j.s_jatekos_id)=p.jatekos_a
          AND GREATEST(j.n_jatekos_id,j.s_jatekos_id)=p.jatekos_b)
      OR (LEAST(j.e_jatekos_id,j.w_jatekos_id)=p.jatekos_a
          AND GREATEST(j.e_jatekos_id,j.w_jatekos_id)=p.jatekos_b));

UPDATE par p JOIN jatekos a ON a.id=p.jatekos_a JOIN jatekos b ON b.id=p.jatekos_b
   SET p.nev = CONCAT(a.megjelenit,' - ',b.megjelenit) WHERE p.nev IS NULL;

CREATE OR REPLACE VIEW v_par AS
SELECT p.id, p.nev, a.megjelenit AS jatekos_a, b.megjelenit AS jatekos_b,
       p.partik, r.kod AS rendszer, p.rendszer_forras, p.ember
FROM par p JOIN jatekos a ON a.id=p.jatekos_a JOIN jatekos b ON b.id=p.jatekos_b
LEFT JOIN rendszer r ON r.id=p.rendszer_id;

-- ---------------------------------------------------------------------
-- 6. ÖNDIAGNÓZIS
-- ---------------------------------------------------------------------
SELECT 'ertekelo'          AS tabla, COUNT(*) AS db, 15   AS varhato FROM ertekelo
UNION ALL SELECT 'parameter',         COUNT(*), 9         FROM parameter
UNION ALL SELECT 'kriterium_keszlet', COUNT(*), 1         FROM kriterium_keszlet
UNION ALL SELECT 'kriterium',         COUNT(*), 3         FROM kriterium
UNION ALL SELECT 'rendszer',          COUNT(*), 14        FROM rendszer
UNION ALL SELECT 'forras_dokumentum', COUNT(*), 8         FROM forras_dokumentum
UNION ALL SELECT 'par',               COUNT(*), NULL      FROM par
UNION ALL SELECT 'leosztas',          COUNT(*), 3389      FROM leosztas
UNION ALL SELECT 'jatszma',           COUNT(*), 3502      FROM jatszma;

SELECT nev, partik FROM v_par ORDER BY partik DESC LIMIT 15;
SELECT COUNT(*) AS parok, SUM(partik>=50) AS legalabb_50,
       SUM(partik>=100) AS legalabb_100 FROM par;
