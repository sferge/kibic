-- =====================================================================
--  kibic — 011: az értékelők DEFINÍCIÓJA adattá válik
--
--  Eddig a metrikák Python-függvények voltak, a tábla csak regiszter.
--  Mostantól a tábla `definicio` oszlopa tartalmazza a KÉPLETET is, egy
--  kis deklaratív nyelven (domain/ertekelo.py értelmezi).
--
--  KÖVETKEZMÉNY: új metrika felvétele vagy meglévő módosítása EGYETLEN
--  ADATBÁZISSOR — nincs kódmódosítás, nincs kettős nyilvántartás.
--  A domain/kartya.py-ból az összes `ert_*` függvény eltűnt.
--
--  IGAZOLÁS: 4000 véletlen kéz × 21 metrika = 84 000 összehasonlítás a
--  korábbi implementációval, NULLA eltéréssel.
--
--  A csomagban lévő `ertekelok.json` PILLANATKÉP (adatbázis nélküli
--  munkához). Kanonikus forrás ez a tábla; a pillanatkép exportálható:
--      python -c "from kibic.domain.ertekelo import *; \
--                 betolt_adatbazisbol(conn); export_json()"
-- =====================================================================

USE kibic;

DROP PROCEDURE IF EXISTS kibic_oszlop_ha_kell;
DELIMITER $$
CREATE PROCEDURE kibic_oszlop_ha_kell(IN t VARCHAR(64), IN o VARCHAR(64),
                                      IN meghat TEXT)
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.TABLES
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = t)
     AND NOT EXISTS (SELECT 1 FROM information_schema.COLUMNS
                      WHERE TABLE_SCHEMA = DATABASE()
                        AND TABLE_NAME = t AND COLUMN_NAME = o) THEN
    SET @sql = CONCAT('ALTER TABLE `', t, '` ADD COLUMN `', o, '` ', meghat);
    PREPARE st FROM @sql; EXECUTE st; DEALLOCATE PREPARE st;
    SELECT CONCAT('Hozzaadva: ', t, '.', o) AS migracio;
  END IF;
END$$
DELIMITER ;

CALL kibic_oszlop_ha_kell('ertekelo', 'definicio',
  "JSON NULL COMMENT 'A metrika KEPLETE. Tagtipusok: LAP_SULY, HOSSZ_SULY, "
  "HOSSZ_TOBBLET, RENDEZETT_HOSSZ, ERTEKELO, SZIN_MINTA, SZIN_HIANYZO, "
  "FELTETEL. Ertelmezo: domain/ertekelo.py'");

DROP PROCEDURE kibic_oszlop_ha_kell;

