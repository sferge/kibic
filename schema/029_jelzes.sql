-- 029_jelzes.sql — kártyajelzési megállapodások (2026-10-20)
--
-- A licit mintájára a jelzés is adat. Két új dolog:
--
--   jelzes_csomag     egy megnevezett jelzési konvenció (pl. SZM_INDITAS):
--                     indítási és hívási szabálysorok, jelzési rács,
--                     módszerek, különleges helyzetek. A `definicio` a
--                     csomag YAML-ja JSON-ként; a KANONIKUS alak a
--                     rendszerek/jelzesek/*.yaml, ez a tábla abból SZÁRMAZIK
--                     (python -m kibic.cli.rendszerimport rendszerek/yaml/).
--
--   rendszer.jelzesek a rendszer jelzési PROFILJA: a csomagok listája
--                     sorrendben (az előrébb álló nyer) + felülírások.
--                     A feloldási láncban a legközelebbi nem üres profil él.
--
-- A motor a szabálysorokat a profil kibontásából számolja (motor/jelzes.py),
-- külön sortábla nincs: a sorok származtatott adatok.
--
-- MySQL 5.7: az ALTER nem idempotens; ha már lefutott, a második futtatás
-- "Duplicate column" hibát ad — ez ártalmatlan.

CREATE TABLE IF NOT EXISTS `jelzes_csomag` (
  `id` smallint(5) unsigned NOT NULL AUTO_INCREMENT,
  `kod` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `nev` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `leiras` varchar(1000) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `verzio` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '0.1',
  `forras` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL
    COMMENT 'A megállapodás forrása (rendszerleírás, fejezet)',
  `definicio` json NOT NULL
    COMMENT 'A csomag YAML-ja JSON-ként (kanonikus: rendszerek/jelzesek/)',
  `aktiv` tinyint(1) NOT NULL DEFAULT '1',
  `frissitve` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_jelzes_csomag` (`kod`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE `rendszer`
  ADD COLUMN `jelzesek` json DEFAULT NULL
    COMMENT 'Jelzési profil: {csomagok: [...], felulirasok: [...], modszer: {...}}'
  AFTER `kartya`;
