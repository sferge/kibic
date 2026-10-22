-- =====================================================================
--  kibic — 023: LAPMINŐSÉG (Moha-kör, 2026-09-29)
--
--  A "jó 10" / "rossz 11" / "jó 12" ponthatárokhoz: mennyire ér a pont
--  annyit, amennyit számol. LAPMINOSEG = jó jelek − rossz jelek;
--  JÓ lap >= 2, ROSSZ lap <= -2 (a YAML-ban: `minoseg: jo | rossz`).
--  Két segédmetrikával (LM_*). A LAP_SULY tag új `min_hossz`/`max_hossz`
--  szűkítését használja (kód: domain/ertekelo.py).
-- =====================================================================

USE kibic;

INSERT INTO ertekelo (kod, nev, leiras, kontextus, definicio) VALUES
  ('LM_ROVID_TOBBLET', 'Lapminőség segéd: rövid színek pontja − hosszú színek pontja', 'Figurapont a legfeljebb 3 lapos színekben mínusz a 4+ lapos színekben. Pozitív: a pontok többsége rövid színben.', 'EGYEB',
   '{"tagok": [{"tipus": "LAP_SULY", "sulyok": {"A": 4, "K": 3, "Q": 2, "J": 1}, "max_hossz": 3}, {"tipus": "LAP_SULY", "sulyok": {"A": 4, "K": 3, "Q": 2, "J": 1}, "min_hossz": 4, "egyutthato": -1}]}'),
  ('LM_ASZ_ES_KIRALY', 'Lapminőség segéd: van ász ÉS király', '2, ha van ász és király is.', 'EGYEB',
   '{"tagok": [{"tipus": "FELTETEL", "bal": {"tipus": "LAP_SULY", "sulyok": {"A": 1}}, "op": ">=", "jobb": 1, "egyutthato": 1}, {"tipus": "FELTETEL", "bal": {"tipus": "LAP_SULY", "sulyok": {"K": 1}}, "op": ">=", "jobb": 1, "egyutthato": 1}]}'),
  ('LAPMINOSEG', 'Lapminőség (Moha)', 'Jó jelek száma mínusz rossz jelek száma. JÓ lap: >= 2, ROSSZ lap: <= -2. Rossz: nincs ász; 4-3-3-3; a pontok fele dáma-bubi; a pontok többsége rövid színben; nincs 10-es/9-es; elszórt figurák (két rövid színben magányos K/D/B ász nélkül, pl. Kxx és Dx). Jó: ász és király is; nincs bubi; két figura (A/K/D) együtt egy 4+ lapos színben (pl. KDxx); a pontok többsége hosszú színben; 5+ lapos szín; legalább két 10-es/9-es.', 'ABSZOLUT',
   '{"tagok": [{"tipus": "FELTETEL", "bal": {"tipus": "LAP_SULY", "sulyok": {"A": 1}}, "op": "<=", "jobb": 0, "egyutthato": -1}, {"tipus": "FELTETEL", "bal": {"tipus": "RENDEZETT_HOSSZ", "rang": 4}, "op": ">=", "jobb": 3, "egyutthato": -1}, {"tipus": "FELTETEL", "bal": {"tipus": "LAP_SULY", "sulyok": {"A": -4, "K": -3, "Q": 2, "J": 1}}, "op": ">=", "jobb": 0, "egyutthato": -1}, {"tipus": "FELTETEL", "bal": {"tipus": "ERTEKELO", "kod": "LM_ROVID_TOBBLET"}, "op": ">", "jobb": 0, "egyutthato": -1}, {"tipus": "FELTETEL", "bal": {"tipus": "LAP_SULY", "sulyok": {"T": 1, "9": 1}}, "op": "<=", "jobb": 0, "egyutthato": -1}, {"tipus": "FELTETEL", "bal": {"tipus": "SZIN_MINTA", "szabalyok": [{"max_hossz": 3, "tart": ["A"], "ertek": 0}, {"max_hossz": 3, "tart": ["K"], "nincs": ["Q", "J"], "ertek": 1}, {"max_hossz": 3, "tart": ["Q"], "nincs": ["K", "J"], "ertek": 1}, {"max_hossz": 3, "tart": ["J"], "nincs": ["K", "Q"], "ertek": 1}]}, "op": ">=", "jobb": 2, "egyutthato": -1}, {"tipus": "FELTETEL", "bal": {"tipus": "ERTEKELO", "kod": "LM_ASZ_ES_KIRALY"}, "op": ">=", "jobb": 2, "egyutthato": 1}, {"tipus": "FELTETEL", "bal": {"tipus": "LAP_SULY", "sulyok": {"J": 1}}, "op": "<=", "jobb": 0, "egyutthato": 1}, {"tipus": "FELTETEL", "bal": {"tipus": "SZIN_MINTA", "szabalyok": [{"min_hossz": 4, "tart": ["A", "K"], "ertek": 1}, {"min_hossz": 4, "tart": ["A", "Q"], "ertek": 1}, {"min_hossz": 4, "tart": ["K", "Q"], "ertek": 1}]}, "op": ">=", "jobb": 1, "egyutthato": 1}, {"tipus": "FELTETEL", "bal": {"tipus": "ERTEKELO", "kod": "LM_ROVID_TOBBLET"}, "op": "<", "jobb": 0, "egyutthato": 1}, {"tipus": "FELTETEL", "bal": {"tipus": "RENDEZETT_HOSSZ", "rang": 1}, "op": ">=", "jobb": 5, "egyutthato": 1}, {"tipus": "FELTETEL", "bal": {"tipus": "LAP_SULY", "sulyok": {"T": 1, "9": 1}}, "op": ">=", "jobb": 2, "egyutthato": 1}]}')
ON DUPLICATE KEY UPDATE
  nev = VALUES(nev), leiras = VALUES(leiras), kontextus = VALUES(kontextus),
  definicio = VALUES(definicio);

SELECT kod, nev FROM ertekelo WHERE kod IN ('LAPMINOSEG','LM_ROVID_TOBBLET','LM_ASZ_ES_KIRALY');
