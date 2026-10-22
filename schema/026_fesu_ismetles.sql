-- =====================================================================
--  kibic — 026: a fésű felüllicitje csak EGYSZER (2026-10-04, Moha)
--
--  A fésű-felüllicit jelentése: „leállás VAGY gémforsz — a következő
--  licitem dönti el”. A partner erre kötelezően bemondja a jelzett színt;
--  a felüllicitező gyenge lappal passzol, minden más licitje gémforsz.
--  Eddig a 4.2 / 4.4 sor (a „vonalunk már mondta” változat) a partner
--  válasza után ÚJRA illeszkedett, és a kibic másodszor is felüllicitált
--  ugyanazzal az alerttel. Most a felüllicit-sorok csak akkor élnek, ha a
--  vonalunk az ellenfél színét még NEM mondta (nem licitáltunk benne).
--
--  Futtatás: bármikor (a 015 után); utána POST /v1/kibic/ujratolt vagy
--  újraindítás. Többször is futtatható.
-- =====================================================================
SET @fesu := (SELECT id FROM rendszer WHERE kod = 'FESU');

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V1"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@V1","ki":"mi"}]},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@I1","ki":"mi"}]}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, {V1} még gém alatt mondható, a vonalunk még nem mondta, és az ő {I1} színükben még nem licitáltunk'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_CUE_1_SAJAT';

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V1"},{"t":"MONDVA","szin":"@V1","ki":"mi"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@I1","ki":"mi"}]}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, {V1} még gém alatt mondható, a vonalunk már mondta, és az ő {I1} színükben még nem licitáltunk'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_CUE_1_FIT';

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V2"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@V2","ki":"mi"}]},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@I2","ki":"mi"}]}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, {V2} még gém alatt mondható, a vonalunk még nem mondta, és az ő {I2} színükben még nem licitáltunk'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_CUE_2_SAJAT';

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"GEM_ALATT","szin":"@V2"},{"t":"MONDVA","szin":"@V2","ki":"mi"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@I2","ki":"mi"}]}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, {V2} még gém alatt mondható, a vonalunk már mondta, és az ő {I2} színükben még nem licitáltunk'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_CUE_2_FIT';

SELECT kulcs, ha_feltetel_szoveg FROM licitmenet WHERE rendszer_id = @fesu AND kulcs LIKE 'FESU_CUE_%';
