-- =====================================================================
--  kibic — 005: a `par` tábla mint önálló entitás
--  Futtatás a 003 UTÁN. A par_rendszer megszűnik: egy pár megfigyeléseiből
--  nem RENDSZERT mérünk, hanem PARAMÉTEREKET (par_parameter, MERT forrás).
-- =====================================================================
USE kibic;

SET FOREIGN_KEY_CHECKS = 0;
DROP VIEW  IF EXISTS v_par;
DROP TABLE IF EXISTS par_rendszer;
DROP TABLE IF EXISTS par;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE par (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  jatekos_a     INT UNSIGNED NOT NULL COMMENT 'MINDIG a kisebb id - normalizalt',
  jatekos_b     INT UNSIGNED NOT NULL,
  nev           VARCHAR(120) NULL,
  rendszer_id   INT UNSIGNED NULL,
  rendszer_forras ENUM('DEKLARALT','FELTETELEZETT','ISMERETLEN')
                NOT NULL DEFAULT 'ISMERETLEN',
  rendszer_tol  DATE NULL,
  partik        INT UNSIGNED NOT NULL DEFAULT 0,
  elso_parti    DATE NULL,
  utolso_parti  DATE NULL,
  ember         TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '0 = robot-par (pl. GIB)',
  aktiv         TINYINT(1)   NOT NULL DEFAULT 1,
  megjegyzes    VARCHAR(500) NULL,
  letrehozva    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_par (jatekos_a, jatekos_b),
  KEY ix_rendszer (rendszer_id),
  KEY ix_partik   (partik),
  CONSTRAINT fk_par_a FOREIGN KEY (jatekos_a)   REFERENCES jatekos(id),
  CONSTRAINT fk_par_b FOREIGN KEY (jatekos_b)   REFERENCES jatekos(id),
  CONSTRAINT fk_par_r FOREIGN KEY (rendszer_id) REFERENCES rendszer(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Feltöltés a játszmákból (újrafuttatható)
INSERT IGNORE INTO par (jatekos_a, jatekos_b)
SELECT DISTINCT LEAST(n_jatekos_id, s_jatekos_id),
                GREATEST(n_jatekos_id, s_jatekos_id)
  FROM jatszma
 WHERE n_jatekos_id IS NOT NULL AND s_jatekos_id IS NOT NULL
   AND n_jatekos_id <> s_jatekos_id;

INSERT IGNORE INTO par (jatekos_a, jatekos_b)
SELECT DISTINCT LEAST(e_jatekos_id, w_jatekos_id),
                GREATEST(e_jatekos_id, w_jatekos_id)
  FROM jatszma
 WHERE e_jatekos_id IS NOT NULL AND w_jatekos_id IS NOT NULL
   AND e_jatekos_id <> w_jatekos_id;

UPDATE par p SET partik = (
  SELECT COUNT(*) FROM jatszma j
   WHERE (LEAST(j.n_jatekos_id, j.s_jatekos_id) = p.jatekos_a
          AND GREATEST(j.n_jatekos_id, j.s_jatekos_id) = p.jatekos_b)
      OR (LEAST(j.e_jatekos_id, j.w_jatekos_id) = p.jatekos_a
          AND GREATEST(j.e_jatekos_id, j.w_jatekos_id) = p.jatekos_b));

UPDATE par p
  JOIN jatekos a ON a.id = p.jatekos_a
  JOIN jatekos b ON b.id = p.jatekos_b
   SET p.nev = CONCAT(a.megjelenit, ' - ', b.megjelenit)
 WHERE p.nev IS NULL;

CREATE OR REPLACE VIEW v_par AS
SELECT p.id, p.nev, a.megjelenit AS jatekos_a, b.megjelenit AS jatekos_b,
       p.partik, r.kod AS rendszer, p.rendszer_forras, p.ember
FROM par p
JOIN jatekos a       ON a.id = p.jatekos_a
JOIN jatekos b       ON b.id = p.jatekos_b
LEFT JOIN rendszer r ON r.id = p.rendszer_id;
