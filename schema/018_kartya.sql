-- kibic — 018: a konvenciókártya szöveges adatai a rendszerhez
--
-- A kártya NAGY része a szabályokból generálódik (nyitások, válaszok,
-- közbeszólások...). Ami NINCS a licitszabályokban — indulások, jelzések,
-- általános stílus, kényszerítő passzok, pszichik —, az ide kerül, a
-- YAML `kartya:` blokkjából (rendszerimport). JSON, mert a szerkezete a
-- WBF-kártya fejezeteit követi, és bővülhet.
ALTER TABLE rendszer
  ADD COLUMN kartya JSON NULL
  COMMENT 'Konvenciókártya-adatok, amik nem a licitszabályokból jönnek (YAML kartya: blokk)';
