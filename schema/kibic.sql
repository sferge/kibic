-- --------------------------------------------------------
-- Gazdagép:                    192.168.77.253
-- Szerver verzió:              5.7.30 - MySQL Community Server (GPL)
-- Szerver OS:                   Linux
-- HeidiSQL Verzió:             12.13.1.1
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- Adatbázis struktúra mentése a kibic.
CREATE DATABASE IF NOT EXISTS `kibic` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */;
USE `kibic`;

-- Struktúra mentése tábla kibic. ertekelo
CREATE TABLE IF NOT EXISTS `ertekelo` (
  `id` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
  `kod` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Erre hivatkozik a licitrendszer-bejegyzés',
  `nev` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `leiras` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `kontextus` enum('ABSZOLUT','SZINTALALKOZAS','SZINTELEN','EGYEB') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ABSZOLUT' COMMENT 'ABSZOLUT: kéz önmagában. SZINTALALKOZAS: csak megtalált szín után értelmes (pl. AP).',
  `aktiv` tinyint(1) NOT NULL DEFAULT '1',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_ertekelo` (`kod`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tábla adatainak mentése kibic.ertekelo: ~6 rows (hozzávetőleg)
REPLACE INTO `ertekelo` (`id`, `kod`, `nev`, `leiras`, `kontextus`, `aktiv`) VALUES
	(1, 'HCP', 'Figurapont (4-3-2-1)', 'Milton Work: A=4, K=3, D=2, B=1', 'ABSZOLUT', 1),
	(2, 'HCP_DIST', 'Figurapont + elosztás', 'HCP + hosszúsági/rövidségi pontok', 'ABSZOLUT', 1),
	(3, 'AP', 'Asztali pont', 'Rövidségi pontok szintalálkozás után', 'SZINTALALKOZAS', 1),
	(4, 'ZAR', 'Zar-pont', 'Zar Petkov: HCP + kontrollok + hossz + elosztás', 'ABSZOLUT', 1),
	(5, 'LTC', 'Losing Trick Count', 'Vesztő ütések száma (színfelvételhez)', 'SZINTALALKOZAS', 1),
	(6, 'KONTROLL', 'Kontrollszám', 'A=2, K=1 (szlemkutatáshoz)', 'ABSZOLUT', 1);

-- Struktúra mentése tábla kibic. esemeny
CREATE TABLE IF NOT EXISTS `esemeny` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `nev` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `helyszin` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `datum` date DEFAULT NULL,
  `szamolas` enum('MP','IMP','BAM','RUBBER','ISMERETLEN') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'ISMERETLEN',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_esemeny` (`nev`,`datum`,`helyszin`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tábla adatainak mentése kibic.esemeny: ~0 rows (hozzávetőleg)

-- Struktúra mentése tábla kibic. forras_fajl
CREATE TABLE IF NOT EXISTS `forras_fajl` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `fajlnev` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `formatum` enum('PBN','LIN','EGYEB') COLLATE utf8mb4_unicode_ci NOT NULL,
  `fajl_hash` char(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'SHA-256 a nyers bájtokon; ismételt import ellen',
  `meret_bajt` int(10) unsigned NOT NULL,
  `nyers_tartalom` longtext COLLATE utf8mb4_unicode_ci COMMENT 'A teljes eredeti fájl, ha meg akarjuk őrizni',
  `importalva` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `megjegyzes` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_forras_hash` (`fajl_hash`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tábla adatainak mentése kibic.forras_fajl: ~0 rows (hozzávetőleg)

-- Struktúra mentése tábla kibic. jatekos
CREATE TABLE IF NOT EXISTS `jatekos` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `azonosito` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Normalizált (kisbetűs, trimmelt) név — ez a kulcs',
  `megjelenit` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Az elsőként látott eredeti írásmód',
  `ember` tinyint(1) NOT NULL DEFAULT '1' COMMENT '0 = robot / saját AI-ülés',
  `megjegyzes` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_jatekos` (`azonosito`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tábla adatainak mentése kibic.jatekos: ~0 rows (hozzávetőleg)

-- Struktúra mentése tábla kibic. jatszma
CREATE TABLE IF NOT EXISTS `jatszma` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `leosztas_id` int(10) unsigned NOT NULL,
  `esemeny_id` int(10) unsigned DEFAULT NULL,
  `forras_fajl_id` int(10) unsigned DEFAULT NULL,
  `n_jatekos_id` int(10) unsigned DEFAULT NULL,
  `e_jatekos_id` int(10) unsigned DEFAULT NULL,
  `s_jatekos_id` int(10) unsigned DEFAULT NULL,
  `w_jatekos_id` int(10) unsigned DEFAULT NULL,
  `licit` json DEFAULT NULL COMMENT '[{"ules":"N","licit":"1C"},{"ules":"E","licit":"X","alert":true,"magyarazat":"..."}]',
  `lejatszas` json DEFAULT NULL COMMENT '{"lapok":["D4","DJ","DK","DA",...],"claim_utes":5,"claim_utesszam":10}',
  `felvevo` enum('N','E','S','W') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `kontraktus` varchar(8) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'pl. 3CX, 4H, 6NTXX, PASS',
  `eredmeny_utes` tinyint(3) unsigned DEFAULT NULL COMMENT 'A felvevő által megnyert ütések (0-13)',
  `pontszam_ns` smallint(6) DEFAULT NULL COMMENT 'É-D szemszögéből, előjelesen',
  `mp_szazalek_ns` decimal(5,2) DEFAULT NULL,
  `imp_ns` smallint(6) DEFAULT NULL,
  `pontszam_ellenorzott` enum('EGYEZIK','ELTER','NEM_ELLENORIZVE') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'NEM_ELLENORIZVE',
  `pontszam_szamitott` smallint(6) DEFAULT NULL COMMENT 'Amit a saját motorunk számolt',
  `cimkek` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'pl. arany_keszlet,claim,szlem',
  `letrehozva` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_leosztas` (`leosztas_id`),
  KEY `ix_esemeny` (`esemeny_id`),
  KEY `ix_kontrakt` (`kontraktus`,`eredmeny_utes`),
  KEY `ix_ellenorzes` (`pontszam_ellenorzott`),
  KEY `ix_jatekos_n` (`n_jatekos_id`),
  KEY `ix_jatekos_e` (`e_jatekos_id`),
  KEY `ix_jatekos_s` (`s_jatekos_id`),
  KEY `ix_jatekos_w` (`w_jatekos_id`),
  KEY `fk_j_forras` (`forras_fajl_id`),
  CONSTRAINT `fk_j_e` FOREIGN KEY (`e_jatekos_id`) REFERENCES `jatekos` (`id`),
  CONSTRAINT `fk_j_esemeny` FOREIGN KEY (`esemeny_id`) REFERENCES `esemeny` (`id`),
  CONSTRAINT `fk_j_forras` FOREIGN KEY (`forras_fajl_id`) REFERENCES `forras_fajl` (`id`),
  CONSTRAINT `fk_j_leosztas` FOREIGN KEY (`leosztas_id`) REFERENCES `leosztas` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_j_n` FOREIGN KEY (`n_jatekos_id`) REFERENCES `jatekos` (`id`),
  CONSTRAINT `fk_j_s` FOREIGN KEY (`s_jatekos_id`) REFERENCES `jatekos` (`id`),
  CONSTRAINT `fk_j_w` FOREIGN KEY (`w_jatekos_id`) REFERENCES `jatekos` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tábla adatainak mentése kibic.jatszma: ~0 rows (hozzávetőleg)

-- Struktúra mentése tábla kibic. kez_ertek
CREATE TABLE IF NOT EXISTS `kez_ertek` (
  `leosztas_id` int(10) unsigned NOT NULL,
  `ules` enum('N','E','S','W') COLLATE utf8mb4_unicode_ci NOT NULL,
  `ertekelo_id` smallint(5) unsigned NOT NULL,
  `ertek` decimal(5,2) NOT NULL,
  PRIMARY KEY (`leosztas_id`,`ules`,`ertekelo_id`),
  KEY `ix_ertek` (`ertekelo_id`,`ertek`),
  CONSTRAINT `fk_ke_ertekelo` FOREIGN KEY (`ertekelo_id`) REFERENCES `ertekelo` (`id`),
  CONSTRAINT `fk_ke_leosztas` FOREIGN KEY (`leosztas_id`) REFERENCES `leosztas` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tábla adatainak mentése kibic.kez_ertek: ~0 rows (hozzávetőleg)

-- Struktúra mentése tábla kibic. leosztas
CREATE TABLE IF NOT EXISTS `leosztas` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `kezek_pbn` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'pl. N:J3.9.AQT8.AQJ763 AT6.A754.42.KT85 ... (mindig É-tól, óramutató szerint)',
  `leosztas_hash` char(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'SHA-256 a kanonikus alakon — deduplikáció',
  `oszto` enum('N','E','S','W') COLLATE utf8mb4_unicode_ci NOT NULL,
  `beliallas` enum('NONE','NS','EW','ALL') COLLATE utf8mb4_unicode_ci NOT NULL,
  `tabla_szam` smallint(5) unsigned DEFAULT NULL COMMENT 'Board number, ha ismert',
  `forras` enum('IMPORT','GENERALT','SAJAT_JATEK') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'IMPORT',
  `n_hcp` tinyint(3) unsigned NOT NULL,
  `e_hcp` tinyint(3) unsigned NOT NULL,
  `s_hcp` tinyint(3) unsigned NOT NULL,
  `w_hcp` tinyint(3) unsigned NOT NULL,
  `n_alak` char(7) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'pl. 4-4-3-2 (pikk-kőr-káró-treff sorrend)',
  `e_alak` char(7) COLLATE utf8mb4_unicode_ci NOT NULL,
  `s_alak` char(7) COLLATE utf8mb4_unicode_ci NOT NULL,
  `w_alak` char(7) COLLATE utf8mb4_unicode_ci NOT NULL,
  `n_kiegyensulyozott` tinyint(1) NOT NULL,
  `e_kiegyensulyozott` tinyint(1) NOT NULL,
  `s_kiegyensulyozott` tinyint(1) NOT NULL,
  `w_kiegyensulyozott` tinyint(1) NOT NULL,
  `dds_utesek` json DEFAULT NULL COMMENT '{"N":{"S":9,"H":7,"D":10,"C":11,"NT":8}, "E":{...}, ...}',
  `dds_par` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Par-kontraktus és -pontszám, ha kiszámolt',
  `letrehozva` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_leosztas` (`leosztas_hash`),
  KEY `ix_hcp` (`n_hcp`,`s_hcp`),
  KEY `ix_hcp_ew` (`e_hcp`,`w_hcp`),
  KEY `ix_forras` (`forras`),
  KEY `ix_beli` (`beliallas`,`oszto`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tábla adatainak mentése kibic.leosztas: ~0 rows (hozzávetőleg)

-- Struktúra mentése tábla kibic. licit_akcio
CREATE TABLE IF NOT EXISTS `licit_akcio` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `jatszma_id` int(10) unsigned NOT NULL,
  `sorszam` tinyint(3) unsigned NOT NULL COMMENT 'Hányadik licit a menetben (0-tól)',
  `ules` enum('N','E','S','W') COLLATE utf8mb4_unicode_ci NOT NULL,
  `jatekos_id` int(10) unsigned DEFAULT NULL,
  `licit` varchar(6) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '1C, X, XX, PASS, 3NT...',
  `kor` tinyint(3) unsigned NOT NULL COMMENT 'Hányadik licitkör',
  `pozicio` tinyint(3) unsigned NOT NULL COMMENT '1-4: hányadik helyen szólal meg az osztótól',
  `licitalo_hcp` tinyint(3) unsigned NOT NULL,
  `licitalo_alak` char(7) COLLATE utf8mb4_unicode_ci NOT NULL,
  `beliallas` enum('NONE','NS','EW','ALL') COLLATE utf8mb4_unicode_ci NOT NULL,
  `allapot_tipus` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Az állapotgép besorolása — a 3. fázistól töltve',
  PRIMARY KEY (`id`),
  KEY `ix_jatszma` (`jatszma_id`,`sorszam`),
  KEY `ix_profil` (`allapot_tipus`,`licit`,`licitalo_hcp`),
  KEY `ix_jatekos` (`jatekos_id`,`allapot_tipus`),
  CONSTRAINT `fk_la_jatekos` FOREIGN KEY (`jatekos_id`) REFERENCES `jatekos` (`id`),
  CONSTRAINT `fk_la_jatszma` FOREIGN KEY (`jatszma_id`) REFERENCES `jatszma` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tábla adatainak mentése kibic.licit_akcio: ~0 rows (hozzávetőleg)

-- Struktúra mentése nézet kibic. v_jatszma_attekintes
-- Ideiglenes tábla létrehozása a VIEW függőségi hibák lekezelésére
CREATE TABLE `v_jatszma_attekintes` (
	`id` INT(10) UNSIGNED NOT NULL,
	`tabla_szam` SMALLINT(5) UNSIGNED NULL COMMENT 'Board number, ha ismert',
	`oszto` ENUM('N','E','S','W') NOT NULL COLLATE 'utf8mb4_unicode_ci',
	`beliallas` ENUM('NONE','NS','EW','ALL') NOT NULL COLLATE 'utf8mb4_unicode_ci',
	`eszak` VARCHAR(1) NULL COMMENT 'Az elsőként látott eredeti írásmód' COLLATE 'utf8mb4_unicode_ci',
	`kelet` VARCHAR(1) NULL COMMENT 'Az elsőként látott eredeti írásmód' COLLATE 'utf8mb4_unicode_ci',
	`del` VARCHAR(1) NULL COMMENT 'Az elsőként látott eredeti írásmód' COLLATE 'utf8mb4_unicode_ci',
	`nyugat` VARCHAR(1) NULL COMMENT 'Az elsőként látott eredeti írásmód' COLLATE 'utf8mb4_unicode_ci',
	`kontraktus` VARCHAR(1) NULL COMMENT 'pl. 3CX, 4H, 6NTXX, PASS' COLLATE 'utf8mb4_unicode_ci',
	`felvevo` ENUM('N','E','S','W') NULL COLLATE 'utf8mb4_unicode_ci',
	`eredmeny_utes` TINYINT(3) UNSIGNED NULL COMMENT 'A felvevő által megnyert ütések (0-13)',
	`pontszam_ns` SMALLINT(6) NULL COMMENT 'É-D szemszögéből, előjelesen',
	`pontszam_ellenorzott` ENUM('EGYEZIK','ELTER','NEM_ELLENORIZVE') NOT NULL COLLATE 'utf8mb4_unicode_ci',
	`esemeny` VARCHAR(1) NULL COLLATE 'utf8mb4_unicode_ci'
);

-- Ideiglenes tábla eltávolítása és a végső VIEW struktúra létrehozása
DROP TABLE IF EXISTS `v_jatszma_attekintes`;
CREATE ALGORITHM=UNDEFINED SQL SECURITY DEFINER VIEW `v_jatszma_attekintes` AS select `j`.`id` AS `id`,`l`.`tabla_szam` AS `tabla_szam`,`l`.`oszto` AS `oszto`,`l`.`beliallas` AS `beliallas`,`jn`.`megjelenit` AS `eszak`,`je`.`megjelenit` AS `kelet`,`js`.`megjelenit` AS `del`,`jw`.`megjelenit` AS `nyugat`,`j`.`kontraktus` AS `kontraktus`,`j`.`felvevo` AS `felvevo`,`j`.`eredmeny_utes` AS `eredmeny_utes`,`j`.`pontszam_ns` AS `pontszam_ns`,`j`.`pontszam_ellenorzott` AS `pontszam_ellenorzott`,`e`.`nev` AS `esemeny` from ((((((`jatszma` `j` join `leosztas` `l` on((`l`.`id` = `j`.`leosztas_id`))) left join `esemeny` `e` on((`e`.`id` = `j`.`esemeny_id`))) left join `jatekos` `jn` on((`jn`.`id` = `j`.`n_jatekos_id`))) left join `jatekos` `je` on((`je`.`id` = `j`.`e_jatekos_id`))) left join `jatekos` `js` on((`js`.`id` = `j`.`s_jatekos_id`))) left join `jatekos` `jw` on((`jw`.`id` = `j`.`w_jatekos_id`)))
;

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
