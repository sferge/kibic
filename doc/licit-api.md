# `POST /v1/kibic/licit` — licitálás és licitmagyarázat

A DD-elemzés testvére. Az megmondja, mi lett volna a legjobb **lap**; ez
azt, mit licitálna a kibic — és ami fontosabb, **miért**, meg hogy **mit
értett meg** az eddigi menetből.

Ugyanabban a névtérben él, mint a `POST /v1/kibic/dd`, és ugyanazokat a
jelöléseket használja: égtáj `N E S W`, szín `C D H S`, szan `N`,
beliállás `none ns ew both`, hívás `P X XX` vagy `2H`.

> **A MohaBridzs webapp nem ezt hívja.** Az a `POST /v1/bridge/bid`
> végpontot használja (`mohabridzs-ai/1.0`), amit a
> `szolgaltatas/atjaro.py` fordít rá erre. Ez itt a **műhely**: ahol a
> kényszertár, a jelöltek és a lefedettség látszik. Lásd:
> [`mohabridzs-atjaro.md`](mohabridzs-atjaro.md).

---

## Miért a magyarázat a lényeg

Egy licitet adni önmagában keveset ér: nem lehet megmondani róla, jó-e.
A válasz ezért mindig elszámol azzal, hogy

* az eddigi licitek közül **melyiket értette meg és melyiket nem**;
* mit tud a négy kézről (`constraints`);
* a javaslat **honnan jön**: konkrét szabály, elv, vagy szimuláció;
* ha több jelölt volt, **mi maradt versenyben**.

Ahol a tudásbázis hiányos — a kompetitív ágakon ma az —, ott a `call`
mező `null`. **Ez nem hiba, hanem mérés.** A `coverage` és az
`auction_understanding` pont azt mutatja meg, hol néma a rendszer, és ez
a legértékesebb visszajelzés, amit az app adhat vissza.

---

## Kérés

```json
{
  "request_id": "opcionális, változatlanul visszaadjuk",
  "hand": ["SK","S7","S4","HA","HQ","H6","H3","D9","D5","D2","C8","C6","C3"],
  "seat": "S",
  "dealer": "N",
  "vulnerability": "none",
  "auction": [{"seat":"N","call":"1S"}, {"seat":"E","call":"2N"}],
  "system": "LICREN_STAND",
  "pair": "gal - korszurku",
  "legal_actions": ["P","X","2S","3C"],
  "simulate": false
}
```

| mező | kötelező | megjegyzés |
|---|---|---|
| `hand` | igen | pontosan 13 lap, a **kérdező** kezéből |
| `seat` | igen | ki licitál most |
| `dealer` | nem | ha hiányzik, a `seat` az osztó |
| `vulnerability` | nem | alapértelmezés `none` |
| `auction` | nem | lehet rövid alak is: `["1s","p"]` — ilyenkor az osztótól osztjuk az üléseket |
| `system` | **igen** | melyik rendszer szemüvegén át (pl. `LICREN_STAND`) |
| `pair` | nem | paraméter-felülírások forrása (a pár saját küszöbei) |
| `legal_actions` | nem | ha megadod, csak ezek közül választ |
| `simulate` | nem | mérlegeljen-e szimulációval (lassabb, DDS kell hozzá) |
| `samples` | nem | hány leosztást vegyen a mérlegeléshez (alap: 60) |
| `calibration` | nem | a `ddtorzitas --mentes` fájljának útvonala |

A hívások elnézőek: `p`, `pass`, `-` mind passz; `dbl`, `d`, `*` kontra;
`1n`, `1nt`, `1sa` egyaránt 1 szan.

---

## Válasz

