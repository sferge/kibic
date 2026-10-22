# Futtatási útmutató — ez a csomag felváltja az előző hármat

Ez a zip **mindhárom eddig kiküldött, de be nem épített csomag végállapota**:

| korábbi csomag | mi lett vele |
|---|---|
| `kibic_fesu_0.4` | benne, változatlanul (014) + a 015 frissült |
| `kibic_merlegeles` | benne, a 015 átírt büntető-kontra sorával |
| `kibic_kalibracio` (és a `kalib2` javítás) | benne |
| `kibic_haromag` | benne, de a 016 **le lett egyszerűsítve** |
| `kibic_elvek` | benne, ugyanígy |

**Nem kell sorrendben kibontanod őket.** Elég ez az egy csomag: minden
fájl a végleges állapotában van benne. A korábbi zipek eldobhatók.

---

## 1. Kibontás

A repó gyökerébe, felülírással. Érintett fájlok:

```
schema/014_kompetitiv.sql      új
schema/015_fesu.sql            új
schema/016_elvek.sql           új
src/kibic/motor/minta.py       módosult
src/kibic/motor/kifejezes.py   módosult
src/kibic/motor/licital.py     módosult
src/kibic/motor/feloldas.py    módosult
src/kibic/motor/helyzet.py     ÚJ modul
src/kibic/motor/propagal.py    ÚJ modul
src/kibic/motor/mintavetel.py  ÚJ modul
src/kibic/motor/merlegel.py    ÚJ modul
src/kibic/cli/ddtorzitas.py    ÚJ
src/kibic/cli/aglefedettseg.py ÚJ
tests/test_fesu.py             ÚJ
tests/test_merlegel.py         ÚJ
tests/test_elvek.py            ÚJ
doc/mintanyelv.md              0.4
```

A kódra a git a rollback: `git checkout -- src tests` mindent visszaad.

## 2. Tesztek — ELŐBB, adatbázis nélkül

```
pytest -q
```

Nálam 140 teszt fut zölden adatbázis nélkül (az integrációsak skipelnek).
Ha itt bármi piros, ne menj tovább — szólj, és megnézem.

## 3. Migrációk

Sorrendben, a 013 után:

```
mysql -u kibic -p kibic < schema/014_kompetitiv.sql
mysql -u kibic -p kibic < schema/015_fesu.sql
mysql -u kibic -p kibic < schema/016_elvek.sql
```

Mindhárom **additív és újrafuttatható**:

* csak `ADD COLUMN`-t tesz, és csak akkor, ha az oszlop még nincs meg;
* `INSERT IGNORE`-ral tölt paramétert és rendszert;
* a saját szabálysorait előbb törli, aztán írja (`DELETE ... WHERE
  rendszer_id = @fesu`), tehát kétszer futtatva sem duplázódik.

Egyik sem nyúl a meglévő adataidhoz: sem játszmához, sem leosztáshoz, sem
a betöltött LICREN-rendszerekhez.

**Rollback.** Nem kell, és nem is javaslom az oszlopok eldobását: ha
visszatennéd a régi kódot, az új oszlopokat egyszerűen nem használja
(a `feloldas.py` észreveszi és visszaesik az alapkészletre). Ha a *tartalomtól*
akarsz megszabadulni, arra ott a `schema/visszavonas.sql` — az a FESU és az
ALAPELVEK sorokat törli, az oszlopokat békén hagyja.

## 4. Mit érdemes futtatni utána

```
source .env

# a) a DD-torzítás mérése, most már az eloszlással együtt
python -m kibic.cli.ddtorzitas --reszletes --mentes kalibracio.json

# b) a licitálás három ágának gyakorisága és a rendszer lefedettsége
python -m kibic.cli.aglefedettseg --rendszer LICREN_STAND
python -m kibic.cli.aglefedettseg --par "gal - korszurku"
```

A (b) az érdekesebb: megmondja, hány *döntési helyzet* esik páros,
küzdelmi és védekező ágba, és hány *szabályunk* van rájuk. A kettő
eltérése a valódi hiány — és ettől függ, mennyit ér az egész elv-gépezet.

