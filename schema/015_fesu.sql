-- =====================================================================
--  kibic — 015: a FÉSŰ, az első valódi konvenció
--
--  MIÉRT EZ AZ ELSŐ: a fésű a legjobb próbája annak, elég-e a
--  mintanyelv. Nem egy licit jelentéséről szól, hanem egy LEKÉPEZÉSRŐL:
--
--     az ellenfél ismert színei, rangsorban:   I1 < I2
--     a mi szabad színeink, rangsorban:        V1 < V2
--     a megállapodás:                          I1 -> V1,  I2 -> V2
--
--  Két rendezett listát fésülünk össze. Innen a konvenció neve — és
--  ettől lett világos, mi hiányzott a mintanyelvből (0.4):
--
--    * INDEXELT SZÍNVÁLTOZÓK (I1/I2/V1/V2). Nem a minta köti meg őket,
--      hanem a KÉNYSZERTÁR: "amit az ellenfél ígért". Ha az ellenfél
--      licitje nem mutat konkrét színeket, a kötés elmarad, és a
--      szabály nem illeszkedik — ami helyes: fésűzni csak ismert
--      színek ellen lehet.
--    * `+` SZINTJELÖLÉS: "a legkisebb szabad licit ebben a színben".
--      Hogy a cue-bid 3C vagy 4C, az a licitállás dolga, nem a
--      szabályé.
--
--  E kettő nélkül a fésűt csak úgy lehetett volna leírni, hogy minden
--  kétszínű konvencióra (Michaels, Ghestem, Szokatlan 2NT) és minden
--  nyitószínre külön sort írunk — több tucat sor ugyanarról az EGY
--  gondolatról. Így hat sor elég.
--
--  FORRÁS: rendszerek/konvenciok/Fésű.docx és
--          rendszerek/konvenciok/KÜZDELMI & VÉDEKEZŐ licitek.doc
--
--  NYITOTT KÉRDÉS (szándékosan nincs kódolva, lásd a fájl végét):
--  a forrás szerint minor utáni Michaels-re NEM fésűzünk, hanem a
--  cue-bid fogást mutat. A "meddig él a fésű" feltétel jelenleg a
--  GEM_ALATT — ez a minor-esetet NEM zárja ki. A szabály addig
--  JAVASOLT állapotban marad.
--
--  Futtatás: a 014 után.
-- =====================================================================

USE kibic;

-- ---------------------------------------------------------------------
-- 1. A fésű paraméterei
-- ---------------------------------------------------------------------

INSERT IGNORE INTO parameter (kod, nev, ertekelo_id, alapertek,
                              min_ertek, max_ertek, csoport, leiras) VALUES
 ('FESU_SAJAT_HOSSZ', 'A fésűvel mutatott SAJÁT szín hossza',
  NULL, '5', 4, 6, 'kompetitiv',
  'Ha a mutatott szint meg senki nem mondta, ez sajat szin.'),
 ('FESU_FIT_HOSSZ', 'A fésűvel mutatott FIT hossza',
  NULL, '3', 3, 4, 'kompetitiv',
  'Ha a mutatott szint a partner mar mondta, ez tamogatas.'),
 ('FESU_GYENGE_MAX', 'A fésű gyenge ágának felső határa',
  (SELECT id FROM ertekelo WHERE kod='HCP'), '8', 5, 10, 'kompetitiv',
  'Leallas: ennel tobbel mar nem allunk meg.'),
 ('FESU_GF_MIN', 'A fésű gémforsz ágának alsó határa',
  (SELECT id FROM ertekelo WHERE kod='HCP'), '13', 11, 15, 'kompetitiv',
  'A ket ag kozott LYUK van - eppen ez a fesu lenyege: az invit sav a '
  'termeszetes licite.'),
 ('FESU_INVIT_MIN', 'A természetes (invit) licit alsó határa',
  (SELECT id FROM ertekelo WHERE kod='HCP'), '9', 7, 11, 'kompetitiv', NULL),
 ('FESU_INVIT_MAX', 'A természetes (invit) licit felső határa',
  (SELECT id FROM ertekelo WHERE kod='HCP'), '12', 10, 14, 'kompetitiv', NULL),
 ('BUNTETO_KAPU_MIN', 'A büntető kontra KAPUŐR alsó határa',
  (SELECT id FROM ertekelo WHERE kod='HCP'), '8', 5, 12, 'kompetitiv',
  'Nem kuszob, hanem szukseges feltetel: ez alatt szoba sem jon. A '
  'dontest a merlegelo hozza (motor/merlegel.py).'),
 ('FESU_ISMERT_HOSSZ', 'Hány lap számít "ígért" színnek',
  NULL, '5', 4, 5, 'kompetitiv',
  'Az I1/I2 kotes kuszobe: ennyi laptol tekintunk egy szint ismertnek.');

