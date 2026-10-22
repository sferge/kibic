-- =====================================================================
--  kibic — a 015/016 TARTALMÁNAK visszavonása
--
--  Ezt CSAK akkor futtasd, ha a fésűtől és az alapelvektől meg akarsz
--  szabadulni. A 014/016 által hozzáadott OSZLOPOKAT szándékosan nem
--  bántjuk:
--
--    * eldobásuk adatvesztéssel járna, ha közben bármit beleírtál;
--    * fölöslegesek is: a régi kód egyszerűen nem használja őket. A
--      `motor/feloldas.py` megpróbálja a bővített lekérdezést, és ha az
--      oszlopok hiányoznak, visszaesik az alapkészletre.
--
--  Vagyis a séma bővítése ártalmatlan; csak a BETÖLTÖTT SZABÁLYOK
--  visszavonása lehet indokolt.
--
--  Enyhébb megoldás, ha csak ki akarod kapcsolni őket: állítsd a
--  sorokat ELVETETT állapotba — akkor megmaradnak, de a motor nem
--  látja őket (lásd a fájl végén).
-- =====================================================================

USE kibic;

-- --- Mit fogunk törölni? Előbb nézd meg. ------------------------------

SELECT r.kod, r.nev, COUNT(lm.id) AS sorok,
       SUM(lm.allapot = 'ELFOGADOTT') AS elfogadott
  FROM rendszer r
  LEFT JOIN licitmenet lm ON lm.rendszer_id = r.id
 WHERE r.kod IN ('FESU', 'ALAPELVEK')
 GROUP BY r.kod, r.nev;

-- Hivatkozik-e rájuk bármelyik konvenciókártya? Ha igen, ELŐBB azt
-- bontsd meg, különben a törlés a hivatkozó sorokat is elviszi.
SELECT h.kod AS hivatkozo, r.kod AS hivatkozott, lm.hivatkozas_aktiv
  FROM licitmenet lm
  JOIN rendszer h ON h.id = lm.rendszer_id
  JOIN rendszer r ON r.id = lm.hivatkozott_id
 WHERE lm.tipus = 'HIVATKOZAS' AND r.kod IN ('FESU', 'ALAPELVEK');

-- --- A törlés ---------------------------------------------------------
--  A `licitmenet` sorok a rendszerre ON DELETE CASCADE-elnek, tehát a
--  rendszer törlése a szabályait is elviszi. A `feloldott_licitmenet`
--  SZÁRMAZTATOTT: újraépíthető, ezért nyugodtan mehet.

DELETE FROM feloldott_licitmenet
 WHERE rendszer_id IN (SELECT id FROM rendszer
                        WHERE kod IN ('FESU', 'ALAPELVEK'))
    OR eredet_rendszer IN (SELECT id FROM rendszer
                            WHERE kod IN ('FESU', 'ALAPELVEK'));

DELETE FROM rendszer_dokumentum
 WHERE rendszer_id IN (SELECT id FROM rendszer
                        WHERE kod IN ('FESU', 'ALAPELVEK'));

DELETE FROM rendszer WHERE kod IN ('FESU', 'ALAPELVEK');

-- A forrásdokumentumok maradhatnak: katalógus-sorok, nem ártanak.
-- Ha mégis: DELETE FROM forras_dokumentum WHERE kod IN ('FESU_DOCX','KUZDELMI_DOC');

-- A kompetitív paraméterek is maradhatnak (használat nélkül semmit nem
-- csinálnak). Ha takarítanál:
-- DELETE FROM parameter WHERE csoport = 'kompetitiv';

SELECT COUNT(*) AS maradt_rendszer FROM rendszer
 WHERE kod IN ('FESU', 'ALAPELVEK');

-- =====================================================================
--  ENYHÉBB VÁLTOZAT — törlés helyett kikapcsolás
--
--  UPDATE licitmenet lm JOIN rendszer r ON r.id = lm.rendszer_id
--     SET lm.allapot = 'ELVETETT'
--   WHERE r.kod IN ('FESU', 'ALAPELVEK');
--
--  A motor csak ELFOGADOTT sorokat használ, tehát ez ugyanúgy
--  "kikapcsolja" őket, de a munka nem vész el. Alapból egyébként
--  mindkét rendszer JAVASOLT állapotban van, vagyis a betöltés
--  önmagában SEM változtat semmit a méréseken.
-- =====================================================================
