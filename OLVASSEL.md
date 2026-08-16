# Bridzs AI — 0. fázis, első komponensek

## Tartalom

| Fájl | Szerep |
|---|---|
| `schema.sql` | MariaDB séma (fej-tétel szerkezet, értékelő-regiszter) |
| `bridzs/domain.py` | Domain-mag: lap, kéz, leosztás, lapértékelők |
| `bridzs/pontozas.py` | Eredménypontozás (scoring) + IMP-átváltás |
| `bridzs/pbn.py` | PBN-olvasó (rotáció-visszafejtéssel, claim-kezeléssel) |
| `bridzs/importalo.py` | Importáló CLI, dry-run móddal |

## Indulás

```bash
mysql -u root -p < schema.sql

# Elemzés adatbázis nélkül — ezzel kezdd:
python -m bridzs.importalo "partik/*.pbn" --dry-run

# Tényleges betöltés:
pip install pymysql
python -m bridzs.importalo "partik/*.pbn" --db bridzs --user root --jelszo TITKOS

# Az arany készlet megjelölése regressziós tesztnek:
python -m bridzs.importalo "arany/*.pbn" --db bridzs --cimke arany_keszlet
```

A CLI kilépési kódja 1, ha bármely pontszám eltért vagy kiosztás hibás volt —
így CI-ben is használható regressziós tesztként.

## Amit a `--dry-run` megválaszol

Hány leosztás, hány egyedi, hány claim, hány hiányos rekord, kik a játékosok,
és a legfontosabb: **egyezik-e a saját pontszámításunk a jegyzőkönyvvel**.
Ez a 0. fázis kilépési feltételének fele.

## Mi következik

1. LIN-olvasó (`bridzs/lin.py`) — ugyanaz az interfész, `PbnJatszma`-kompatibilis
   kimenettel. Kereszt-ellenőrzés: ugyanaz a parti mindkét formátumból
   azonos `leosztas_hash`-t és azonos lapsorrendet kell adjon.
2. Visszajátszó (`bridzs/visszajatszo.py`) — a lejátszás szabályossági
   ellenőrzése ütésről ütésre (színkötelezettség, ütésgyőztes, ütésszám),
   és az eredmény egyeztetése a jegyzőkönyvvel.
3. DDS-kötés + a `leosztas.dds_utesek` gyorsítótár feltöltése.