```json
{
  "seat": "S",
  "system": "TESZT",
  "branch": "KUZDELMI",
  "call": null,
  "source": "NINCS",
  "source_text": "nincs rá szabály a betöltött rendszerben",
  "explanation": "nincs illeszkedő szabály",
  "uncertain": false,
  "candidates": [],
  "to_deliberate": [],
  "undecidable_rules": 0,
  "auction_understanding": [
    {"seat":"N","call":"1S","understood":true,
     "meaning":"12-21 pont; S: 5-13"},
    {"seat":"E","call":"2NT","understood":false,
     "note":"nincs rá szabály a betöltött rendszerben"}
  ],
  "constraints": {
    "N": {"points":[12,21], "suits":{"S":[5,13]},
          "described":"12-21 pont; S: 5-13", "understood":true},
    "E": {"described":"nyilatkozott, de nem értettük a licitjeit",
          "understood":false},
    "S": null,
    "W": null
  },
  "coverage": {"understood":1, "unknown":1,
               "unknown_calls":["E:2NT"], "ratio":0.5},
  "warning": "…",
  "elapsed_ms": 12
}
```

### A mezők

**`call`** — a javasolt licit, vagy `null`, ha nincs rá szabály. Soha nem
találgat.

**`source`** — honnan jön a javaslat:

| érték | jelentés |
|---|---|
| `SZABALY` | konkrét szabály a rendszerben |
| `ELV` | nincs rá megállapodás, az általános elv szerint |
| `MERLEGELES` | a szabály csak beengedte; a döntés szimulációból jön |
| `NINCS` | nincs rá szabály a betöltött rendszerben |

**`branch`** — a licitálás melyik ágában vagyunk: `PAROS` (mi kezdtünk, ők
hallgatnak), `KUZDELMI` (mi kezdtünk, ők belelicitáltak), `VEDEKEZO` (ők
kezdtek). Hasznos a naplózáshoz: a lefedettség áganként nagyon eltérő.

**`auction_understanding`** — licitenként `understood` + `meaning`, vagy
`note` azzal, hogy miért nem. A `ambiguous` mező jelzi, ha a licitnek
több lehetséges jelentése volt.

**`constraints`** — ülésenként, amit a licitekből tudunk. `null`, ha az
illető nem nyilatkozott; `understood: false`, ha nyilatkozott, de egyik
licitjét sem értettük (a kettő nem ugyanaz).

**`candidates`** — a szabály-alapú jelöltek. Ha több van, a rendszer
önmagában nem dönt: `uncertain: true`.

**`to_deliberate`** — olyan jelöltek, amelyeknek a szabálya kimondja, hogy
nem ő dönt (büntető kontra, elvek). Ezekből csak `simulate: true` mellett
lesz `deliberation` blokk:

```json
"deliberation": {
  "samples": 60,
  "biased_sample": true,
  "penalty":  {"contract":"3CX", "average_score": -23},
  "our_best": {"contract":"4S",  "average_score": 420},
  "imp_difference": -9.8,
  "mp_win_rate": 0.12,
  "calibrated": true
}
```

Az `imp_difference` és az `mp_win_rate` **külön** van, mert IMP-en és
párosversenyen más lehet a helyes döntés. A modul nem választ helyetted.

**`undecidable_rules`** — hány szabály hivatkozott feloldatlan metrikára.
Ha nagy, a paramétertár vagy az értékelők hiányosak.

---

## Üzemeltetés

A rendszer feloldása (öröklés + paraméterek) drága, ezért a szolgáltatás
**gyorsítótárazza** `(system, pair)` kulcs szerint. A tudásbázis
módosítása után:

```
POST /v1/kibic/ujratolt
```

Az életjel megmutatja, mi van betöltve és elérhető-e a DDS meg az
adatbázis:

```
GET /v1/kibic/allapot
```

Hitelesítés ugyanúgy, mint a DD-nél: ha a `KIBIC_SHARED_SECRET`
környezeti változó be van állítva, `Authorization: Bearer <titok>` kell.

---

## Amit az app érdemes megmutasson

A `call` önmagában a kevésbé érdekes fele. A felhasználónak sokkal
többet mond:

1. **mit értett meg a gép a licitmenetből** — ez azonnal látszik a
   játékosnak, és rögtön lehet vitatkozni vele;
2. **min múlt a javaslat** (`candidates[].why`);
3. **hol néma** (`coverage.unknown_calls`) — ebből lesz a következő
   konvenció, amit érdemes beírni a tudásbázisba.

A harmadik a leghasznosabb nekünk: minden „nem értettem" egy konkrét,
címzett hiánylista.
