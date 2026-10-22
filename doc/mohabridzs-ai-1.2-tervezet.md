# MohaBridzs AI Gateway — `mohabridzs-ai/1.2` TERVEZET: rendszerválasztás

| Tétel | Érték |
|---|---|
| Állapot | **vázlat** — megbeszélendő, a MohaBridzs még nem valósítja meg |
| Alapja | `mohabridzs-ai/1.1` (`mohabridzs-ai-1.1.md`) |
| Dátum | 2026. szeptember 28. |

**Cél.** Egy AI-játékos ne csak egy, előre beállított rendszert
játszhasson: a pár (a humán partner, a tanár vagy az admin) választhasson
az AI által ismert rendszerek közül.

**Az 1.1-ben ma:** egy AI-játékos = egy rendszer. Több rendszerhez több
AI-játékos kell (a kibicnél több szolgáltatás-példány, mindegyik a saját
`KIBIC_RENDSZER`-ével). Ez működik; ez a tervezet csak kényelmesebbé tenné.

---

## 1. Ami már megvan az 1.1-ben, és erre épül

* `capabilities.systems[]` — az AI által ismert rendszerek (kód, név,
  leírás, kártyakivonat).
* `game.systems` — a MohaBridzs minden kérésben megmondja, melyik vonal
  mit játszik.

## 2. A javasolt változás

### 2.1 A saját rendszer a `game.systems`-ből

Az AI a **saját vonalára** küldött rendszert játssza, ha ismeri
(`capabilities.systems` eleme). Ha nincs megadva, vagy nem ismeri: a
`default_system`-et (mint 1.1-ben), és ezt a válasz `meta`-jában jelzi.

Nincs külön „beállító” végpont és nincs új kérésmező: a rendszer
kiválasztása a MohaBridzsben történik (a pár adata), és a `game.systems`
viszi az AI-hoz. Az AI nem tárol asztali állapotot — így egy
AI-szolgáltatás sok asztalt szolgálhat ki, mindegyiket a saját
rendszerével.

A `profile_code` marad, ami most: a MohaBridzs/gateway azonosítója (pl. a
modell neve). Rendszert nem jelöl.

### 2.2 Más rendszer kártyája: `POST /v1/bridge/card` + `system`

| Kérdés | Kérés | Válasz |
|---|---|---|
| „Partner, mutasd a kártyádat, mit játszunk?” | `system` nélkül | Az AI által most játszott rendszer kártyája (`current: true`). |
| „Mutasd meg ennek a rendszernek a kártyáját.” | `"system": "MOHA_STAND"` | A kért rendszeré, attól függetlenül, mit játszik most (`current` jelzi, azé-e). |

A válasz mindkét esetben: `system`, `name`, `current_system` (amit az AI
most játszik), `current`, `card`, `html`. Ismeretlen vagy kártya nélküli
`system`: HTTP 404.

(A kibic ezt már tudja; az 1.1-ben nem dokumentált, nem kötelező.)

## 3. A folyamat (MohaBridzs-oldal)

**Admin, a meccs indítása előtt:**

1. Kiválasztja az AI-játékosokat (vagy a jelentkezők adják meg magukat).
   Amikor az indulók listája teljes, lekéri **minden érintett AI**
   `capabilities`-ét: képességek, ismert rendszerek, alapértelmezett
   rendszer.
2. Páronként beállítja a rendszert (ha kell, eltérőt az alapértelmezéstől).
   A döntést segíti a `systems[].summary`, és a teljes kártya (`card` +
   `system`).

**Játék közben — az AI humán partnere vagy a tanár:** ugyanez.
„Mutasd a kártyádat” (`card` `system` nélkül) → ha nem tetszik: a lista
(`capabilities`) → egy rendszer kártyája (`card` `system`-mel) → beállítás.

**Szabályok (SHOULD):**

* **Leosztás közben nincs váltás.** Az új rendszer a következő
  leosztástól él — különben a már elhangzott licitek jelentése
  megváltozna, és az `explain` mást mondana, mint amit a licitáló gondolt.
* **Egy pár, egy rendszer.** A rendszer a pár adata: AI-párnál mindkét
  tagra vonatkozik; ha az AI partnere ember, az ember rendszere.
  Olyan rendszer választható, amit a pár minden AI-tagja ismer.
* **Az ellenfél értesül.** Váltás után az ellenfél kérhesse az új kártyát.

## 4. Nyitott kérdések

* Mi legyen, ha a pár rendszerét az AI nem ismeri: a MohaBridzs ne engedje
  kiválasztani, vagy az AI a `default_system`-mel játsszon és jelezzen?
* Rendszerkódok egyeztetése több különböző AI-szolgáltatás között (közös
  kódlista a MohaBridzsben, vagy AI-nként eltérő kódok leképzése).
