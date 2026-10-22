-- kibic — 022: jegyzetek a szerkesztőnek
--
-- A JEGYZET tartós magyarázat: MIÉRT ilyen egy szabály, fejezet vagy
-- konvenció. A YAML-forrásban él (`jegyzet:`), onnan importálódik, és a
-- szerkesztő mindig megmutatja. Nem azonos a MEGJEGYZÉSSEL (021), ami
-- munkajegyzet / kérdés, és lezárható.

ALTER TABLE rendszer
  ADD COLUMN jegyzet TEXT NULL COMMENT 'A rendszer / konvenció jegyzete',
  ADD COLUMN fejezet_jegyzetek JSON NULL COMMENT '{fejezet: jegyzet}';

ALTER TABLE licitmenet
  ADD COLUMN jegyzet TEXT NULL COMMENT 'A szabály jegyzete (miért ilyen)';
