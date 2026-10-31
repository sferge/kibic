-- =====================================================================
--  kibic — 033: HOSSZ_NT — hosszú (6+) szín a partner szanja ellen
--  (a szerkesztő, 2026-10-31; licit-szál)
--
--  HCP + szingli 1 / renonsz 2 (színenként) + 1, ha a leghosszabb,
--  legalább 6 lapos színben ász vagy király van (a dáma nem számít).
--  Az 1NT / 2NT utáni 6+ lapos nemesnél: invit / Texas / szleminvit
--  sávja (YAML: `nt_pont`).
-- =====================================================================

USE kibic;

INSERT INTO ertekelo (kod, nev, leiras, kontextus, definicio) VALUES
  ('HOSSZ_NT', 'Hosszú szín a szan ellen',
   'HCP + szingli 1 / renonsz 2 + 1, ha a leghosszabb, legalább 6 lapos színben ász vagy király van (a dáma nem számít)',
   'SZINTALALKOZAS',
   '{"tagok":[{"egyutthato":1,"kod":"HCP","tipus":"ERTEKELO"},{"sulyok":{"0":2,"1":1},"tipus":"HOSSZ_SULY"},{"bal":{"min_hossz":6,"sulyok":{"A":1,"K":1},"szin_rang":1,"tipus":"LAP_SULY"},"jobb":1,"op":">=","tipus":"FELTETEL"}]}')
ON DUPLICATE KEY UPDATE
  nev = VALUES(nev), leiras = VALUES(leiras), definicio = VALUES(definicio);
