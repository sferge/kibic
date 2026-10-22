"""
Mérlegelés: ahol a szabály véget ér, és dönteni kell.

MIÉRT. A rendszerleírás megmondja, MIKOR JÖN SZÓBA egy licit. Van, amikor
ezzel el is dőlt a dolog. És van, amikor nem — a büntető kontra a
tankönyvi példa. A forrás úgy fogalmaz, hogy "legalább az egyik színt
önállóan meg tudja büntetni", de ez nem feltétel, amit küszöbbel el
lehetne találni. Pontosabb megfogalmazásban:

    "biztosan elbukik, ÉS nekem ehhez megfelelő adum van"

— és a bukás nem az aduból jön, hanem a pár közös erejéből; az adu csak
az eszköz hozzá. A valódi kérdés pedig még ennél is tágabb:

    megéri-e jobban a kontrázott bukás írása, mint a saját
    kontraktusunké?

Ez döntés, nem szabály. A dolgunk nem az, hogy küszöbbe sűrítsük, hanem
hogy ÖSSZEMÉRJÜK a két kimenetelt a lehetséges leosztásokon.

A LÁNC:
    kényszertár  ->  mintavétel  ->  DDS  ->  pontozás  ->  várható írás
    (propagal)       (mintavetel)    (solver)  (pontozas)    (itt)

KÉT FONTOS FENNTARTÁS
---------------------
1. A DOUBLE DUMMY ELMOZDULHAT — DE NEM AZÉRT, AMIÉRT ELSŐRE GONDOLNÁNK.
   A DD tökéletes lejátszást ÉS tökéletes védekezést feltételez, és a
   valóságban egyik sem igaz: a felvevő is hibázik, a védelem is. Amit
   mérünk, az a KÉT HIBA EGYENLEGE. A gyűjteményen SZÍNBEN ez majdnem
   kioltja egymást (+0.03 ütés), SZANBAN nem (+0.30): ott a védelem
   feladata a nehezebb. A `Kalibracio` ezt a mért egyenleget viszi be;
   amíg nincs megmérve, nulla korrekcióval fut, és ezt meg is mondja.

2. IMP-BEN ÉS MP-BEN MÁS A HELYES DÖNTÉS. IMP-nél a várható
   IMP-különbség számít (a nagy tételek dominálnak); párosversenyen a
   NYERÉSI GYAKORISÁG (egy fél pont ugyanannyit ér, mint ötszáz). Ezért
   a modul mindkettőt kiszámolja, és nem választ helyetted.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from ..domain import Kontraktus, Leosztas, SZINEK, ULESEK, vonal
from ..domain.pontozas import imp, pontszam
from .helyzet import Allas

JELENTESEK = list(SZINEK) + ["NT"]


# --- A double dummy torzításának kalibrálása -------------------------

MIN_MINTA = 200
"""Ez alatt a cellaszám alatt nem hiszünk a saját mérésünknek, és a
durvább modellre esünk vissza. A gyűjteményen a kontrázott szan cellája
37 játszmából állt: ±0.24 ütés standard hibával az "eredménye" zaj,
amit korrekcióként használni rosszabb, mint nem korrigálni."""


@dataclass
class Kalibracio:
    """
    A DD-ütésszám és a VALÓDI ütésszám különbsége, kontextusonként.

    A kulcs: (kontrázott, szan-e). Pozitív eltolás azt jelenti, hogy a
    valóságban TÖBB ütést visz a felvevő, mint a DD szerint járna neki —
    vagyis a védelem hibázott.

    AZ ÁTLAG KEVÉS, ÉS EZT MEGMÉRTÜK. A gyűjteményen a kontrázott
    színkontraktusok eltolása +0.16 ütés, 0.84 szórással. Ha ezt
    átlagként adjuk a DD-ütéshez, a kerekítés megeszi: round(8 + 0.16)
    továbbra is 8, tehát a korrekció SOHA nem billent át egy ütést —
    miközben a védelem valójában elég gyakran hibázik egyet. Az átlagot
    hozzáadni rossz művelet.

    Ezért a kalibráció az ELTÉRÉS-ELOSZLÁST tartja (hány játszmában volt
    a különbség -2, -1, 0, +1 ...), és a szimuláció ebből HÚZ. Így a
    mintavétel nemcsak a lapok bizonytalanságát modellezi, hanem a
    lejátszásét és a védekezését is — és mindkettő adatból jön.

    MÉRT FŐ HATÁSOK (6440 játszmás gyűjtemény, 2026-09):
        szan  +0.264 ütés (7.5 szigma)   <- a DOMINÁNS
        kontra +0.126 ütés (2.9 szigma)
    Színben a felvevő és a védelem nagyjából egyforma gyakran hibázik
    (21% / 24%), ezért a nettó elmozdulás ott majdnem nulla. Szanban a
    védelem téved gyakrabban (20% / 37%) — a vak kijátszás dönt, és
    nincs adu, ami mentene.
    """
    eltolas: dict[tuple[bool, bool], float] = field(default_factory=dict)
    szoras: dict[tuple[bool, bool], float] = field(default_factory=dict)
    minta_db: dict[tuple[bool, bool], int] = field(default_factory=dict)
    eloszlas: dict[tuple[bool, bool], dict[int, int]] = \
        field(default_factory=dict)
    """(kontrázott, szan) -> {eltérés: hány játszmában}. Ebből húzunk."""

    @classmethod
    def betolt(cls, ut: str) -> "Kalibracio":
        """
        A `kibic.cli.ddtorzitas --mentes` által írt JSON beolvasása.
        A kulcs ott két számjegy: kontrázott + szan (pl. "10").
        """
        import json
        with open(ut, encoding="utf8") as f:
            d = json.load(f)

        def _kulcsok(resz):
            return {(bool(int(k[0])), bool(int(k[1]))): v
                    for k, v in (resz or {}).items()}

        eloszlas = {k: {int(e): int(n) for e, n in v.items()}
                    for k, v in _kulcsok(d.get("eloszlas")).items()}
        return cls(_kulcsok(d.get("eltolas")), _kulcsok(d.get("szoras")),
                   _kulcsok(d.get("minta_db")), eloszlas)

    @property
    def megmerve(self) -> bool:
        return bool(self.eltolas)

    @property
    def van_eloszlas(self) -> bool:
        return bool(self.eloszlas)

    # -- hierarchikus visszaesés --

    def _cella(self, kontrazott: bool, szan: bool) -> tuple[bool, bool] | None:
        """
        A használható legspecifikusabb cella. Ha a kérteben kevés a minta,
        előbb a kontra-bontást adjuk fel (az a gyengébb hatás), a szanét
        csak utána — mert a mérés szerint a szan a fontosabb.
        """
        for jelolt in ((kontrazott, szan), (False, szan), (kontrazott, False)):
            if self.minta_db.get(jelolt, 0) >= MIN_MINTA:
                return jelolt
        # Végső esetben bármi, aminek van elég mintája
        eleg = [k for k, n in self.minta_db.items() if n >= MIN_MINTA]
        return max(eleg, key=lambda k: self.minta_db[k]) if eleg else None

    def korrigal(self, dd_utes: float, kontrazott: bool,
                 szan: bool) -> float:
        """
        Az ÁTLAGOS eltolás. Megtartjuk, mert jelentésekhez és a
        várható-érték-számításhoz jó — de a szimulációban a `huz()`
        a helyes művelet, a fenti okból.
        """
        c = self._cella(kontrazott, szan)
        return dd_utes + (self.eltolas.get(c, 0.0) if c else 0.0)

    def huz(self, dd_utes: int, kontrazott: bool, szan: bool, rnd) -> int:
        """
        Egy KONKRÉT valószínű ütésszám: a DD-érték plusz egy eltérés,
        a mért eloszlásból húzva. Ez megy a szimulációba.
        """
        c = self._cella(kontrazott, szan)
        eo = self.eloszlas.get(c) if c else None
        if not eo:
            return dd_utes
        ertekek = list(eo)
        eltol = rnd.choices(ertekek, weights=[eo[e] for e in ertekek])[0]
        return max(0, min(13, dd_utes + eltol))

    def leiras(self) -> str:
        if not self.megmerve:
            return ("NINCS KALIBRÁLVA — a double dummy elfogultsága "
                    "korrigálatlan, a büntetés túlértékelt lehet.")
        sorok = []
        for (k, sz) in sorted(self.eltolas):
            v = self.eltolas[(k, sz)]
            db = self.minta_db.get((k, sz), 0)
            jel = "" if db >= MIN_MINTA else "  (kevés minta: összevonva)"
            sorok.append(f"{'kontrázott' if k else 'sima':11s} "
                         f"{'szan' if sz else 'szín':5s}: {v:+.2f} ütés "
                         f"({db} játszmából){jel}")
        if not self.van_eloszlas:
            sorok.append("Eloszlás nincs mentve — a szimuláció csak az "
                         "átlagot tudja használni, amit a kerekítés elnyel. "
                         "Futtasd újra a mérőt.")
        return "\n".join(sorok)


# --- Egy kimenetel értékelése ----------------------------------------

@dataclass
class Kimenetel:
    """Egy lehetséges végkifejlet a mintán kiértékelve."""
    cimke: str
    kontraktus: Kontraktus
    pontszamok: list[int] = field(default_factory=list)   # a MI vonalunknak

    @property
    def atlag(self) -> float:
        return statistics.mean(self.pontszamok) if self.pontszamok else 0.0

    @property
    def median(self) -> float:
        return statistics.median(self.pontszamok) if self.pontszamok else 0.0

    def __str__(self) -> str:
        return f"{self.cimke} [{self.kontraktus}]: átlag {self.atlag:+.0f}"


@dataclass
class Osszemeres:
    """Két kimenetel összevetése — a döntés két mértékkel."""
    a: Kimenetel
    b: Kimenetel
    kalibralva: bool = False

    @property
    def imp_kulonbseg(self) -> float:
        """
        Az `a` várható IMP-nyeresége a `b`-hez képest, leosztásonként.
        IMP-versenyen EZ a helyes mérték.
        """
        if not self.a.pontszamok:
            return 0.0
        return statistics.mean(
            imp(x - y) for x, y in zip(self.a.pontszamok, self.b.pontszamok))

    @property
    def nyeresi_arany(self) -> float:
        """
        Hányszor ad az `a` többet, mint a `b`. PÁROSVERSENYEN ez a helyes
        mérték: ott egy fél pont ugyanannyit ér, mint ötszáz.
        """
        if not self.a.pontszamok:
            return 0.0
        jo = sum(1 for x, y in zip(self.a.pontszamok, self.b.pontszamok)
                 if x > y)
        dontetlen = sum(1 for x, y in zip(self.a.pontszamok, self.b.pontszamok)
                        if x == y)
        return (jo + dontetlen / 2) / len(self.a.pontszamok)

    def osszefoglalo(self) -> str:
        s = [str(self.a), str(self.b),
             f"IMP-ben: {self.imp_kulonbseg:+.2f} / leosztás  "
             f"(a(z) {self.a.cimke!r} javára, ha pozitív)",
             f"MP-ben:  {self.nyeresi_arany:.0%} nyerési arány"]
        if not self.kalibralva:
            s.append("FIGYELEM: a DD-torzítás nincs kalibrálva — "
                     "a büntetés értéke felfelé torzít.")
        # Ahol a két mérték ELTÉR, ott van a döntés érdekes része.
        if (self.imp_kulonbseg > 0) != (self.nyeresi_arany > 0.5):
            s.append("A két mérték ELLENTÉTES irányba mutat: IMP-en és "
                     "párosversenyen más a helyes döntés.")
        return "\n".join(s)


# --- A fő összehasonlítás --------------------------------------------

def _dd(leosztas: Leosztas, tablak: dict | None = None) -> dict:
    if tablak is not None:
        return tablak
    from ..solver import dds
    return dds.dd_tabla(leosztas)


def _pont_nekunk(kontraktus: Kontraktus, utesek: int, beliallas: str,
                 mi_vonal: str) -> int:
    """A pontszám a MI vonalunk előjelével."""
    p = pontszam(kontraktus, utesek, beliallas)
    return p if vonal(kontraktus.felvevo) == mi_vonal else -p


def buntetes_vagy_sajat(allas: Allas, leosztasok: list[Leosztas],
                        dd_tablak: list[dict] | None = None,
                        kalibracio: Kalibracio | None = None,
                        max_sajat_szint: int = 5,
                        mag: int | None = None,
                        hatarido: float | None = None) -> Osszemeres:
    """
    A kontrázott bukás és a saját legjobb kontraktus összemérése.

    `allas`: a licithelyzet (az ellenfél kontraktusa ebből jön).
    `leosztasok`: a kényszertárból vett minta (motor/mintavetel.py).
    `dd_tablak`: előre kiszámolt DD-táblák, ha vannak.

    KORLÁT: a "saját legjobb kontraktus" itt a DD-tábla alapján legjobb,
    a jelenlegi szint fölött elérhető kontraktusunk. A valóságban oda el
    is kellene jutnunk a licittel, és az sem biztos. Ez tehát a saját
    alternatíva FELSŐ becslése — vagyis a büntetés ellen dolgozik, ami
    a DD elfogultságát némileg ellensúlyozza. Mindkét torzítást jobb
    ismerni, mint kioltottnak hinni.

    Ha a kalibrációnak van ELOSZLÁSA, a DD-ütésszám nem az átlaggal
    tolódik el, hanem a mért eloszlásból húzunk hozzá egy eltérést. A
    húzás leosztásonként és (ülés, szín) párosonként EGY — ugyanaz a
    lejátszás áll a 3H és a 4H mögött, csak a szerződés más. Ha
    kontraktusonként húznánk, a jelöltek közötti összehasonlításba zajt
    kevernénk.
    """
    import random
    rnd = random.Random(mag)
    kal = kalibracio or Kalibracio()
    mi = vonal(allas.ules)
    beli = allas.beliallas

    if allas._legmagasabb is None or allas._legmagasabb_ules is None:
        raise ValueError("Nincs mit kontrázni: még nem hangzott el szín-licit")
    szint, szin = allas._legmagasabb
    ok_felvevo = allas._legmagasabb_ules
    if vonal(ok_felvevo) == mi:
        raise ValueError("A legmagasabb licit a MI vonalunké")

    ovek = Kontraktus(szint, szin, "X", ok_felvevo)
    buntetes = Kimenetel("kontra és bent hagyjuk", ovek)

    # A saját jelöltek: minden kontraktus a jelenlegi licit FÖLÖTT,
    # a mi vonalunk felvevőjével.
    jeloltek: dict[tuple[int, str, str], Kimenetel] = {}

    import time
    for i, lo in enumerate(leosztasok):
        # IDŐKERET (2026-10-20): ha letelt, az addig feldolgozott mintán döntünk
        if hatarido is not None and i > 0 and time.monotonic() > hatarido:
            break
        tabla = _dd(lo, dd_tablak[i] if dd_tablak else None)

        def _utes(felvevo: str, sz: str, kontrazott: bool) -> int:
            """A várható ütésszám: DD + a mért eltérés-eloszlásból húzva."""
            dd = int(tabla[felvevo][sz])
            if kal.van_eloszlas:
                return kal.huz(dd, kontrazott, sz == "NT", rnd)
            return max(0, min(13, round(
                kal.korrigal(dd, kontrazott, sz == "NT"))))

        # a) a kontrázott kontraktusuk
        buntetes.pontszamok.append(
            _pont_nekunk(ovek, _utes(ok_felvevo, szin, True), beli, mi))

        # b) a mi lehetőségeink — (ülés, szín) párosonként EGY húzás,
        #    amin az összes szint osztozik
        for u in (allas.ules, allas.partner):
            for sz in JELENTESEK:
                mi_utes = _utes(u, sz, False)
                for sznt in range(1, max_sajat_szint + 1):
                    if not _magasabb(sznt, sz, szint, szin):
                        continue
                    kulcs = (sznt, sz, u)
                    k = jeloltek.get(kulcs)
                    if k is None:
                        k = Kimenetel(f"{u} játssza", Kontraktus(sznt, sz, "", u))
                        jeloltek[kulcs] = k
                    k.pontszamok.append(
                        _pont_nekunk(k.kontraktus, mi_utes, beli, mi))

    if not jeloltek:
        raise ValueError("Nincs elérhető saját kontraktus a jelenlegi szint "
                         "fölött")

    # A kontraktust EGYSZER választjuk, nem leosztásonként: ezért az
    # átlag dönt, nem a mintánkénti maximum. (A mintánkénti maximum a
    # "kettős könyvelés" klasszikus hibája volna.)
    sajat = max(jeloltek.values(), key=lambda k: k.atlag)
    sajat.cimke = f"saját kontraktus, {sajat.cimke}"
    return Osszemeres(buntetes, sajat, kalibralva=kal.megmerve)


def _magasabb(szint: int, szin: str, mint_szint: int, mint_szin: str) -> bool:
    if szint != mint_szint:
        return szint > mint_szint
    return JELENTESEK.index(szin) > JELENTESEK.index(mint_szin)


# --- Végkontraktus-választás (a mérlegelő sorok közül) -----------------

def _felvevo(allas: Allas, szin: str, mi_vonal: str) -> str | None:
    """A vonalon az első, aki ezt a jelentést (színt / szant) mondta."""
    for e in allas.licitek:
        u = e.get("ules")
        if u is None or vonal(u) != mi_vonal:
            continue
        szint, sz = allas._bont(str(e.get("licit", "")).upper())
        if szint is not None and sz == szin:
            return u
    return None


def vegkontraktus_valasztas(allas: Allas, leosztasok: list[Leosztas],
                            licitek: list[str],
                            dd_tablak: list[dict] | None = None,
                            kalibracio: Kalibracio | None = None,
                            mag: int | None = None,
                            hatarido: float | None = None) -> list[Kimenetel]:
    """
    Melyik VÉGKONTRAKTUS a jobb a jelölt licitek közül? (Pl. P/C után:
    passz = a 3M marad, 4m = javítás.) A szerkesztő: „az dönt, melyiknek
    nagyobb a teljesítési esélye — hány plusz ütés szerezhető lopással,
    mennyire fenyeget, hogy a magas lapjainkat lopják —, NEM az aduk
    száma”. Ezt a DD-ütésszám méri a mintán, a pontozás pedig azt, hogy
    a 3M-hez 9, a 4m-hez 10 ütés kell.

    `licitek`: "P" (a jelenlegi kontraktus marad) vagy szín-/szanlicit
    (azt a vonalunkon az játssza, aki a jelentést először mondta). A
    kontra itt nem jelölt. Visszaad: kimenetelek a licitek sorrendjében.
    """
    import random
    rnd = random.Random(mag)
    kal = kalibracio or Kalibracio()
    mi = vonal(allas.ules)
    beli = allas.beliallas

    kimenetelek: list[Kimenetel] = []
    for licit in licitek:
        if licit == "P":
            if allas._legmagasabb is None:
                raise ValueError("Passz: nincs kontraktus")
            szint, szin = allas._legmagasabb
            felvevo = _felvevo(allas, szin, vonal(allas._legmagasabb_ules)) \
                or allas._legmagasabb_ules
            kontra = ("XX" if allas._rekontra else
                      "X" if allas._kontra != "NINCS" else "")
        else:
            szint, szin = allas._bont(licit)
            if szint is None:
                raise ValueError(f"Nem kontraktus-jelölt: {licit!r}")
            felvevo = _felvevo(allas, szin, mi) or allas.ules
            kontra = ""
        kimenetelek.append(Kimenetel(licit, Kontraktus(szint, szin, kontra, felvevo)))

    import time
    for i, lo in enumerate(leosztasok):
        if hatarido is not None and i > 0 and time.monotonic() > hatarido:
            break                                  # időkeret: a feldolgozott mintán döntünk
        tabla = _dd(lo, dd_tablak[i] if dd_tablak else None)
        huzas: dict[tuple[str, str, bool], int] = {}   # (felvevő, szín, kontra) -> ütés
        for k in kimenetelek:
            kk = k.kontraktus
            kulcs = (kk.felvevo, kk.szin, bool(kk.kontra))
            if kulcs not in huzas:
                dd = int(tabla[kk.felvevo][kk.szin])
                huzas[kulcs] = (kal.huz(dd, bool(kk.kontra), kk.szin == "NT", rnd)
                                if kal.van_eloszlas else
                                max(0, min(13, round(kal.korrigal(
                                    dd, bool(kk.kontra), kk.szin == "NT")))))
            k.pontszamok.append(_pont_nekunk(kk, huzas[kulcs], beli, mi))
    return kimenetelek
