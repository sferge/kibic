-- 030_jelzesmenet.sql — a jelzésrendszerek SOROKBAN (2026-10-20)
--
-- A 029 csomagonként egyetlen JSON-ban tárolta a jelzéseket. Ez a migráció
-- a licit mintájára sorokra bontja őket (lásd rendszerek/jelzesek/README.md):
--
--   jelzesrendszer   egy jelzésrendszer (ALAPRENDSZER / RENDSZER / KONVENCIO):
--                    hivatkozásai és kizárásai sorrendben (JSON)
--   jelzesmenet      a sorai, mindegyik KULCCSAL: SZABALY (melyik lap),
--                    RACS, MODSZER, ELV, KULONLEGES, LICIT, TORLES;
--                    állapottal és jóváhagyóval, mint a licitmenet
--
-- A kanonikus alak a YAML (rendszerek/jelzesek/); a táblák ebből származnak
-- (python -m kibic.cli.rendszerimport rendszerek/yaml/). Az import megőrzi a
-- jóváhagyást, ha a sor tartalma nem változott.
--
-- A 029 `jelzes_csomag` táblája csak származtatott adatot tartalmazott:
-- eldobjuk. A `rendszer.jelzesek` oszlop marad: {"rendszer": "MOHA_STAND"}.

DROP TABLE IF EXISTS `jelzes_csomag`;

CREATE TABLE IF NOT EXISTS `jelzesrendszer` (
  `id` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
  `kod` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nev` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `fajta` enum('ALAPRENDSZER','RENDSZER','KONVENCIO') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ALAPRENDSZER',
  `verzio` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '0.1',
  `forras` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `leiras` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `jegyzet` text COLLATE utf8mb4_unicode_ci,
  `fejezet_jegyzetek` json DEFAULT NULL COMMENT '{fejezet: jegyzet}',
  `hivatkozasok` json DEFAULT NULL COMMENT '["SZEGEDI_MRAZ", ...] — sorrendben, az előrébb álló nyer',
  `kizarasok` json DEFAULT NULL COMMENT '[{"kod": ..., "fejezet": ...}]',
  `aktiv` tinyint(1) NOT NULL DEFAULT '1',
  `frissitve` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_jelzesrendszer` (`kod`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `jelzesmenet` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `jelzesrendszer_id` smallint(5) unsigned NOT NULL,
  `fejezet` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `seq` int(10) unsigned NOT NULL COMMENT 'Sorszám a YAML-ban, 10-esével',
  `fajta` enum('SZABALY','RACS','MODSZER','ELV','KULONLEGES','LICIT','TORLES')
    COLLATE utf8mb4_unicode_ci NOT NULL,
  `kulcs` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL
    COMMENT 'A FELÜLÍRÁS kulcsa (TORLES-nél a törölt sor kulcsa)',
  `adat` json NOT NULL COMMENT 'A sor tartalma (motor/jelzes.py JSor.adat)',
  `szoveg` varchar(600) COLLATE utf8mb4_unicode_ci DEFAULT NULL
    COMMENT 'Emberi nyelvű leírás (a motor generálja)',
  `allapot` enum('JAVASOLT','ELFOGADOTT','FELULVIZSGALANDO','JEGELT')
    COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'JAVASOLT',
  `jovahagyta` varchar(60) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `jovahagyva` datetime DEFAULT NULL,
  `megjegyzes` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `jegyzet` text COLLATE utf8mb4_unicode_ci,
  PRIMARY KEY (`id`),
  KEY `ix_jm_kulcs` (`jelzesrendszer_id`, `kulcs`),
  KEY `ix_jm_allapot` (`allapot`),
  CONSTRAINT `fk_jm_r` FOREIGN KEY (`jelzesrendszer_id`) REFERENCES `jelzesrendszer` (`id`)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