-- ---------------------------------------------------------------------
-- 2. A forrásdokumentumok
-- ---------------------------------------------------------------------

INSERT IGNORE INTO forras_dokumentum (kod, cim, formatum, eredeti_utvonal,
                                      megjegyzes) VALUES
 ('FESU_DOCX', 'Fésű', 'DOCX', 'rendszerek/konvenciok/Fésű.docx',
  'Ket resz: teljes fesu (mindket szin ismert) es felfesu (egy szin).'),
 ('KUZDELMI_DOC', 'KÜZDELMI & VÉDEKEZŐ licitek', 'DOC',
  'rendszerek/konvenciok/KÜZDELMI & VÉDEKEZŐ licitek.doc',
  'A fesu elvet tobb kulonbozo ketszinu konvencio utan is kimondja.');

-- ---------------------------------------------------------------------
-- 3. A konvenció
-- ---------------------------------------------------------------------

INSERT INTO rendszer (kod, nev, nev_en, fajta, csalad, leiras, leiras_en, verzio)
VALUES ('FESU', 'Fésű', 'Comb (Hungarian cue-bid scheme)', 'KONVENCIO',
        'EGYEB',
        'Az ellenfel ketszinu licitje utan: az ismert szinek felullicitjei '
        'a sajat szineket kodoljak RANGSORRENDBEN (I1->V1, I2->V2), '
        '"leallas vagy gemforsz" jelentessel; a termeszetes licit marad '
        'a pontos invitnek.',
        'After a two-suited overcall: cue-bids of the opponents known '
        'suits show our own suits IN RANK ORDER (lowest cue-bid = lowest '
        'suit), weak-or-game-forcing; natural bids are exactly invitational.',
        '0.1')
ON DUPLICATE KEY UPDATE
  nev = VALUES(nev), nev_en = VALUES(nev_en),
  leiras = VALUES(leiras), leiras_en = VALUES(leiras_en);

INSERT IGNORE INTO rendszer_dokumentum (rendszer_id, dokumentum_id, megjegyzes)
SELECT r.id, d.id, 'Elsodleges forras'
  FROM rendszer r, forras_dokumentum d
 WHERE r.kod = 'FESU' AND d.kod IN ('FESU_DOCX', 'KUZDELMI_DOC');

-- ---------------------------------------------------------------------
-- 4. A szabályok
-- ---------------------------------------------------------------------
--  Hat sor. Kettő a cue-bidekre (saját szín / fit szerint kettéválva),
--  kettő a természetes licitekre, egy a büntető kontrára, egy a passzra.
--
--  A `feltetel` a KÉZRŐL szól, a `ha_feltetel` a HELYZETRŐL. A
--  `@V1`/`@V2` hivatkozás mindkettőben ugyanazt a színt jelenti — a
--  mintaillesztés köti meg, a kényszertárból.
-- ---------------------------------------------------------------------

SET @fesu := (SELECT id FROM rendszer WHERE kod = 'FESU');
SET @dok  := (SELECT id FROM forras_dokumentum WHERE kod = 'FESU_DOCX');

DELETE FROM licitmenet WHERE rendszer_id = @fesu;

-- 4.1 Cue-bid az ALACSONYABB ismert színre: a V1 szín, SAJÁT hosszként
INSERT INTO licitmenet
  (rendszer_id, fejezet, alfejezet, seq, tipus, minta, kulcs,
   prioritas, feltetel, feltetel_szoveg, ha_feltetel, ha_feltetel_szoveg,
   jelentes, magyarazat, magyarazat_en, alert, forsz, elvaras,
   dokumentum_id, nyers_szoveg, allapot, megbizhatosag)
