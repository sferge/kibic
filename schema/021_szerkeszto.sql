-- kibic — 021: a rendszerszerkesztő megjegyzései
--
-- A szerkesztőben (GET /szerkeszto) a szabályokhoz és fejezetekhez írt
-- megjegyzések. A licitmenet sorai újraimportkor újra létrejönnek (új
-- id-vel), ezért a megjegyzés NEM az id-hez kötődik, hanem ahhoz, ami
-- újraimport után is ugyanaz: rendszer + kulcs (+ minta, fejezet). Az id
-- csak tájékoztató.
--
-- Az export (GET /v1/kibic/szerk/export) ezeket adja ki egy fájlban, amit
-- a beszélgetésbe feltöltve Claude feldolgoz.

CREATE TABLE IF NOT EXISTS szerkeszto_megjegyzes (
  id            INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  rendszer_kod  VARCHAR(40)  NOT NULL,
  fejezet       VARCHAR(120) NULL,
  kulcs         VARCHAR(120) NULL     COMMENT 'NULL: a fejezetre / rendszerre vonatkozik',
  minta         VARCHAR(120) NULL,
  licitmenet_id INT UNSIGNED NULL     COMMENT 'tájékoztató: újraimportkor elavul',
  szoveg        TEXT         NOT NULL,
  szerzo        VARCHAR(60)  NULL,
  allapot       ENUM('NYITOTT','LEZART') NOT NULL DEFAULT 'NYITOTT',
  letrehozva    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY ix_hely (rendszer_kod, kulcs),
  KEY ix_allapot (allapot)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
