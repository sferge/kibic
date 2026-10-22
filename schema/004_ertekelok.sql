-- =====================================================================
--  kibic — 004: az értékelő-regiszter bővítése + dokumentum-katalógus
--  Futtatás a 003 UTÁN.
-- =====================================================================
USE kibic;

-- Kiderült, hogy két AP-iskola van; a meglévő a 3-2-1
UPDATE ertekelo
   SET kod = 'AP_321',
       nev = 'Asztali pont (3-2-1)',
       leiras = 'HCP + renonsz 3 / szingli 2 / dubló 1'
 WHERE kod = 'AP';

INSERT IGNORE INTO ertekelo (kod, nev, leiras, kontextus) VALUES
 ('AP_531',     'Asztali pont (5-3-1)',
  'HCP + sikén 5 / szingli 3 / dubló 1. Standard American, Győr 2002.',
  'SZINTALALKOZAS'),
 ('NANO',       'Nano-pont',
  'A=3, K=2, D=1. Sylstandard 2 treff nyitás válaszainál.', 'ABSZOLUT'),
 ('GYORSUTES',  'Gyorsütés',
  'AK=2, AQ=1,5, A=1, KQ=1, Kx=0,5. A LICREN t jelzoje ennek 10-szerese.',
  'ABSZOLUT'),
 ('EGYENLETES', 'Egyenletes (LICREN b)',
  'Legalabb ket lap minden szinben. Tagabb, mint a kiegyensulyozott.',
  'ABSZOLUT'),
 ('F1', 'Figurapont a leghosszabb szinben',    'LICREN f1', 'ABSZOLUT'),
 ('F2', 'Figurapont a 2. leghosszabb szinben', 'LICREN f2', 'ABSZOLUT'),
 ('F3', 'Figurapont a 3. leghosszabb szinben', 'LICREN f3', 'ABSZOLUT'),
 ('F4', 'Figurapont a legrovidebb szinben',    'LICREN f4', 'ABSZOLUT');

-- A forrásdokumentumok katalogizálása
INSERT IGNORE INTO forras_dokumentum (kod, cim, szerzo, ev, formatum) VALUES
 ('MBSZ_EGYENI',    'Egyeni verseny licitrendszere - Standard', 'MBSZ', NULL, 'PDF'),
 ('STD_AMERICAN',   'Standard American',          'Gyor',        2002, 'PDF'),
 ('SYLSTANDARD',    'Sylstandard',                NULL,          2009, 'PDF'),
 ('MEZHON_DP',      'DP Licitrendszer',           NULL,          2011, 'PDF'),
 ('SZEGEDI_MRAZ',   'Szegedi-Mraz licitrendszer', 'Szegedi Balazs & Mraz Mate', 2008, 'PDF'),
 ('HEAVYCLUB_2004', 'Heavy Club',                 'Hajdu Peter', 2004, 'DOC'),
 ('LICREN_STAND',   'LICREN stand.lr',            NULL,          2013, 'EGYEB'),
 ('LICREN_SZILPRE', 'LICREN szilpre.lr',          NULL,          2013, 'EGYEB');
