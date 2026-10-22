# BBO GIB rendszer — nyitások

| fájl | hova |
|---|---|
| `rendszerek/gib.lr` | `rendszerek/gib/gib.lr` — ÚJ |
| `eszkozok/gib_ellenorzes.py` | `eszkozok/gib_ellenorzes.py` — ÚJ |

## A fordítás

Forrás: a `BBO_GIB.docx` nyitási táblázata és az „Overview" szakasz.
A rendszer: **2/1 gémforsz, ötös nemesek, erős szan, mesterséges 2♣**.

| licit | feltétel | forrás |
|---|---|---|
| `1S`/`1H` | 5+ lap, 11+ HCP **vagy** 12+ total points | „normally show 5 in all seats" |
| `1C` | 3+ treff, nincs ötös nemes | „could be 3 if 4333, 3433 or 4423" |
| `1D` | 4+ káró (és legalább annyi, mint a treff), **vagy** 4432-nél 3 káró | „usually 4 unless 4432. Opens 1♦ with 4-4 in the minors" |
| `1N` | 15-17, kiegyensúlyozott, ötös nemessel is | „may have a 5-card major" |
| `2D`/`2H`/`2S` | hatos szín, 5-10, **színbeli figurával** | „Disciplined, with honors in the suit" |
| `3C`..`3S` | 7+ lap, 3-9 | |
| `2N` | 20-21, kiegyensúlyozott | |
| `2C` | 22+ | „strong, artificial. 22+ HCP" |

**Nincs Gambling 3NT** — a leírás kifejezetten felsorolja a nem játszott
konvenciók között (Namyats, Bergen, DONT, Puppet Stayman mellett).

## FONTOS: a `@PONT` feloldása itt `P_AP321`

A GIB „total points" definíciója a leírás szerint **HCP + 3 renonszért,
2 szingliért, 1 dublóért** — ez pontosan a mi `AP_321` metrikánk, NEM a
`P_HOSSZ` (ami hosszúsági pontot ad). A rendszernek ezért saját
paraméter-beállítás kell:

```sql
INSERT INTO rendszer_parameter (rendszer_id, parameter_id, ertek, megjegyzes)
SELECT r.id, p.id, 'P_AP321', 'A GIB "total points" = HCP + 3/2/1 rovidsegert'
  FROM rendszer r, parameter p
 WHERE r.kod = 'GIB' AND p.kod = 'PONT_METRIKA';
```

Offline mérésnél: `--metrikak P_AP321`.

## Az ellenőrzés — ez a lényeg

A gyűjteményben ~591 gépi magyarázatú licit van. Ezek **nem emberi
vélemények, hanem a robot pontos állításai a saját lapjáról**:

```
minor suit opening -- 3+ !c; 11-21 hcp; 12-22 total points
```

Az ellenőrző három dolgot mér:

**(A) Igazat mond-e a robot?** A kimondott feltételt összeveti a valódi
kézzel. Ha bármi nem teljesül, akkor **a mi magyarázat-elemzőnk hibás**
— a robot nem hazudik a saját lapjáról.

**(B) Jól fordítottunk-e?** A `gib.lr` ugyanazt a licitet adja-e.
**Ez szigorúbb mérce, mint az emberi partikon mért egyezés:** a GIB
determinisztikus, tehát minden eltérés a MI hibánk. Nincs „a játékos
másképp gondolta" kifogás.

**(C) Hol térünk el?** Az eltéréseket a robot saját feltételével együtt
írja ki — azonnal látszik, melyik feltételt rontottuk el.

```bash
source .env
python eszkozok/gib_ellenorzes.py rendszerek/gib/gib.lr
```

## Amit menet közben javítottam

Az első fordításban **a `1D` szabály soha nem tüzelt**: az `1C` volt
utána a fájlban, és mivel az utolsó illeszkedő nyer, mindig az `1C`
győzött. A sorrend megfordítva, és a minorválasztás a GIB szabálya
szerint pontosítva (4+ káró és legalább annyi, mint a treff; vagy
4432-nél 3 káró).

## Korlát

Ez **csak a nyitásokat** tartalmazza. A válaszok és folytatások
(2/1 gémforsz, Jacoby 2NT, splinterek, kétirányú gémpróbák, RKCB 0314)
a dokumentumban le vannak írva — ha a mérés azt mutatja, hogy a nyitások
jól sikerültek, érdemes folytatni.
