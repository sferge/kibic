-- =====================================================================
--  kibic — 035: a spirál megállapodása paraméterekben (a szerkesztő,
--  2026-11-11; licit-szál). A rendszer a saját változatát a
--  `parameterek`-ben rögzítheti; az alapérték a Moha-féle spirál
--  (motor/spiral.py: SPIRAL_ALAP).
-- =====================================================================

USE kibic;

INSERT IGNORE INTO parameter (kod, nev, tipus, alapertek, csoport, leiras) VALUES
 ('SPIRAL_RETEGEK', 'Spirál: a rétegek', 'FELSOROLAS', 'QA|K|Q|JA,J', 'szlem',
  'QA = adu dáma (ha nem ismert), K/Q/J = a külső színek királyai/dámái/bubijai, JA = adu bubi; rétegek |-vel, egy rétegen belül vesszővel.'),
 ('SPIRAL_SZINSOR', 'Spirál: a külső színek sorrendje', 'FELSOROLAS', 'SHDC', 'szlem',
  'A külső színek sorrendje (S, H, D, C).'),
 ('SPIRAL_SIKEN', 'Spirál: a tudott sikén', 'FELSOROLAS', 'KIRALY', 'szlem',
  'KIRALY = a válaszoló tudott sikénje királynak számít; KIMARAD = a szín kimarad a sorból.');
