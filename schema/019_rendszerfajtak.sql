-- kibic — 019: rendszer-fajták, téma, kizárás
--
-- 1. FAJTÁK (a cél szerint elnevezve):
--      ALAPRENDSZER  emberi forrásból, sok szabállyal   (korábban LICITRENDSZER)
--      KONVENCIO     egy konkrét probléma megoldása      (változatlan)
--      RENDSZER      amit egy pár játszik; csak hivatkozásokból áll
--                                                        (korábban KONVENCIOKARTYA)
--      GYUJTEMENY    csak hivatkozások, a kényelem kedvéért (új)
--
-- 2. TÉMA: minden konvenció megmondhatja, melyik problémát oldja meg
--    ("1NT nyitásunk kontrája után"). Az azonos témájú konvenciók egymás
--    ALTERNATÍVÁI: ha egy rendszerben kettő is szerepel, a feloldás a
--    közelebbit (kisebb mélység, azon belül a kártyán előbb állót) tartja
--    meg, és ezt jelzi.
--
-- 3. KIZÁRÁS: a HIVATKOZAS sor lehet beemelés (BE) vagy kizárás (KI). A KI
--    sor a hivatkozó rendszer ALATTI teljes fában kizár egy konvenciót /
--    gyűjteményt, vagy (kizart_fejezet megadásával) annak egy fejezetét.
--    "Ezt a gyűjteményt játsszuk, ennek kivételével."
--
-- Futtatás: a 018 után. A régi fajtanevű sorok átíródnak.

-- 1. fajták: előbb bővítjük az enumot, átírjuk az értékeket, majd szűkítjük
ALTER TABLE rendszer
  MODIFY fajta ENUM('LICITRENDSZER','KONVENCIO','KONVENCIOKARTYA',
                    'ALAPRENDSZER','RENDSZER','GYUJTEMENY') NOT NULL;
UPDATE rendszer SET fajta = 'ALAPRENDSZER' WHERE fajta = 'LICITRENDSZER';
UPDATE rendszer SET fajta = 'RENDSZER'     WHERE fajta = 'KONVENCIOKARTYA';
ALTER TABLE rendszer
  MODIFY fajta ENUM('ALAPRENDSZER','KONVENCIO','RENDSZER','GYUJTEMENY') NOT NULL;

-- 2. téma
ALTER TABLE rendszer
  ADD COLUMN tema VARCHAR(120) NULL
  COMMENT 'A konvenció témája; az azonos témájúak egymás alternatívái',
  ADD KEY ix_tema (tema);

-- 3. kizárás
ALTER TABLE licitmenet
  ADD COLUMN hivatkozas_mod ENUM('BE','KI') NOT NULL DEFAULT 'BE'
  COMMENT 'HIVATKOZAS: BE = beemelés, KI = kizárás a hivatkozó alatti fából'
  AFTER hivatkozas_aktiv,
  ADD COLUMN kizart_fejezet VARCHAR(120) NULL
  COMMENT 'KI esetén: csak ez a fejezet (NULL = az egész rendszer)'
  AFTER hivatkozas_mod;
