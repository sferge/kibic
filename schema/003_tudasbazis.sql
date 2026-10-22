-- =====================================================================
--  kibic — 003: licitrendszer-tudásbázis  (v0.2)
--
--  A v0.1 (külön konvencio + rendszer_konvencio táblákkal) ELAVULT.
--  Ez a változat EGYETLEN fogalomra vezeti vissza a licitrendszert, a
--  konvenciót és a konvenciókártyát: mindhárom `rendszer`, csak a
--  `fajta` enum különbözteti meg őket. Ettől a modell REKURZÍV lesz:
--  egy rendszer behivatkozhat másik rendszereket, azok újakat, és a
--  hivatkozó saját sorai felülírják a behivatkozottakat.
--
--  Alapelvek:
--   * FEJ-TÉTEL:  rendszer (fej) 1:N licitmenet (tétel)
--   * A minta a KANONIKUS alak; a kibontott index SZÁRMAZTATOTT.
--   * Minden szám PARAMÉTERRE hivatkozik, nem beégetett érték.
--   * Minden tételnek van PROVENIENCIÁJA és ÁLLAPOTA.
--   * A licitáló motor KIZÁRÓLAG elfogadott tételeket használ.
-- =====================================================================

USE kibic;

-- A v0.1 táblák eldobása (üresek voltak)
SET FOREIGN_KEY_CHECKS = 0;
DROP VIEW  IF EXISTS v_bejegyzes;
DROP VIEW  IF EXISTS v_licitmenet;
DROP VIEW  IF EXISTS v_feloldott;
DROP VIEW  IF EXISTS v_par;
DROP TABLE IF EXISTS feloldott_licitmenet;
DROP TABLE IF EXISTS licitmenet_index;
DROP TABLE IF EXISTS licitmenet;
DROP TABLE IF EXISTS bejegyzes_index;
DROP TABLE IF EXISTS bejegyzes;
DROP TABLE IF EXISTS rendszer_dokumentum;
DROP TABLE IF EXISTS par_rendszer;
DROP TABLE IF EXISTS par;
DROP TABLE IF EXISTS par_konvencio;
DROP TABLE IF EXISTS rendszer_konvencio;
DROP TABLE IF EXISTS konvencio;
DROP TABLE IF EXISTS rendszer;
DROP TABLE IF EXISTS forras_dokumentum;
SET FOREIGN_KEY_CHECKS = 1;

-- ---------------------------------------------------------------------
-- 1. Forrásdokumentum — KATALÓGUS
--    Hol van az "igazság forrása": az emberi nyelvű leírás, amire a
--    kibic-nyelvű fordítás épül. N:M a rendszerrel: egy rendszert több
--    dokumentum írhat le, egy dokumentum több rendszert tartalmazhat.
-- ---------------------------------------------------------------------

