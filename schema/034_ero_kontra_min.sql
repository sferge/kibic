-- =====================================================================
--  kibic — 034: ERO_KONTRA_MIN — az erős (elosztástól független)
--  újranyitó kontra alsó határa (a szerkesztő, 2026-11-10; licit-szál)
--
--  (Nx) P (P) X és 1x (y) P (P) X: ennyi figuraponttól bármilyen
--  elosztással. KIBIC_STAND: 17 (alapérték), MOHA_STAND: 18.
-- =====================================================================

USE kibic;

INSERT IGNORE INTO parameter (kod, nev, ertekelo_id, alapertek,
                              min_ertek, max_ertek, csoport, leiras)
VALUES ('ERO_KONTRA_MIN', 'Erős újranyitó kontra minimuma (figurapont)',
        (SELECT id FROM ertekelo WHERE kod = 'HCP'), '17', 16, 19, 'kompetitiv',
        'A sor végi (és a nyitó) újranyitó kontrája ennyi ponttól bármilyen elosztással.');
