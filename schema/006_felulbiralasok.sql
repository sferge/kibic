-- =====================================================================
--  kibic — 006: paraméter-felülbírálások rendszer- és pár-szinten
--
--  A paraméterek feloldása HÁROMSZINTŰ:
--     alapérték  ->  rendszerszintű  ->  pár-szintű
--
--  A pár-szintű lehet DEKLARALT (konvenciókártyáról) vagy MERT
--  (a megfigyelt licitekből következtetve). A kettő EGYÜTT állhat:
--  a különbségük maga az ÁGENSPROFIL.
--
--  Futtatás: a 003 (rendszer) és 005 (par) UTÁN.
-- =====================================================================

USE kibic;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS rendszer_parameter;
DROP TABLE IF EXISTS par_parameter;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE rendszer_parameter (
  rendszer_id  INT UNSIGNED     NOT NULL,
  parameter_id SMALLINT UNSIGNED NOT NULL,
  ertek        VARCHAR(30)      NOT NULL,
  megjegyzes   VARCHAR(255)     NULL,
  PRIMARY KEY (rendszer_id, parameter_id),
  CONSTRAINT fk_rp_r FOREIGN KEY (rendszer_id)  REFERENCES rendszer(id) ON DELETE CASCADE,
  CONSTRAINT fk_rp_p FOREIGN KEY (parameter_id) REFERENCES parameter(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE par_parameter (
  par_id       INT UNSIGNED     NOT NULL,
  parameter_id SMALLINT UNSIGNED NOT NULL,
  forras       ENUM('DEKLARALT','MERT') NOT NULL DEFAULT 'DEKLARALT',
  ertek        VARCHAR(30)      NOT NULL,
  megfigyeles  INT UNSIGNED     NOT NULL DEFAULT 0
               COMMENT 'MERT esetén: hány megfigyelésre épül. '
                       'Kevés adatnál a mezőnyátlag felé zsugorítunk.',
  megbizhatosag TINYINT UNSIGNED NULL,
  frissitve    DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP
               ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (par_id, parameter_id, forras),
  CONSTRAINT fk_pp_par FOREIGN KEY (par_id)       REFERENCES par(id) ON DELETE CASCADE,
  CONSTRAINT fk_pp_p   FOREIGN KEY (parameter_id) REFERENCES parameter(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- A deklarált és a mért érték egymás mellett — ez maga a profil
CREATE OR REPLACE VIEW v_par_elteres AS
SELECT p.id AS par_id, p.nev, pa.kod AS parameter,
       d.ertek AS deklaralt, m.ertek AS mert, m.megfigyeles
FROM par p
JOIN par_parameter d ON d.par_id = p.id AND d.forras = 'DEKLARALT'
LEFT JOIN par_parameter m ON m.par_id = p.id
     AND m.parameter_id = d.parameter_id AND m.forras = 'MERT'
JOIN parameter pa ON pa.id = d.parameter_id;
