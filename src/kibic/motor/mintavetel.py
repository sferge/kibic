"""
Mintavétel a kényszertárból: "milyen lapok LEHETNEK a többieknél?"

Ez a híd a következtetés és a mérés között. A kényszertár (motor/propagal.py)
azt mondja meg, mit ígértek a licitjeikkel; ez a modul abból ELOSZTÁSOKAT
készít, amelyeken már futtatható a solver és a pontozás.

MIÉRT KELL. Vannak döntések, amelyeket nem lehet küszöbbel eltalálni. A
büntető kontra ilyen: nem azért kontrázunk, mert négy adunk van, hanem
mert a kontrázott bukás írása várhatóan többet ér, mint a saját
kontraktusunké. Ehhez a kettőt ÖSSZE KELL MÉRNI — és ehhez kellenek a
lehetséges leosztások.

A MÓDSZER. Tiszta elfogadás-elutasítás (keverj, ossz, ellenőrizd) szoros
kényszerek mellett reménytelenül lassú. Ezért három lépés:

  1. HOSSZVEKTOR sorsolása. Színenként annyi lapot osztunk szét, amennyi
     maradt, játékosonként 13-at, a min/max korlátokon belül. Kis
     állapottér, gyorsan mintavehető.
  2. LAPKIOSZTÁS a hosszak szerint, színenként véletlenül.
  3. JAVÍTÓ CSERÉK a pont-kényszerekre. Aki alatta van a minimumának,
     annak adunk egy figurát attól, aki fölötte van a maximumának —
     SZÍNEN BELÜL, hogy a hosszak ne sérüljenek.

Ha a javítás nem konvergál, eldobjuk és újrapróbáljuk. A sikertelen
próbák száma visszajelzés: ha nagyon magas, a kényszertár
ellentmondásos vagy túl szűk — ezt jobb tudni, mint csendben rossz
mintán mérni.

MIT NEM TUD. A kényszertár a "mi LEHET" tára; az itteni mintavétel
EGYENLETES a lehetséges kezeken. Hogy melyik VALÓSZÍNŰBB, az az
ágensprofil dolga — az súlyozza majd ezt a mintát, nem helyettesíti.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..domain import ERTEKELOK, LAPOK, SZINEK, ULESEK, Kez, Lap, Leosztas
from .helyzet import Igeret

# Alapértelmezett pont-metrika. NEM beégetett képlet: az `ertekelo`
# táblából jövő bármelyik metrika kódja megadható helyette.
ALAP_METRIKA = "HCP"


class MintavetelHiba(ValueError):
    pass


@dataclass
class Minta:
    """A mintavétel eredménye és a minősége."""
    leosztasok: list[Leosztas] = field(default_factory=list)
    probak: int = 0
    elutasitva: int = 0
    torzitott: bool = False
    """Igaz, ha az irányított eljárásra kellett visszaesni. A minta
    ilyenkor NEM egyenletes a lehetséges kezeken — a belőle számolt
    várható érték óvatosan kezelendő."""

    @property
    def hatekonysag(self) -> float:
        return len(self.leosztasok) / self.probak if self.probak else 0.0

    def osszefoglalo(self) -> str:
        s = (f"{len(self.leosztasok)} leosztás {self.probak} próbából "
             f"({self.hatekonysag:.0%})")
        return s + " — TORZÍTOTT minta" if self.torzitott else s


def _megfelel(kezek: dict[str, list], tar: dict[str, Igeret],
              metrika: str) -> bool:
    """Teljesíti-e a kiosztás a kényszertárat? (Az elutasításos ághoz.)"""
    for u, lapok in kezek.items():
        ig = tar[u]
        kez = Kez(frozenset(lapok))
        for sz in SZINEK:
            lo, hi = ig.hossz(sz)
            if not lo <= kez.hossz(sz) <= hi:
                return False
        if not ig.pont_min <= _pont(kez, metrika) <= ig.pont_max:
            return False
    return True


# --- 1. lépés: hosszvektor -------------------------------------------

def _hossz_korlatok(ig: Igeret, szin: str, keszlet: int) -> tuple[int, int]:
    lo, hi = ig.hossz(szin)
    return (max(0, lo), min(hi, keszlet, 13))


def _hosszvektor(ulesek: list[str], keszlet: dict[str, int],
                 tar: dict[str, Igeret], rnd: random.Random,
                 max_proba: int = 400) -> dict[str, dict[str, int]] | None:
    """
    Színenként szétosztja a maradék lapokat a három ülés között úgy, hogy
    minden ülésnek 13 lapja legyen és a korlátok teljesüljenek.

    Sorsolás + javítás: először a minimumokat adjuk ki, majd a maradékot
    véletlenül szórjuk szét azokra, akiknél még van hely.
    """
    for _ in range(max_proba):
        vektor = {u: {sz: 0 for sz in SZINEK} for u in ulesek}
        jo = True

        # A színek sorrendje VÉLETLEN. Fix sorrendnél az utoljára
        # kiosztott szín rendszeresen az marad, amire már nincs hely —
        # a treff például feltűnően gyakran lett sikén. Az ilyen
        # torzítás csendben rossz várható értéket ad.
        szinsor = list(SZINEK)
        rnd.shuffle(szinsor)

        for sz in szinsor:
            maradek = keszlet[sz]
            for u in ulesek:
                lo, hi = _hossz_korlatok(tar[u], sz, keszlet[sz])
                if lo > hi:
                    return None            # ellentmondásos kényszer
                vektor[u][sz] = lo
                maradek -= lo
            if maradek < 0:
                jo = False
                break
            # A maradék szétszórása, a MÉG SZABAD HELYEK arányában.
            # Egyenletes választás mellett az a kéz telne meg elsőként,
            # amelyiknek amúgy is kevés helye van.
            while maradek > 0:
                jeloltek, sulyok = [], []
                for u in ulesek:
                    felso = _hossz_korlatok(tar[u], sz, keszlet[sz])[1]
                    hely = min(felso - vektor[u][sz],
                               13 - sum(vektor[u].values()))
                    if hely > 0:
                        jeloltek.append(u)
                        sulyok.append(hely)
                if not jeloltek:
                    jo = False
                    break
                vektor[rnd.choices(jeloltek, weights=sulyok)[0]][sz] += 1
                maradek -= 1
            if not jo:
                break

        if jo and all(sum(vektor[u].values()) == 13 for u in ulesek):
            return vektor
    return None


# --- 2-3. lépés: lapok és pontjavítás --------------------------------

def _pont(kez: Kez, metrika: str) -> float:
    fv = ERTEKELOK.get(metrika)
    if fv is None:
        raise MintavetelHiba(
            f"Ismeretlen metrika: {metrika!r}. Betöltötted az értékelőket "
            "az adatbázisból (domain.ertekelo.betolt_adatbazisbol)?")
    return float(fv(kez))


def _kioszt(vektor: dict[str, dict[str, int]], keszlet_lapok: dict[str, list],
            rnd: random.Random) -> dict[str, list]:
    kezek = {u: [] for u in vektor}
    for sz in SZINEK:
        lapok = list(keszlet_lapok[sz])
        rnd.shuffle(lapok)
        i = 0
        for u in vektor:
            db = vektor[u][sz]
            kezek[u].extend(lapok[i:i + db])
            i += db
    return kezek


def _javit(kezek: dict[str, list], tar: dict[str, Igeret], metrika: str,
           rnd: random.Random, max_lepes: int = 60) -> bool:
    """
    Pont-kényszerek teljesítése SZÍNEN BELÜLI cserékkel, hogy a
    hosszvektor sértetlen maradjon.
    """
    ulesek = list(kezek)
    for _ in range(max_lepes):
        pontok = {u: _pont(Kez(frozenset(kezek[u])), metrika) for u in ulesek}
        kicsi = [u for u in ulesek if pontok[u] < tar[u].pont_min]
        nagy = [u for u in ulesek if pontok[u] > tar[u].pont_max]
        if not kicsi and not nagy:
            return True

        # Kitől kihez vigyünk értéket?
        ad = nagy[0] if nagy else max(ulesek, key=lambda u: pontok[u])
        kap = kicsi[0] if kicsi else min(ulesek, key=lambda u: pontok[u])
        if ad == kap:
            return False

        csere = _legjobb_csere(kezek[ad], kezek[kap], rnd)
        if csere is None:
            return False
        magas, alacsony = csere
        kezek[ad].remove(magas)
        kezek[kap].remove(alacsony)
        kezek[ad].append(alacsony)
        kezek[kap].append(magas)
    return False


def _legjobb_csere(adó: list, kapó: list, rnd: random.Random):
    """
    Egy színen belüli lappár, ahol az `adó` magasabb lapot ad, mint amit
    visszakap. A színen belüliség tartja meg a hosszvektort.
    """
    jeloltek = []
    for sz in SZINEK:
        a = [l for l in adó if l.szin == sz]
        k = [l for l in kapó if l.szin == sz]
        for x in a:
            for y in k:
                if x.rang > y.rang:
                    jeloltek.append((x.rang - y.rang, x, y))
    if not jeloltek:
        return None
    # A legnagyobb lépések közül véletlenül — különben minden minta
    # ugyanabba a sarokba konvergálna.
    jeloltek.sort(key=lambda t: -t[0])
    _, x, y = rnd.choice(jeloltek[:max(3, len(jeloltek) // 4)])
    return (x, y)


# --- Fő belépő --------------------------------------------------------

def mintavetel(sajat: Kez, ules: str, kenyszertar: dict[str, Igeret],
               db: int = 50, beliallas: str = "NONE",
               metrika: str = ALAP_METRIKA, mag: int | None = None,
               max_proba_szorzo: int = 40,
               teritő: tuple[str, Kez] | None = None) -> Minta:
    """
    `db` darab leosztás, amelyeken a saját lapunk fix, a többi kéz pedig
    kielégíti a kényszertárat.

    `teritő`: ha a felvevő terítése már látható, (ülés, kéz) alakban —
    ilyenkor csak két kezet kell kitalálni, és a minta sokkal élesebb.
    """
    rnd = random.Random(mag)
    ismert = {ules: sajat}
    if teritő:
        ismert[teritő[0]] = teritő[1]
    ulesek = [u for u in ULESEK if u not in ismert]

    # A még ki nem osztott lapok színenként
    kiosztott = {l for k in ismert.values() for l in k.lapok}
    keszlet_lapok = {sz: [Lap(sz, e) for e in LAPOK
                          if Lap(sz, e) not in kiosztott]
                     for sz in SZINEK}
    keszlet = {sz: len(keszlet_lapok[sz]) for sz in SZINEK}

    tar = {u: kenyszertar.get(u, Igeret()) for u in ulesek}
    for u, ig in tar.items():
        if ig.ellentmondas:
            raise MintavetelHiba(
                f"A kényszertár ellentmondásos {u} ülésre: {ig.leiras()}")

    ki = Minta()
    hatar = db * max_proba_szorzo

    # --- 0. lépés: TISZTA ELUTASÍTÁS ---------------------------------
    # Véletlen osztás + ellenőrzés. Ez az EGYETLEN torzítatlan módszer:
    # a megengedett leosztásokon pontosan egyenletes. Csak akkor drága,
    # ha a kényszerek szűkek — ezért adunk neki egy szabott keretet, és
    # csak utána esünk vissza az irányított eljárásra.
    osszes = [l for sz in SZINEK for l in keszlet_lapok[sz]]
    keret = min(hatar, db * 30)
    while len(ki.leosztasok) < db and ki.probak < keret:
        ki.probak += 1
        rnd.shuffle(osszes)
        kezek = {u: osszes[i * 13:(i + 1) * 13] for i, u in enumerate(ulesek)}
        if not _megfelel(kezek, tar, metrika):
            ki.elutasitva += 1
            continue
        teljes = dict(ismert)
        teljes.update({u: Kez(frozenset(kezek[u])) for u in ulesek})
        ki.leosztasok.append(Leosztas(teljes, oszto=ules,
                                      beliallas=beliallas))
    if len(ki.leosztasok) >= db:
        return ki

    # --- visszaesés: IRÁNYÍTOTT mintavétel ---------------------------
    # Gyors, de nem egyenletes: a sok szabad hellyel rendelkező kezek
    # felé húz. A `torzitott` jelző ezért van — aki ebből számol várható
    # értéket, tudja, hogy óvatosan kell bánnia vele.
    ki.torzitott = True
    while len(ki.leosztasok) < db and ki.probak < hatar:
        ki.probak += 1
        vektor = _hosszvektor(ulesek, keszlet, tar, rnd)
        if vektor is None:
            ki.elutasitva += 1
            continue
        kezek = _kioszt(vektor, keszlet_lapok, rnd)
        if not _javit(kezek, tar, metrika, rnd):
            ki.elutasitva += 1
            continue
        teljes = dict(ismert)
        teljes.update({u: Kez(frozenset(kezek[u])) for u in ulesek})
        lo = Leosztas(teljes, oszto=ules, beliallas=beliallas)
        try:
            lo.ellenorizd()
        except ValueError:             # elvileg nem fordulhat elő
            ki.elutasitva += 1
            continue
        ki.leosztasok.append(lo)

    return ki
