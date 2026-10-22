-- =====================================================================
--  kibic — 025: a pozitív szabad licit paramétere (2026-10-02)
--
--  SZABAD_LICIT_MIN: a nyitásunk utáni közbeszólásra a válaszoló nem ugró
--  új színének (2-es / 3-as szint) pontminimuma, figurapontban. Van, aki
--  10-zel, van, aki 11-gyel játssza: rendszerenként (rendszer_parameter,
--  a YAML `parameterek:` blokkja) és páronként (par_parameter) állítható.
--  A KIBIC_STAND az alapértéket (10) használja, a MOHA_STAND 11-et.
--
--  Futtatás: a 024 után, a rendszerimport ELŐTT (különben a MOHA_STAND
--  importja „ismeretlen paraméter: SZABAD_LICIT_MIN” hibával megáll).
-- =====================================================================
INSERT IGNORE INTO parameter (kod, nev, ertekelo_id, alapertek,
                              min_ertek, max_ertek, csoport, leiras)
VALUES ('SZABAD_LICIT_MIN', 'Pozitív szabad licit minimuma (figurapont)',
        (SELECT id FROM ertekelo WHERE kod = 'HCP'), '10', 9, 12, 'valasz',
        'Közbeszólás után a válaszoló nem ugró új színe: 10 vagy 11 — a partnerek megállapodása.');
