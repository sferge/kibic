-- 032_jelzes_szinadas.sql — új jelzésterület: SZINADAS (2026-10-21)
--
-- A színadás második kézben is megállapodás lehet (pl. „dubló figurából a
-- figura”: `helyzet: MASODIK_KEZ` a jelzésrendszer YAML-jában). Az ilyen sor
-- területe SZINADAS. Utána: python -m kibic.cli.rendszerimport rendszerek/yaml/ --csak KIBIC_STAND

ALTER TABLE `jelzesmenet`
  MODIFY `terulet` enum('INDITAS','HIVAS','SZINADAS','JELZES','MODSZER','KULONLEGES','LICIT')
    COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'Miről szól (a licit `ag`-ja helyett)';
