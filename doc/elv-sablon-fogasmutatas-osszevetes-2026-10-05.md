# FOGASMUTATAS elv-sablon — összevetés a régi (soronkénti) MOHA_STAND-dal

Célzott készlet: 30 000 generált leosztásból azok, ahol a licit 1M–2m–2M-mel indult (É oszt; 2732 döntéspont). A régi rendszer (MOHA_STAND) döntéseit rögzítettük, majd ugyanezekben a helyzetekben (ugyanazzal a menet-előtaggal) a MOHA_STAND_ELV döntött. **49 eltérés** — csoportosítva. (`adat/arany/elteres-2026-10-05-fogasmutatas-elv.jsonl`)

A teljes, általános aranykészleten (300 leosztás, 2887 pont) a MOHA_STAND_ELV 3 helyen tér el a rögzített MOHA_STAND-tól: egy lassú emelés (mint A), egy a régi 2NT után (mint D), és egy a hézag-elv közös javítása, ami a MOHA_STAND-ban is megvan: 1♦–1♥–3♣–3♠ (negyedik szín, pikkfogást kér) után ♠2 ♥K62 ♦AQ963 ♣AK75 lappal nem 3NT, hanem 4♥ (`adat/arany/elteres-2026-10-05-hamis-fogas.jsonl`).

## A. A válaszoló 3 lapos támogatással, erővel: a régi KIBICEGY 2NT („lapleírást kér”) helyett lassú emelés (gyors-lassú elv) — 11 eset

| Menet | Lap (FP) | Régi | Új (elv) |
|---|---|---|---|
| 1♠ – 2♣ – 2♠ – ? | ♠J87 ♥AK72 ♦A108 ♣QJ7 (15) | 2NT | **3♠** |
| 1♠ – 2♣ – 2♠ – ? | ♠AK4 ♥Q1064 ♦A2 ♣Q864 (15) | 2NT | **3♠** |
| 1♥ – 2♣ – 2♥ – ? | ♠A10 ♥Q54 ♦AKJ8 ♣Q972 (16) | 2NT | **3♥** |
| 1♠ – 2♣ – 2♠ – ? | ♠AQ9 ♥1063 ♦AJ108 ♣KJ4 (15) | 2NT | **3♠** |
| 1♠ – 2♣ – 2♠ – ? | ♠A92 ♥AK43 ♦A1042 ♣QJ (18) | 2NT | **3♠** |
| 1♠ – 2♣ – 2♠ – ? | ♠A42 ♥K97 ♦AK86 ♣Q102 (16) | 2NT | **3♠** |
| 1♠ – 2♣ – 2♠ – ? | ♠QJ2 ♥AKQ3 ♦A74 ♣652 (16) | 2NT | **3♠** |
| 1♠ – 2♣ – 2♠ – ? | ♠AQ6 ♥KJ53 ♦AJ32 ♣98 (15) | 2NT | **3♠** |
| 1♥ – 2♣ – 2♥ – ? | ♠A8 ♥AJ5 ♦AJ86 ♣QJ102 (17) | 2NT | **3♥** |
| 1♠ – 2♣ – 2♠ – ? | ♠952 ♥AK63 ♦AK3 ♣K42 (17) | 2NT | **3♠** |
| 1♥ – 2♣ – 2♥ – ? | ♠A73 ♥A72 ♦AK42 ♣A83 (19) | 2NT | **3♥** |

## B. A válaszolónak mindkét nem licitált színben van fogása (11 FP): a régi színenkénti fogásmutatás helyett rögtön 3NT — 10 eset

| Menet | Lap (FP) | Régi | Új (elv) |
|---|---|---|---|
| 1♠ – 2♣ – 2♠ – ? | ♠62 ♥AK86 ♦Q653 ♣Q108 (11) | 3♦ | **3NT** |
| 1♠ – 2♣ – 2♠ – ? | ♠7 ♥QJ6 ♦J962 ♣AK876 (11) | 3♦ | **3NT** |
| 1♠ – 2♣ – 2♠ – ? | ♠8 ♥K953 ♦AJ85 ♣K1054 (11) | 3♦ | **3NT** |
| 1♠ – 2♣ – 2♠ – ? | ♠86 ♥AQ5 ♦K762 ♣Q875 (11) | 3♦ | **3NT** |
| 1♠ – 2♣ – 2♠ – ? | ♠5 ♥A763 ♦AK6 ♣98642 (11) | 3♦ | **3NT** |
| 1♠ – 2♣ – 2♠ – ? | ♠Q ♥AK98 ♦J754 ♣J986 (11) | 3♦ | **3NT** |
| 1♠ – 2♣ – 2♠ – ? | ♠Q5 ♥KJ8 ♦KQ10 ♣87543 (11) | 3♦ | **3NT** |
| 1♥ – 2♣ – 2♥ – ? | ♠QJ5 ♥9 ♦K932 ♣AJ1054 (11) | 2♠ | **3NT** |
| 1♥ – 2♣ – 2♥ – ? | ♠A6 ♥9 ♦AJ82 ♣Q109872 (11) | 2♠ | **3NT** |
| 1♠ – 2♣ – 2♠ – ? | ♠7 ♥J1098 ♦AQ64 ♣A654 (11) | 3♦ | **3NT** |

## C. A válaszolónak nincs fogása a nem licitált színekben: a régi „természetes 2NT” helyett a saját színe (3♣) — 3 eset