VALUES
 (@fesu, 'Teljes fésű', 'Cue-bid', 10, 'SZABALY', '.. (*) +I1', 'FESU_CUE_1_SAJAT',
  20,
  '{"t":"ES","gy":[{"t":"OSSZE","op":">=","bal":{"t":"SZIN","szin":"@V1"},"jobb":{"t":"PARAM","kod":"FESU_SAJAT_HOSSZ"}},{"t":"VAGY","gy":[{"t":"OSSZE","op":"<=","bal":{"t":"ERT","kod":"HCP"},"jobb":{"t":"PARAM","kod":"FESU_GYENGE_MAX"}},{"t":"OSSZE","op":">=","bal":{"t":"ERT","kod":"HCP"},"jobb":{"t":"PARAM","kod":"FESU_GF_MIN"}}]}]}',
  '{V1} hossz >= {FESU_SAJAT_HOSSZ} és (figurapont <= {FESU_GYENGE_MAX} vagy figurapont >= {FESU_GF_MIN})',
  '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V1"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@V1","ki":"mi"}]}]}',
  'mindkét színük ismert, {V1} még gém alatt mondható és a vonalunk még nem mondta',
  '{"hossz":{"@V1":{"min":"FESU_SAJAT_HOSSZ"}},"vagy":[{"pont":{"max":"FESU_GYENGE_MAX"}},{"pont":{"min":"FESU_GF_MIN"}}]}',
  'Fésű: az alacsonyabb ismert szín felüllicitje a mi alacsonyabb szabad színünket mutatja. Leállás VAGY gémforsz — a következő licitem dönti el.',
  'Comb: cue-bid of their lower suit shows our lower free suit. Weak (to play) or game-forcing.',
  1, 'EGY_MENET', 'DONTS', @dok,
  '3 treff: gyenge vagy GF kőrrel', 'JAVASOLT', 85),

-- 4.2 Ugyanez, ha a V1 színt a partner MÁR MONDTA: akkor fit, nem saját szín
 (@fesu, 'Teljes fésű', 'Cue-bid', 20, 'SZABALY', '.. (*) +I1', 'FESU_CUE_1_FIT',
  20,
  '{"t":"ES","gy":[{"t":"OSSZE","op":">=","bal":{"t":"SZIN","szin":"@V1"},"jobb":{"t":"PARAM","kod":"FESU_FIT_HOSSZ"}},{"t":"VAGY","gy":[{"t":"OSSZE","op":"<=","bal":{"t":"ERT","kod":"HCP"},"jobb":{"t":"PARAM","kod":"FESU_GYENGE_MAX"}},{"t":"OSSZE","op":">=","bal":{"t":"ERT","kod":"HCP"},"jobb":{"t":"PARAM","kod":"FESU_GF_MIN"}}]}]}',
  '{V1} hossz >= {FESU_FIT_HOSSZ} és (figurapont <= {FESU_GYENGE_MAX} vagy figurapont >= {FESU_GF_MIN})',
  '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V1"},{"t":"MONDVA","szin":"@V1","ki":"mi"}]}',
  'mindkét színük ismert, {V1} még gém alatt mondható és a vonalunk már mondta',
  '{"hossz":{"@V1":{"min":"FESU_FIT_HOSSZ"}},"vagy":[{"pont":{"max":"FESU_GYENGE_MAX"}},{"pont":{"min":"FESU_GF_MIN"}}]}',
  'Fésű: az alacsonyabb ismert szín felüllicitje a partner színének támogatása. Leállás VAGY gémforsz.',
  'Comb: cue-bid of their lower suit raises partner''s suit. Weak or game-forcing.',
  1, 'EGY_MENET', 'DONTS', @dok,
  '3 káró: gyenge vagy GF pikkel', 'JAVASOLT', 85),

