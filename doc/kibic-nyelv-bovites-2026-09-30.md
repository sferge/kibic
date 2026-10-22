# A kibic nyelv bővítése (2026-09-30)

A cél: amit emberi nyelven egy mondat mond, az a YAML-ban is egy sor
legyen. A kibontás (melyik szín, melyik szint) licitáláskor, a
memóriában történik, nem a szabálytárban.

## Licitmintában

| jel | jelentés |
|---|---|
| `+A` | a LEGOLCSÓBB licit az A színben. Az előzményben is csak a legolcsóbb illik rá (az `1M-2M-4M` nem `1M-2M-+A`). |
| `A`, `B`, `E` a definiált licitben | SZABAD színváltozó: a motor mind a négy színt kipróbálja, és az a licit lesz jelölt, amelyikre a feltétel igaz. Csak akkor bont ki, ha a feltétel hivatkozik a változóra (különben a licit önkényes volna). |

## Kéz-feltételben (YAML-kulcsok)

| kulcs | példa | jelentés |
|---|---|---|
| `mellekszin` | `[A, B]` | ezek nem az adu (M) színe. A jelentés-propagálás is figyeli. |
| `licit_alatt` | `4M` | a most definiált licit e határ alatt van (gém alatt). |
| `alulrol` | `true` | több illeszkedő licit közül a legolcsóbb (Bánky); az ellenőrző nem jelzi ütközésnek. |
| `kivalt` | `true` | a kártyán mögötte álló rendszer ugyanilyen kulcsú szabályát ez a konvenció kiváltja (bármely konvencióban). |
| `lapok` | `[BA, MK]` | változós színnel is: a B szín ásza, az adu királya. |
| `fohonor` | `{M: 0-1}` | változós színnel is. |
| `vesztok` | `5-5.5` | vesztőütés (Dxx = 2,5). |
| `szin_vesztok` | `{A: 2.5-3}` | vesztőütés egy színben. |
| `fedoutes` | `{M: 2-3.75}` | fedőütés az adu mellett (Moha: A, K, adu D, szingli 1, sikén 2; dubló, DBx 0,5; Dxx 0,25). |
| `igeret` | `{ap: also}`, `{pont: felso}`, `{ap: max}` | a lap az eddig ÍGÉRT saját sáv alsó felében (legfeljebb a közepe) / felső felében / tetején. A sávot a kényszertár adja; ha az ígéret változik, a határ magától követi. |
| `kulcslapok` | `[0, 3]` | kulcslap (4 ász + a megállapodott adu királya). |
| `adu_dama` | `true` | a megállapodott adu dámája nála van. |
| `kontroll` | `0-2` | kontroll (ász = 2, király = 1). |
| `szlem` | `igen / talan / nem / nem_kizart` | a lap szlemjellege (Moha szlem-elv): saját vesztők − a partner fedői. |
| `ot_biztos` | `true` | az 5-ös szint biztonságos (30+ pont a két kézben, vagy legfeljebb 2 maradék vesztő). |
| `licit_alatt` / `licit_felett` / `licit_gem` | `gem` | a licit a megállapodott adu géme alatt / fölött / maga a gém. |
| `nem_adu`, `adu_szin` | `[B]`, `[A]` | a színváltozó nem az adu / épp az adu. |
| `nem_rkc` | `true` | a licit nem a kulcslapkérdés (4♠ kőr adunál, 4NT pikknél, 4m minornál). |
| `leghosszabb` | `A` | az A szín (az egyik) leghosszabb színe. |
| `maradek_vesztok` | `0-3.5` | a saját vesztők mínusz a partner BIZTOS fedői (a mutatott rövidsége is). |
| `osszesen` | `{ap: 25+}` | a saját asztali pont + a partner ígért MAXIMUMA (gémesély). |
| `igeret` | `{pont: also, hatar: 0.35}` | a határ helye a sávban; alapból 7+ pontos sávnál 35%, keskenyebbnél 50%. |
| `onallo_adu` | `M` / `{M: 0.8}` | önállóan játszható adu: a partner sikénjével szemben is legfeljebb 1 aduvesztő, legalább 2/3 (vagy a megadott) eséllyel — kiszámolva (motor/adu_esely.py). |
| `nanopont` | `0-2` | nano-pont (A = 3, K = 2, D = 1): a 2♣ kuka-válaszához. |
| `kulonbozo` | `[A, B]` | a színváltozók más-más színt jelölnek. |
| `kontrollok` | `true` | minden külső színben van kontroll (ász, király, sikén, szingli): csak a kulcslapok kérdésesek. |
| `licit_alatt` | `lezaras` / `{lezaras: B}` | a licit a leállás (3M / 4m) alatt — az adué, vagy a B színé. |
| `licit_alatt` / `licit_gem` | `{gem: A}` | az A szín géméhez képest (akkor is, ha még nincs megállapodott adu). |
| `igeret` | `{pont: also}` nyitott sávnál | a sáv alja + 2 (pl. 12+ után 12-14) = „minimális”; fölötte `felso`. |
| `fit` | `{A: 9+}` | közös adu: a saját lapjaim + amit a partner BIZTOSAN ígért az A színben (a törvényhez, LoTT). |
| `vesztok` | `{O: "0-6", A: "0-5", M: "0-5", S: "0-4"}` | zónás vesztőhatár is lehet (mint a zónás pont): ők bellben / senki / mindenki / mi bellben. |
| `jatekutes` | `6+` / zónás | játékütés (J_KLASSZIKUS: figuraütések + hosszú lapok). |
| `gyorsutes` | `2+` | gyorsütés (AK = 2, AQ = 1,5, A = 1, KQ = 1, Kx = 0,5). |
| `gemeselyes` | `true` / `false` | gémesély a partner ígért sávjával: nemes fittel 25, minor fittel 27, szanban 24 FP — szanban 12-12 … 14-10 elosztásnál; 15-9-től 5-ös, 19-5-től 6-os szín kell (kifejezes.gemesely). |
| `splinter_tamogatas` | `true` | feltételezett 8 lapos fit a partner (tudott, 4+) nemesében. |
| `osszesen` | `{ap_biztos: 25+}` | a saját AP + a partner ígért MINIMUMA (biztos gém). |
| `fogas` | `[Q]` | színváltozóra is (pl. Q, a negyedik szín). |
| `pont` | `{param: SZABAD_LICIT_MIN, alap: 10}` | legalább a PARAMÉTER értéke (rendszerenként — YAML `parameterek:` — és páronként állítható); `eltolas: -1`: eggyel kevesebb (pl. jó lappal). A paraméternek az adatbázisban is léteznie kell (migráció). |

