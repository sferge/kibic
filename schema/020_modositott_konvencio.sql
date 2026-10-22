-- kibic — 020: módosított konvenció és konvenció-változat
--
-- A legtöbb "saját" konvenció valójában egy ismert konvenció VÁLTOZATA
-- (névvel bíró, ismert eltérés, pl. fordított Bergen) vagy MÓDOSÍTÁSA
-- (saját eltérés, pl. a Moha-féle Lebensohl). Ezt így írjuk le:
--
--   rendszer.alapja  = a kiinduló konvenció kódja (pl. LEBENSOHL)
--   rendszer.viszony = VALTOZAT / MODOSITAS
--
-- A módosított konvenció behivatkozza az alapját (az importáló egy BE
-- módú HIVATKOZAS sort ír), a saját sorai azonos kulcson FELÜLÍRJÁK az
-- alapéit, és egy alapbeli szabályt KI IS VEHET: ez a TORLES fajtájú sor
-- ("ebben a változatban ez a licit nem létezik"). Kivenni csak itt lehet,
-- mert itt szándékos; a rendszercheck jelzi, ha ettől lyuk keletkezik.
--
-- Futtatás: a 019 után.

ALTER TABLE rendszer
  ADD COLUMN alapja VARCHAR(40) NULL
  COMMENT 'Módosított konvenciónál / változatnál: a kiinduló konvenció kódja',
  ADD COLUMN viszony ENUM('VALTOZAT','MODOSITAS') NULL
  COMMENT 'VALTOZAT: ismert, névvel bíró változat; MODOSITAS: saját eltérés';

ALTER TABLE licitmenet
  MODIFY szabaly_fajta ENUM('SZABALY','ELV','KIVETEL','TORLES')
  NOT NULL DEFAULT 'SZABALY'
  COMMENT 'TORLES: módosított konvencióban az alap egy szabályát kiveszi';