-- 4.3-4.4 A MAGASABB ismert színre ugyanez, V2-vel
 (@fesu, 'Teljes fésű', 'Cue-bid', 30, 'SZABALY', '.. (*) +I2', 'FESU_CUE_2_SAJAT',
  20,
  '{"t":"ES","gy":[{"t":"OSSZE","op":">=","bal":{"t":"SZIN","szin":"@V2"},"jobb":{"t":"PARAM","kod":"FESU_SAJAT_HOSSZ"}},{"t":"VAGY","gy":[{"t":"OSSZE","op":"<=","bal":{"t":"ERT","kod":"HCP"},"jobb":{"t":"PARAM","kod":"FESU_GYENGE_MAX"}},{"t":"OSSZE","op":">=","bal":{"t":"ERT","kod":"HCP"},"jobb":{"t":"PARAM","kod":"FESU_GF_MIN"}}]}]}',
  '{V2} hossz >= {FESU_SAJAT_HOSSZ} és (figurapont <= {FESU_GYENGE_MAX} vagy figurapont >= {FESU_GF_MIN})',
  '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V2"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@V2","ki":"mi"}]}]}',
  'mindkét színük ismert, {V2} még gém alatt mondható és a vonalunk még nem mondta',
  '{"hossz":{"@V2":{"min":"FESU_SAJAT_HOSSZ"}},"vagy":[{"pont":{"max":"FESU_GYENGE_MAX"}},{"pont":{"min":"FESU_GF_MIN"}}]}',
  'Fésű: a magasabb ismert szín felüllicitje a mi magasabb szabad színünket mutatja. Leállás VAGY gémforsz.',
  'Comb: cue-bid of their higher suit shows our higher free suit. Weak or game-forcing.',
  1, 'EGY_MENET', 'DONTS', @dok,
  'A továbbiakban alacsonyabb felüllicit, alacsonyabb rangú színt jelent',
  'JAVASOLT', 85),

 (@fesu, 'Teljes fésű', 'Cue-bid', 40, 'SZABALY', '.. (*) +I2', 'FESU_CUE_2_FIT',
  20,
  '{"t":"ES","gy":[{"t":"OSSZE","op":">=","bal":{"t":"SZIN","szin":"@V2"},"jobb":{"t":"PARAM","kod":"FESU_FIT_HOSSZ"}},{"t":"VAGY","gy":[{"t":"OSSZE","op":"<=","bal":{"t":"ERT","kod":"HCP"},"jobb":{"t":"PARAM","kod":"FESU_GYENGE_MAX"}},{"t":"OSSZE","op":">=","bal":{"t":"ERT","kod":"HCP"},"jobb":{"t":"PARAM","kod":"FESU_GF_MIN"}}]}]}',
  '{V2} hossz >= {FESU_FIT_HOSSZ} és (figurapont <= {FESU_GYENGE_MAX} vagy figurapont >= {FESU_GF_MIN})',
  '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V2"},{"t":"MONDVA","szin":"@V2","ki":"mi"}]}',
  'mindkét színük ismert, {V2} még gém alatt mondható és a vonalunk már mondta',
  '{"hossz":{"@V2":{"min":"FESU_FIT_HOSSZ"}},"vagy":[{"pont":{"max":"FESU_GYENGE_MAX"}},{"pont":{"min":"FESU_GF_MIN"}}]}',
  'Fésű: a magasabb ismert szín felüllicitje a partner színének támogatása. Leállás VAGY gémforsz.',
  'Comb: cue-bid of their higher suit raises partner''s suit. Weak or game-forcing.',
  1, 'EGY_MENET', 'DONTS', @dok,
  '3 káró: gyenge vagy GF pikkel', 'JAVASOLT', 85),

