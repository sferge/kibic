-- =====================================================================
--  kibic — 010: logikai metrikák és rendszerváltozatok
--
--  A `@PONT`, `@JATEKUTES`, `@INDULOERO` hivatkozások feloldása.
--  Ettől ugyanaz a 750 szabály TÖBBFÉLE ÉRTELMEZÉSSEL futtatható, és
--  a mérés dönti el, melyik reprodukálja a valódi liciteket.
--
--  Futtatás: a 009 UTÁN, a LICREN-import ELŐTT (vagy után, mindegy).
-- =====================================================================

USE kibic;

-- ---------------------------------------------------------------------
-- 1. Jelölt értékelők a regiszterbe
-- ---------------------------------------------------------------------

INSERT IGNORE INTO ertekelo (kod, nev, leiras, kontextus) VALUES
 ('P_HCP',    'Pont = figurapont',
  'PONT-jelolt: nincs elosztasi pont.', 'ABSZOLUT'),
 ('P_HOSSZ',  'Pont = figurapont + hosszusagi pont',
  'PONT-jelolt: minden 4 feletti lap a szinben +1. A legelterjedtebb.',
  'ABSZOLUT'),
 ('P_HOSSZ5', 'Pont = figurapont + hosszusagi pont (max 3 szinenkent)',
  'PONT-jelolt: a nagyon hosszu szinek tulertekelese ellen.', 'ABSZOLUT'),
 ('P_AP531',  'Pont = figurapont + rovidsegi pont (5-3-1)',
  'PONT-jelolt: siken 5 / szingli 3 / dublo 1.', 'SZINTALALKOZAS'),
 ('P_AP321',  'Pont = figurapont + rovidsegi pont (3-2-1)',
  'PONT-jelolt: renonsz 3 / szingli 2 / dublo 1.', 'SZINTALALKOZAS'),
 ('J_KLASSZIKUS', 'Jatekutes: figuraütesek + hosszu lapok',
  'JATEKUTES-jelolt. A LICREN j jelzoje ennek 10-szerese.', 'ABSZOLUT'),
 ('J_AKQ',    'Jatekutes: A=2, K=1, D=0,5',
  'JATEKUTES-jelolt: egyszeru figurasulyozas.', 'ABSZOLUT'),
 ('J_HOSSZ',  'Jatekutes: gyorsutes + hosszu szinek tobbletlapjai',
  'JATEKUTES-jelolt: gatlo nyitasoknal szokasos becsles.', 'ABSZOLUT');

-- ---------------------------------------------------------------------
-- 2. A logikai metrikákat beállító paraméterek
--    Ezek ÉRTÉKE egy értékelő KÓDJA (szöveg), nem szám.
-- ---------------------------------------------------------------------

INSERT IGNORE INTO parameter (kod, nev, tipus, alapertek, csoport, leiras) VALUES
 ('PONT_METRIKA', 'Melyik metrika a "pont"', 'FELSOROLAS', 'P_HOSSZ', 'metrika',
  'A @PONT hivatkozas feloldasa. Jeloltek: P_HCP, P_HOSSZ, P_HOSSZ5, '
  'P_AP531, P_AP321, ZAR.'),
 ('JATEKUTES_METRIKA', 'Melyik metrika a "jatekutes"', 'FELSOROLAS',
  'J_KLASSZIKUS', 'metrika',
  'A @JATEKUTES hivatkozas feloldasa. Jeloltek: J_KLASSZIKUS, J_AKQ, J_HOSSZ.'),
 ('INDULOERO_KESZLET', 'Melyik kriterium-keszlet az "induloero"',
  'FELSOROLAS', 'NYITAS_ERO', 'metrika',
  'A @INDULOERO hivatkozas feloldasa egy kriterium_keszlet kodjara. '
  'Igy az induloerot TOBB ERTEKELES egyuttese dontheti el.');

-- ---------------------------------------------------------------------
-- 3. Az alaprendszerek beállítása
-- ---------------------------------------------------------------------

