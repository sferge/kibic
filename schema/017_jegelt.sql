-- kibic — 017: JEGELT állapot a licitmenetben (teszt mód)
--
-- A motor élesben csak az ELFOGADOTT sorokat használja; TESZT MÓDBAN
-- (KIBIC_TESZT_MOD=1, vagy a kérésben "test_mode": true) a JAVASOLT és a
-- FELULVIZSGALANDO sorokat is. A JEGELT sort egyik mód sem használja:
-- "tudunk róla, de még ne használd, teszteléskor sem" — pl. egy ütköző
-- vagy félkész szabály.
--
-- Az enum bővítése a meglévő sorokat nem érinti.

ALTER TABLE licitmenet
  MODIFY allapot ENUM('JAVASOLT','ELFOGADOTT','ELVETETT','FELULVIZSGALANDO','JEGELT')
  COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'JAVASOLT';