-- 4.5 A TERMÉSZETES licit: pontosan invit.
--     Ez a fésű másik fele. A cue-bid azért lehet kétértelmű ("gyenge
--     vagy GF"), mert a köztes sávnak MEGVAN a maga licitje: a szín
--     természetes megmondása. Ezért nem baj, hogy a kényszertárban a
--     cue-bid pontsávja lyukas — a lyukat ez a szabály tölti ki.
 (@fesu, 'Teljes fésű', 'Természetes', 50, 'SZABALY', '.. (*) +V1',
  'FESU_NAT_1', 10,
  '{"t":"ES","gy":[{"t":"INTERV","kif":{"t":"ERT","kod":"HCP"},"min":{"t":"PARAM","kod":"FESU_INVIT_MIN"},"max":{"t":"PARAM","kod":"FESU_INVIT_MAX"}}]}',
  'figurapont {FESU_INVIT_MIN}-{FESU_INVIT_MAX} között',
  '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V1"}]}',
  'mindkét színük ismert, {V1} még gém alatt mondható',
  '{"pont":{"min":"FESU_INVIT_MIN","max":"FESU_INVIT_MAX"},"hossz":{"@V1":{"min":"FESU_FIT_HOSSZ"}}}',
  'Természetes, PONTOSAN invit. A gyenge és a gémforsz kéz a fésű-felüllicitre megy.',
  'Natural, EXACTLY invitational. Weak and game-forcing hands use the cue-bid.',
  1, 'NEM', 'DONTS', @dok, '3 kőr: természetes GI', 'JAVASOLT', 85),

 (@fesu, 'Teljes fésű', 'Természetes', 60, 'SZABALY', '.. (*) +V2',
  'FESU_NAT_2', 10,
  '{"t":"ES","gy":[{"t":"INTERV","kif":{"t":"ERT","kod":"HCP"},"min":{"t":"PARAM","kod":"FESU_INVIT_MIN"},"max":{"t":"PARAM","kod":"FESU_INVIT_MAX"}}]}',
  'figurapont {FESU_INVIT_MIN}-{FESU_INVIT_MAX} között',
  '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V2"}]}',
  'mindkét színük ismert, {V2} még gém alatt mondható',
  '{"pont":{"min":"FESU_INVIT_MIN","max":"FESU_INVIT_MAX"},"hossz":{"@V2":{"min":"FESU_FIT_HOSSZ"}}}',
  'Természetes, PONTOSAN invit.',
  'Natural, EXACTLY invitational.',
  1, 'NEM', 'DONTS', @dok, '3 pikk: természetes GI', 'JAVASOLT', 85),

-- 4.6 BÜNTETŐ KONTRA — és itt ér véget az, amit szabállyal le lehet írni.
--
--     A forrás úgy fogalmaz: "legalább az egyik minort önállóan meg
--     tudja büntetni". Ez így nem jó megfogalmazás, és nem is
--     algoritmizálható küszöbbel. Pontosabban:
--
--         "biztosan elbukik, ÉS nekem ehhez megfelelő adum van"
--
--     A bukás ugyanis nem az aduból jön, hanem a PÁR KÖZÖS erejéből; az
--     adu csak az eszköz hozzá. A valódi kérdés pedig még tágabb: megéri-e
--     jobban a kontrázott bukás írása, mint a saját kontraktusunké? Erre
--     négy dolog hat egyszerre, és egyik sem fér egy küszöbbe:
--       * a vonalunkon jelentős erő van (gémközelben vagyunk);
--       * nincs megfelelő színtalálkozásunk, ezért a gém bizonytalan;
--       * van erőm a színükben, de a szan mégsem jó (átmenetek, elosztás);
--       * a bukás lehet, hogy nem éri el a gém értékét — de ennek
--         valószínűsége az erőnkkel arányos.
--
--     Ezért ez a sor NEM DÖNT. A `dontesi_mod='MERLEGELO'` azt mondja ki,
--     hogy a szabály dolga csak annyi: beengedni a kontrát a mérlegelésbe.
--     Az összemérést a motor/merlegel.py végzi, a kényszertárból vett
--     mintán, DDS-sel és pontozással — IMP-ben és MP-ben külön, mert a
--     két versenyformában más lehet a helyes döntés.
--
--     A `feltetel` így SZÜKSÉGES, de nem elégséges feltétel: "megfelelő
--     adum van". A `ha_feltetel` pedig azt zárja ki, ami nyilvánvalóan
--     nem büntetési helyzet.
 (@fesu, 'Teljes fésű', 'Kontra', 70, 'SZABALY', '.. (*) X', 'FESU_X', 30,
  '{"t":"ES","gy":[{"t":"OSSZE","op":">=","bal":{"t":"ERT","kod":"HCP"},"jobb":{"t":"PARAM","kod":"BUNTETO_KAPU_MIN"}},{"t":"VAGY","gy":[{"t":"OSSZE","op":">=","bal":{"t":"SZIN","szin":"@I1"},"jobb":{"t":"PARAM","kod":"BUNTETO_ADU"}},{"t":"OSSZE","op":">=","bal":{"t":"SZIN","szin":"@I2"},"jobb":{"t":"PARAM","kod":"BUNTETO_ADU"}}]}]}',
  'KAPUŐR: figurapont >= {BUNTETO_KAPU_MIN} és az egyik ismert színükben {BUNTETO_ADU}+ lap (szükséges, de nem elégséges — a döntés a mérlegelőé)',
  '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"NYILATKOZOTT","ki":"p"},{"t":"NEM","gy":[{"t":"FIT","szin":"@V1","min":8}]},{"t":"NEM","gy":[{"t":"FIT","szin":"@V2","min":8}]}]}',
  'mindkét színük ismert, a partner már nyilatkozott, és nincs ismert 8+ fitünk',
  '{"pont":{"min":"BUNTETO_KAPU_MIN"}}',
  'Büntető. Elbukik, és megvan hozzá az adum — de hogy megéri-e a saját kontraktusunknál jobban, azt a leosztás mérlegelése dönti el.',
  'Penalty. It should go down and I hold the trumps for it — whether it beats our own contract is decided by simulation, not by a rule.',
  1, 'NEM', 'DONTS', @dok,
  'kontra: büntető (legalább az egyik minort önállóan meg tudja büntetni és a másik minorban min. dubló figura/három kis lap)',
  'JAVASOLT', 85);

UPDATE licitmenet SET dontesi_mod = 'MERLEGELO'
 WHERE rendszer_id = @fesu AND kulcs = 'FESU_X';

-- ---------------------------------------------------------------------
-- 5. Ellenőrzés
-- ---------------------------------------------------------------------

SELECT lm.seq, lm.alfejezet, lm.minta, lm.kulcs, lm.elvaras, lm.forsz,
       lm.allapot, lm.megbizhatosag,
       lm.feltetel_szoveg, lm.ha_feltetel_szoveg
  FROM licitmenet lm
  JOIN rendszer r ON r.id = lm.rendszer_id
 WHERE r.kod = 'FESU'
 ORDER BY lm.seq;

-- A paraméterek egy helyen:
SELECT kod, nev, alapertek, min_ertek, max_ertek
  FROM parameter WHERE csoport = 'kompetitiv' ORDER BY kod;

-- =====================================================================
--  MIÉRT MARAD MINDEN SOR `JAVASOLT` ÁLLAPOTBAN
--
--  A motor kizárólag ELFOGADOTT sorokat használ. A fésű addig nem
--  léphet élesbe, amíg két kérdés nyitva van:
--
--  1. MEDDIG ÉL A FÉSŰ? A `ha_feltetel` most a GEM_ALATT — "ameddig a
--     szín gém alatt belicitálható". Ez a nemes színekre jól működik
--     (1S-(2NT): 3C/3D cue-bid, a nemes gém a 4. szinten). De a forrás
--     szerint MINOR utáni Michaels-re NEM fésűzünk, hanem a cue-bid
--     fogást mutat — pedig ott is gém alatt volnánk. A GEM_ALATT tehát
--     szükséges, de nem elégséges feltétel.
--
--  2. (MEGVÁLASZOLVA.) Az "önállóan meg tudja büntetni" nem küszöb
--     kérdése volt, hanem rossz kérdésfeltevés: a szabály és a döntés
--     összekeverése. A 4.6 sor ezért `MERLEGELO` lett — a feltétele
--     szükséges, de nem elégséges, és az összemérést a szimuláció
--     végzi. Az 1. kérdés viszont nyitva marad.
--
--  Ez bridzsszakmai döntés, nem technikai. A séma úgy van megcsinálva,
--  hogy a válasz EGY paraméter-sor vagy EGY ha_feltetel átírása legyen —
--  nem kódváltás.
-- =====================================================================