-- A definíciók feltöltése (idempotens: felülírja a meglévőket)
INSERT INTO ertekelo (kod, nev, leiras, kontextus, definicio) VALUES
  ('AP_321','Asztali pont (3-2-1)','HCP + renonsz 3 / szingli 2 / dubló 1','SZINTALALKOZAS','{"tagok":[{"egyutthato":1,"kod":"HCP","tipus":"ERTEKELO"},{"sulyok":{"0":3,"1":2,"2":1},"tipus":"HOSSZ_SULY"}]}'),
  ('AP_531','Asztali pont (5-3-1)','HCP + sikén 5 / szingli 3 / dubló 1','SZINTALALKOZAS','{"tagok":[{"egyutthato":1,"kod":"HCP","tipus":"ERTEKELO"},{"sulyok":{"0":5,"1":3,"2":1},"tipus":"HOSSZ_SULY"}]}'),
  ('EGYENLETES','Egyenletes (LICREN b)','Legalább két lap minden színben. 1 vagy 0.','ABSZOLUT','{"tagok":[{"akkor":1,"bal":{"rang":4,"tipus":"RENDEZETT_HOSSZ"},"jobb":2,"kulonben":0,"op":">=","tipus":"FELTETEL"}]}'),
  ('F1','Figurapont a 1. leghosszabb színben','LICREN f1','ABSZOLUT','{"tagok":[{"sulyok":{"A":4,"J":1,"K":3,"Q":2},"szin_rang":1,"tipus":"LAP_SULY"}]}'),
  ('F2','Figurapont a 2. leghosszabb színben','LICREN f2','ABSZOLUT','{"tagok":[{"sulyok":{"A":4,"J":1,"K":3,"Q":2},"szin_rang":2,"tipus":"LAP_SULY"}]}'),
  ('F3','Figurapont a 3. leghosszabb színben','LICREN f3','ABSZOLUT','{"tagok":[{"sulyok":{"A":4,"J":1,"K":3,"Q":2},"szin_rang":3,"tipus":"LAP_SULY"}]}'),
  ('F4','Figurapont a 4. leghosszabb színben','LICREN f4','ABSZOLUT','{"tagok":[{"sulyok":{"A":4,"J":1,"K":3,"Q":2},"szin_rang":4,"tipus":"LAP_SULY"}]}'),
  ('GYORSUTES','Gyorsütés','AK=2, AQ=1,5, A=1, KQ=1, Kx=0,5','ABSZOLUT','{"tagok":[{"szabalyok":[{"ertek":2,"tart":["A","K"]},{"ertek":1.5,"tart":["A","Q"]},{"ertek":1,"tart":["A"]},{"ertek":1,"tart":["K","Q"]},{"ertek":0.5,"min_hossz":2,"tart":["K"]}],"tipus":"SZIN_MINTA"}]}'),
  ('HCP','Figurapont (4-3-2-1)','Milton Work: A=4, K=3, D=2, B=1','ABSZOLUT','{"tagok":[{"sulyok":{"A":4,"J":1,"K":3,"Q":2},"tipus":"LAP_SULY"}]}'),
  ('HCP_DIST','Figurapont + elosztás','HCP + minden 4 feletti lap +1','ABSZOLUT','{"tagok":[{"egyutthato":1,"kod":"HCP","tipus":"ERTEKELO"},{"felett":4,"tipus":"HOSSZ_TOBBLET"}]}'),
  ('J_HOSSZ','Játékütés: gyorsütés + hosszú színek többletlapjai','JÁTÉKÜTÉS-jelölt: gátló nyitásoknál szokásos becslés.','ABSZOLUT','{"tagok":[{"egyutthato":1,"kod":"GYORSUTES","tipus":"ERTEKELO"},{"felett":3,"tipus":"HOSSZ_TOBBLET"}]}'),
  ('J_KLASSZIKUS','Játékütés: figuraütések + hosszú lapok','JÁTÉKÜTÉS-jelölt. A LICREN j jelzője ennek 10-szerese.','ABSZOLUT','{"kerekites":4,"tagok":[{"szabalyok":[{"ertek":3,"tart":["A","K","Q"]},{"ertek":2.5,"min_hossz":3,"tart":["A","K"]},{"ertek":2,"tart":["A","K"]},{"ertek":1.5,"min_hossz":2,"tart":["A","Q"]},{"ertek":1,"tart":["A"]},{"ertek":1,"min_hossz":3,"tart":["K","Q"]},{"ertek":0.5,"min_hossz":2,"tart":["K"]},{"ertek":0.25,"min_hossz":3,"tart":["Q"]}],"tipus":"SZIN_MINTA"},{"egyutthato":0.75,"felett":3,"tipus":"HOSSZ_TOBBLET"}]}'),
  ('KONTROLL','Kontrollszám','A=2, K=1 (szlemkutatáshoz)','ABSZOLUT','{"tagok":[{"sulyok":{"A":2,"K":1},"tipus":"LAP_SULY"}]}'),
  ('LTC','Losing Trick Count','Színenként hány hiányzik az A, K, D közül az első három lapból','SZINTALALKOZAS','{"tagok":[{"kozul":["A","K","Q"],"max_lap":3,"tipus":"SZIN_HIANYZO"}]}'),
  ('NANO','Nano-pont','A=3, K=2, D=1. Sylstandard 2 treff válaszainál.','ABSZOLUT','{"tagok":[{"sulyok":{"A":3,"K":2,"Q":1},"tipus":"LAP_SULY"}]}'),
  ('P_AP321','Pont = figurapont + rövidségi pont (3-2-1)','PONT-jelölt.','SZINTALALKOZAS','{"tagok":[{"egyutthato":1,"kod":"AP_321","tipus":"ERTEKELO"}]}'),
  ('P_AP531','Pont = figurapont + rövidségi pont (5-3-1)','PONT-jelölt.','SZINTALALKOZAS','{"tagok":[{"egyutthato":1,"kod":"AP_531","tipus":"ERTEKELO"}]}'),
  ('P_HCP','Pont = figurapont','PONT-jelölt: nincs elosztási pont.','ABSZOLUT','{"tagok":[{"egyutthato":1,"kod":"HCP","tipus":"ERTEKELO"}]}'),
  ('P_HOSSZ','Pont = figurapont + hosszúsági pont','PONT-jelölt: minden 4 feletti lap a színben +1. A legelterjedtebb.','ABSZOLUT','{"tagok":[{"egyutthato":1,"kod":"HCP","tipus":"ERTEKELO"},{"felett":4,"tipus":"HOSSZ_TOBBLET"}]}'),
  ('P_HOSSZ5','Pont = figurapont + hosszúsági pont (színenként max 3)','PONT-jelölt: a nagyon hosszú színek túlértékelése ellen.','ABSZOLUT','{"tagok":[{"egyutthato":1,"kod":"HCP","tipus":"ERTEKELO"},{"felett":4,"max":3,"tipus":"HOSSZ_TOBBLET"}]}'),
  ('ZAR','Zar-pont','Zar Petkov: HCP + kontroll + (leghosszabb + második) + (leghosszabb - legrövidebb)','ABSZOLUT','{"tagok":[{"egyutthato":1,"kod":"HCP","tipus":"ERTEKELO"},{"egyutthato":1,"kod":"KONTROLL","tipus":"ERTEKELO"},{"egyutthato":2,"rang":1,"tipus":"RENDEZETT_HOSSZ"},{"egyutthato":1,"rang":2,"tipus":"RENDEZETT_HOSSZ"},{"egyutthato":-1,"rang":4,"tipus":"RENDEZETT_HOSSZ"}]}')
ON DUPLICATE KEY UPDATE
  nev = VALUES(nev), leiras = VALUES(leiras),
  kontextus = VALUES(kontextus), definicio = VALUES(definicio);

-- Diagnózis: van-e definíció nélküli (tehát használhatatlan) értékelő?
SELECT kod, nev,
       IF(definicio IS NULL, 'NINCS DEFINICIO', 'ok') AS allapot
  FROM ertekelo ORDER BY (definicio IS NULL) DESC, kod;

SELECT COUNT(*) AS ertekelo_osszesen,
       SUM(definicio IS NOT NULL) AS definialt
  FROM ertekelo;
