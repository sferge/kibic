# Feloldó és licitmotor

| fájl | hova |
|---|---|
| `motor/feloldas.py` | `src/kibic/motor/feloldas.py` — ÚJ |
| `motor/licital.py` | `src/kibic/motor/licital.py` — ÚJ |
| `tests/test_licital.py` | `tests/test_licital.py` — ÚJ (15 teszt) |

## Feloldó

Egy rendszer teljes, érvényes szabálylistáját állítja elő az öröklés
feloldásával: szélességi bejárás a `HIVATKOZAS` sorokon, a **kisebb
mélységű nyer** azonos `kulcs`-nál, körfigyeléssel. Az eredmény a
`feloldott_licitmenet` táblába menthető — enélkül nem látható, mit
jelent ténylegesen egy örökölt rendszer.

```python
from kibic.motor.feloldas import feloldas, ment
f = feloldas(conn, "LICREN_STUND")
print(f.lanc)          # [('LICREN_STUND', 0), ('LICREN_STAND', 1)]
print(len(f.sorok), f.kulcsok, f.felulirt)
ment(conn, f)
```

## Licitmotor

Kap egy licitállást és egy kezet, visszaad egy döntést **és a
jelölthalmazt**. Három mód: `SORREND` (a legmagasabb prioritású nyer —
LICREN-hű), `SPECIFIKUSSAG`, `MERLEGELO` (nem dönt, a hívó dönt).

```python
from kibic.motor.licital import Licitmotor
m = Licitmotor(f.sorok, ktx, mod="SORREND")
d = m.licital(licitek, "S", kez, beliallas="NS",
              engedelyezett=["1S", "1NT", "PASS"])   # legal_actions
print(d.osszefoglalo())
```

**A jelölthalmaz a fontos újdonság.** Ahol egynél több szabály
illeszkedik, ott a rendszer önmagában nem dönt — a `d.bizonytalan`
jelzi. Ez rajzolja ki automatikusan a helyzeteket, ahol a további
megfontolások (beliállás, verseny állása, partner és ellenfél stílusa)
számítanának.

## Ami menet közben kiderült

**Változóval végződő minták.** Az `1M-2M` (emelés) utolsó tokenje maga
változó — az első megoldásommal ezek soha nem tudtak licitet adni.
Átalakítva: a minta **előzmény-részét** illesztjük a licitmenetre, a
kötésekből pedig **kiszámítjuk** a licitet. Így az `1M-2M` a partner
`1H` nyitására `2H`-t ad, `1S`-re `2S`-t; az `1A-1B-1E-2Q` pedig
kiszámolja, melyik a negyedik szín. Ha a változó kötetlen marad
(`1C-1M`), a szabály kimarad — nem tudjuk, melyik nemest mondjuk.

**A `stand.lr` válaszszabályaiban nincs erőminimum.** Az `1S:(S>3)`
mindössze négy pikket kér, pontküszöb nélkül — a motor tehát egy két
pontos lappal is `1S`-t válaszolna. A LICREN gyakorlóprogramja nyilván
máshol dönti el, hogy a válaszoló passzoljon-e; a fájlban ez nincs benne.
**Ez a te döntésed:** vagy felveszünk egy rendszerparamétert
(`VALASZ_MIN`, és a motor az alatt passzol), vagy explicit `PASS`
szabályokat írunk a tudásbázisba. Az elsőt javaslom — kevesebb sor,
és paraméterként söpörhető is.

## Próba

Teljes pároslicit a `stand.lr` szabályaival, 12 pontos kiegyensúlyozott
és 15 pontos kéz szemben:

```
N: 1NT   [2 jelölt]   figurapont 12-14 között, nincs szingli...
S: 3NT   [3 jelölt]   pont 14-18 között...
N: PASS
S: PASS
```

Bridzsszakmailag helyes, és a jelölthalmaz is látszik.
