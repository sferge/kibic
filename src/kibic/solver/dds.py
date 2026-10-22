"""
DDS-kötés (double dummy solver) az `endplay` csomagra.

Ez a modul a szimbolikus mag és a solver közötti határréteg. Kifelé
kizárólag domain-objektumokkal (Leosztas, Kontraktus) dolgozik, befelé
endplay-típusokkal — így ha egyszer más solverre váltunk, csak ez a fájl
változik.

Két szolgáltatást ad:

1. TELJES TÁBLA — `dd_tabla(leosztas)`: mind a 20 érték (4 irány × 5 szín),
   vagyis hány ütést visz double dummy szerint az adott felvevő az adott
   színben. Ez tölti a `leosztas.dds_utesek` gyorsítótárat.

2. MARADÉK POZÍCIÓ — `maradek_utesek(...)`: egy félbehagyott lejátszásból
   (terítés) kiindulva hány ütést visz még a felvevő. Ez teszi
   ellenőrizhetővé a 2333 terítéses partit.

FONTOS: a `--onteszt` kapcsolóval futtatható önellenőrzés. Az endplay
API-jának előjel- és perspektíva-konvencióit ez igazolja ismert
végállásokon, MIELŐTT több ezer leosztásra engednénk a modult.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..domain import Lap, Leosztas, SZINEK, ULESEK, kovetkezo_ules, vonal
from ..domain import Kontraktus

# --- endplay-leképezés ------------------------------------------------

_SZIN_ENDPLAY = {"S": "spades", "H": "hearts", "D": "diamonds",
                 "C": "clubs", "NT": "nt"}
_ULES_ENDPLAY = {"N": "north", "E": "east", "S": "south", "W": "west"}
_BELI_ENDPLAY = {"NONE": "none", "NS": "ns", "EW": "ew", "ALL": "both"}


def _betolt():
    """Az endplay lusta betöltése, beszédes hibaüzenettel."""
    try:
        from endplay.types import Deal, Denom, Player, Vul  # noqa
        from endplay.dds import calc_dd_table, calc_all_tables, solve_board, par
    except ImportError as e:
        raise ImportError(
            "Az endplay csomag nem érhető el. Telepítés: pip install endplay"
        ) from e
    return dict(Deal=Deal, Denom=Denom, Player=Player, Vul=Vul,
                calc_dd_table=calc_dd_table, calc_all_tables=calc_all_tables,
                solve_board=solve_board, par=par)


def _denom(ep, szin: str):
    return getattr(ep["Denom"], _SZIN_ENDPLAY[szin])


def _player(ep, ules: str):
    return getattr(ep["Player"], _ULES_ENDPLAY[ules])


def _ules_from_player(p) -> str:
    """
    endplay Player -> 'N'/'E'/'S'/'W'.

    A Player IntEnum, ezért a str() a SZÁMOT adja ('1'), nem a nevet.
    Több úton próbálkozunk, hogy verzióváltásra se törjön el.
    """
    nev = getattr(p, "name", None)
    if isinstance(nev, str):
        forditott = {v: k for k, v in _ULES_ENDPLAY.items()}
        if nev.lower() in forditott:
            return forditott[nev.lower()]
    try:
        # endplay sorrend: north=0, east=1, south=2, west=3
        return ULESEK[int(p) % 4]
    except (TypeError, ValueError):
        pass
    raise ValueError(f"Ismeretlen endplay Player: {p!r}")


def _utes_gyoztes(lapok: list[tuple[str, Lap]], adu: str | None) -> str:
    """
    Egy ütés győztese. Szándékos, kicsi duplikáció a visszajátszóból:
    a solver-réteg nem függhet a motor-rétegtől (mindkettő csak a
    domain-magra épül). Egyben kereszt-ellenőrzés is: ha a két
    implementáció eltérne, a claim-ellenőrzés kimutatná.
    """
    gyoztes, legjobb = lapok[0]
    for ules, lap in lapok[1:]:
        if lap.szin == legjobb.szin:
            if lap.rang > legjobb.rang:
                gyoztes, legjobb = ules, lap
        elif adu and lap.szin == adu and legjobb.szin != adu:
            gyoztes, legjobb = ules, lap
    return gyoztes


# --- 1. Teljes DD-tábla ----------------------------------------------

def dd_tabla(leosztas: Leosztas) -> dict[str, dict[str, int]]:
    """
    Mind a 20 érték. Visszaad: {ules: {szin: utesszam}}, ahol a `szin`
    kulcsok 'S','H','D','C','NT'.
    """
    ep = _betolt()
    d = ep["Deal"](leosztas.pbn("N"))
    t = ep["calc_dd_table"](d)
    return {u: {sz: int(t[_denom(ep, sz), _player(ep, u)])
                for sz in list(SZINEK) + ["NT"]}
            for u in ULESEK}


def dd_tablak(leosztasok: list[Leosztas], koteg: int = 32
              ) -> list[dict[str, dict[str, int]]]:
    """
    Kötegelt kiszámítás — lényegesen gyorsabb, mint egyesével.
    A DDS egy hívásban legfeljebb 32 táblát kezel, ezért kötegelünk.
    """
    ep = _betolt()
    eredmeny: list[dict[str, dict[str, int]]] = []
    szinek = list(SZINEK) + ["NT"]
    for i in range(0, len(leosztasok), koteg):
        darab = leosztasok[i:i + koteg]
        dealek = [ep["Deal"](l.pbn("N")) for l in darab]
        tablak = ep["calc_all_tables"](dealek)
        for t in tablak:
            eredmeny.append({u: {sz: int(t[_denom(ep, sz), _player(ep, u)])
                                 for sz in szinek}
                             for u in ULESEK})
    return eredmeny


def par_eredmeny(leosztas: Leosztas) -> tuple[int, str]:
    """
    Par-eredmény: az a pontszám, amit tökéletes licit mellett elérnének.
    Visszaad: (pontszam_ns, leiras). A licitminőség fő metrikája ehhez mér.
    """
    ep = _betolt()
    d = ep["Deal"](leosztas.pbn("N"))
    t = ep["calc_dd_table"](d)
    vul = getattr(ep["Vul"], _BELI_ENDPLAY[leosztas.beliallas])
    p = ep["par"](t, vul, _player(ep, leosztas.oszto))
    # Az endplay ParList `score` mezője É-D szemszögéből előjelezett
    pont = int(getattr(p, "score", 0))
    leiras = "; ".join(str(k) for k in p) if hasattr(p, "__iter__") else str(p)
    return pont, leiras[:50]


# --- 2. Maradék pozíció (terítés-ellenőrzés) -------------------------

@dataclass
class MaradekEredmeny:
    lejatszott_utes: int         # hány teljes ütés ment le
    felvevo_eddig: int           # ebből a felvevőé
    felvevo_meg: int             # double dummy szerint még ennyit visz
    felvevo_osszesen: int        # a kettő összege
    hiba: str | None = None


def maradek_utesek(leosztas: Leosztas, lapok: list[str],
                   kontraktus: Kontraktus) -> MaradekEredmeny:
    """
    Egy félbehagyott lejátszás folytatásának double dummy kiértékelése.

    `lapok`: a ténylegesen kijátszott lapok IDŐRENDBEN (a visszajátszó
    kimenete). A pozíciót az endplay saját `play()` metódusával állítjuk
    elő — ez egyben kereszt-ellenőrzés a saját visszajátszónkra.
    """
    ep = _betolt()
    d = ep["Deal"](leosztas.pbn("N"))
    d.trump = _denom(ep, kontraktus.szin)
    kijatszo = kovetkezo_ules(kontraktus.felvevo)
    d.first = _player(ep, kijatszo)
    adu = None if kontraktus.szin == "NT" else kontraktus.szin

    # A pozíció felépítése az endplay-ben, ÉS párhuzamosan a saját
    # ütésszámolásunk — így nem függünk az endplay állapot-API-jától.
    soron = kijatszo
    utes_kezdo = kijatszo
    aktualis: list[tuple[str, Lap]] = []
    felvevo_eddig = 0
    teljes_utes = 0

    for jeloles in lapok:
        lap = Lap.parse(jeloles)
        try:
            d.play(f"{lap.szin}{lap.ertek}")
        except Exception as e:                       # noqa: BLE001
            return MaradekEredmeny(teljes_utes, felvevo_eddig, 0, felvevo_eddig,
                                   hiba=f"Lejátszás nem folytatható: {e}")
        aktualis.append((soron, lap))
        soron = kovetkezo_ules(soron)
        if len(aktualis) == 4:
            teljes_utes += 1
            gy = _utes_gyoztes(aktualis, adu)
            if vonal(gy) == vonal(kontraktus.felvevo):
                felvevo_eddig += 1
            utes_kezdo = soron = gy
            aktualis = []

    # A folyamatban lévő (befejezetlen) ütés is a MARADÉKHOZ tartozik:
    # a `teljes_utes` csak a lezárt ütéseket számolja, ezért a képlet
    # ütés közben is helyes. A DDS a részleges ütést kezeli.
    maradek = 13 - teljes_utes
    if maradek == 0:
        return MaradekEredmeny(teljes_utes, felvevo_eddig, 0, felvevo_eddig)

    # A soron lévő OLDAL maximuma double dummy szerint
    sb = dict(ep["solve_board"](d))
    if not sb:
        return MaradekEredmeny(teljes_utes, felvevo_eddig, 0, felvevo_eddig,
                               hiba="A solver nem adott megoldást")
    legjobb = max(int(v) for v in sb.values())

    try:
        soron_ules = _ules_from_player(d.curplayer)
    except ValueError:
        soron_ules = soron          # a saját számolásunk a tartalék

    if vonal(soron_ules) == vonal(kontraktus.felvevo):
        felvevo_meg = legjobb
    else:
        felvevo_meg = maradek - legjobb

    return MaradekEredmeny(teljes_utes, felvevo_eddig, felvevo_meg,
                           felvevo_eddig + felvevo_meg)


def teriteheto(leosztas: Leosztas, lapok: list[str],
               kontraktus: Kontraktus) -> bool:
    """
    Teríthető-e a maradék? A szabály szerint a terítésnek a lapok BÁRMELY
    elhelyezkedése ellen állnia kell — a licitből származó következtetések
    nem számítanak. Itt a szűkebb, korrekt kérdést tesszük fel: az ismert
    (nyílt) állásban minden maradék ütés a felvevőé-e.

    FIGYELEM: ez az importált partik ELLENŐRZÉSÉRE való, ahol mind a négy
    kéz ismert. A saját játék közbeni terítés-döntéshez ez NEM elég —
    ott a fizikailag lehetséges elosztások MINDEGYIKÉN kell állnia,
    egyetlen, elosztásfüggetlen vonallal.
    """
    e = maradek_utesek(leosztas, lapok, kontraktus)
    if e.hiba:
        return False
    return e.felvevo_meg == 13 - e.lejatszott_utes


# --- 3. Laponkénti elemzés (hibaelemzés emberi partikhoz) ------------

@dataclass
class LapErtekeles:
    lap: str
    utesek: int           # a KIJÁTSZÓ oldala ennyi ütést visz a folytatásban
    felvevo_osszesen: int # a felvevő végső ütésszáma, ha ezt a lapot hívja
    legjobb: bool         # ez-e (az egyik) legjobb választás
    veszteseg: int        # hány ütést ad fel a legjobbhoz képest


def lap_elemzes(leosztas: Leosztas, lapok: list[str],
                kontraktus: Kontraktus) -> list[LapErtekeles]:
    """
    A soron lévő játékos MINDEN játszható lapjára megmondja, mi lenne az
    eredmény tökéletes folytatás mellett.

    Ez az, amire egy hibaelemző szolgáltatásnak szüksége van: "melyik
    lapot kellett volna hívni, és mennyibe került a tévedés".

    `lapok`: az eddig kijátszott lapok IDŐRENDBEN (üres lista = a
    lejátszás eleje). A pozíció bárhol lehet, ütés közben is.

    FIGYELEM: ez DOUBLE DUMMY elemzés — nyílt lapokkal. Azt mondja meg,
    mi lett volna a legjobb, ha mindenki mindent lát. Emberi hiba
    megítélésére ez FELSŐ korlát: egy "hibának" látszó lap lehet teljesen
    ésszerű az akkori információ birtokában. A tényleges hibaelemzéshez
    a rejtett kezekből mintavételezés kellene.
    """
    ep = _betolt()
    d = ep["Deal"](leosztas.pbn("N"))
    d.trump = _denom(ep, kontraktus.szin)
    kijatszo = kovetkezo_ules(kontraktus.felvevo)
    d.first = _player(ep, kijatszo)
    adu = None if kontraktus.szin == "NT" else kontraktus.szin

    soron = utes_kezdo = kijatszo
    aktualis: list[tuple[str, Lap]] = []
    felvevo_eddig = 0
    teljes_utes = 0

    for jeloles in lapok:
        lap = Lap.parse(jeloles)
        d.play(f"{lap.szin}{lap.ertek}")
        aktualis.append((soron, lap))
        soron = kovetkezo_ules(soron)
        if len(aktualis) == 4:
            teljes_utes += 1
            gy = _utes_gyoztes(aktualis, adu)
            if vonal(gy) == vonal(kontraktus.felvevo):
                felvevo_eddig += 1
            utes_kezdo = soron = gy
            aktualis = []

    maradek = 13 - teljes_utes
    if maradek == 0:
        return []

    try:
        soron_ules = _ules_from_player(d.curplayer)
    except ValueError:
        soron_ules = soron
    soron_a_felvevoe = vonal(soron_ules) == vonal(kontraktus.felvevo)

    sb = dict(ep["solve_board"](d))
    if not sb:
        return []

    nyers: list[tuple[str, int]] = []
    for lap, utesek in sb.items():
        jel = str(lap).replace(" ", "").upper()
        # az endplay Card str-je "SA" vagy "♠A" alakú lehet
        for jelkod, betu in (("♠", "S"), ("♥", "H"), ("♦", "D"), ("♣", "C")):
            jel = jel.replace(jelkod, betu)
        nyers.append((jel[:2], int(utesek)))

    legtobb = max(u for _, u in nyers)
    ki: list[LapErtekeles] = []
    for jel, u in nyers:
        felvevo_meg = u if soron_a_felvevoe else maradek - u
        ki.append(LapErtekeles(
            lap=jel, utesek=u,
            felvevo_osszesen=felvevo_eddig + felvevo_meg,
            legjobb=(u == legtobb), veszteseg=legtobb - u))
    ki.sort(key=lambda x: (-x.utesek, x.lap))
    return ki


# --- Önteszt ----------------------------------------------------------

def onteszt() -> int:
    """
    Az endplay API-konvencióinak igazolása ismert állásokon.
    Futtatás: python -m kibic.solver.dds --onteszt
    """
    hibak = 0

    def allit(nev: str, kapott, vart) -> None:
        nonlocal hibak
        rendben = kapott == vart
        hibak += 0 if rendben else 1
        jel = "OK  " if rendben else "HIBA"
        print(f"  [{jel}] {nev}: kapott={kapott}, várt={vart}")

    print("=== 1. Triviális leosztás: északnál minden magas lap ===")
    # Észak: minden pikk + minden kőr; adu pikk esetén mindent visz.
    kezek = ("N:AKQJT98765432... "
             ".AKQJT98765432.. "
             "..AKQJT98765432. "
             "...AKQJT98765432")
    try:
        l = Leosztas.pbn_bol(kezek, "N", "NONE")
    except ValueError as e:
        print(f"  A tesztleosztás érvénytelen: {e}")
        return 1
    t = dd_tabla(l)
    # Észak tartja mind a 13 pikket. Felvevőként ő is, a PARTNERE (dél) is
    # 13 ütést visz pikkben — a felvevő a partnere lapjával játszik.
    allit("észak pikkben (adu = teljes szín)", t["N"]["S"], 13)
    allit("dél pikkben (a partner tartja az adukat)", t["S"]["S"], 13)
    allit("kelet pikkben (az ellenfélé minden adu)", t["E"]["S"], 0)
    # Szanban nyugat viszi az összes treffet, ezért É-D nulla.
    allit("észak szanban", t["N"]["NT"], 0)

    print("\n=== 2. Kötegelt számítás egyezik az egyesével számolttal ===")
    t2 = dd_tablak([l, l])
    allit("koteg[0] == egyesevel", t2[0], t)
    allit("koteg[1] == egyesevel", t2[1], t)

    print("\n=== 3. Maradék pozíció: üres lejátszás == teljes tábla ===")
    k = Kontraktus(4, "S", "", "N")
    e = maradek_utesek(l, [], k)
    if e.hiba:
        print(f"  HIBA: {e.hiba}")
        hibak += 1
    else:
        allit("lejátszás nélkül a felvevő ütései", e.felvevo_osszesen,
              t["N"]["S"])

    print("\n=== 3b. Maradék pozíció 4 lap után ===")
    # A kijátszó a felvevőtől BALRA ül: 4S felvevő = észak -> kelet kezd.
    # Keletnek csak kőrje van; dél kárót, nyugat treffet tesz, észak lop.
    try:
        e2 = maradek_utesek(l, ["HA", "D2", "C2", "S2"], k)
        if e2.hiba:
            print(f"  HIBA: {e2.hiba}")
            hibak += 1
        else:
            allit("1 ütés ment le", e2.lejatszott_utes, 1)
            allit("abból a felvevőé (észak lopott!)", e2.felvevo_eddig, 1)
            allit("a felvevő még hozza a maradékot", e2.felvevo_meg, 12)
    except Exception as ex:                          # noqa: BLE001
        print(f"  HIBA: {ex}")
        hibak += 1

    print("\n=== 4. Par-eredmény lefut ===")
    try:
        pont, leiras = par_eredmeny(l)
        print(f"  [OK  ] par: {pont} ({leiras})")
    except Exception as ex:                          # noqa: BLE001
        print(f"  [HIBA] par: {ex}")
        hibak += 1

    print(f"\n{'MINDEN TESZT RENDBEN' if not hibak else f'{hibak} HIBA'}")
    return hibak


if __name__ == "__main__":
    import sys
    if "--onteszt" in sys.argv:
        raise SystemExit(onteszt())
    print(__doc__)