INSERT IGNORE INTO rendszer_parameter (rendszer_id, parameter_id, ertek, megjegyzes)
SELECT r.id, p.id, 'P_HOSSZ', 'Kiindulo feltetelezes - MERESSEL ellenorzendo'
  FROM rendszer r, parameter p
 WHERE r.kod IN ('LICREN_STAND','LICREN_STUND','LICREN_SZILPRE')
   AND p.kod = 'PONT_METRIKA';

INSERT IGNORE INTO rendszer_parameter (rendszer_id, parameter_id, ertek, megjegyzes)
SELECT r.id, p.id, 'J_KLASSZIKUS', 'Kiindulo feltetelezes'
  FROM rendszer r, parameter p
 WHERE r.kod IN ('LICREN_STAND','LICREN_STUND','LICREN_SZILPRE')
   AND p.kod = 'JATEKUTES_METRIKA';

INSERT IGNORE INTO rendszer_parameter (rendszer_id, parameter_id, ertek, megjegyzes)
SELECT r.id, p.id, 'NYITAS_ERO', 'Tobb ertekeles egyuttese (LEGALABB)'
  FROM rendszer r, parameter p
 WHERE r.kod IN ('LICREN_STAND','LICREN_STUND','LICREN_SZILPRE')
   AND p.kod = 'INDULOERO_KESZLET';

-- ---------------------------------------------------------------------
-- 4. PÉLDA VÁLTOZATOK: ugyanaz a 750 szabály, más pont-értelmezéssel.
--    Mindegyik KÉT SOR: egy hivatkozás + egy paraméter-felülbírálat.
-- ---------------------------------------------------------------------

INSERT IGNORE INTO rendszer (kod, nev, fajta, csalad, leiras) VALUES
 ('STAND_P_HCP',   'LICREN standard - pont = figurapont',
  'KONVENCIOKARTYA', 'NATURAL',
  'Ugyanaz a szabalyhalmaz, a "pont" a puszta figurapont.'),
 ('STAND_P_AP531', 'LICREN standard - pont = figurapont + rovidseg',
  'KONVENCIOKARTYA', 'NATURAL',
  'Ugyanaz a szabalyhalmaz, a "pont" asztali pont (5-3-1).'),
 ('STAND_P_ZAR',   'LICREN standard - pont = Zar-pont',
  'KONVENCIOKARTYA', 'NATURAL',
  'Ugyanaz a szabalyhalmaz, a "pont" a Zar-pont.');

INSERT IGNORE INTO licitmenet (rendszer_id, fejezet, seq, tipus,
                               hivatkozott_id, allapot, nyers_szoveg)
SELECT v.id, 'Alaprendszer', 0, 'HIVATKOZAS', a.id, 'ELFOGADOTT',
       CONCAT('A(z) ', a.kod, ' teljes beemelese')
  FROM rendszer v, rendszer a
 WHERE v.kod IN ('STAND_P_HCP','STAND_P_AP531','STAND_P_ZAR')
   AND a.kod = 'LICREN_STAND';

INSERT IGNORE INTO rendszer_parameter (rendszer_id, parameter_id, ertek)
SELECT r.id, p.id, v.metrika
  FROM (SELECT 'STAND_P_HCP' AS kod, 'P_HCP' AS metrika
        UNION ALL SELECT 'STAND_P_AP531', 'P_AP531'
        UNION ALL SELECT 'STAND_P_ZAR',   'ZAR') v
  JOIN rendszer r ON r.kod = v.kod
  JOIN parameter p ON p.kod = 'PONT_METRIKA';

-- ---------------------------------------------------------------------
-- 5. Diagnózis
-- ---------------------------------------------------------------------

SELECT r.kod AS rendszer, p.kod AS parameter, rp.ertek
  FROM rendszer_parameter rp
  JOIN rendszer r  ON r.id = rp.rendszer_id
  JOIN parameter p ON p.id = rp.parameter_id
 ORDER BY r.kod, p.kod;
