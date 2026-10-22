-- =====================================================================
--  kibic — 012: a BBO GIB "total points" metrikája
--
--  VISSZAFEJTVE a robot saját magyarázataiból. A BBO_GIB.docx azt írja,
--  hogy a total points = HCP + 3 renonszért / 2 szingliért / 1 dublóért
--  (ez a mi AP_321-ünk). A robot állításai viszont ennél MAGASABB
--  értékeket mondanak:
--
--    2.Q965.KQ943.Q84   9 HCP, AP_321 = 11, a robot szerint 12-22
--    AKJT74.A.J96.AK6  20 HCP, AP_321 = 22, a robot szerint 23+
--
--  A különbség pontosan a HOSSZÚSÁGI PONT (minden 4 feletti lap +1).
--  Mindkét eset stimmel, ha a képlet:
--      HCP + rövidségi pont (3/2/1) + hosszúsági pont
--
--  Ez a dokumentáció hiányossága, nem a robot tévedése — és jó példa
--  arra, miért éri meg a fordítást MÉRNI, nem elhinni.
-- =====================================================================

USE kibic;

INSERT INTO ertekelo (kod, nev, leiras, kontextus, definicio) VALUES
  ('TOTAL_POINTS', 'Total points (BBO GIB)', 'HCP + rovidsegi pont (renonsz 3 / szingli 2 / dublo 1) + hosszusagi pont (minden 4 feletti lap +1). A GIB sajat magyarazataibol visszafejtve.', 'ABSZOLUT', '{"tagok":[{"kod":"HCP","tipus":"ERTEKELO"},{"sulyok":{"0":3,"1":2,"2":1},"tipus":"HOSSZ_SULY"},{"felett":4,"tipus":"HOSSZ_TOBBLET"}]}')
ON DUPLICATE KEY UPDATE
  nev = VALUES(nev), leiras = VALUES(leiras), definicio = VALUES(definicio);

-- A GIB rendszer beállítása (ha már be van töltve)
INSERT IGNORE INTO rendszer (kod, nev, fajta, csalad, leiras) VALUES
 ('GIB', 'BBO GIB (2/1 gemforsz)', 'LICITRENDSZER', 'NATURAL',
  'A BBO robotjanak rendszere. Forras: BBO_GIB.docx + a robot sajat '
  'magyarazatai a gyujtemenybol.');

INSERT IGNORE INTO rendszer_parameter (rendszer_id, parameter_id, ertek, megjegyzes)
SELECT r.id, p.id, 'TOTAL_POINTS',
       'A GIB "total points"-ja: HCP + rovidseg + hosszusag'
  FROM rendszer r, parameter p
 WHERE r.kod = 'GIB' AND p.kod = 'PONT_METRIKA';

SELECT kod, nev, definicio IS NOT NULL AS van_definicio
  FROM ertekelo WHERE kod IN ('AP_321','TOTAL_POINTS','P_HOSSZ');