## Helyzeti feltételben (`ha:`)

| kulcs | jelentés |
|---|---|
| `adu: nemes / minor / barmely / C D H S` | van MEGÁLLAPODOTT adunk (ez a szín vagy fajta): a vonalunk ismert 8+ lapos fitje a kényszertár szerint (nemes előbb). |
| `gemforsz: true / false` | gémforszban vagyunk-e: volt-e a vonalunkon gémforsz licit, VAGY elfogadott géminvit. |
| `adu: nincs` | még nincs megállapodott adu. |
| `partner_szin: C` / `{A: 5}` | a partner TUDOTTAN 4+ (5+) lapot ígért ebben a színben (a nyitott sáv nem elég). |
| `partner_gi: true` | a partner utolsó licitje géminvit volt. |
| `ellenfel_pont: 16+` | valamelyik ellenfél a licitjeivel TUDOTTAN ennyi pontot ígért (a kényszertár szerint — az ellenfél rendszere/családja alapján). Pl. erős treff elleni védekezés: él az erős 1♣ ellen, nem él a 2♣-jük (11-15) vagy a természetes 1♣ ellen. |
| `ellenfel_csalad: STRONG_CLUB` | az ellenfél vonalának rendszercsaládja (lista is lehet); ha nem tudjuk, a sor nem él. |
| `ellenfel_szin: H` / `{H: 5}` | az ellenfél TUDOTTAN 4+ (5+) lapot ígért a színben — a rendszerükből vagy az alertjük szövegéből (pl. transzfer-közbeszólás: 2♦ = kőr). |
| `ellenfel_licitalt: true` | az ellenfél már mondott nem-passz licitet (küzdelmi helyzet). |
| `negyedik_szin: true` | a most definiált licit a negyedik szín: a vonal már három igazi színt mondott (amiben legalább 3 lapot ígért), ezt az ellenfél nem mondta, és ez a legolcsóbb licit benne; 2-es szinttől (`{min_szint: 1}`-gyel 1-es szinten is). |
| `partner_negyedik: true` | a partner utolsó licitje a negyedik szín volt. |
| `splinter: true` | ugrás új színben a partner (tudott, 4+) nemesének 3-as szintje fölé, a géme alá. |
| `en_mondtam: E` | ezt a színt én már bemondtam. |
| `en_igertem: {B: 6}` | az eddigi licitjeim szerint ebben a színben legalább ennyi lapot ígértem (pl. a gyenge ugró közbeszóló folytatásához). |
| `ugras: true` | az én (a soron lévő) licitem ugrás: a legolcsóbb szabályos ugyanilyen színű licitnél magasabb szinten van. |
| `gyenge_ugras: 1` / `2` | a gyenge ugrás elve: új szín egyszeres (1) / dupla (2) ugrással, első megszólalásként, kényszer nélkül (a partner nem forszolt, nincs gémforsz), nem splinter-helyzet, és az alacsonyabb licit a színben konkrétan definiált, maga az ugrás nem. A megértésnél a pontplafon az alacsonyabb licit minimuma − 1. |
| `eros_ugras: true` | a párja: új szín egyszeres ugrással MÁSODIK (későbbi) megszólalásként — erő, gémforsz; nem splinter-helyzet, korábban nem limitáltam a lapom (pont_max ≥ 15), és az ugrás nincs konkrétan definiálva. |
| `en_nyitottam: true` | a menet első nem-passz licitje az enyém volt. |
| `en_nyilatkoztam: true` | licitáltam-e már (nem passzt). |

