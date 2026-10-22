-- =====================================================================
--  kibic — 002: paraméterek és kritérium-készletek
--
--  Ez a fájl korábban CSAK a beszélgetésben létezett, fájlként nem —
--  ezért hiányzott a schema/ mappából. A benne lévő táblák az
--  adatbázisban már megvannak; a fájl a REPRODUKÁLHATÓSÁGOT szolgálja
--  (friss telepítésnél ez építi fel őket).
--
--  Két fogalom:
--   * PARAMÉTER — megnevezett szám, amire a bejegyzések NÉVVEL
--     hivatkoznak ("NYITAS_MIN"), nem beégetve.
--   * KRITÉRIUM-KÉSZLET — összetett feltétel SZÁMOSSÁGGAL:
--     a kötelezőknek mind teljesülniük kell, a választhatókból
--     `min_teljesul` darabnak. Így az "indulóerő" eldönthető több
--     értékelés TÖBBSÉGE alapján (FP + Zar + LTC + kontroll...),
--     nem egyetlen szabállyal.
--
--  Futtatás: a 001 (alapséma, `ertekelo` táblával) UTÁN,
--            a 003 (tudásbázis) ELŐTT.
-- =====================================================================

USE kibic;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS kriterium;
DROP TABLE IF EXISTS kriterium_keszlet;
DROP TABLE IF EXISTS parameter;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 1. Paraméterek
-- ---------------------------------------------------------------------