CREATE TABLE forras_dokumentum (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  kod             VARCHAR(40)  NOT NULL,          -- HEAVYCLUB_2004
  cim             VARCHAR(255) NOT NULL,
  szerzo          VARCHAR(255) NULL,
  ev              SMALLINT     NULL,
  eredeti_utvonal VARCHAR(500) NULL,
  formatum        ENUM('DOC','DOCX','PDF','MD','EGYEB') NOT NULL DEFAULT 'EGYEB',
  kinyert_szoveg  LONGTEXT     NULL COMMENT 'A géppel olvasható markdown',
  megjegyzes      VARCHAR(500) NULL,
  UNIQUE KEY uq_fdok (kod)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 2. Rendszer (FEJ) — licitrendszer, konvenció VAGY konvenciókártya
-- ---------------------------------------------------------------------

CREATE TABLE rendszer (
  id          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  kod         VARCHAR(40)  NOT NULL,              -- HEAVYCLUB, STAYMAN, FERGE_PAR
  nev         VARCHAR(255) NOT NULL,
  fajta       ENUM('LICITRENDSZER','KONVENCIO','KONVENCIOKARTYA') NOT NULL,
  csalad      ENUM('NATURAL','STRONG_CLUB','ACOL','PRECISION','POLISH','EGYEB')
              NOT NULL DEFAULT 'EGYEB',
  leiras      VARCHAR(1000) NULL,
  verzio      VARCHAR(20)  NOT NULL DEFAULT '0.1',
  aktiv       TINYINT(1)   NOT NULL DEFAULT 1,
  UNIQUE KEY uq_rendszer (kod),
  KEY ix_fajta (fajta, aktiv)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- N:M kapcsolat a katalógussal
CREATE TABLE rendszer_dokumentum (
  rendszer_id   INT UNSIGNED NOT NULL,
  dokumentum_id INT UNSIGNED NOT NULL,
  fejezettol    VARCHAR(120) NULL COMMENT 'Ha a dokumentumnak csak egy része',
  megjegyzes    VARCHAR(255) NULL,
  PRIMARY KEY (rendszer_id, dokumentum_id),
  CONSTRAINT fk_rd_r FOREIGN KEY (rendszer_id)   REFERENCES rendszer(id) ON DELETE CASCADE,
  CONSTRAINT fk_rd_d FOREIGN KEY (dokumentum_id) REFERENCES forras_dokumentum(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 3. Licitmenet (TÉTEL) — egy sor a rendszer leírásából
--
--    Kétféle sor lehet:
--      tipus='SZABALY'    -> saját szabály (minta + kritérium + jelentés)
--      tipus='HIVATKOZAS' -> egy másik rendszer beemelése (REKURZIÓ)
--
--    A FELÜLÍRÁS KULCSA a `kulcs` mező (alapból a normalizált minta):
--    a hivatkozó rendszer saját sorai kiütik a behivatkozott rendszer
--    azonos kulcsú sorait, FÜGGETLENÜL a sorrendtől.
-- ---------------------------------------------------------------------

CREATE TABLE licitmenet (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  rendszer_id   INT UNSIGNED NOT NULL,

  -- STRUKTÚRA: fejezet/alfejezet + sorszám. A tagolás önmagában is segít:
  -- egy konkrét helyzet sorai így együtt kereshetők.
  fejezet       VARCHAR(120) NULL COMMENT 'pl. "1♣ indulás"',
  alfejezet     VARCHAR(120) NULL COMMENT 'pl. "1♣-1♦ folytatások"',
  seq           INT UNSIGNED NOT NULL DEFAULT 0
                COMMENT 'Sorszám, 10-esével hagyva helyet a beszúrásnak',

  tipus         ENUM('SZABALY','HIVATKOZAS') NOT NULL DEFAULT 'SZABALY',

  -- --- HIVATKOZÁS esetén ---
  hivatkozott_id   INT UNSIGNED NULL
                   COMMENT 'A beemelt rendszer/konvenció id-je',
  hivatkozas_aktiv TINYINT(1) NOT NULL DEFAULT 1
                   COMMENT 'Kikapcsolható: "ezt a konvenciót mi nem játsszuk"',

  -- --- SZABÁLY esetén ---
  minta         VARCHAR(120) NULL
                COMMENT 'doc/mintanyelv.md — pl. "1NT-2C", "1M-2M", "1D (2C) 2M"',
  kulcs         VARCHAR(120) NULL
                COMMENT 'A FELÜLÍRÁS kulcsa. Alapból a normalizált minta, de '
                        'kézzel megadható csoportos felülíráshoz (pl. "STAYMAN_AG")',
  specifikussag SMALLINT UNSIGNED NOT NULL DEFAULT 0
                COMMENT 'Számított: konkrét szín 4, kötött változó 2, helyettesítő 0',
  prioritas     SMALLINT     NOT NULL DEFAULT 0,

  kriterium_id  SMALLINT UNSIGNED NULL COMMENT 'MIKOR licitálható (kéz-feltétel)',
  jelentes      JSON NULL
                COMMENT 'MIT JELENT — kényszertár-frissítés. '
                        '{"hcp":{"min":0,"max":"1C_NEG_MAX"},'
                        ' "szinhossz":{"H":{"min":5}},"tagad":["5_SZIN"]}',
  magyarazat    VARCHAR(500) NULL COMMENT 'Emberi nyelvű: alert + prompt',
  alert         TINYINT(1)   NOT NULL DEFAULT 0,
  forsz         ENUM('NEM','EGY_MENET','GEMFORSZ','SZLEMFORSZ','KIZARO')
                NOT NULL DEFAULT 'NEM',

  -- --- PROVENIENCIA és ÁLLAPOT (mindkét típusnál) ---
  dokumentum_id INT UNSIGNED NULL,
  dok_fejezet   VARCHAR(120) NULL COMMENT 'Melyik fejezetből fordítottuk',
  nyers_szoveg  TEXT         NULL COMMENT 'Az eredeti emberi nyelvű mondat',
  allapot       ENUM('JAVASOLT','ELFOGADOTT','ELVETETT','FELULVIZSGALANDO')
                NOT NULL DEFAULT 'JAVASOLT',
  megbizhatosag TINYINT UNSIGNED NULL COMMENT '0-100, ha LLM javasolta',
  jovahagyta    VARCHAR(60)  NULL,
  jovahagyva    DATETIME     NULL,
  letrehozva    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

  KEY ix_rendszer  (rendszer_id, seq),
  KEY ix_kulcs     (rendszer_id, kulcs),
  KEY ix_minta     (minta),
  KEY ix_allapot   (allapot),
  KEY ix_hivatkozas(hivatkozott_id),
  KEY ix_fejezet   (rendszer_id, fejezet, alfejezet, seq),
  CONSTRAINT fk_lm_rendszer FOREIGN KEY (rendszer_id)    REFERENCES rendszer(id) ON DELETE CASCADE,
  CONSTRAINT fk_lm_hivatk   FOREIGN KEY (hivatkozott_id) REFERENCES rendszer(id),
  CONSTRAINT fk_lm_krit     FOREIGN KEY (kriterium_id)   REFERENCES kriterium_keszlet(id),
  CONSTRAINT fk_lm_dok      FOREIGN KEY (dokumentum_id)  REFERENCES forras_dokumentum(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 4. SZÁRMAZTATOTT táblák — eldobhatók és újraépíthetők
-- ---------------------------------------------------------------------

-- 5a. A minták kibontott alakja: gyors keresés ÉS emberi ellenőrzés
--     ("mit fed le pontosan ez a minta?")
CREATE TABLE licitmenet_index (
  licitmenet_id INT UNSIGNED NOT NULL,
  szekvencia    VARCHAR(120) NOT NULL COMMENT 'Konkrét, kibontott: "1H-2H"',
  kotesek       VARCHAR(120) NULL     COMMENT 'A változók kötése: "M=H"',
  PRIMARY KEY (licitmenet_id, szekvencia),
  KEY ix_szekv (szekvencia),
  CONSTRAINT fk_lmi FOREIGN KEY (licitmenet_id) REFERENCES licitmenet(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5b. A REKURZIÓ FELOLDÁSÁNAK eredménye.
--     Enélkül nem látható, mit jelent ténylegesen egy konvenciókártya
--     az összes hivatkozás feloldása után — a rekurzív modellek
--     hibakeresése enélkül reménytelen.
CREATE TABLE feloldott_licitmenet (
  rendszer_id     INT UNSIGNED NOT NULL COMMENT 'Melyik rendszer feloldása',
  kulcs           VARCHAR(120) NOT NULL,
  licitmenet_id   INT UNSIGNED NOT NULL COMMENT 'A GYŐZTES sor',
  eredet_rendszer INT UNSIGNED NOT NULL COMMENT 'Melyik rendszerből származik',
  melyseg         TINYINT UNSIGNED NOT NULL COMMENT '0 = saját sor',
  felulirt_db     TINYINT UNSIGNED NOT NULL DEFAULT 0
                  COMMENT 'Hány sort ütött ki — ha >0, érdemes ránézni',
  PRIMARY KEY (rendszer_id, kulcs),
  KEY ix_eredet (eredet_rendszer),
  CONSTRAINT fk_fl_r  FOREIGN KEY (rendszer_id)   REFERENCES rendszer(id) ON DELETE CASCADE,
  CONSTRAINT fk_fl_lm FOREIGN KEY (licitmenet_id) REFERENCES licitmenet(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------------------------------------------------------------------
-- 5. Kiinduló konvenciók (mind `rendszer` sor, fajta='KONVENCIO')
-- ---------------------------------------------------------------------

INSERT IGNORE INTO rendszer (kod, nev, fajta, leiras) VALUES
 ('STAYMAN',       'Stayman',           'KONVENCIO', '1NT után 2♣ kérdés a négyes nemesre'),
 ('JACOBY_TRF',    'Jacoby transzfer',  'KONVENCIO', '1NT után 2♦/2♥ transzfer a nemesre'),
 ('TEXAS_TRF',     'Texas transzfer',   'KONVENCIO', '1NT után 4♦/4♥ transzfer gémszinten'),
 ('NEGYEDIK_SZIN', 'Negyedik szín',     'KONVENCIO', 'A még nem mondott szín mesterséges, gémforsz'),
 ('BERGEN',        'Bergen emelések',   'KONVENCIO', 'Nemes fit után 3♣/3♦ emelések'),
 ('FORD_BERGEN',   'Fordított Bergen',  'KONVENCIO', '3♣ erősebb, 3♦ gyengébb'),
 ('JACOBY_2NT',    'Jacoby 2NT',        'KONVENCIO', 'Nemes után 2NT: fit + gémforsz'),
 ('SPLINTER',      'Splinter',          'KONVENCIO', 'Ugró új szín: fit + rövidség'),
 ('NEG_DBL',       'Negatív kontra',    'KONVENCIO', 'Közbeszólás utáni információs kontra'),
 ('FORD_EMELES',   'Fordított emelés',  'KONVENCIO', 'Minor fit erősségjelző emelések'),
 ('MULTI',         'Multi 2♦',          'KONVENCIO', 'Több jelentésű 2♦ nyitás'),
 ('LEBENSOHL',     'Lebensohl',         'KONVENCIO', '2NT relé leállás előkészítésére'),
 ('RKC',           'Roman Keycard',     'KONVENCIO', 'Ászkérdés az adu királlyal'),
 ('NEGY_SZIN_TRF', '4-színű transzfer', 'KONVENCIO', '1NT után minden színre transzfer');

-- ---------------------------------------------------------------------
-- 6. Áttekintő nézetek
-- ---------------------------------------------------------------------

CREATE OR REPLACE VIEW v_licitmenet AS
SELECT lm.id, r.kod AS rendszer, r.fajta,
       lm.fejezet, lm.alfejezet, lm.seq, lm.tipus,
       h.kod AS hivatkozott, lm.hivatkozas_aktiv,
       lm.minta, lm.kulcs, lm.magyarazat, lm.forsz,
       kk.kod AS kriterium, lm.allapot, lm.specifikussag, lm.prioritas,
       d.kod AS dokumentum, lm.dok_fejezet
FROM licitmenet lm
JOIN rendszer r                ON r.id  = lm.rendszer_id
LEFT JOIN rendszer h           ON h.id  = lm.hivatkozott_id
LEFT JOIN kriterium_keszlet kk ON kk.id = lm.kriterium_id
LEFT JOIN forras_dokumentum d  ON d.id  = lm.dokumentum_id;

-- Egy rendszer TELJES, feloldott képe — ezt "látja" a licitáló motor
CREATE OR REPLACE VIEW v_feloldott AS
SELECT f.rendszer_id, r.kod AS rendszer, f.kulcs,
       lm.minta, lm.magyarazat, lm.forsz, lm.jelentes,
       e.kod AS honnan, f.melyseg, f.felulirt_db
FROM feloldott_licitmenet f
JOIN rendszer r     ON r.id  = f.rendszer_id
JOIN rendszer e     ON e.id  = f.eredet_rendszer
JOIN licitmenet lm  ON lm.id = f.licitmenet_id;
