# A kibic beállításai (környezeti változók) — 2026-10-25

Ezek a **kibic** folyamat beállításai. Két helyen hatnak:

- **a szolgáltatásban** (uvicorn, amit az MB hív): induláskor olvassa be — változtatás után **újraindítás** kell;
- **a mérőeszközökben** (`jatekmeres`, `inditaselemzes` …): abban a shellben kell megadni, ahonnan indítod
  (pl. `KIBIC_ALFAMU=1 PYTHONPATH=src python -m kibic.cli.jatekmeres …`). A szolgáltatás beállításai a mérést nem érintik, és fordítva.

Megadás: shellből `export NEV=érték`; fájlból (systemd `EnvironmentFile=`, Docker `env_file`, dotenv) `NEV=érték`, `export` nélkül.

## Kapcsolat, rendszer, titok

| Változó | Alap | Mire |
|---|---|---|
| `KIBIC_SHARED_SECRET` | – | a kibic titka; = az MB `AI_SHARED_SECRET`-je |
| `KIBIC_AI_SHARED_SECRET` | – | külön titok csak az AI-végpontokra (üresen a fenti) |
| `KIBIC_HOST`, `KIBIC_USER`, `KIBIC_PASS`, `KIBIC_DB` | localhost, kibic, –, kibic | az adatbázis |
| `KIBIC_RENDSZER` | LICREN_STAND | az alaprendszer (`default_system`) |
| `KIBIC_PAR` | – | alapértelmezett pár-paraméterek |
| `KIBIC_PROFILOK` | – | profilkód → rendszer: `kod=RENDSZER:pár;…` |
| `KIBIC_TESZT_MOD` | ki | `1`: a JAVASOLT szabályok is élnek |

## Naplók

| Változó | Alap | Mire |
|---|---|---|
| `KIBIC_ATJARO_NAPLO` | – | az átjáró JSONL-naplója (útvonal) |
| `KIBIC_ATJARO_NAPLO_KERES` | ki | `1`: a teljes kérés is (a kezek!) — a visszajátszáshoz, méréshez |
| `KIBIC_KIOSZTAS_NAPLO` | – | a kiosztástervező naplója |

## Licit

| Változó | Alap | Mire |
|---|---|---|
| `KIBIC_ATJARO_SZIMULACIO` | 1 | mérlegelő helyzetekben DD-szimuláció |
| `KIBIC_ATJARO_SZIM_MS` | 10000 | a szimuláció időkerete licitdöntésenként |
| `KIBIC_ATJARO_SZIM_TARTALEK_MS` | 1500 | a határidőből ennyi marad a licit többi részére |
| `KIBIC_SZIM_MS` | 10000 | a /v1/kibic/licit szimulációs kerete |
| `KIBIC_SZIM_MIN_MINTA` | 12 | legalább ennyi kiszámolt minta a szimulációs döntéshez |
| `KIBIC_KOVETKEZTETES_MS` | 800 | a kizárásos következtetés licitdöntésenként (a `bid`-nél legfeljebb a határidő negyede) |
| `KIBIC_KOVETKEZTETES_MINTA` | 120 | a kizárásos következtetés mintaszáma |
| `KIBIC_MUHELY_KOVETKEZTETES_MS` | 3000 | ugyanez a tanári részletnél (`/v1/kibic/magyaraz`) |
| `KIBIC_INFO_KERES` | 1 | `0`: nem kér magyarázatot licitdöntés közben |
| `KIBIC_ARNYEK` | – | árnyék mód (új döntéshozó / másik rendszer próbája élesben) |

## Lejátszás

| Változó | Alap | Mire |
|---|---|---|
| `KIBIC_LEJATSZAS_MS` | 10000 | időkeret lapdöntésenként (legfeljebb a `deadline_ms` 40%-a) |
| `KIBIC_LEJATSZAS_MINTA` | 3000 | legfeljebb ennyi minta (a döntés biztossága szerint áll meg) |
| `KIBIC_LEJATSZAS_MIN_MINTA` | 60 | legalább ennyi minta, mielőtt biztosnak veszi |
| `KIBIC_LEJATSZAS_KOVETKEZTETES_MS` | 15000 | a licit kizárásos következtetése a lejátszásban (leosztásonként egyszer; legfeljebb a határidő 30%-a) |
| `KIBIC_LEJATSZAS_KIS_LAP` | 8 | kimerítő elemzésben ennél nem nagyobb rejtett lapok egyenértékűek (`0`: ki) |
| `KIBIC_LEJATSZAS_MINTAZAT_HATAR` | 5000 | ennyi mintázatig a teljes sokaságot nézi |
| `KIBIC_LICIT_LAZA` | 0.15 | puha licitkorlát: a minta legfeljebb ekkora része jöhet a licitnek nem megfelelő kezekből (`0`: kemény korlát) |
| `KIBIC_VALASZTAS_KORLAT` | 1 | korlátozott választás (restricted choice) a mintában (`0`: ki) |
| `KIBIC_ALFAMU` | 0 | `1`: „ugyanaz a lap minden világban” előrelátás a felvevőnek (kísérleti) |
| `KIBIC_ALFAMU_VILAG` | 40 | az előrelátás világszáma (120 ajánlott, ha be van kapcsolva) |
| `KIBIC_KOVETKEZTETES_SULY` | – | a jelzésrendszer következtetés-sorainak súly-felülírása (hangoláshoz), pl. `FELVETEL_HIHETO=0.4` |
| `KIBIC_GONDOLKODAS_MS` | 1500-3000 | a kijátszás legrövidebb válaszideje (kényszerű lapnál se azonnal); `0`: ki |
| `KIBIC_TERITES` | 1 | a felvevő terítést ajánl (`meta.kibic.claim`) |
| `KIBIC_CLAIM_MS` | 20000 | a terítés elbírálásának időkerete (legfeljebb a határidő fele) |

## Összhang az MB-vel

Az MB (az „AI gateway” kliense) minden kérésben megküldi a határidőt (`deadline_ms`, a tesztasztalon 60 000).
A kibic minden időkeretét ehhez igazítja, ezért **a két oldalon csak ennyi kell**:

- **Titok:** `KIBIC_SHARED_SECRET` = MB `AI_SHARED_SECRET`.
- **Határidő:** az MB `AI_PLAY_TIMEOUT_MS` / `AI_CLAIM_TIMEOUT_MS` (ezt küldi `deadline_ms`-ként). A kibic lapdöntése legfeljebb a `deadline_ms` 40%-a + a licit-következtetés (első döntésnél, legfeljebb 30%) — 60 s-nél bőven belefér. Ha az MB-n a határidőt 20 s alá veszed, a kibic gondolkodása arányosan rövidül.
- **Az MB kapcsolói** (nem kibic-beállítás): „AI játékos teríthet”, „AI játékos elbírálhatja a terítést”, tanári asztal / tesztmód.
- **Tanári asztal:** az MB minden döntéshez tanári részletet kér (`/v1/kibic/magyaraz`); ezt a `KIBIC_MUHELY_KOVETKEZTETES_MS` fogja rövidre.

Ellenőrzés: a kibic naplójában (`KIBIC_ATJARO_NAPLO`) minden válasznál ott az `elapsed_ms` és a `deadline_ms`.
