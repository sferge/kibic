# Teljes licitmenet-mérés — az 1. fázis zárómérése

| fájl | hova |
|---|---|
| `cli/licitmeres.py` | `src/kibic/cli/licitmeres.py` — ÚJ |

```bash
source .env
python -m kibic.cli.licitmeres --lr rendszerek/gfk/stand.lr \
    --par "gal - korszurku" --metrika P_HOSSZ
```

## Mit mér

**Pozíciónként.** Minden valódi licitnél megkérdezi a motort, de a
menetet a *valódi* licitekkel viszi tovább — így az eltérések nem
halmozódnak, és megmondja, hol romlik el.

**Szimulációval.** A motor végiglicitál a saját döntéseivel; az
ellenfél licitjeit a valódi menetből vesszük. Külön jelzi, hány partiban
egyezett **végig** — ott a szimuláció hiteles; ahol eltért, onnantól
hipotetikus (a valóságban az ellenfél másképp licitált volna).

**Double dummy összehasonlítással.** A DDS-táblából kiszámolja, melyik
kontraktus jobb, és IMP-ben adja meg a különbséget. **Ez a rész
független attól, hogyan jutottunk a kontraktushoz**, tehát megbízható.

## A legfontosabb szám: a LEFEDETTSÉG

Az első próbafutás (`stand.lr`, 120 `gal`-parti) megmutatta, miért nem
elég a nyers egyezési arány:

```
vizsgált licit:      616
LEFEDETTSÉG:         105  (17.0%)   <- volt-e EGYÁLTALÁN szabály
pontosság a lefedetteken: 84/105  (80.0%)   <- EZ A VALÓDI MÉRCE
nincs szabály:       511   (ebből a valódi is passz volt: 320)
nyers egyezés:       404  (65.6%)   (a passz-fallbackkel — FÉLREVEZETŐ)
kompetitív helyzet:  374   (ebből lefedett: 0)
```

A 65,6% nagyrészt „mindketten passzoltunk" egyezés. **A valódi
teljesítmény 80,0% — de csak a pozíciók 17%-án.**

És kiderül a szűk keresztmetszet is: **374 kompetitív helyzetből
NULLA a lefedett.** A `stand.lr` kizárólag pároslicitet ír le; ahol az
ellenfél megszólal, a motornak nincs mit mondania.

## Ebből mi következik

Nem a motor pontossága a gyenge, hanem a **tudásbázis lefedettsége**.
Két irány nyílik, és a lefedettségi szám mondja meg, melyik éri meg:

* **kompetitív szabályok** (közbeszólás, negatív kontra, versenylicit) —
  a helyzetek 61%-át fedné le, jelenleg nulláról
* **mélyebb pároslicit-folytatások** — a maradék javítása

A mérés mostantól minden bővítés értékét számszerűsíti.

## Kapcsolók

`--lr` vagy `--rendszer` (fájlból vagy adatbázisból) · `--par` vagy
`--par-id` (melyik pár szemszögéből) · `--metrika` (a `@PONT`
feloldása) · `--mod SORREND|SPECIFIKUSSAG` · `--limit` · `--peldak`