| Menet | Lap (FP) | Régi | Új (elv) |
|---|---|---|---|
| 1♥ – 2♣ – 2♥ – ? | ♠A7 ♥A73 ♦A97 ♣QJ763 (15) | 2NT | **3♣** |
| 1♠ – 2♣ – 2♠ – ? | ♠KJ2 ♥AQ6 ♦A3 ♣Q9653 (16) | 2NT | **3♣** |
| 1♠ – 2♣ – 2♠ – ? | ♠K72 ♥Q10 ♦AK4 ♣K10983 (15) | 2NT | **3♣** |

## D. A RÉGI menet folytatása: a válaszoló régi 2NT-je után (az új rendszerben ő már nem mondana 2NT-t) — a 2NT itt fogást mutat, a nyitó 3NT-t mond — 19 eset

| Menet | Lap (FP) | Régi | Új (elv) |
|---|---|---|---|
| 1♠ – 2♣ – 2♠ – 2NT – ? | ♠A109432 ♥KJ3 ♦76 ♣K9 (11) | 4♠ | **3NT** |
| 1♠ – 2♦ – 2♠ – 2NT – ? | ♠AJ10874 ♥A64 ♦Q ♣642 (11) | 4♠ | **3NT** |
| 1♥ – 2♦ – 2♥ – 2NT – ? | ♠Q4 ♥AK543 ♦1053 ♣K108 (12) | 5♦ | **3NT** |
| 1♠ – 2♣ – 2♠ – 2NT – ? | ♠AQ8743 ♥K87 ♦864 ♣A (13) | 4♠ | **3NT** |
| 1♠ – 2♦ – 2♠ – 2NT – ? | ♠A10972 ♥854 ♦AJ103 ♣Q (11) | 5♦ | **3NT** |
| 1♠ – 2♣ – 2♠ – 2NT – ? | ♠QJ108654 ♥J97 ♦KJ ♣A (12) | 4♠ | **3NT** |
| 1♠ – 2♣ – 2♠ – 2NT – ? | ♠KJ6532 ♥82 ♦AQJ ♣102 (11) | 4♠ | **3NT** |
| 1♠ – 2♣ – 2♠ – 2NT – ? | ♠AK10987 ♥872 ♦A ♣1074 (11) | 4♠ | **3NT** |
| 1♥ – 2♦ – 2♥ – 2NT – ? | ♠QJ ♥KJ98642 ♦3 ♣KJ7 (11) | 4♥ | **3NT** |
| 1♥ – 2♦ – 2♥ – 2NT – ? | ♠K32 ♥AK963 ♦J875 ♣2 (11) | 5♦ | **3NT** |
| 1♥ – 2♦ – 2♥ – 2NT – ? | ♠10643 ♥AK9842 ♦J ♣K5 (11) | 4♥ | **3NT** |
| 1♥ – 2♦ – 2♥ – 2NT – ? | ♠Q103 ♥KJ642 ♦K96 ♣Q6 (11) | 5♦ | **3NT** |
| 1♠ – 2♣ – 2♠ – 2NT – ? | ♠KJ10872 ♥10 ♦75 ♣AK75 (11) | 4♠ | **3NT** |
| 1♥ – 2♦ – 2♥ – 2NT – ? | ♠10 ♥K10982 ♦Q52 ♣AK98 (12) | 3♦ | **3NT** |
| 1♥ – 2♦ – 2♥ – 2NT – 3♦ – ? | ♠AQJ ♥A6 ♦AJ1083 ♣Q54 (18) | 3♥ | **3NT** |
| 1♥ – 2♦ – 2♥ – 2NT – 3♦ – 3♥ – ? | ♠10 ♥K10982 ♦Q52 ♣AK98 (12) | 3♠ | **3NT** |
| 1♥ – 2♦ – 2♥ – 2NT – 3♦ – 3♥ – 3♠ – ? | ♠AQJ ♥A6 ♦AJ1083 ♣Q54 (18) | 4♥ | **3NT** |
| 1♠ – 2♣ – 2♠ – 2NT – ? | ♠AKQJ876 ♥Q82 ♦84 ♣5 (12) | 4♠ | **3NT** |
| 1♠ – 2♣ – 2♠ – 2NT – ? | ♠AK10873 ♥KJ3 ♦109 ♣A6 (15) | 4♠ | **3NT** |

## E. Hézag-elv: nem mond 3NT-t, ha a 3NT jelentése olyan fogást ígér, ami nincs meg — 5 eset

| Menet | Lap (FP) | Régi | Új (elv) |
|---|---|---|---|
| 1♥ – 2♦ – 2♥ – 3♣ – 3♥ – ? | ♠1042 ♥J ♦AK632 ♣A1092 (12) | 3NT | **4♥** |
| 1♠ – 2♦ – 2♠ – 3♣ – 3♦ – 3♠ – ? | ♠AQ972 ♥Q10 ♦A932 ♣64 (12) | 3NT | **5♦** |
| 1♥ – 2♦ – 2♥ – 3♣ – 3♦ – 3♥ – ? | ♠762 ♥AQJ108 ♦843 ♣A4 (11) | 3NT | **5♦** |
| 1♥ – 2♦ – 2♥ – 3♣ – 3♦ – ? | ♠1072 ♥43 ♦AK1074 ♣A87 (11) | 3NT | **5♦** |
| 1♥ – 2♦ – 2♥ – 3♠ – ? | ♠A532 ♥AQ653 ♦97 ♣Q4 (12) | 3NT | **4♥** |

## F. A nyitó plusz erővel (15+) és fogással: a lassú 2NT a 3NT helyett — 1 eset

| Menet | Lap (FP) | Régi | Új (elv) |
|---|---|---|---|
| 1♥ – 2♦ – 2♥ – 2♠ – ? | ♠106 ♥AK862 ♦AK6 ♣A82 (18) | 3NT | **2NT** |