## 5. Mi NEM megy élesbe

A `FESU` és az `ALAPELVEK` minden sora `JAVASOLT` állapotban van. A motor
kizárólag `ELFOGADOTT` sorokat használ, tehát **a betöltés után sem
változik semmi** a mérésekben, amíg te át nem állítod őket:

```sql
UPDATE licitmenet lm JOIN rendszer r ON r.id = lm.rendszer_id
   SET lm.allapot = 'ELFOGADOTT'
 WHERE r.kod = 'FESU';
```

Ez szándékos: a fésűnél nyitva van, meddig él a konvenció (minor utáni
Michaels-re a forrásod szerint nem fésűzünk), az elveknél pedig még nincs
megbeszélve a válasz-szerkezet (passz / nem ugró / ugró).

---

# Kiegészítés — a MohaBridzs-átjáró (ez a zip)

Ez a csomag **a teljes projekt pillanatképe**, nem fejlesztési darab.
Az előző körhöz (`kibic_licit_api`) képest az új rész:

```
src/kibic/szolgaltatas/atjaro.py   ÚJ  — a mohabridzs-ai/1.0 fordító
src/kibic/szolgaltatas/api.py      +   /v1/bridge/bid, /v1/bridge/play,
                                       /healthz, /readyz, idempotencia
src/kibic/cli/atjaroproba.py       ÚJ  — a szerződés ellenőrzőlistája
tests/test_atjaro.py               ÚJ  — 18 próba, adatbázis nélkül
doc/mohabridzs-atjaro.md           ÚJ  — a beüzemelés és a tesztelés
```

Adatbázis-migráció ehhez **nincs**. A 014–016 marad, ahogy volt.

## Beüzemelés — EGY app, EGY port

**Nem kell két példány.** A `kibic.szolgaltatas.api:app` egyetlen
alkalmazás: a DD-elemzés (`/v1/kibic/dd`) és a gateway-végpontok
(`/v1/bridge/bid`, `/v1/bridge/play`) ugyanabban a folyamatban élnek.
A port marad **9050**, ahogy eddig; a MohaBridzs DD-beállítása nem
változik, az AI-profilba pedig ugyanez az alapcím kerül.

```bash
export KIBIC_AI_SHARED_SECRET="…"     # = a MohaBridzs AI_SHARED_SECRET-je
                                      # (NE a KIBIC_SHARED_SECRET-et: az a
                                      #  DD-végpontot is titokhoz kötné)
export KIBIC_RENDSZER=LICREN_STAND
export KIBIC_ATJARO_NAPLO=$HOME/kibic-atjaro.jsonl
uvicorn kibic.szolgaltatas.api:app --host 0.0.0.0 --port 9050
```

A MohaBridzs AI-profiljába **csak az alapcím** kerül
(`http://192.168.77.70:9050`) — az útvonalat a webapp teszi hozzá.

## Mielőtt a webapp először hív

```bash
python -m kibic.cli.atjaroproba --cim http://localhost:9050 --titok "…"
```

Végigméri a szerződés 14. pontjának ellenőrzőlistáját (18 tétel). Ha ez
zöld, ami marad, az már bridzskérdés, nem integrációs.

Egyetlen helyzet teljes kéréssel-válasszal:

```bash
python -m kibic.cli.atjaroproba --cim http://localhost:9050 --titok "…" \
    --kez "SK S7 S4 HA HQ H6 H3 D9 D5 D2 C8 C6 C3" \
    --menet "1S P" --ules S --oszto N --beli ns
```

## Amire számíts az első parti után

Sok `"source": "fallback"` sor a MohaBridzs admin AI-naplójában. **Ez nem
hiba, hanem az első éles lefedettségmérés**: minden ilyen döntésnél a
`meta.kibic.unknown_calls` megmondja, melyik licitet nem értette a
tudásbázis. Ebből lesz a következő konvenció, amit érdemes beírni.

Részletek: `doc/mohabridzs-atjaro.md`.