**Feltételes felülírás (2026-10-02):** ha a kártyán előrébb álló
konvenció egy kulcsot csak `ha:`-val ad (minden sora helyzeti feltételes),
a hátrébb álló ugyanilyen kulcsú szabály megmarad, és ott él, ahol a
felülíró feltétele nem teljesül (Timbuktu „(1C) X” erős treff ellen — az
információs kontra minden más 1♣ ellen). Ha a két szabály mindig együtt
élne, adj a felülírónak saját `kulcs`-ot.

**A negyedik szín (`Q`) a feltételben (2026-10-02):** az `1A-1B-1E-…` menetben
a `Q` (amit még senki nem mondott) a kéz-feltételben is használható
(`fogas: [Q]`, `hossz: {Q: 0-1}`).

**Alert 3NT fölött (2026-10-02):** 4♣-tól nincs alert — szabály, kivétel
nélkül (licit.ALERT_FELSO_HATAR); a jelentés ettől még kérdezhető (explain).

**Elv = általános megállapodás (2026-10-02, Moha):** az ELV nem egy konkrét
menetre szól, hanem minden helyzetre, amire igaz. Ezért a helyzetet a `ha:`
csomópont dönti el (negyedik szín, splinter, gémesély), a minta csak
`.. +A` / `.. 3B` alakú.

**Téma (2026-10-02):** egy témát (`tema:`) csak az a konvenció foglalhat
el, amelynek az adott módban van használható sora — a még jóvá nem hagyott
új konvenció (pl. Rubensohl) élesben nem szorítja ki az elfogadott
alternatíváját (Lebensohl).

