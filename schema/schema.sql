-- =====================================================================
--  Bridzs AI — adatbázis-séma (MariaDB 10.6+)
--  Verzió: 0.1  ·  Karakterkészlet: utf8mb4
--
--  Tervezési elvek:
--   1. Egy kanonikus igazságforrás: a nyers importált tartalom és a
--      PBN-alakú kiosztás. Minden más származtatott és újraépíthető.
--   2. Fej-tétel szerkezet: leosztas (a lapok) 1:N jatszma (lejátszásai).
--   3. Lapértékelés több metrikával párhuzamosan (ertekelo + kez_ertek).
--   4. Az importált és a generált leosztás ugyanaz a tábla, `forras` flaggel.
-- =====================================================================

CREATE DATABASE IF NOT EXISTS bridzs
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bridzs;

-- ---------------------------------------------------------------------
-- 1. Proveniencia
-- ---------------------------------------------------------------------

CREATE TABLE forras_fajl (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  fajlnev         VARCHAR(255)    NOT NULL,
  formatum        ENUM('PBN','LIN','EGYEB') NOT NULL,
  fajl_hash       CHAR(64)        NOT NULL COMMENT 'SHA-256 a nyers bájtokon; ismételt import ellen',
  meret_bajt      INT UNSIGNED    NOT NULL,
  nyers_tartalom  LONGTEXT        NULL COMMENT 'A teljes eredeti fájl, ha meg akarjuk őrizni',
  importalva      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  megjegyzes      VARCHAR(500)    NULL,
  UNIQUE KEY uq_forras_hash (fajl_hash)
) ENGINE=InnoDB;

CREATE TABLE esemeny (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  nev             VARCHAR(255)    NOT NULL,
  helyszin        VARCHAR(255)    NULL,
  datum           DATE            NULL,
  szamolas        ENUM('MP','IMP','BAM','RUBBER','ISMERETLEN') NOT NULL DEFAULT 'ISMERETLEN',
  UNIQUE KEY uq_esemeny (nev, datum, helyszin)
) ENGINE=InnoDB;

