# Az értékelők definíciója adattá válik

| fájl | hova |
|---|---|
| `domain/ertekelo.py` | `src/kibic/domain/ertekelo.py` — TELJES CSERE (értelmező lett) |
| `domain/ertekelok.json` | `src/kibic/domain/ertekelok.json` — ÚJ (pillanatkép) |
| `domain/kartya.py` | cserélni — az összes `ert_*` függvény ELTŰNT |
| `domain/__init__.py` | cserélni (újraexport igazítva) |
| `cli/alertek.py` | cserélni (egy hivatkozás igazítva) |
| `tests/test_ertekelo.py` | ÚJ |
| `tests/test_kifejezes.py` | cserélni (`P` → `@PONT`) |
| `schema/011_ertekelo_definicio.sql` | `schema/` + lefuttatni |

## Mi változott

**Nincs többé kettős nyilvántartás.** Eddig a metrikák Python-függvények
voltak, a tábla csak regiszter — ezért tudott elcsúszni a kettő (lásd a
`J_AKQ` esetét). Mostantól az `ertekelo.definicio` oszlop tartalmazza a
**képletet** is, és a `domain/ertekelo.py` csak **értelmezi**.

A `domain/kartya.py`-ból az összes `ert_hcp`, `ert_zar`, `ert_ltc`,
`ert_ap`, `ert_kontroll`, `ert_hcp_dist` függvény, valamint a
`HCP_TABLA` és `KONTROLL_TABLA` **eltűnt**. Nulla primitív maradt.

## A nyelv: nyolc tagtípus

    ÉRTÉK = Σ (együttható × tag_értéke)

`LAP_SULY` (laponkénti súlyozás, szűkíthető színre vagy a hossz szerinti
n-edik színre) · `HOSSZ_SULY` · `HOSSZ_TOBBLET` · `RENDEZETT_HOSSZ` ·
`ERTEKELO` (hivatkozás másikra, körfigyeléssel) · `SZIN_MINTA`
(színenként az első illeszkedő szabály) · `SZIN_HIANYZO` (vesztőütés) ·
`FELTETEL`.

Ezzel mind a 21 metrika leírható. Például a Zar-pont három hivatkozásból
és három hossztagból: `HCP + KONTROLL + 2×L1 + L2 − L4`.

## Új metrika felvétele: EGY adatbázissor

```sql
INSERT INTO ertekelo (kod, nev, leiras, kontextus, definicio) VALUES
 ('SAJAT_PONT', 'Saját pontszámítás', 'Ászok duplán', 'ABSZOLUT',
  '{"tagok":[{"tipus":"ERTEKELO","kod":"HCP"},
             {"tipus":"LAP_SULY","sulyok":{"A":4}}]}');
```

Ezután `betolt_adatbazisbol(conn)` — és a kritérium-motor, a
kifejezésfa és a licitrendszerek azonnal látják. Kódmódosítás nincs.

## IGAZOLÁS: egyetlen szám sem változott

**4000 véletlen kéz × 21 metrika = 84 000 összehasonlítás** a korábbi
Python-implementációkkal, **nulla eltéréssel**. A teljes tesztkészlet
(115 teszt) is zölden fut.

## A pillanatkép

A csomagban lévő `ertekelok.json` azért van, hogy adatbázis nélkül
(tesztek, offline munka) is működjön minden. **Kanonikus forrás az
adatbázis**; a pillanatkép abból regenerálható:

```python
from kibic.domain.ertekelo import betolt_adatbazisbol, export_json
betolt_adatbazisbol(conn)
export_json()
```

Ez ugyanaz az elv, mint a `licitmenet_index`-nél: kanonikus + származtatott.
