-- 031_jelzesmenet_szerkezet.sql — a jelzésmenet ugyanolyan szerkezetű, mint a licitmenet (2026-10-20)
--
-- 1. A licitmenetben három külön dolog van: `tipus` (szabály vagy
--    hivatkozás), `szabaly_fajta` (a sor szerepe) és `ag` (miről szól). A
--    030-as jelzésmenet ezt egyetlen `fajta` oszlopba sűrítette. Most:
--
--      tipus     SZABALY | HIVATKOZAS          (mint a licitmenetben)
--      fajta     SZABALY | ELV | KIVETEL | KIHAGYAS   (a licit szabaly_fajta-ja)
--      terulet   INDITAS | HIVAS | JELZES | MODSZER | KULONLEGES | LICIT
--
--    A régi értékek: RACS -> SZABALY/JELZES, MODSZER -> SZABALY/MODSZER,
--    KULONLEGES -> SZABALY/KULONLEGES, LICIT -> SZABALY/LICIT,
--    TORLES -> KIHAGYAS, SZABALY -> SZABALY/INDITAS vagy HIVAS.
--    A kulcsok és a jóváhagyások maradnak.
--
-- 2. A hivatkozások és a kizárások SOROK lesznek (mint a licitmenetben:
--    tipus = HIVATKOZAS, hivatkozas_mod BE/KI, kizart_fejezet); a
--    jelzesrendszer JSON-oszlopai megszűnnek. A sorokat a rendszerimport
--    írja be — a migráció után azonnal futtasd:
--      python -m kibic.cli.rendszerimport rendszerek/yaml/ --csak KIBIC_STAND
--
-- 3. TORLES -> KIHAGYAS a LICITMENETBEN is (a sor nem törlődik, csak ebben
--    a változatban nem él). A YAML `torol: true` továbbra is jó, az új neve
--    `kihagy: true`.

-- --- 1. jelzésmenet ------------------------------------------------------
ALTER TABLE `jelzesmenet`
  MODIFY `fajta` enum('SZABALY','RACS','MODSZER','ELV','KULONLEGES','LICIT','TORLES',
                      'KIVETEL','KIHAGYAS') COLLATE utf8mb4_unicode_ci NOT NULL,
  ADD COLUMN `tipus` enum('SZABALY','HIVATKOZAS') COLLATE utf8mb4_unicode_ci NOT NULL
    DEFAULT 'SZABALY' AFTER `seq`,
  ADD COLUMN `terulet` enum('INDITAS','HIVAS','JELZES','MODSZER','KULONLEGES','LICIT')
    COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Miről szól (a licit `ag`-ja helyett)' AFTER `fajta`,
  ADD COLUMN `hivatkozott_id` smallint(5) unsigned DEFAULT NULL AFTER `terulet`,
  ADD COLUMN `hivatkozas_mod` enum('BE','KI') COLLATE utf8mb4_unicode_ci DEFAULT NULL
    COMMENT 'BE: hivatkozás (behozza); KI: kizárás' AFTER `hivatkozott_id`,
  ADD COLUMN `hivatkozas_aktiv` tinyint(1) NOT NULL DEFAULT '1' AFTER `hivatkozas_mod`,
  ADD COLUMN `kizart_fejezet` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL
    COMMENT 'KI-nél: csak ez a fejezet (NULL: az egész rendszer)' AFTER `hivatkozas_aktiv`,
  ADD CONSTRAINT `fk_jm_hiv` FOREIGN KEY (`hivatkozott_id`) REFERENCES `jelzesrendszer` (`id`);

UPDATE `jelzesmenet` SET `terulet` = 'JELZES', `fajta` = 'SZABALY' WHERE `fajta` = 'RACS';
UPDATE `jelzesmenet` SET `terulet` = 'MODSZER', `fajta` = 'SZABALY' WHERE `fajta` = 'MODSZER';
UPDATE `jelzesmenet` SET `terulet` = 'KULONLEGES', `fajta` = 'SZABALY' WHERE `fajta` = 'KULONLEGES';
UPDATE `jelzesmenet` SET `terulet` = 'LICIT', `fajta` = 'SZABALY' WHERE `fajta` = 'LICIT';
UPDATE `jelzesmenet`
   SET `terulet` = IF(JSON_UNQUOTE(JSON_EXTRACT(`adat`, '$.helyzet')) = 'HIVAS', 'HIVAS', 'INDITAS')
 WHERE `fajta` = 'SZABALY' AND `terulet` IS NULL;
-- a kihagyás tartalma: {"torol": K} -> {"kihagy": K} (a jóváhagyás így marad)
UPDATE `jelzesmenet`
   SET `fajta` = 'KIHAGYAS',
       `adat` = JSON_OBJECT('kihagy', JSON_UNQUOTE(JSON_EXTRACT(`adat`, '$.torol')))
 WHERE `fajta` = 'TORLES';

ALTER TABLE `jelzesmenet`
  MODIFY `fajta` enum('SZABALY','ELV','KIVETEL','KIHAGYAS') COLLATE utf8mb4_unicode_ci NOT NULL
    DEFAULT 'SZABALY' COMMENT 'A sor szerepe, mint a licitmenet szabaly_fajta-ja',
  MODIFY `kulcs` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL
    COMMENT 'A FELÜLÍRÁS kulcsa (KIHAGYAS-nál a kihagyott sor kulcsa; HIVATKOZAS-nál HIV/KÓD)';

ALTER TABLE `jelzesrendszer`
  DROP COLUMN `hivatkozasok`,
  DROP COLUMN `kizarasok`;

-- --- 3. licitmenet: TORLES -> KIHAGYAS -----------------------------------
ALTER TABLE `licitmenet`
  MODIFY `szabaly_fajta` enum('SZABALY','ELV','KIVETEL','TORLES','KIHAGYAS')
    COLLATE utf8mb4_unicode_ci NOT NULL
    COMMENT 'KIHAGYAS: módosított konvencióban az alap egy szabálya ebben a változatban nem él';
UPDATE `licitmenet` SET `szabaly_fajta` = 'KIHAGYAS' WHERE `szabaly_fajta` = 'TORLES';
ALTER TABLE `licitmenet`
  MODIFY `szabaly_fajta` enum('SZABALY','ELV','KIVETEL','KIHAGYAS')
    COLLATE utf8mb4_unicode_ci NOT NULL
    COMMENT 'KIHAGYAS: módosított konvencióban az alap egy szabálya ebben a változatban nem él';
