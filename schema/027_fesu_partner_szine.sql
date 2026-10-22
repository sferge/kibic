-- =====================================================================
--  kibic — 027: fésű csak akkor, ha a partner már licitált (2026-10-04, Moha)
--
--  „A valóságos fésű helyzet akkor van, ha a partner már licitált: legalább
--  egy TUDOTTAN saját színünk van.” Eddig elég volt, hogy az ellenfél két
--  színét ismerjük — így 1♠ (P) 2♦ után a 2♥ a fésű „pontosan invit”
--  természetes sora lett (a partner passzolt!), és a kibic újra és újra
--  „fésűzött”. Most a fésű felüllicit- és természetes sorai csak akkor
--  élnek, ha a partner legalább egy színre 4+ lapot ígért.
--
--  A 026 feltételét (a felüllicit csak egyszer) is tartalmazza, ezért a 026
--  nélkül is futtatható. Futtatás után: POST /v1/kibic/ujratolt.
-- =====================================================================
SET @fesu := (SELECT id FROM rendszer WHERE kod = 'FESU');

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"ISMERT_SZINEK","ki":"p","db":1,"op":">="},{"t":"GEM_ALATT","szin":"@V1"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@V1","ki":"mi"}]},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@I1","ki":"mi"}]}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, a partner már mutatott színt, {V1} még gém alatt mondható, a vonalunk még nem mondta, és az ő {I1} színükben még nem licitáltunk'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_CUE_1_SAJAT';

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"ISMERT_SZINEK","ki":"p","db":1,"op":">="},{"t":"GEM_ALATT","szin":"@V1"},{"t":"MONDVA","szin":"@V1","ki":"mi"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@I1","ki":"mi"}]}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, a partner már mutatott színt, {V1} még gém alatt mondható, a vonalunk már mondta, és az ő {I1} színükben még nem licitáltunk'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_CUE_1_FIT';

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"ISMERT_SZINEK","ki":"p","db":1,"op":">="},{"t":"GEM_ALATT","szin":"@V2"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@V2","ki":"mi"}]},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@I2","ki":"mi"}]}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, a partner már mutatott színt, {V2} még gém alatt mondható, a vonalunk még nem mondta, és az ő {I2} színükben még nem licitáltunk'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_CUE_2_SAJAT';

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"ISMERT_SZINEK","ki":"p","db":1,"op":">="},{"t":"GEM_ALATT","szin":"@V2"},{"t":"MONDVA","szin":"@V2","ki":"mi"},{"t":"NEM","gy":[{"t":"MONDVA","szin":"@I2","ki":"mi"}]}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, a partner már mutatott színt, {V2} még gém alatt mondható, a vonalunk már mondta, és az ő {I2} színükben még nem licitáltunk'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_CUE_2_FIT';

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"ISMERT_SZINEK","ki":"p","db":1,"op":">="},{"t":"GEM_ALATT","szin":"@V1"}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, a partner már mutatott színt, {V1} még gém alatt mondható'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_NAT_1';

UPDATE licitmenet SET
  ha_feltetel = '{"t":"ES","gy":[{"t":"ISMERT_SZINEK","ki":"ok","db":2},{"t":"ISMERT_SZINEK","ki":"p","db":1,"op":">="},{"t":"GEM_ALATT","szin":"@V2"}]}',
  ha_feltetel_szoveg = 'mindkét színük ismert, a partner már mutatott színt, {V2} még gém alatt mondható'
WHERE rendszer_id = @fesu AND kulcs = 'FESU_NAT_2';

SELECT kulcs, ha_feltetel_szoveg FROM licitmenet WHERE rendszer_id = @fesu ORDER BY seq;