CREATE TABLE jatekos (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  azonosito       VARCHAR(100)    NOT NULL COMMENT 'Normalizált (kisbetűs, trimmelt) név — ez a kulcs',
  megjelenit      VARCHAR(100)    NOT NULL COMMENT 'Az elsőként látott eredeti írásmód',
  ember           TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '0 = robot / saját AI-ülés',
  megjegyzes      VARCHAR(500)    NULL,
  UNIQUE KEY uq_jatekos (azonosito)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 2. Lapértékelők (a "sokféle pontszámítás" regisztere)
--    Az eredménypontozás (scoring) NEM itt van: az szabály, nem konvenció.
--    Itt kizárólag a kézértékelő metrikák élnek.
-- ---------------------------------------------------------------------

CREATE TABLE ertekelo (
  id              SMALLINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  kod             VARCHAR(30)     NOT NULL COMMENT 'Erre hivatkozik a licitrendszer-bejegyzés',
  nev             VARCHAR(100)    NOT NULL,
  leiras          VARCHAR(500)    NULL,
  kontextus       ENUM('ABSZOLUT','SZINTALALKOZAS','SZINTELEN','EGYEB') NOT NULL DEFAULT 'ABSZOLUT'
                  COMMENT 'ABSZOLUT: kéz önmagában. SZINTALALKOZAS: csak megtalált szín után értelmes (pl. AP).',
  aktiv           TINYINT(1)      NOT NULL DEFAULT 1,
  UNIQUE KEY uq_ertekelo (kod)
) ENGINE=InnoDB;

INSERT INTO ertekelo (kod, nev, leiras, kontextus) VALUES
  ('HCP',      'Figurapont (4-3-2-1)', 'Milton Work: A=4, K=3, D=2, B=1', 'ABSZOLUT'),
  ('HCP_DIST', 'Figurapont + elosztás', 'HCP + hosszúsági/rövidségi pontok', 'ABSZOLUT'),
  ('AP',       'Asztali pont',         'Rövidségi pontok szintalálkozás után', 'SZINTALALKOZAS'),
  ('ZAR',      'Zar-pont',             'Zar Petkov: HCP + kontrollok + hossz + elosztás', 'ABSZOLUT'),
  ('LTC',      'Losing Trick Count',   'Vesztő ütések száma (színfelvételhez)', 'SZINTALALKOZAS'),
  ('KONTROLL', 'Kontrollszám',         'A=2, K=1 (szlemkutatáshoz)', 'ABSZOLUT');

-- ---------------------------------------------------------------------
-- 3. Leosztás (fej) — a lapok maguk
-- ---------------------------------------------------------------------

CREATE TABLE leosztas (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,

  -- KANONIKUS ALAK: PBN deal-string, mindig 'N:' normalizálva
  kezek_pbn       VARCHAR(80)     NOT NULL
                  COMMENT 'pl. N:J3.9.AQT8.AQJ763 AT6.A754.42.KT85 ... (mindig É-tól, óramutató szerint)',
  leosztas_hash   CHAR(64)        NOT NULL COMMENT 'SHA-256 a kanonikus alakon — deduplikáció',

  oszto           ENUM('N','E','S','W') NOT NULL,
  beliallas       ENUM('NONE','NS','EW','ALL') NOT NULL,
  tabla_szam      SMALLINT UNSIGNED NULL COMMENT 'Board number, ha ismert',

  forras          ENUM('IMPORT','GENERALT','SAJAT_JATEK') NOT NULL DEFAULT 'IMPORT',

  -- SZÁRMAZTATOTT, INDEXELT oszlopok: a gyakori szűrésekhez.
  -- Mindig újraszámíthatók a kezek_pbn-ből.
  n_hcp           TINYINT UNSIGNED NOT NULL,
  e_hcp           TINYINT UNSIGNED NOT NULL,
  s_hcp           TINYINT UNSIGNED NOT NULL,
  w_hcp           TINYINT UNSIGNED NOT NULL,
  n_alak          CHAR(7)         NOT NULL COMMENT 'pl. 4-4-3-2 (pikk-kőr-káró-treff sorrend)',
  e_alak          CHAR(7)         NOT NULL,
  s_alak          CHAR(7)         NOT NULL,
  w_alak          CHAR(7)         NOT NULL,
  n_kiegyensulyozott TINYINT(1)   NOT NULL,
  e_kiegyensulyozott TINYINT(1)   NOT NULL,
  s_kiegyensulyozott TINYINT(1)   NOT NULL,
  w_kiegyensulyozott TINYINT(1)   NOT NULL,

  -- DDS-gyorsítótár: 20 érték (4 irány × 5 szín), JSON-ban.
  -- NULL = még nem számoltuk ki. Így egy leosztást sosem oldunk meg kétszer.
  dds_utesek      JSON            NULL
                  COMMENT '{"N":{"S":9,"H":7,"D":10,"C":11,"NT":8}, "E":{...}, ...}',
  dds_par         VARCHAR(50)     NULL COMMENT 'Par-kontraktus és -pontszám, ha kiszámolt',

  letrehozva      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

  UNIQUE KEY uq_leosztas (leosztas_hash),
  KEY ix_hcp    (n_hcp, s_hcp),
  KEY ix_hcp_ew (e_hcp, w_hcp),
  KEY ix_forras (forras),
  KEY ix_beli   (beliallas, oszto)
) ENGINE=InnoDB;

-- Kézértékek: leosztás × ülés × értékelő. Itt él az AP, a Zar és a többi.
-- A HCP redundánsan a leosztas táblában is szerepel — szándékosan:
-- ott indexelt szűrésre való, itt egységes lekérdezésre.
CREATE TABLE kez_ertek (
  leosztas_id     INT UNSIGNED    NOT NULL,
  ules            ENUM('N','E','S','W') NOT NULL,
  ertekelo_id     SMALLINT UNSIGNED NOT NULL,
  ertek           DECIMAL(5,2)    NOT NULL,
  PRIMARY KEY (leosztas_id, ules, ertekelo_id),
  KEY ix_ertek (ertekelo_id, ertek),
  CONSTRAINT fk_ke_leosztas FOREIGN KEY (leosztas_id) REFERENCES leosztas(id) ON DELETE CASCADE,
  CONSTRAINT fk_ke_ertekelo FOREIGN KEY (ertekelo_id) REFERENCES ertekelo(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 4. Játszma (tétel) — egy konkrét lejátszás
-- ---------------------------------------------------------------------

CREATE TABLE jatszma (
  id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  leosztas_id     INT UNSIGNED    NOT NULL,
  esemeny_id      INT UNSIGNED    NULL,
  forras_fajl_id  INT UNSIGNED    NULL,

  n_jatekos_id    INT UNSIGNED    NULL,
  e_jatekos_id    INT UNSIGNED    NULL,
  s_jatekos_id    INT UNSIGNED    NULL,
  w_jatekos_id    INT UNSIGNED    NULL,

  -- LICIT: JSON-tömb. Elemenként {ules, licit, alert, magyarazat}.
  -- A JSON itt fizet: az alert/magyarázat a licitrendszer-tudásbázis és
  -- az ágensprofil legértékesebb nyersanyaga.
  licit           JSON            NULL
                  COMMENT '[{"ules":"N","licit":"1C"},{"ules":"E","licit":"X","alert":true,"magyarazat":"..."}]',

  -- LEJÁTSZÁS: vékony objektum. A lapok időrendben (nem PBN-rotációban!).
  lejatszas       JSON            NULL
                  COMMENT '{"lapok":["D4","DJ","DK","DA",...],"claim_utes":5,"claim_utesszam":10}',

  felvevo         ENUM('N','E','S','W') NULL,
  kontraktus      VARCHAR(8)      NULL COMMENT 'pl. 3CX, 4H, 6NTXX, PASS',
  eredmeny_utes   TINYINT UNSIGNED NULL COMMENT 'A felvevő által megnyert ütések (0-13)',
  pontszam_ns     SMALLINT        NULL COMMENT 'É-D szemszögéből, előjelesen',
  mp_szazalek_ns  DECIMAL(5,2)    NULL,
  imp_ns          SMALLINT        NULL,

  -- Ellenőrzés: egyezik-e a saját pontszámításunk a jegyzőkönyvvel?
  pontszam_ellenorzott ENUM('EGYEZIK','ELTER','NEM_ELLENORIZVE') NOT NULL DEFAULT 'NEM_ELLENORIZVE',
  pontszam_szamitott   SMALLINT   NULL COMMENT 'Amit a saját motorunk számolt',

  cimkek          VARCHAR(255)    NULL COMMENT 'pl. arany_keszlet,claim,szlem',
  letrehozva      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

  KEY ix_leosztas (leosztas_id),
  KEY ix_esemeny  (esemeny_id),
  KEY ix_kontrakt (kontraktus, eredmeny_utes),
  KEY ix_ellenorzes (pontszam_ellenorzott),
  KEY ix_jatekos_n (n_jatekos_id), KEY ix_jatekos_e (e_jatekos_id),
  KEY ix_jatekos_s (s_jatekos_id), KEY ix_jatekos_w (w_jatekos_id),
  CONSTRAINT fk_j_leosztas FOREIGN KEY (leosztas_id) REFERENCES leosztas(id) ON DELETE CASCADE,
  CONSTRAINT fk_j_esemeny  FOREIGN KEY (esemeny_id)  REFERENCES esemeny(id),
  CONSTRAINT fk_j_forras   FOREIGN KEY (forras_fajl_id) REFERENCES forras_fajl(id),
  CONSTRAINT fk_j_n FOREIGN KEY (n_jatekos_id) REFERENCES jatekos(id),
  CONSTRAINT fk_j_e FOREIGN KEY (e_jatekos_id) REFERENCES jatekos(id),
  CONSTRAINT fk_j_s FOREIGN KEY (s_jatekos_id) REFERENCES jatekos(id),
  CONSTRAINT fk_j_w FOREIGN KEY (w_jatekos_id) REFERENCES jatekos(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 5. Származtatott: normalizált licit-akciók
--    Ez a profilépítés igáslova. Eldobható és újraépíthető a jatszma.licit-ből.
--    A 3. fázisig üresen is maradhat.
-- ---------------------------------------------------------------------

CREATE TABLE licit_akcio (
  id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  jatszma_id      INT UNSIGNED    NOT NULL,
  sorszam         TINYINT UNSIGNED NOT NULL COMMENT 'Hányadik licit a menetben (0-tól)',
  ules            ENUM('N','E','S','W') NOT NULL,
  jatekos_id      INT UNSIGNED    NULL,
  licit           VARCHAR(6)      NOT NULL COMMENT '1C, X, XX, PASS, 3NT...',
  kor             TINYINT UNSIGNED NOT NULL COMMENT 'Hányadik licitkör',
  pozicio         TINYINT UNSIGNED NOT NULL COMMENT '1-4: hányadik helyen szólal meg az osztótól',
  -- A licitáló kezének jellemzői a döntés pillanatában — a profilépítéshez.
  licitalo_hcp    TINYINT UNSIGNED NOT NULL,
  licitalo_alak   CHAR(7)         NOT NULL,
  beliallas       ENUM('NONE','NS','EW','ALL') NOT NULL,
  allapot_tipus   VARCHAR(50)     NULL COMMENT 'Az állapotgép besorolása — a 3. fázistól töltve',
  KEY ix_jatszma (jatszma_id, sorszam),
  KEY ix_profil  (allapot_tipus, licit, licitalo_hcp),
  KEY ix_jatekos (jatekos_id, allapot_tipus),
  CONSTRAINT fk_la_jatszma FOREIGN KEY (jatszma_id) REFERENCES jatszma(id) ON DELETE CASCADE,
  CONSTRAINT fk_la_jatekos FOREIGN KEY (jatekos_id) REFERENCES jatekos(id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- 6. Kényelmi nézetek
-- ---------------------------------------------------------------------

CREATE OR REPLACE VIEW v_jatszma_attekintes AS
SELECT
  j.id, l.tabla_szam, l.oszto, l.beliallas,
  jn.megjelenit AS eszak, je.megjelenit AS kelet,
  js.megjelenit AS del,   jw.megjelenit AS nyugat,
  j.kontraktus, j.felvevo, j.eredmeny_utes, j.pontszam_ns,
  j.pontszam_ellenorzott, e.nev AS esemeny
FROM jatszma j
JOIN leosztas l ON l.id = j.leosztas_id
LEFT JOIN esemeny e  ON e.id = j.esemeny_id
LEFT JOIN jatekos jn ON jn.id = j.n_jatekos_id
LEFT JOIN jatekos je ON je.id = j.e_jatekos_id
LEFT JOIN jatekos js ON js.id = j.s_jatekos_id
LEFT JOIN jatekos jw ON jw.id = j.w_jatekos_id;