CREATE TABLE parameter (
  id          SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  kod         VARCHAR(40)  NOT NULL COMMENT 'NYITAS_MIN, 1NT_MIN, 1NT_MAX...',
  nev         VARCHAR(100) NOT NULL,
  leiras      VARCHAR(500) NULL,
  tipus       ENUM('EGESZ','TIZEDES','LOGIKAI','FELSOROLAS')
              NOT NULL DEFAULT 'EGESZ',
  ertekelo_id SMALLINT UNSIGNED NULL
              COMMENT 'MELYIK metrikában értendő. NULL, ha nem lapérték '
                      '(pl. minimális színhossz).',
  alapertek   VARCHAR(30)  NOT NULL,
  min_ertek   DECIMAL(6,2) NULL COMMENT 'A söpréshez: értelmes alsó határ',
  max_ertek   DECIMAL(6,2) NULL COMMENT 'A söpréshez: értelmes felső határ',
  csoport     VARCHAR(40)  NULL
              COMMENT 'Együtt mozgó paraméterek. Ha a nyitási minimum '
                      'változik, a válaszok küszöbeit is hangolni kell.',
  UNIQUE KEY uq_parameter (kod),
  KEY ix_csoport (csoport),
  CONSTRAINT fk_p_ertekelo FOREIGN KEY (ertekelo_id) REFERENCES ertekelo(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 2. Kritérium-készletek
-- ---------------------------------------------------------------------

CREATE TABLE kriterium_keszlet (
  id           SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  kod          VARCHAR(40)  NOT NULL COMMENT 'NYITAS_ERO, 1NT_ERO...',
  nev          VARCHAR(100) NOT NULL,
  leiras       VARCHAR(500) NULL,
  min_teljesul TINYINT UNSIGNED NOT NULL DEFAULT 1
               COMMENT 'A NEM kötelező kritériumokból ennyinek kell '
                       'teljesülnie. 0 = nem számítanak, 1 = VAGY, '
                       'N = ÉS, közte = "legalább M az N-ből".',
  UNIQUE KEY uq_kk (kod)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE kriterium (
  id          SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  keszlet_id  SMALLINT UNSIGNED NOT NULL,
  sorrend     SMALLINT UNSIGNED NOT NULL DEFAULT 0,
  ertekelo_id SMALLINT UNSIGNED NOT NULL COMMENT 'HCP / ZAR / LTC / NANO...',
  operator    ENUM('>=','<=','=','KOZOTT') NOT NULL,
  -- Az érték jöhet PARAMÉTERBŐL vagy fix számként:
  param_id    SMALLINT UNSIGNED NULL,
  ertek       DECIMAL(6,2) NULL,
  -- A KOZOTT felső határa (szintén paraméter vagy fix):
  param_id2   SMALLINT UNSIGNED NULL,
  ertek2      DECIMAL(6,2) NULL,
  kotelezo    TINYINT(1)   NOT NULL DEFAULT 0,
  leiras      VARCHAR(255) NULL,
  KEY ix_keszlet (keszlet_id, sorrend),
  CONSTRAINT fk_k_keszlet  FOREIGN KEY (keszlet_id)  REFERENCES kriterium_keszlet(id) ON DELETE CASCADE,
  CONSTRAINT fk_k_ertekelo FOREIGN KEY (ertekelo_id) REFERENCES ertekelo(id),
  CONSTRAINT fk_k_param    FOREIGN KEY (param_id)    REFERENCES parameter(id),
  CONSTRAINT fk_k_param2   FOREIGN KEY (param_id2)   REFERENCES parameter(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 3. Kiinduló paraméterek
-- ---------------------------------------------------------------------

INSERT IGNORE INTO parameter (kod, nev, ertekelo_id, alapertek,
                              min_ertek, max_ertek, csoport, leiras) VALUES
 ('NYITAS_MIN', 'Nyitási minimum (figurapont)',
  (SELECT id FROM ertekelo WHERE kod='HCP'),   '12', 10, 14, 'nyitas',
  'Van, aki 11-gyel, van, aki 13-mal nyit.'),
 ('NYITAS_ZAR', 'Nyitási küszöb Zar-pontban',
  (SELECT id FROM ertekelo WHERE kod='ZAR'),   '26', 24, 30, 'nyitas', NULL),
 ('NYITAS_LTC', 'Nyitási küszöb vesztőütésben',
  (SELECT id FROM ertekelo WHERE kod='LTC'),    '7',  6,  8, 'nyitas', NULL),
 ('1NT_MIN',    '1 szan nyitás minimuma',
  (SELECT id FROM ertekelo WHERE kod='HCP'),   '15', 12, 16, 'szan', NULL),
 ('1NT_MAX',    '1 szan nyitás maximuma',
  (SELECT id FROM ertekelo WHERE kod='HCP'),   '17', 14, 19, 'szan', NULL),
 ('INVIT_MIN',  'Invit minimuma',
  (SELECT id FROM ertekelo WHERE kod='HCP'),   '10',  8, 12, 'valasz', NULL),
 ('GEM_MIN',    'Gémerő minimuma (a pár együtt)',
  (SELECT id FROM ertekelo WHERE kod='HCP'),   '25', 23, 27, 'gem', NULL),
 ('SZLEM_MIN',  'Kisszlem-erő minimuma (a pár együtt)',
  (SELECT id FROM ertekelo WHERE kod='HCP'),   '33', 30, 34, 'szlem', NULL),
 ('MAJOR_MIN_HOSSZ', 'Nemes nyitás minimális színhossza',
  NULL, '5', 4, 5, 'nyitas', 'Standard American: 5, Acol: 4');

-- Példa összetett kritériumra: az INDULÓERŐ több értékelés alapján.
-- A figurapont KÖTELEZŐ; a Zar és a vesztőütés közül legalább egy.
INSERT IGNORE INTO kriterium_keszlet (kod, nev, min_teljesul, leiras) VALUES
 ('NYITAS_ERO', 'Nyitási (induló) erő', 1,
  'HCP kötelező; a Zar-pont és a vesztőütés közül legalább az egyik. '
  'A min_teljesul emelésével szigorítható.');

INSERT IGNORE INTO kriterium (keszlet_id, sorrend, ertekelo_id, operator,
                              param_id, kotelezo, leiras)
SELECT (SELECT id FROM kriterium_keszlet WHERE kod='NYITAS_ERO'), s.sorrend,
       (SELECT id FROM ertekelo WHERE kod=s.ek), s.op,
       (SELECT id FROM parameter WHERE kod=s.pk), s.kot, s.leiras
FROM (
  SELECT 10 AS sorrend, 'HCP' AS ek, '>=' AS op, 'NYITAS_MIN' AS pk,
         1 AS kot, 'Figurapont - kötelező' AS leiras
  UNION ALL SELECT 20, 'ZAR', '>=', 'NYITAS_ZAR', 0, 'Zar-pont - választható'
  UNION ALL SELECT 30, 'LTC', '<=', 'NYITAS_LTC', 0, 'Vesztőütés - választható'
) s;