Szabálykulcs: `folytatas: {mint: 2NT, pont: 2}` — a menet ezzel a licittel
UGYANÚGY folytatódik, mint a megadott menet után (2♣-2♦-2NT → mint a 2NT
nyitás után; 2M-2NT → mint az 1M-2NT után). A `pont` az eltolás: az
átirányított licit gazdája ennyivel erősebb, a partnere pontjához ennyit
adunk (és a jelentésben visszatoljuk). Csak akkor él, ha a menetre nincs
konkrét szabály; csak pároslicitben. Az „ígérthez mért” feltételek
(`igeret: {pont: also}`) eltolás nélkül is jól működnek.

Szabálykulcs: `invit: true` (géminvit; a szövegből is: „invit”, „géminvit”),
`elfogad: true` (elfogadja a partner invitjét; a szövegből: „fogadja az
invitet”). Az egylicites elv („.. 4NT”) bármilyen előzmény után illik.
Jelentés-kulcsok: `jelentes: {fedo_plusz: 1}` (a licit +1 fedőt mutat,
összeadódik), `jelentes: {szin_fedo: {C: {min: 1, valoszinu: 2}}}` (fedő
egy színben: a szlemjelleg a biztosat, a biztonságos 5-ös szint a
valószínűt veszi), `jelentes: {tartalek: true}` (csak akkor számít, ha más
nem értelmezte a licitet — pl. EMELES_ELV).

## Elvek és az ellenfél passza

A „..”-tal kezdődő, ellenfél-tokent nem tartalmazó minta (ELV) a partner
és a saját licitjeiről szól: az ellenfél PASSZA közöttük átlátszó
(„4S (P) 4NT” = „4S-4NT”). Ezért egy elvet nem kell külön pároslicitre
és küzdelmi menetre leírni.

## A kényszertár

Az asztali pont-sávot is nyilvántartja (`ap_min`, `ap_max`), ha a szabály
azt ígéri (`ap:`). A mérlegelő lehetőség-sor (pl. „5 asztali ponttal is”)
nem tágítja az ígéretet, ha van rendes jelentés is.

## Példák

* `MOHA_FEDOKERESO`: 262 sor helyett 23 (a kulcslapkérdést az RKC elv adja).
* `GYORS_LASSU`, `MOHA_PC`: egy-egy sor az egész elvre.
* `RKC`: helyzeti elv — az összeemelt színből a 4-es szint +1 lépcső a
  kulcslapkérdés (kőr: 4♠, pikk: 4NT; minor gémforszban: 4m = ORKC);
  minor mellett a 4NT opcionális ászkérdés és szleminvit; bármely
  licitmenetben.

## A partner fedője a rövidségéből

A kényszertárban a partner tudott rövidsége (legfeljebb 1 lap egy külső
színben, pl. splinter) mellett a saját vesztőimből a rövidségén túliak
fedőnek számítanak: xxx a szingli mellett 2 fedő, a sikén mellett 3.


## Kizárásos következtetés (2026-10-02)

Amit a licitáló NEM mondott, az is információ. A kibic minden licitnél
(passznál is) a licitáló helyébe képzeli magát: a licit előtti tudás
szerint lehetséges kezeket sorsol, lefuttatja rájuk a licitáló rendszerét,
és megtartja azokat, amelyekkel ő is ugyanezt mondta volna. Ebből jön a
VALÓSZÍNŰ pontsáv és színhossz („a partner kontrázott, nem 2♦-t mondott:
nincs ötös kárója 11 ponttal”). Ehhez nem kell a tagadást kézzel leírni:
a szabályok sorrendje (prioritás) és a „minden más” sorok elég.

Következmény a rendszerírásnál: minél pontosabb a megállapodás (és minél
kevesebb a hézag), annál többet tud a kibic kiolvasni — a hézagos helyzet
(ahol a rendszer nem mond semmit) nem bizonyíték.
