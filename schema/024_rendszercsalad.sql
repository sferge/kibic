-- =====================================================================
--  kibic — 024: RENDSZERCSALÁD (2026-10-01)
--
--  Új rendszer-fajta: RENDSZERCSALAD — egy rendszercsalád ÁLTALÁNOS
--  rendszere (pl. „erős treff”): a nyitások és a legfontosabb válaszok,
--  amit egy ismeretlen pár rendszeréről a családja alapján feltételezni
--  lehet. A kód megegyezik a `rendszer.csalad` értékével (STRONG_CLUB,
--  NATURAL, ACOL, POLISH), így egy ismert rendszer a családján keresztül
--  is hivatkozható.
--
--  A MohaBridzs a `game.systems`-ben ismert rendszer HELYETT a család
--  kódját is küldheti ("EW": "STRONG_CLUB"); a kibic az ellenfél
--  licitjeit ilyenkor a család általános rendszere szerint érti.
--
--  Futtatás: a 023 után, a rendszerimport ELŐTT.
-- =====================================================================

USE kibic;

ALTER TABLE rendszer
  MODIFY fajta ENUM('ALAPRENDSZER','KONVENCIO','RENDSZER','GYUJTEMENY',
                    'RENDSZERCSALAD') NOT NULL;

SELECT COLUMN_TYPE FROM information_schema.COLUMNS
 WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'rendszer' AND COLUMN_NAME = 'fajta';
