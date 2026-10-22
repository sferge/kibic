# A rendszerszerkesztő

Böngészőben: `http://<a kibic gépe>:9050/szerkeszto`
(pl. `http://192.168.77.70:9050/szerkeszto`). Ha a szolgáltatásnak van
titka (`KIBIC_SHARED_SECRET`), a jobb felső mezőbe kell beírni; a böngésző
megjegyzi.

Előfeltétel: a `schema/021_szerkeszto.sql` (megjegyzések) és a
`schema/022_jegyzet.sql` (jegyzetek) lefuttatva.

## Mi ír közvetlenül, mi nem

| Mit csinálsz | Hová ír | Hat a licitálásra? |
|---|---|---|
| jóváhagyás, jegelés, kiolvasztás, visszavonás | `licitmenet.allapot` | igen, azonnal (élesben csak az elfogadott él; teszt módban a javasolt is; a jegelt soha) |
| megjegyzés (szabály, fejezet, rendszer) | `szerkeszto_megjegyzes` | nem — az Exporttal jut el Claude-hoz |
| a szabály tartalma, új szabály, hivatkozás, törlés | — | csak megjegyzésben; Claude a YAML-ban javítja, és új zipben jön |

## Jegyzet és megjegyzés

* **Jegyzet** (sárga, ℹ): tartós magyarázat — MIÉRT ilyen a szabály,
  fejezet vagy konvenció. A YAML-ban él (`jegyzet:`), minden importtal
  frissül. Ha egy megjegyzésből tartós tudás lesz, Claude jegyzetként
  írja be.
* **Megjegyzés** (💬): munkajegyzet, kérdés, kérés Claude-nak; lezárható.

## Sor-címkék (rámutatva magyarázat jelenik meg)

* **↳ lehetőség** — zárójeles lapszámból, pl. (4)5+, keletkezett második
  sor (behúzva, a fő sor alatt).
* **mérlegelő** — nem a szabály dönt, a licit csak jelölt.
* **törlés** — módosított konvencióban az alap egy szabályát kiveszi.
* **elv**, **kivétel** — az elvek rétege.

## Rendszer lap

* **Hivatkozási fa** — a kiválasztott rendszer feloldása: mit hivatkoz be,
  milyen fajta, milyen témájú; alatta a feloldás megjegyzései (kizárás,
  téma szerinti csere, módosítás által kivett szabály, figyelmeztetések).
* **Rendszer** — a kiválasztott elem fajtája, témája, alapja, jegyzete és
  SAJÁT hivatkozásai (beemel / kizár / alapja); **Megjegyzés a
  rendszerhez** — ide írd, ha új hivatkozást, kizárást javasolsz.
* **Fejezetek** — egy elemre kattintva a fejezetei, állapotonkénti
  számmal (javasolt / elfogadott / felülvizsgálandó / jegelt). Több
  fejezetnél az első sor **Összes fejezet egyben**: a teljes rendszer,
  minden szabály mellett a fejezete neve. Kiválasztáskor ez nyílik meg.
  (Egész fejezetet jóváhagyni és fejezethez megjegyzést írni csak egy
  konkrét fejezetben lehet.)
* **Szabályok** — emberi nyelven, ♣♦♥♠ jelekkel, a forrás idézetével, a
  helyzeti feltétellel („helyzet: 3./4. kézben”). A sorrend folytatólagos:
  nyitásonként előbb a pároslicit (1♥, 1♥–1♠, 1♥–1♠–2♣, 1♥–1NT …), utána a
  küzdelmi menetek (1♥ (X) 1♠, 1♥ (1♠) X …), a végén a védekezők.
  Az „1♥ (P) 1♠” ugyanaz, mint az „1♥–1♠”.
  * Kijelöltek: jóváhagyás, jegelés, kiolvasztás, jóváhagyás visszavonása.
  * Az egész fejezet jóváhagyása egy gombbal (megerősítéssel).
  * A változás azonnal él: a szolgáltatás gyorsítótára ürül.
* **Keresés a feloldott nézetben** — licit szerint, nem betű szerint: az
  `1S-1NT` megtalálja az `1M-1NT` szabályt és a folytatásait is (M =
  bármelyik nemes), az `1M` az 1♥, 1♠ és 1M kezdetűeket, az `1m-1H` az
  1♣-1♥-et is. A változó kötése számít: az `1S-2H` nem hozza az `1M-2M`-et.
  Kisbetű is jó (`1s-1n`); a végén kötőjel (`1NT-`): csak ami utána jön.
* **Megjegyzés** szabályhoz vagy fejezethez. A **Mentés** gomb (vagy
  Ctrl+Enter) írja be az adatbázisba; addig a piszkozat a böngészőben
  megmarad, akkor is, ha bezárod a lapot.

## Próbakéz lap

Kéz (`AKQ2.K73.84.952` — pikk.kőr.káró.treff, vagy `♠AKQ2 ♥K73 ♦84 ♣952`),
osztó, beliállás, licitmenet az osztótól (`P P 1H X`). A felső sávban
választott rendszerrel licitál; teszt módban a még jóvá nem hagyott
szabályokkal is. Eredmény: a licit, a magyarázat, a győztes szabály (honnan
jön), és minden szabály, ami szóba jött — ha nem teljesült, miért nem (a kéz
tényleges értékeivel).

## Megjegyzések lap

A nyitott megjegyzések listája, lezárás. Az **Export Claude-nak** gomb egy
JSON-fájlt tölt le: ezt kell a beszélgetésbe feltölteni.

## Következő lépés: vizsga mód

A kibic egy helyzethez kezeket ad, te licitálsz; a végén az eltérések
listája. (Tervezett.)
