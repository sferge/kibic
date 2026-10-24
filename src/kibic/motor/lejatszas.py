"""
A JÁTÉK KÖZBENI DÖNTÉS (2026-10-21): melyik lapot játsszuk.

A sorrend (rendszerek/jelzesek/README.md, „A lejátszó réteg”):

  1. TÉNYEK — amit tudunk: a saját kezünk és az asztal, a lejátszott lapok,
     a renonszok (ki nem adott színt), a licitből a kényszertár. Ebből
     MINTÁT veszünk a rejtett kezekből: minden minta egy lehetséges teljes
     leosztás, amely mindennel összhangban van, amit láttunk.
  2. DD-SZŰRŐ — minden mintán double dummy kiértékeljük a szabályos lapokat,
     és laponként összesítünk:
        JO               átlagosan (szinte) annyi ütést hoz, mint a legjobb;
        BIZTOSAN_ROSSZ   a minták nagy részében legalább egy ütést veszít;
        TALAN            a kettő között.
  3. A MEGÁLLAPODÁS A JÓ LAPOK KÖZÖTT — a DD-nek mindegy, hogy a 7-est vagy a
     2-est tesszük, a partnernek nem. Védőként a jelzésrendszer választ, de
     csak a JÓ lapok közül:
        indítás / hívás   színenként a megállapodás szerinti lap (indító
                          kijátszás, menet közbeni hívás) — a színt a DD dönti
        színadás          a rács jele (kérés, lapszám, Smith) — magas vagy
                          alacsony lap a jók közül
        dobás             preferencia
     Felvevőként a DD legjobbja (azonos értékűek közül a legkisebb).
  4. MÉRLEGELŐ ELVEK — ahol a DD vak (a DD-felvevő mindent lát: „ne oldjuk
     meg a felvevő problémáját”). Ezek most még csak a jelzésrendszerben
     állnak szövegként; a döntésbe nem lépnek be.

Ha nincs DDS (vagy kifut az időből), a 3. lépés a szabályos lapok közül
választ: a megállapodás akkor is a legjobb tudásunk.

A modul NEM nyúl adatbázishoz és hálózathoz: a kényszertárat, a
jelzésrendszert és a DD-függvényt kívülről kapja (szolgaltatas/atjaro.py).
"""
from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from itertools import combinations
from math import comb

from ..domain import LAPOK, SZINEK, ULESEK, Kez, Kontraktus, Lap, Leosztas, kovetkezo_ules, vonal

# Az osztályozás küszöbei (ütésben, illetve arányban).
JO_TURES = 0.2          # a legjobb átlagától legfeljebb ennyivel marad el (teljes bizonytalanságnál)
ROSSZ_ARANY = 0.75      # a minták ennyi részében legalább egy ütést veszít
# Ha a lehetséges elosztások száma ennyi vagy kevesebb, MINDET megnézzük
# (kimerítő elemzés: a végjátékban ez pontos — nincs mintavételi zaj).
KIMERITO_HATAR = 600
# A kényszertárat csak akkor engedjük el, ha a próbák első felében ennél
# kevesebb illeszkedő minta jött (2026-10-21: korábban már akkor is, ha a
# célszámot — 400 — nem érte el, és így szinte minden döntésnél elengedte).
LAZIT_MIN = 30
# A JÓ tűrése a bizonytalansággal arányos: ennyi ismeretlen lapnál teljes
# (a kijátszás elején 26-39 lap ismeretlen), a végjátékban közel nulla —
# ott a DD különbsége valódi, nem a minta zaja.
TURES_TELJES_ISMERETLEN = 26
# JÁTÉK KÖZBEN a tűrés csak a minta zaja (2026-10-21): a lap akkor JÓ, ha a
# legjobbtól való átlagos elmaradása nem nagyobb, mint a párosított különbség
# kétszeres standard hibája (legfeljebb a fenti tűrés, de legalább ennyi ütés
# — a kimerítő, súlyozott elemzésben is: egy 1%-os súlyú elosztás ne döntsön). Indításnál marad a
# fenti tűrés: ott a megállapodás erős, játék közben a szabály leértékelődik.
PAROS_MIN = 0.02
FIGURAK = set("AKQJ")


class LejatszasHiba(ValueError):
    pass


# --- 0. A játékállás a kérésből --------------------------------------------------

def lap_drotrol(s: str) -> Lap:
    """'SA', 'D6', 'HT', 'S10', 'AS' -> Lap."""
    t = str(s).strip().upper().replace("10", "T")
    try:
        return Lap.parse(t)
    except ValueError as e:
        raise LejatszasHiba(f"Érvénytelen lap: {s!r}") from e


def _kontraktus(c: dict, felvevo: str) -> Kontraktus:
    if not isinstance(c, dict):
        raise LejatszasHiba("A 'state.contract' hiányzik")
    szin = str(c.get("strain", "")).upper()
    szin = "NT" if szin in ("N", "NT") else szin
    if szin not in ("S", "H", "D", "C", "NT") or not c.get("level"):
        raise LejatszasHiba(f"Érvénytelen kontraktus: {c!r}")
    kontra = {1: "", 2: "X", 4: "XX"}.get(int(c.get("multiplier") or 1), "")
    return Kontraktus(int(c["level"]), szin, kontra, felvevo)


@dataclass
class JatekAllas:
    ules: str                               # aki most játszik (acting_for_seat)
    kontraktus: Kontraktus
    asztal: str                             # a dummy ülése
    lathato: dict[str, list[Lap]]           # a most kézben lévő, látható lapok
    lejatszott: list[tuple[str, Lap]]       # időrendben, a folyamatban lévő ütéssel
    legalis: dict[Lap, str]                 # Lap -> a kérésbeli pontos jelölés
    licitek: list = field(default_factory=list)
    oszto: str = "N"
    beliallas: str = "NONE"
    partner_szinek: list[str] = field(default_factory=list)   # amit a partner licitált (4+)
    pontozas: str = "IMP"                   # IMP / MP (a kérés game.scoring-ja)
    partner_smith: str | None = None        # a partner Smith-jele: VALT / FOLYTAT (a mintákból)
    lopasos_arany: float | None = None      # indulásnál: a minták hányadában épül a felvétel lopásra

    @property
    def felvevo(self) -> str:
        return self.kontraktus.felvevo

    @property
    def vedo(self) -> bool:
        return vonal(self.ules) != vonal(self.felvevo)

    @property
    def felvetel(self) -> str:
        return "SZAN" if self.kontraktus.szin == "NT" else "SZIN"

    @property
    def adu(self) -> str | None:
        return None if self.kontraktus.szin == "NT" else self.kontraktus.szin

    @property
    def utesek(self) -> list[list[tuple[str, Lap]]]:
        """A lejátszás ütésekre bontva (az utolsó lehet befejezetlen)."""
        return [self.lejatszott[i:i + 4] for i in range(0, len(self.lejatszott), 4)]

    @property
    def aktualis(self) -> list[tuple[str, Lap]]:
        n = len(self.lejatszott) % 4
        return self.lejatszott[len(self.lejatszott) - n:] if n else []

    def jatszott(self, ules: str) -> list[Lap]:
        return [l for u, l in self.lejatszott if u == ules]

    def eredeti(self, ules: str) -> set[Lap]:
        """Egy LÁTHATÓ kéz eredeti 13 lapja (a mostaniak + amit már letett)."""
        return set(self.lathato[ules]) | set(self.jatszott(ules))

    def renonszok(self) -> dict[str, set[str]]:
        """Ki melyik színt NEM tudta már adni (a hívott színre mást tett)."""
        ki: dict[str, set[str]] = {u: set() for u in ULESEK}
        for utes in self.utesek:
            if not utes:
                continue
            hivott = utes[0][1].szin
            for u, l in utes[1:]:
                if l.szin != hivott:
                    ki[u].add(hivott)
        return ki

    def partner(self, ules: str | None = None) -> str:
        return kovetkezo_ules(ules or self.ules, 2)


def allas_keresbol(keres: dict) -> JatekAllas:
    """A MohaBridzs kijátszáskérése (mohabridzs-ai/1.0, 7.1) -> JatekAllas."""
    if not isinstance(keres, dict):
        raise LejatszasHiba("A kérés JSON-objektum legyen")
    st = keres.get("state") or {}
    szereplo = keres.get("actor") or {}
    ules = str(szereplo.get("acting_for_seat") or szereplo.get("seat") or "").upper()
    if ules not in ULESEK:
        raise LejatszasHiba("Az 'actor.acting_for_seat' hiányzik vagy hibás")
    felvevo = str(st.get("declarer") or "").upper()
    if felvevo not in ULESEK:
        raise LejatszasHiba("A 'state.declarer' hiányzik vagy hibás")
    asztal = str(st.get("dummy") or kovetkezo_ules(felvevo, 2)).upper()
    k = _kontraktus(st.get("contract"), felvevo)
    lathato = {str(u).upper(): [lap_drotrol(x) for x in lapok]
               for u, lapok in (st.get("visible_hands") or {}).items()
               if str(u).upper() in ULESEK}
    if ules not in lathato:
        raise LejatszasHiba(f"A 'visible_hands' nem tartalmazza a(z) {ules} kezet")

    # A lejátszás: a history.play az időrendi lista; ha nincs, az ütésekből
    hist = (keres.get("history") or {}).get("play")
    if hist is None:
        hist = [c for t in (st.get("completed_tricks") or []) for c in (t.get("cards") or [])]
        hist += list(st.get("current_trick") or [])
    lejatszott = []
    for x in hist:
        u = str(x.get("seat") or "").upper()
        if u not in ULESEK:
            raise LejatszasHiba(f"Érvénytelen ülés a lejátszásban: {x!r}")
        lejatszott.append((u, lap_drotrol(x.get("card"))))
    legalis = {}
    for x in ((keres.get("legal_actions") or {}).get("cards") or []):
        legalis[lap_drotrol(x)] = str(x)
    if not legalis:
        raise LejatszasHiba("A 'legal_actions.cards' üres")
    beli = str((keres.get("game") or {}).get("vulnerability") or "none").upper()
    beli = {"NONE": "NONE", "NS": "NS", "EW": "EW", "BOTH": "ALL", "ALL": "ALL"}.get(beli, "NONE")
    g = keres.get("game") or {}
    return JatekAllas(ules=ules, kontraktus=k, asztal=asztal, lathato=lathato,
                      lejatszott=lejatszott, legalis=legalis,
                      licitek=list((keres.get("history") or {}).get("auction") or []),
                      oszto=str(st.get("dealer") or "N").upper()[:1], beliallas=beli,
                      pontozas=pontozas_neve(g.get("scoring") or g.get("scoring_type")))


def pontozas_neve(x) -> str:
    """A kérés pontozása -> IMP / MP. Párosverseny (MP, BAM): MP; minden más
    (IMP, csapat, összpont, ismeretlen): IMP — ott a teljesítés a fő kérdés."""
    s = str(x or "").upper().replace("-", "_")
    return "MP" if s in ("MP", "MATCHPOINTS", "MATCHPOINT", "PAIRS", "PAIRS_MP", "BAM",
                         "TOP", "PAROS") else "IMP"


def partner_szinei(allas: JatekAllas, kenyszertar: dict | None = None) -> list[str]:
    """
    A partner licitált színei. A kényszertárból (4+ lapot ígért — így a
    mesterséges licit, pl. a Stayman 2♣ nem számít); ha nincs kényszertár, a
    partner színlicitjei szó szerint. Az utolsó licitált szín elöl.
    """
    p = allas.partner()
    if kenyszertar and p in kenyszertar:
        ig = kenyszertar[p]
        return [sz for sz in SZINEK if ig.hossz(sz)[0] >= 4]
    ki: list[str] = []
    for x in allas.licitek:
        ules = str((x.get("seat") if isinstance(x, dict) else "") or "").upper()
        hivas = str((x.get("call") if isinstance(x, dict) else x) or "").upper()
        if ules == p and len(hivas) == 2 and hivas[0] in "1234567" and hivas[1] in SZINEK:
            if hivas[1] in ki:
                ki.remove(hivas[1])
            ki.insert(0, hivas[1])
    return ki


# --- 1. Mintavétel a rejtett kezekből ----------------------------------------------

@dataclass
class MintaEredmeny:
    leosztasok: list[Leosztas]
    probak: int = 0
    lazitott: bool = False      # a kényszertárat el kellett engedni (túl szűk / ellentmondásos)
    kimerito: bool = False      # az összes lehetséges elosztás (nem minta)
    ismeretlen: int = 0         # ennyi lap helye ismeretlen
    kizart_jatek: int = 0       # ennyi elosztást zárt ki a lejátszásból levont következtetés
    sulyok: list[float] = field(default_factory=list)   # elosztásonként (kimerítő mód); üres = mind 1
    osszevont: bool = False     # a kimerítő elemzés a kis lapokat összevonta (mintázatok)
    leertekelt: dict[str, int] = field(default_factory=dict)  # kód -> ennyi elosztást értékelt le
    igazitott: list[str] = field(default_factory=list)  # ezeknek a licitjét a lapokhoz kellett igazítani


def _uti(lap: Lap, elotte: list[Lap], adu: str | None) -> bool:
    """Viszi-e a `lap` az ütést az előtte tett lapok ellen."""
    if not elotte:
        return True
    hivott = elotte[0].szin
    for l in elotte:
        if lap.szin == l.szin:
            if lap.rang < l.rang:
                return False
        elif adu and l.szin == adu:
            return False                     # valaki már lopott, mi nem adut tettünk
        elif lap.szin != hivott and lap.szin != adu:
            return False                     # dobás
    return True


def _partnersegben(stat, lapok: list[Lap], jo: list[Lap], sor: dict | None) -> list[Lap]:
    """
    A `lapok` közül azok, amelyeket a partnerség kedvéért vállalunk: a jók, és
    amelyek az elemzés átlaga szerint legfeljebb a sor tűrésével maradnak el a
    legjobbtól (de nem biztosan rosszak). Elemzés nélkül csak a jók.
    """
    if not sor or not lapok:
        return []
    if not stat:
        return [l for l in lapok if l in jo]
    from .jelzes import MERLEGELES_TURES
    tures = float(sor.get("tures", MERLEGELES_TURES.get(sor.get("merlegeles"), 0.0)))
    # a tűrés a pontozás egységében (IMP-ben IMP, MP-ben ütés — ott az érték az
    # átlagos ütés): ütésben mérve egy 0,16 ütéssel „alig rosszabb” lap a
    # minták 19%-ában a felvételt engedte teljesülni (2026-10-23, fred-mérés)
    legjobb = max(s.ertek for s in stat.values() if s.n) if any(s.n for s in stat.values()) else 0.0
    return [l for l in lapok if l in jo or (
        l in stat and stat[l].n and stat[l].osztaly != "BIZTOSAN_ROSSZ"
        and stat[l].ertek >= legjobb - tures - 1e-9)]


def _nyero(utes: list[tuple[str, Lap]], adu: str | None) -> tuple[str, Lap]:
    """Az ütésben eddig a legerősebb lap (ülés, lap)."""
    nyero = utes[0]
    for u, l in utes[1:]:
        if _uti(l, [nyero[1]], adu) and (l.szin == nyero[1].szin or (adu and l.szin == adu)):
            nyero = (u, l)
    return nyero


def _egyenerteku(x: Lap, y: Lap, sajat: set[Lap], lement: set[Lap]) -> bool:
    """Egyenértékű-e két lap: azonos szín, és minden rang köztük a sajátunk vagy már lement."""
    if x.szin != y.szin:
        return False
    lo, hi = sorted((x.rang, y.rang))
    return all(Lap(x.szin, e) in sajat or Lap(x.szin, e) in lement
               for e in LAPOK if lo < Lap(x.szin, e).rang < hi)


def kovetkezetlen_vedo(allas: JatekAllas, eredeti: dict[str, set[Lap]],
                       ulesek) -> str | None:
    """Régi név: mindkét következtetés a megadott ülésekre."""
    return kovetkezetlen(allas, eredeti, {u: set(KOVETKEZTETES_KODOK) for u in ulesek})


KOVETKEZTETES_KODOK = ("LEGKISEBB_EGYENERTEKU", "LEGOLCSOBB_NYERO")


def kovetkeztetes_szabalyai(allas: JatekAllas, jelzesek, rejtett: list[str]) -> dict[str, set[str]]:
    """
    A jelzésrendszer `kovetkeztetes:` soraiból: kinek a lapjaiból mit
    következtetünk ({ülés: {kód}}), csak a rejtett ülésekre. Sor nélkül semmit
    — nincs rejtett tudás.
    """
    ki: dict[str, set[str]] = {}
    for sor in (getattr(jelzesek, "kovetkeztetes_sorok", None) or []):
        for forras in sor["kitol"]:
            if forras == "PARTNER" and allas.vedo:
                ulesek = [allas.partner()]
            elif forras == "ELLENJATEKOSOK":
                ulesek = [u for u in ULESEK if vonal(u) != vonal(allas.felvevo)]
            elif forras == "FELVEVO":
                ulesek = [allas.felvevo]
            else:
                ulesek = []
            for u in ulesek:
                if u in rejtett:
                    ki.setdefault(u, set()).add(sor["kovetkeztetes"])
    return ki


def _ellentmondasok(allas: JatekAllas, eredeti: dict[str, set[Lap]],
                    szabalyok: dict[str, set[str]]):
    """
    KÖVETKEZTETÉS AZ ELLENJÁTÉKOS lapjaiból (2026-10-21). Az ellenjátékos a
    partnerét segíti, ezért (a felvevővel ellentétben) a lapja beszél:

      * a LEGKISEBB AZ EGYENÉRTÉKŰEK KÖZÜL: ha harmadik vagy negyedik kézben
        ütést próbált vinni (a lapja verte az előtte tetteket), nem volt nála
        kisebb, vele egyenértékű lap (KD-ből a D-t teszi; ha a K-t tette, nincs
        nála a D);
      * NEGYEDIK KÉZBEN A LEGOLCSÓBB NYERŐ LAP: ha negyedikként vitte, nem volt
        nála kisebb lap, amely szintén vitte volna;
      * a NEM ÜTÉSRE TETT FIGURA (2026-10-23, FIGURA_SOROZAT): ha az Á, K, D
        vagy B nem veri az előtte tetteket (aláteszi, vagy dobja), zárt sorozat
        teteje — nála van a következő, még kint lévő kisebb lap —, vagy abban a
        színben az egyetlen lapja volt (szingli). A partner ászára tett D: DB
        vagy szingli D; a dobott K: KD.

    Sorra adja az ellentmondásokat: (kód, leírás). `eredeti` lehet részleges
    is (a rejtett kéznek csak a letett lapjai): a FIGURA_SOROZAT csak akkor
    ellentmondás, ha a következő lap BIZONYOSAN máshol van.
    """
    adu = allas.adu
    lement: set[Lap] = set()
    for utes in allas.utesek:
        elotte: list[Lap] = []
        for poz, (u, x) in enumerate(utes):
            kodok = szabalyok.get(u) or set()
            # csak harmadik és negyedik kézben: a hívó lapja a hívási megállapodás
            # (sorozat teteje), a második kéz lapja jelzés (lapszám) lehet
            if poz >= 2 and kodok and _uti(x, elotte, adu):
                kez_akkor = eredeti[u] - lement
                for y in kez_akkor:
                    if y.szin != x.szin or y.rang >= x.rang or not _uti(y, elotte, adu):
                        continue
                    if "LEGKISEBB_EGYENERTEKU" in kodok and \
                            _egyenerteku(x, y, kez_akkor, lement | set(elotte)):
                        yield ("LEGKISEBB_EGYENERTEKU",
                               f"{u} a(z) {x}-t tette, pedig nála volt az egyenértékű {y}")
                    if "LEGOLCSOBB_NYERO" in kodok and poz == 3 and len(utes) == 4:
                        yield ("LEGOLCSOBB_NYERO",
                               f"{u} negyedikként a(z) {x}-vel vitte, pedig a(z) {y} is vitte volna")
            if poz >= 1 and "FIGURA_SOROZAT" in kodok and x.ertek in FIGURAK \
                    and not _uti(x, elotte, adu):
                szinben = [y for y in eredeti[u] - lement if y.szin == x.szin]
                kint = lement | set(elotte)
                kovetkezo = max((Lap(x.szin, e) for e in LAPOK
                                 if Lap(x.szin, e).rang < x.rang and Lap(x.szin, e) not in kint),
                                key=lambda l: l.rang, default=None)
                if len(szinben) >= 2 and kovetkezo is not None and kovetkezo not in eredeti[u] \
                        and any(kovetkezo in eredeti[v] for v in eredeti if v != u):
                    yield ("FIGURA_SOROZAT",
                           f"{u} a(z) {x}-t nem ütésre tette, de a(z) {kovetkezo} nem nála volt")
            elotte.append(x)
        lement |= {l for _, l in utes}


def kovetkezetlen(allas: JatekAllas, eredeti: dict[str, set[Lap]],
                  szabalyok: dict[str, set[str]]) -> str | None:
    """Az első ellentmondás leírása (lásd `_ellentmondasok`), vagy None; a hívó
    csak akkor zár ki, ha marad elosztás (az ellenjátékos is tévedhet)."""
    return next((leiras for _, leiras in _ellentmondasok(allas, eredeti, szabalyok)), None)


def kovetkezetlen_kodok(allas: JatekAllas, eredeti: dict[str, set[Lap]],
                        szabalyok: dict[str, set[str]]) -> set[str]:
    """Mely következtetéseknek mond ellent az elosztás."""
    return {kod for kod, _ in _ellentmondasok(allas, eredeti, szabalyok)}


LAP_KODOK = ("LEGKISEBB_EGYENERTEKU", "LEGOLCSOBB_NYERO", "FIGURA_SOROZAT")
FIGURA_ERO = set("AKQ")


@dataclass
class Kovetkeztetes:
    """
    A jelzésrendszer `kovetkeztetes:` sorai erre az állásra (2026-10-21):
    ki(k)nek a lapjaiból / licitjéből mit következtetünk, és mennyit ér az
    elosztás, amely ennek ellentmond (`suly`: 0 = kizárjuk). Sor nélkül üres
    — nincs rejtett tudás.
    """
    kodok: dict[str, set[str]] = field(default_factory=dict)    # ülés -> kódok
    suly: dict[str, float] = field(default_factory=dict)        # kód -> súly
    tures: int = 0                                              # LICIT_PONTHATAR
    jelzesek: object = None
    valoszinu: dict = field(default_factory=dict)               # LICIT_KIZARAS: {ülés: Igeret}
    nem_kovetett: set = field(default_factory=set)              # akik a lap-megállapodást nem követik

    def van(self, ules: str, kod: str) -> bool:
        return kod in self.kodok.get(ules, ())

    def __bool__(self) -> bool:
        return any(self.kodok.values())


def kovetkeztetes_beallitas(allas: JatekAllas, jelzesek, rejtett: list[str],
                            valoszinu: dict | None = None) -> Kovetkeztetes:
    """`valoszinu`: a licit KIZÁRÁSOS következtetése ülésenként ({ülés: Igeret},
    a licit-szál kovetkeztetes.py-ja) — a LICIT_KIZARAS sor használja."""
    from .jelzes import KOVETKEZTETES_SULY
    kov = Kovetkeztetes(kodok=kovetkeztetes_szabalyai(allas, jelzesek, rejtett), jelzesek=jelzesek,
                        valoszinu=dict(valoszinu or {}))
    for sor in (getattr(jelzesek, "kovetkeztetes_sorok", None) or []):
        kod = sor["kovetkeztetes"]
        kov.suly[kod] = float(sor.get("suly", KOVETKEZTETES_SULY.get(kod, 0.0)))
        if kod == "LICIT_PONTHATAR":
            kov.tures = int(sor.get("tures", 2))
    # a mérőpad hangolásához (2026-10-24): KIBIC_KOVETKEZTETES_SULY="KOD=0.4,KOD2=1"
    # felülírja a meglévő sorok súlyát (élesben nincs beállítva)
    for tetel in os.getenv("KIBIC_KOVETKEZTETES_SULY", "").split(","):
        kod, _, ertek = tetel.partition("=")
        if kod.strip() in kov.suly and ertek.strip():
            kov.suly[kod.strip()] = float(ertek)
    # aki a lapjaival MÁR megmutatta, hogy nem így játszik (pl. QJT-ből a D-vel
    # ütött, és a B-t később le is tette), arra a lapból levont következtetés
    # nem él — különben minden elosztást kizárna, és vele a többi
    # következtetést is el kellene engedni
    ismert = {u: (allas.eredeti(u) if u in allas.lathato else set(allas.jatszott(u)))
              for u in ULESEK}
    for u in list(kov.kodok):
        lapkod = kov.kodok[u] & set(LAP_KODOK)
        megszegett = kovetkezetlen_kodok(allas, ismert, {u: lapkod}) if lapkod else set()
        if megszegett:
            kov.kodok[u] -= megszegett
            kov.nem_kovetett.add(u)
    return kov


def _pont_tav(lapok: set[Lap], ig, _latott: frozenset = frozenset()) -> float | None:
    """
    Hány ponttal esik a kéz a licit(ek) pontsávján kívül (0: belül); None, ha
    a hossza nem stimmel. A többértelmű licitnél (Igeret.alternativak) a
    legközelebbi változat számít. Mivel mind ugyanannak a kéznek a pontja,
    a távolság a LEGNAGYOBB eltérés (nem adódik össze).
    """
    if ig is None:
        return 0.0
    for sz in SZINEK:
        lo, hi = ig.hossz(sz)
        if not lo <= sum(1 for l in lapok if l.szin == sz) <= hi:
            return None
    h = _hcp(lapok)
    tav = max(ig.pont_min - h, h - ig.pont_max, 0.0)
    if id(ig) in _latott:                    # védekezés a hivatkozási kör ellen
        return tav
    _latott = _latott | {id(ig)}
    for csoport in (getattr(ig, "alternativak", None) or []):
        t = [x for x in (_pont_tav(lapok, v, _latott) for v in csoport) if x is not None]
        if not t:
            return None
        tav = max(tav, min(t))
    return tav


def _igeret_suly(lapok: set[Lap], ig, tures: int = 0, suly: float = 0.5) -> float:
    """
    Mennyire illik egy teljes kéz a licitjeihez: 1 = teljesen; a pontsávon
    kívül `tures` pontig pontonként `suly`-lyal kevesebb; azon túl, vagy ha a
    hosszak nem stimmelnek, 0. A többértelmű licitnél a kéznek legalább egy
    változatot ki kell elégítenie.
    """
    tav = _pont_tav(lapok, ig)
    if tav is None or tav > tures:
        return 0.0
    return suly ** tav if tav else 1.0


def _licit_suly(kezek: dict[str, set[Lap]], rejtett: list[str], tar: dict,
                kov: Kovetkeztetes | None) -> float:
    w = 1.0
    for u in rejtett:
        puha = bool(kov) and kov.van(u, "LICIT_PONTHATAR")
        w *= _igeret_suly(kezek[u], tar.get(u), kov.tures if puha else 0,
                          kov.suly.get("LICIT_PONTHATAR", 0.5) if puha else 0.0)
        if not w:
            return 0.0
    return w


def _licitalt_szinek(allas: JatekAllas, ules: str) -> set[str]:
    ki = set()
    for x in allas.licitek:
        u = str((x.get("seat") if isinstance(x, dict) else "") or "").upper()
        h = str((x.get("call") if isinstance(x, dict) else x) or "").upper()
        if u == ules and len(h) == 2 and h[0] in "1234567" and h[1] in SZINEK:
            ki.add(h[1])
    return ki


def _dobas_ker(jel: str | None, modszer: dict, irany: str) -> bool | None:
    """A dobás (magas / alacsony lap) a jelzésrendszer szerint kéri-e a színt."""
    if jel == "PREF" and modszer.get("PREF") == "EGYENES":
        return irany == "ALACSONY"           # egyenes: kis lap kér, nagy nem kér
    if jel in ("KERES", "ATTITUD"):
        kicsi_ker = modszer.get("KERES", "KICSI") == "KICSI"
        return (irany == "ALACSONY") == kicsi_ker
    return None


def _jelzes_suly(allas: JatekAllas, eredeti: dict[str, set[Lap]], kov: Kovetkeztetes,
                 cache: dict) -> tuple[float, set[str]]:
    """
    A partner JELZÉSEINEK összhangja egy elosztással: az indító lapja a
    megállapodás szerinti-e (PARTNER_INDITASA), az első dobásai a dobási jel
    szerint kérnek-e (PARTNER_DOBASA) — a mi jelzésrendszerünk szerint.
    Visszaadja: (súly, a leértékelő kódok).
    """
    w, okok = 1.0, set()
    j = kov.jelzesek
    if not j or not allas.lejatszott:
        return w, okok
    # az indító lap
    u0, l0 = allas.lejatszott[0]
    if kov.van(u0, "PARTNER_INDITASA") and u0 in eredeti:
        sor = tuple(_lapsor([l for l in eredeti[u0] if l.szin == l0.szin]))
        helyzet = "PARTNER_SZINE" if l0.szin in _licitalt_szinek(allas, allas.partner(u0)) \
            else "INDITAS"
        kulcs = ("I", helyzet, sor)
        if kulcs not in cache:
            try:
                cache[kulcs] = j.indito_lap(list(sor), allas.felvetel, helyzet)[0]
            except Exception:              # noqa: BLE001
                cache[kulcs] = None
        if cache[kulcs] is not None and cache[kulcs] != l0.ertek:
            w *= kov.suly.get("PARTNER_INDITASA", 0.2)
            okok.add("PARTNER_INDITASA")
    # az ELSŐ dobás (a rács DOBAS cellája az első dobásról szól)
    dobo = [u for u in eredeti if kov.van(u, "PARTNER_DOBASA")]
    if dobo:
        tilt = j.nincs_jelzes(allas.kontraktus.szint, allas.felvetel) \
            if hasattr(j, "nincs_jelzes") else None
        jel = None if tilt else _racs_jel(j, "DOBAS", allas.felvetel, False)
        modszer = dict(getattr(j, "modszer", {}) or {})
        if jel:
            for u in dobo:
                volt = False
                letett: set[Lap] = set()
                for utes in allas.utesek:
                    if not utes or volt:
                        continue
                    hivott = utes[0][1].szin
                    for uu, l in utes:
                        if uu != u:
                            continue
                        if l.szin != hivott and l.szin != allas.adu and not volt:
                            volt = True
                            akkor = [x for x in eredeti[u] if x.szin == l.szin and x not in letett]
                            kicsik = [x for x in akkor if x.ertek not in FIGURAK]
                            irany = None
                            if len(akkor) >= 2 and l == min(akkor, key=lambda x: x.rang):
                                irany = "ALACSONY"
                            elif len(akkor) >= 2 and kicsik and l == max(kicsik, key=lambda x: x.rang):
                                irany = "MAGAS"
                            ker = _dobas_ker(jel, modszer, irany) if irany else None
                            if ker is True and not any(x.ertek in FIGURA_ERO for x in akkor) or \
                                    ker is False and any(x.ertek in "AK" for x in akkor):
                                w *= kov.suly.get("PARTNER_DOBASA", 0.25)
                                okok.add("PARTNER_DOBASA")
                        letett.add(l)
    return w, okok


def partner_kert_szine(allas: JatekAllas, jelzesek) -> str | None:
    """
    A partner ELSŐ dobása a mi szemszögünkből (a kezét nem látjuk): KÉRŐ jel,
    ha a dobott lapnál kisebb ebből a színből nem lehetett nála (mind látjuk
    vagy lement) és a dobási jel szerint a kis lap kér. Visszaadja a színt.
    """
    if not jelzesek or not allas.vedo:
        return None
    if hasattr(jelzesek, "nincs_jelzes") and jelzesek.nincs_jelzes(allas.kontraktus.szint,
                                                                    allas.felvetel):
        return None
    jel = _racs_jel(jelzesek, "DOBAS", allas.felvetel, False)
    modszer = dict(getattr(jelzesek, "modszer", {}) or {})
    if _dobas_ker(jel, modszer, "ALACSONY") is not True:
        return None
    p = allas.partner()
    latott = set().union(*(allas.eredeti(u) for u in allas.lathato))
    lement: set[Lap] = set()
    for utes in allas.utesek:
        if not utes:
            continue
        hivott = utes[0][1].szin
        for u, l in utes:
            if u == p and l.szin != hivott and l.szin != allas.adu:
                kisebb = [Lap(l.szin, e) for e in LAPOK if Lap(l.szin, e).rang < l.rang]
                if all(x in latott or x in lement for x in kisebb):
                    return l.szin
                return None
        lement |= {l for _, l in utes}
    return None


def _jatek_suly(allas: JatekAllas, eredeti: dict[str, set[Lap]], kov: Kovetkeztetes | None,
                cache: dict) -> tuple[float, set[str]]:
    """A lejátszásból levont következtetések súlya egy elosztásra."""
    if not kov:
        return 1.0, set()
    w, okok = _jelzes_suly(allas, eredeti, kov, cache)
    # LICIT_KIZARAS: amit a licitjével kizárt (a licit-szál kizárásos
    # következtetése: pl. a passz 1♥-re „0-5 pont”). 1 pont eltérés félig,
    # több vagy a hossz ellentmondása `suly`-lyal.
    for u, ig in kov.valoszinu.items():
        if u in eredeti and kov.van(u, "LICIT_KIZARAS"):
            tav = _pont_tav(eredeti[u], ig)
            if tav is None or tav > 1:
                w *= kov.suly.get("LICIT_KIZARAS", 0.2)
                okok.add("LICIT_KIZARAS")
            elif tav > 0:
                w *= (1 + kov.suly.get("LICIT_KIZARAS", 0.2)) / 2
                okok.add("LICIT_KIZARAS")
    lap = {u: k & set(LAP_KODOK) for u, k in kov.kodok.items() if k & set(LAP_KODOK)}
    if lap:
        for kod in kovetkezetlen_kodok(allas, eredeti, lap):
            w *= kov.suly.get(kod, 0.0)
            okok.add("LAP" if kod != "FIGURA_SOROZAT" else kod)
    return w, okok


def _felsorol(rejtett: list[str], szabad: list[Lap], kell: dict[str, int],
              renonsz: dict[str, set[str]], hatar: int) -> list[dict] | None:
    """Az összes elosztás a rejtett kezek között (renonsz szerint), ha legfeljebb
    `hatar` darab lehet; különben None."""
    becsles, m = 1, len(szabad)
    for u in rejtett[:-1]:
        becsles *= comb(m, kell[u])
        m -= kell[u]
        if becsles > hatar:
            return None
    ki: list[dict] = []

    def rek(i: int, marad: list[Lap], hely: dict):
        u = rejtett[i]
        if i == len(rejtett) - 1:
            if all(l.szin not in renonsz[u] for l in marad):
                ki.append({**hely, u: list(marad)})
            return
        for valasztott in combinations(marad, kell[u]):
            if any(l.szin in renonsz[u] for l in valasztott):
                continue
            vs = set(valasztott)
            rek(i + 1, [l for l in marad if l not in vs], {**hely, u: list(valasztott)})

    rek(0, list(szabad), {})
    return ki


# KIS LAPOK ÖSSZEVONÁSA (2026-10-23, a szerkesztő ötlete): a kimerítő elemzésben
# a rejtett kis lapok (alapból a 8-as és alatta) egyenértékűek, ha nincs
# köztük látható (még kézben lévő) lap — így nem kell minden elosztásukat
# külön megnézni: egy „mintázat” (a számító lapok helye + a kis lapok száma
# kezenként) képviseli mindet, a súlya az általa képviselt elosztások száma.
# A kimerítő elemzés így sokkal korábban elérhető. Kikapcsolás: "0".
KIS_LAP = os.getenv("KIBIC_LEJATSZAS_KIS_LAP", "8").strip().upper()
# ennyi mintázatig a teljes sokaság (véletlen sorrendben, a döntés eldőltével
# megállhat); ennél több: mintavétel
MINTAZAT_HATAR = int(os.getenv("KIBIC_LEJATSZAS_MINTAZAT_HATAR", "5000"))


def kis_lap_osztalyok(szabad: list[Lap], lathato: list[Lap], hatar: str = KIS_LAP
                      ) -> list[list[Lap]]:
    """
    A rejtett kis lapok egyenértékűségi osztályai: színenként a `hatar`
    rangú és kisebb rejtett lapok, a látható (még kézben lévő) lapok mentén
    szétvágva (a dummy 6-osa fölötti 7-es nem egyenértékű az alatta lévő 5-össel).
    """
    if not hatar or hatar in ("0", "NEM") or hatar not in LAPOK:
        return []
    felso = Lap("S", hatar).rang
    ki = []
    for sz in SZINEK:
        kis = sorted((l for l in szabad if l.szin == sz and l.rang <= felso), key=lambda l: l.rang)
        hatarok = sorted(l.rang for l in lathato if l.szin == sz)
        csoport: list[Lap] = []
        for l in kis:
            if csoport and any(csoport[-1].rang < h < l.rang for h in hatarok):
                if len(csoport) > 1:
                    ki.append(csoport)
                csoport = []
            csoport.append(l)
        if len(csoport) > 1:
            ki.append(csoport)
    return ki


def _mintazat_felsorol(rejtett: list[str], szabad: list[Lap], kell: dict[str, int],
                       renonsz: dict[str, set[str]], osztalyok: list[list[Lap]],
                       hatar: int, rnd: random.Random) -> list[tuple[dict, int]] | None:
    """
    Az összes MINTÁZAT (a számító lapok helye lapra pontosan, a kis lapoké
    osztályonként darabra), egy-egy képviselő elosztással és a súlyával (ennyi
    valódi elosztás tartozik hozzá). Ha `hatar`-nál több: None.
    """
    kis = {l for o in osztalyok for l in o}
    szamito = [l for l in szabad if l not in kis]
    ki: list[tuple[dict, int]] = []
    tul = [False]

    def kicsik(j, marad, hely, szorzo):
        if tul[0]:
            return
        if j == len(osztalyok):
            if not any(marad.values()):
                ki.append((hely, szorzo))
                if len(ki) > hatar:
                    tul[0] = True
            return
        o = osztalyok[j]
        sz = o[0].szin

        def eloszt(i, maradek, ks):
            if i == len(rejtett) - 1:
                u = rejtett[i]
                if maradek <= marad[u] and not (maradek and sz in renonsz[u]):
                    yield ks + (maradek,)
                return
            u = rejtett[i]
            felso = 0 if sz in renonsz[u] else min(maradek, marad[u])
            for k in range(felso + 1):
                yield from eloszt(i + 1, maradek - k, ks + (k,))
        for ks in eloszt(0, len(o), ()):
            lapok = o[:]
            rnd.shuffle(lapok)
            uj, uj_marad, x, m, w = dict(hely), dict(marad), 0, len(o), szorzo
            for u, k in zip(rejtett, ks):
                uj[u] = hely[u] + lapok[x:x + k]
                uj_marad[u] -= k
                w *= comb(m, k)
                m -= k
                x += k
            kicsik(j + 1, uj_marad, uj, w)

    def szamitok(i, marad, hely):
        if tul[0]:
            return
        if i == len(szamito):
            kicsik(0, marad, hely, 1)
            return
        l = szamito[i]
        for u in rejtett:
            if marad[u] > 0 and l.szin not in renonsz[u]:
                szamitok(i + 1, {**marad, u: marad[u] - 1}, {**hely, u: hely[u] + [l]})

    szamitok(0, dict(kell), {u: [] for u in rejtett})
    return None if tul[0] else ki


def _hcp(lapok) -> int:
    return sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(l.ertek, 0) for l in lapok)


def _megfelel(lapok: set[Lap], ig) -> bool:
    """A kényszertár (motor/helyzet.Igeret) egy teljes, 13 lapos kézre."""
    if ig is None:
        return True
    for sz in SZINEK:
        lo, hi = ig.hossz(sz)
        if not lo <= sum(1 for l in lapok if l.szin == sz) <= hi:
            return False
    return ig.pont_min <= _hcp(lapok) <= ig.pont_max


def _igeret_igazit(ig, hatar: dict[str, tuple[int, int]], pont: tuple[int, int],
                   _latott: frozenset = frozenset()):
    """
    Az ígéret a lejátszás tényeihez igazítva: ahol a licit a már ismert
    lapokkal lehetetlent ígér (5 kőr, de csak 4 lehet nála), a sávot a
    lehetséges legközelebbi értékre húzzuk — a többi ígéret marad. A
    többértelmű licit változatai közül a lehetetleneket elhagyjuk (ezek
    úgyis 0 súlyt kapnának); ha mind lehetetlen, mindet igazítjuk.
    Visszaad: (az ígéret vagy az igazított másolata, igazítani kellett-e).
    """
    import copy

    def osszefer(x, latott=frozenset()) -> bool:
        if not all(x.hossz(sz)[0] <= hatar[sz][1] and x.hossz(sz)[1] >= hatar[sz][0]
                   for sz in SZINEK):
            return False
        if x.pont_max < pont[0] or x.pont_min > pont[1]:
            return False
        if id(x) in latott:                  # védekezés a hivatkozási kör ellen
            return True
        latott = latott | {id(x)}
        return all(any(osszefer(v, latott) for v in cs)
                   for cs in (getattr(x, "alternativak", None) or []))

    if ig is None or osszefer(ig):
        return ig, False
    uj = copy.copy(ig)
    uj.hossz_min, uj.hossz_max = dict(ig.hossz_min), dict(ig.hossz_max)
    for sz in SZINEK:
        lo, hi = ig.hossz(sz)
        if lo > hatar[sz][1]:
            uj.hossz_min[sz] = hatar[sz][1]
        if hi < hatar[sz][0]:
            uj.hossz_max[sz] = hatar[sz][0]
    if uj.pont_max < pont[0]:
        uj.pont_max = float(pont[0])
    if uj.pont_min > pont[1]:
        uj.pont_min = float(pont[1])
    csoportok = []
    _latott = _latott | {id(ig)}
    for cs in (getattr(ig, "alternativak", None) or []):
        jo = [v for v in cs if osszefer(v)]
        csoportok.append(jo or [v if id(v) in _latott else _igeret_igazit(v, hatar, pont, _latott)[0]
                                for v in cs])
    uj.alternativak = csoportok
    return uj, True


def tar_igazitas(tar: dict, rejtett: list[str], fix: dict, szabad: list[Lap],
                 renonsz: dict) -> tuple[dict, list[str]]:
    """
    A licit kényszertára a lejátszás tényeihez igazítva (2026-10-23): eddig
    ha EGY ígéret ellentmondott a letett lapoknak (pl. a 2♥ közbeszólás 5
    kőrt ígér, de csak 4 lehet nála), az egész licitet elengedtük — a
    pontsávokat, a többi játékos ígéreteit és a lejátszás következtetéseit is.
    Most csak az ellentmondó részt igazítjuk. Visszaad: (tár, igazított ülések).
    """
    if not tar:
        return tar, []
    szabad_db = {sz: sum(1 for l in szabad if l.szin == sz) for sz in SZINEK}
    szabad_hcp = _hcp(szabad)
    ki, igazitott = dict(tar), []
    for u in rejtett:
        if tar.get(u) is None:
            continue
        hatar = {}
        for sz in SZINEK:
            van = sum(1 for l in fix[u] if l.szin == sz)
            hatar[sz] = (van, van + (0 if sz in renonsz.get(u, ()) else szabad_db[sz]))
        h = _hcp(fix[u])
        ki[u], valt = _igeret_igazit(tar[u], hatar, (h, h + szabad_hcp))
        if valt:
            igazitott.append(u)
    return ki, igazitott


class HosszSorsolo:
    """
    ÉPÍTŐ SORSOLÁS (2026-10-23): a rejtett kezek színhosszait a licit
    hosszígéretei (a kényszertár burka), a renonszok és a már letett lapok
    szerint sorsolja — PONTOSAN olyan arányban, ahány valódi elosztás tartozik
    az egyes hossz-kombinációkhoz (dinamikus programozás a négy színen) —,
    utána a lapokat színenként véletlenül. Így a hosszakra nincs eldobás: a
    régi sorsolás szűk licitnél (pl. 5 kőr + 4 minor, 15-17 egyenletes) a
    próbák 90–97%-át eldobta, és nem is volt pontosan egyenletes.
    A pontsávot és a többértelmű licit változatait továbbra is az elfogadás
    (súly) kezeli.
    """

    def __init__(self, rejtett: list[str], fix: dict, szabad: list[Lap],
                 renonsz: dict, tar: dict):
        self.rejtett = rejtett
        self.lapok = {sz: [l for l in szabad if l.szin == sz] for sz in SZINEK}
        self.kell = tuple(13 - len(fix[u]) for u in rejtett)
        self.sav: dict[tuple[str, str], tuple[int, int]] = {}
        self.ok = True
        for u in rejtett:
            ig = (tar or {}).get(u)
            for sz in SZINEK:
                van = sum(1 for l in fix[u] if l.szin == sz)
                lo_h, hi_h = ig.hossz(sz) if ig is not None else (0, 13)
                lo = max(0, lo_h - van)
                hi = min(len(self.lapok[sz]), hi_h - van)
                if sz in renonsz.get(u, ()):
                    hi = min(hi, 0)
                if lo > hi:
                    self.ok = False
                self.sav[(u, sz)] = (lo, hi)
        self._memo: dict = {}
        if self.ok:
            self.ok = self._db(0, self.kell) > 0

    def _osztasok(self, sz: str, marad: tuple[int, ...]):
        """Egy szín lapjainak lehetséges szétosztása a rejtett kezek között."""
        n = len(self.lapok[sz])
        savok = [self.sav[(u, sz)] for u in self.rejtett]

        def rek(i, maradek):
            if i == len(savok) - 1:
                lo, hi = savok[i]
                if lo <= maradek <= min(hi, marad[i]):
                    yield (maradek,)
                return
            lo, hi = savok[i]
            for k in range(lo, min(hi, maradek, marad[i]) + 1):
                for tobbi in rek(i + 1, maradek - k):
                    yield (k,) + tobbi
        yield from rek(0, n)

    @staticmethod
    def _multinom(n: int, ks: tuple[int, ...]) -> int:
        w, m = 1, n
        for k in ks[:-1]:
            w *= comb(m, k)
            m -= k
        return w

    def _db(self, i: int, marad: tuple[int, ...]) -> int:
        """Ennyi valódi elosztás van a még hátralévő színekre (i-től)."""
        if i == len(SZINEK):
            return 1 if not any(marad) else 0
        kulcs = (i, marad)
        if kulcs in self._memo:
            return self._memo[kulcs]
        sz = SZINEK[i]
        ossz = 0
        for ks in self._osztasok(sz, marad):
            uj = tuple(m - k for m, k in zip(marad, ks))
            ossz += self._multinom(len(self.lapok[sz]), ks) * self._db(i + 1, uj)
        self._memo[kulcs] = ossz
        return ossz

    def sorsol(self, rnd: random.Random) -> dict[str, list[Lap]]:
        ki = {u: [] for u in self.rejtett}
        marad = self.kell
        for i, sz in enumerate(SZINEK):
            opciok = []
            for ks in self._osztasok(sz, marad):
                uj = tuple(m - k for m, k in zip(marad, ks))
                w = self._multinom(len(self.lapok[sz]), ks) * self._db(i + 1, uj)
                if w:
                    opciok.append((w, ks, uj))
            r = rnd.randrange(sum(w for w, _, _ in opciok))
            for w, ks, uj in opciok:
                if r < w:
                    break
                r -= w
            lapok = self.lapok[sz][:]
            rnd.shuffle(lapok)
            j = 0
            for u, k in zip(self.rejtett, ks):
                ki[u] += lapok[j:j + k]
                j += k
            marad = uj
        return ki


def mintavetel(allas: JatekAllas, kenyszertar: dict | None = None, db: int = 40,
               mag: int | None = None, max_proba: int = 4000,
               kovetkeztetes: "Kovetkeztetes | dict[str, set[str]] | None" = None) -> MintaEredmeny:
    """
    `db` lehetséges teljes leosztás. A látható kezek eredetije fix; a rejtett
    kezekben fix, amit már letettek; a többi lap véletlen, de a renonszot nem
    sértheti, és a teljes kéznek ki kell elégítenie a licit kényszertárát.
    Ha a kényszertárral a próbák nagy része elbukik, a második félidőben
    elengedjük (`lazitott`) — jobb egy kicsit pontatlan minta, mint semmi.

    SÚLYOK (2026-10-21): a következtetések (a jelzésrendszer `kovetkeztetes:`
    sorai) nem csak kizárnak, le is értékelhetnek egy elosztást (a partner
    jelzése ellentmond neki, a licit pontsávjától 1-2 ponttal eltér). A
    kimerítő módban az elosztás súlyt kap (`sulyok`), a véletlen mintában a
    súly az elfogadás valószínűsége — így a minta maga lesz súlyozott.
    """
    rnd = random.Random(mag)
    ismert = {u: allas.eredeti(u) for u in allas.lathato}
    rejtett = [u for u in ULESEK if u not in ismert]
    fix = {u: set(allas.jatszott(u)) for u in rejtett}
    foglalt = set().union(*ismert.values(), *fix.values()) if (ismert or fix) else set()
    szabad = [Lap(sz, e) for sz in SZINEK for e in LAPOK if Lap(sz, e) not in foglalt]
    kell = {u: 13 - len(fix[u]) for u in rejtett}
    if sum(kell.values()) != len(szabad) or any(v < 0 for v in kell.values()):
        raise LejatszasHiba("A látható és a lejátszott lapok nem adnak ki egy leosztást")
    renonsz = allas.renonszok()
    tar, igazitott = tar_igazitas(kenyszertar or {}, rejtett, fix, szabad, renonsz)
    kov = kovetkeztetes
    if isinstance(kov, dict):                 # régi alak: {ülés: {kód}} — kizáró következtetés
        kov = Kovetkeztetes(kodok=kov) if kov else None
    cache: dict = {}
    ki = MintaEredmeny([], ismeretlen=len(szabad), igazitott=igazitott)

    def jegyez(okok):
        for o in okok:
            ki.leertekelt[o] = ki.leertekelt.get(o, 0) + 1

    # KIMERÍTŐ: ha kevés a lehetséges elosztás, mindet (a végjátékban pontos)
    osszes = _felsorol(rejtett, szabad, kell, renonsz, KIMERITO_HATAR)
    szorzok: list[int] | None = None
    if osszes is None:
        lathato = [l for v in allas.lathato.values() for l in v]
        osztalyok = kis_lap_osztalyok(szabad, lathato)
        if osztalyok:
            mintazat = _mintazat_felsorol(rejtett, szabad, kell, renonsz, osztalyok,
                                          MINTAZAT_HATAR, rnd)
            if mintazat is not None:
                osszes = [h for h, _ in mintazat]
                szorzok = [w for _, w in mintazat]
                ki.osszevont = True
    if osszes is not None:
        ki.kimerito = True
        kezek = [{u: set(fix[u]) | set(h[u]) for u in rejtett} for h in osszes]
        wl = [_licit_suly(k, rejtett, tar, kov) for k in kezek]
        if osszes and not any(wl):
            wl, ki.lazitott = [1.0] * len(osszes), bool(tar)
        wj, okok = [], []
        for k, w in zip(kezek, wl):
            x, o = _jatek_suly(allas, {**ismert, **k}, kov, cache) if w else (1.0, set())
            wj.append(x)
            okok.append(o)
        w = [a * b for a, b in zip(wl, wj)]
        if not any(w):                        # a következtetés mindent kizárna: a partner is tévedhet
            w = wl
        else:
            ki.kizart_jatek = sum(1 for a, b in zip(wl, wj) if a and not b)
            for a, o in zip(w, okok):
                if a:
                    jegyez(o)
        jegyez(["LICIT_PONTHATAR"] * sum(1 for a, b in zip(wl, w) if b and a < 1))
        if szorzok:                           # egy mintázat ennyi valódi elosztást képvisel
            w = [a * sz for a, sz in zip(w, szorzok)]
        jok = [(h, a) for h, a in zip(osszes, w) if a > 0]
        # véletlen sorrend: ha az időkeret a végére nem ér el, a megnézett rész
        # ne a felsorolás sorrendje szerint torzuljon
        rnd.shuffle(jok)
        # a TÉNYLEGESEN bizonytalan lapok: amelyiknek a helye elosztásonként más
        # (a renonszok és a licit után sokszor jóval kevesebb, mint a ki nem
        # játszott lapok száma — akár 0: akkor minden lap tudható)
        if jok:
            hol = {}
            for h, _ in jok:
                for u, lapok in h.items():
                    for l in lapok:
                        hol.setdefault(l, set()).add(u)
            ki.ismeretlen = sum(1 for v in hol.values() if len(v) > 1)
        for h, a in jok:
            kezek_ = {u: Kez(frozenset(v)) for u, v in ismert.items()}
            kezek_.update({u: Kez(frozenset(set(fix[u]) | set(h[u]))) for u in rejtett})
            ki.leosztasok.append(Leosztas(kezek_, oszto=allas.oszto, beliallas=allas.beliallas))
            ki.sulyok.append(a)
        ki.probak = len(osszes)
        return ki
    lazit_utan = max_proba // 2
    elengedve = False
    epito = HosszSorsolo(rejtett, fix, szabad, renonsz, tar)
    szabad_epito = HosszSorsolo(rejtett, fix, szabad, renonsz, {})   # licit nélkül
    while len(ki.leosztasok) < db and ki.probak < max_proba:
        ki.probak += 1
        if ki.probak == lazit_utan + 1 and tar and len(ki.leosztasok) < LAZIT_MIN:
            elengedve = True                  # túl szűk / ellentmondásos: a második félidőben nélküle
        # a hosszak a licit szerint (ha a licit hosszai teljesíthetők; elengedve
        # vagy ellentmondásnál csak a renonszok szerint)
        sorsolo = epito if (epito.ok and not elengedve) else szabad_epito
        if not sorsolo.ok:
            raise LejatszasHiba("A renonszok és a lapszámok nem adnak ki egy leosztást")
        hely = {u: list(fix[u]) + v for u, v in sorsolo.sorsol(rnd).items()}
        if not epito.ok and ki.probak == 1 and tar:
            elengedve = True                  # a licit hosszai nem teljesíthetők: nélküle

        kezek = {u: set(v) for u, v in hely.items()}
        okok: set[str] = set()
        szigoru = not elengedve
        if szigoru:
            wl = _licit_suly(kezek, rejtett, tar, kov)
            if wl < 1:
                if rnd.random() >= wl:
                    continue
                okok.add("LICIT_PONTHATAR")
        else:
            ki.lazitott = True
        if szigoru and kov:
            wj, o = _jatek_suly(allas, {**ismert, **kezek}, kov, cache)
            if wj < 1:
                if not wj:
                    ki.kizart_jatek += 1
                if rnd.random() >= wj:
                    continue
                okok |= o
        jegyez(okok)
        kezek_ = {u: Kez(frozenset(v)) for u, v in ismert.items()}
        kezek_.update({u: Kez(frozenset(v)) for u, v in hely.items()})
        ki.leosztasok.append(Leosztas(kezek_, oszto=allas.oszto, beliallas=allas.beliallas))
    return ki


# --- 2. DD-szűrő --------------------------------------------------------------------

@dataclass
class LapStat:
    lap: Lap
    n: int = 0
    utes: float = 0.0           # a mi oldalunk ütései a folytatásban (átlag)
    veszt: float = 0.0          # a mintán elérhető legjobbhoz képest (átlag)
    rossz: float = 0.0          # a minták hányadában veszít legalább egy ütést
    legjobb: float = 0.0        # a minták hányadában (az egyik) legjobb
    osztaly: str = "TALAN"      # JO / TALAN / BIZTOSAN_ROSSZ
    # a pontozás szerinti várható érték (nagyobb a jobb): IMP-ben a mintán
    # elérhető legjobbhoz mért IMP-veszteség negatívja, MP-ben (és ha nincs
    # eredményadat) az átlagos ütés. A `veszt` is ebben az egységben van.
    ertek: float = 0.0


# A minta nagyságát a döntés biztossága szabja meg (2026-10-23): legalább
# MIN_MINTA, legfeljebb a hívó `db`-je, és közben az időkeret. Megáll, ha a
# legjobb lap minden más laptól vagy biztosan jobb (a különbség három standard
# hibán túl), vagy biztosan alig különbözik tőle (BIZTOS_ALIG alatt).
MIN_MINTA = int(os.getenv("KIBIC_LEJATSZAS_MIN_MINTA", "60"))
KOTEG = 40
BIZTOS_ALIG = 0.05


class DDGyujto:
    """
    A mintánkénti DD-eredmények gyűjtője. Mintánként laponként két szám:
    az ütés (a mi oldalunké a folytatásban) és a pontozás szerinti érték —
    IMP-ben: a lapra jutó pontszám IMP-ben mérve az ezen a mintán elérhető
    legjobbhoz (≤ 0); MP-ben (vagy ha a DD nem ad eredményt): az ütés.
    """

    def __init__(self, allas: JatekAllas, pontozas: str | None = None):
        self.allas = allas
        self.pontozas = pontozas or "UTES"
        self.lapok = list(allas.legalis)
        self.mintak: list[tuple[float, dict[Lap, float], dict[Lap, int]]] = []
        self.fo = vonal(allas.ules) == vonal(allas.felvevo)

    @property
    def n(self) -> int:
        return len(self.mintak)

    def hozzaad(self, eredmenyek, w: float = 1.0) -> bool:
        utes = {lap_drotrol(e.lap): e.utesek for e in eredmenyek}
        if not utes:
            return False
        ertek: dict[Lap, float] = dict(utes)
        if self.pontozas == "IMP":
            fo_ut = {lap_drotrol(e.lap): getattr(e, "felvevo_osszesen", None) for e in eredmenyek}
            if all(v is not None for v in fo_ut.values()):
                from ..domain.pontozas import imp, pontszam
                pont = {l: pontszam(self.allas.kontraktus, v, self.allas.beliallas)
                        for l, v in fo_ut.items()}
                if not self.fo:
                    pont = {l: -p for l, p in pont.items()}
                csucs = max(pont.values())
                ertek = {l: -imp(csucs - p) for l, p in pont.items()}
        self.mintak.append((w, ertek, utes))
        return True

    def _kulonbseg(self, a: Lap, b: Lap) -> tuple[float, float, bool]:
        """(a−b átlaga, standard hibája, mindig 0-e) a pontozás egységében."""
        d = [(w, e[a] - e[b]) for w, e, _ in self.mintak if a in e and b in e and w > 0]
        W = sum(w for w, _ in d)
        if not d or W <= 0:
            return 0.0, 0.0, True
        m = sum(w * x for w, x in d) / W
        var = sum(w * (x - m) ** 2 for w, x in d) / W
        n_eff = W * W / sum(w * w for w, _ in d)
        se = (var / n_eff) ** 0.5 if n_eff > 1 else 0.0
        return m, se, all(x == 0 for _, x in d)

    def _legjobb(self) -> Lap | None:
        atlag = {}
        for l in self.lapok:
            xs = [(w, e[l]) for w, e, _ in self.mintak if l in e]
            W = sum(w for w, _ in xs)
            if W > 0:
                atlag[l] = sum(w * x for w, x in xs) / W
        return max(atlag, key=atlag.get) if atlag else None

    def biztos(self) -> bool:
        """El dőlt-e a döntés: a legjobb mindenkitől biztosan jobb vagy alig különbözik."""
        a = self._legjobb()
        if a is None:
            return False
        for b in self.lapok:
            if b == a:
                continue
            m, se, nulla = self._kulonbseg(a, b)
            if nulla or m - 3 * se > 0 or m + 3 * se < BIZTOS_ALIG:
                continue
            return False
        return True

    def stat(self, tures: float = JO_TURES, paros: bool = False) -> dict[Lap, LapStat]:
        stat = {l: LapStat(l) for l in self.lapok}
        osszsuly = {l: 0.0 for l in stat}
        for w, ertek, utes in self.mintak:
            csucs = max(ertek.values())
            for l, s in stat.items():
                if l not in ertek:
                    continue
                s.n += 1
                osszsuly[l] += w
                s.utes += w * utes[l]
                s.ertek += w * ertek[l]
                s.veszt += w * (csucs - ertek[l])
                s.rossz += w if ertek[l] < csucs else 0
                s.legjobb += w if ertek[l] == csucs else 0
        for l, s in stat.items():
            if s.n and osszsuly[l] > 0:
                for mezo in ("utes", "ertek", "veszt", "rossz", "legjobb"):
                    setattr(s, mezo, getattr(s, mezo) / osszsuly[l])
            elif s.n:
                s.n = 0
        if self.mintak:
            legkisebb = min(s.veszt for s in stat.values() if s.n)
            elso = min((s for s in stat.values() if s.n), key=lambda s: s.veszt).lap
            for s in stat.values():
                hatar = tures
                if paros and s.n and s.lap != elso:
                    hatar = max(PAROS_MIN, min(tures, 2 * self._kulonbseg(elso, s.lap)[1]))
                if not s.n:
                    s.osztaly = "TALAN"
                elif s.veszt <= legkisebb + hatar + 1e-9:
                    s.osztaly = "JO"
                elif s.rossz >= ROSSZ_ARANY:
                    s.osztaly = "BIZTOSAN_ROSSZ"
                else:
                    s.osztaly = "TALAN"
        return stat


def dd_szuro(allas: JatekAllas, leosztasok: list[Leosztas], dd_fv=None,
             ido_keret_s: float = 6.0, min_minta: int = 6,
             tures: float = JO_TURES,
             sulyok: list[float] | None = None,
             paros: bool = False, pontozas: str | None = None
             ) -> tuple[dict[Lap, LapStat], int]:
    """
    Laponként összesített DD-eredmény a mintákon. `dd_fv(leosztas, lapok,
    kontraktus)` a solver.dds.lap_elemzes (vagy egy teszt-helyettes).
    Az időkeret lejártával megáll (de legalább `min_minta` mintát megnéz).
    `sulyok`: elosztásonként (a kimerítő mód következtetései); az átlagok
    ezzel súlyozottak. `pontozas`: IMP / MP / None (ütés).
    Visszaadja: ({lap: stat}, a ténylegesen kiértékelt minták száma).
    """
    if dd_fv is None:
        from ..solver.dds import lap_elemzes as dd_fv
    jatszott = [str(l) for _, l in allas.lejatszott]
    gy = DDGyujto(allas, pontozas)
    start = time.time()
    for i, lo in enumerate(leosztasok):
        w = sulyok[i] if sulyok and i < len(sulyok) else 1.0
        if gy.n >= min_minta and time.time() - start > ido_keret_s:
            break
        gy.hozzaad(dd_fv(lo, jatszott, allas.kontraktus), w)
    return gy.stat(tures, paros), gy.n


def _paros_hiba(ertekek: list[tuple[float, dict]], a: Lap, b: Lap) -> float:
    """Az a−b ütéskülönbség súlyozott átlagának standard hibája a mintákon."""
    d = [(w, e[a] - e[b]) for w, e in ertekek if a in e and b in e and w > 0]
    W = sum(w for w, _ in d)
    if not d or W <= 0:
        return 0.0
    m = sum(w * x for w, x in d) / W
    var = sum(w * (x - m) ** 2 for w, x in d) / W
    n_eff = W * W / sum(w * w for w, _ in d)
    return (var / n_eff) ** 0.5 if n_eff > 1 else 0.0


# --- 3. A megállapodás a jó lapok között --------------------------------------------

@dataclass
class Dontes:
    lap: Lap
    indok: str
    szabaly: str | None = None              # a jelzésrendszer kulcsa, ha az döntött
    helyzet: str = ""                       # INDITAS / HIVAS / SZINADAS / DOBAS / FELVEVO
    jo: list[Lap] = field(default_factory=list)


def _szep(l: Lap) -> str:
    return {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}[l.szin] + \
        {"A": "Á", "Q": "D", "J": "B", "T": "10"}.get(l.ertek, l.ertek)


def _lapsor(lapok) -> list[str]:
    """A jelzésrendszer lapsora egy színben: rangok csökkenő sorrendben."""
    return [l.ertek for l in sorted(lapok, key=lambda l: -l.rang)]


def _jok(stat: dict[Lap, LapStat] | None, legalis) -> list[Lap]:
    """A JÓ lapok; DD nélkül minden szabályos lap."""
    if not stat:
        return list(legalis)
    jo = [l for l, s in stat.items() if s.osztaly == "JO"]
    return jo or list(legalis)


def _racs_jel(jelzesek, racs_helyzet: str, felvetel: str, elso_felvevo_hivas: bool):
    """A rács első jele ebben a helyzetben (a `mikor`-os cellánál a Smith a
    felvevő első hívására értendő; egyébként a `kulonben`)."""
    cellak = ((jelzesek.racs.get(racs_helyzet) or {}).get(felvetel) or []) if jelzesek else []
    c = next((x for x in cellak if x["sorrend"] == 1), None)
    if c is None:
        return None
    if c.get("mikor"):
        if c["jel"] == "SMITH" and elso_felvevo_hivas:
            return "SMITH"
        return c.get("kulonben")
    return c["jel"]


def _magas_vagy_alacsony(jel: str | None, modszer: dict, akar: bool | None,
                         szamlalt: int) -> str | None:
    """A jel és a módszer -> 'MAGAS' / 'ALACSONY' (None: nincs mondanivaló)."""
    if jel in ("KERES", "ATTITUD"):
        if akar is None:
            return None
        kicsi_ker = modszer.get("KERES", "KICSI") == "KICSI"
        return ("ALACSONY" if akar else "MAGAS") if kicsi_ker else ("MAGAS" if akar else "ALACSONY")
    if jel in ("LAPSZAM", "MARADEK"):
        n = szamlalt - 1 if jel == "MARADEK" else szamlalt
        forditott = modszer.get("LAPSZAM", "FORDITOTT") == "FORDITOTT"
        paros = n % 2 == 0
        # fordított: kicsi-nagy = páros (párosból először kicsi)
        return ("ALACSONY" if paros else "MAGAS") if forditott else ("MAGAS" if paros else "ALACSONY")
    if jel == "SMITH":
        if akar is None:
            return None
        nagy_jo = modszer.get("SMITH", "NAGY_POZITIV") == "NAGY_POZITIV"
        return ("MAGAS" if akar else "ALACSONY") if nagy_jo else ("ALACSONY" if akar else "MAGAS")
    return None


def _valaszt_iranyban(jok: list[Lap], irany: str | None) -> Lap:
    """
    MAGAS: a legnagyobb NÉLKÜLÖZHETŐ a jók közül — figura nem, és a magában
    álló 10-es / 9-es sem (az lehet játszó lap; „nem a legkisebb” elég a
    jelzéshez). ALACSONY: a legkisebb.
    """
    from .jelzes import legnagyobb_nelkulozheto
    sor = sorted(jok, key=lambda l: -l.rang)
    if irany == "MAGAS":
        ertek = legnagyobb_nelkulozheto([l.ertek for l in sor])
        return next(l for l in sor if l.ertek == ertek)
    return sor[-1]


def _eros_szin(lapok: list[Lap]) -> bool:
    """Szan elleni saját hosszú erős szín: 5+ lap, 2+ figura, köztük Á vagy K."""
    fig = [l for l in lapok if l.ertek in FIGURAK]
    return len(lapok) >= 5 and len(fig) >= 2 and any(l.ertek in "AK" for l in fig)


def _szin_elsobbseg(allas: JatekAllas, jelzesek, kez: list[Lap], stat) -> Dontes | None:
    """
    Az indulás SZÍNÉNEK elsőbbsége a jelzésrendszer `szinvalasztas:` sora
    szerint (PARTNER_SZINE): a partner licitált színe megelőzi a DD
    színválasztását — a kivételekkel. A lap a színen belül a megállapodásé
    (a partner színében: PARTNER_SZINE helyzet); a DD csak a biztosan rossz
    lapot vétózza meg.
    """
    sor = jelzesek.szinvalasztas("PARTNER_SZINE", allas.felvetel) \
        if hasattr(jelzesek, "szinvalasztas") else None
    if not sor or not allas.partner_szinek:
        return None
    kiv = set(sor["kiveve"])

    def szinben(sz):
        return sorted([l for l in kez if l.szin == sz], key=lambda l: -l.rang)

    def konv_lap(sz, helyzet):
        try:
            r, _ = jelzesek.indito_lap(_lapsor(szinben(sz)), allas.felvetel, helyzet)
        except Exception:                  # noqa: BLE001
            r = None
        return _asz_alol(Lap(sz, r), kez, allas, jelzesek) if r else None

    def nem_rossz(l):
        return l is not None and (not stat or l not in stat or stat[l].osztaly != "BIZTOSAN_ROSSZ")

    def legjobb(lapok):
        return max(lapok, key=lambda l: (stat[l].ertek if stat and l in stat else 0.0,
                                         len(szinben(l.szin))))

    # a kivételek: saját erős szín (szan), saját lopás (szín, rövid aduval)
    sajat: list[tuple[Lap, str]] = []
    if "SAJAT_EROS_SZIN" in kiv and allas.adu is None:
        for sz in SZINEK:
            if sz not in allas.partner_szinek and _eros_szin(szinben(sz)):
                l = konv_lap(sz, "INDITAS")
                if nem_rossz(l):
                    sajat.append((l, "saját hosszú erős szín"))
    if "LOPAS" in kiv and allas.adu is not None:
        adu = len(szinben(allas.adu))
        if 1 <= adu <= 3:
            for sz in SZINEK:
                if sz not in (allas.adu, *allas.partner_szinek) and len(szinben(sz)) == 1:
                    l = szinben(sz)[0]
                    if nem_rossz(l):
                        sajat.append((l, "saját lopási esély (szingli, rövid adu)"))
    if sajat:
        lap = legjobb([l for l, _ in sajat])
        ok = next(o for l, o in sajat if l == lap)
        return Dontes(lap, f"indító kijátszás: {ok} — a partner színe helyett",
                      szabaly=sor["kulcs"], helyzet="INDITAS")

    jeloltek = []
    for sz in allas.partner_szinek:
        lapok = szinben(sz)
        if not lapok and "NINCS_LAP" in kiv:
            continue
        if len(lapok) == 1 and lapok[0].rang < 10 and "KIS_SZINGLI" in kiv:
            continue
        if not lapok:
            continue
        l = konv_lap(sz, "PARTNER_SZINE")
        if nem_rossz(l):
            jeloltek.append(l)
    if not jeloltek:
        return None
    lap = legjobb(jeloltek)
    return Dontes(lap, "indító kijátszás: a partner licitált színe (a megállapodás lapja)",
                  szabaly=sor["kulcs"], helyzet="INDITAS")


# HÍVÁS menet közben: két szín „egyforma”, ha a legjobb lapjuk értéke ennyin
# belül van (a pontozás egységében) — ilyenkor a megállapodás választhat.
SZIN_EGYENLO = 0.05
# a Smith-jel olvasása: a minták legalább ekkora (súlyozott) részében a
# partner lapja a legkisebb (illetve nem a legkisebb) volt
SMITH_BIZTOS = 0.65


def smith_utes(allas: JatekAllas) -> tuple[int, Lap] | None:
    """A felvevő első hívása (nem az első ütés) és benne a partner lapja,
    ha színt adott (nem ütésre), és a szín nem az indításé: (az ütés sorszáma, a lap)."""
    if not allas.vedo or not allas.lejatszott:
        return None
    inditas = allas.lejatszott[0][1].szin
    for i, utes in enumerate(allas.utesek):
        if i == 0 or not utes or vonal(utes[0][0]) != vonal(allas.felvevo):
            continue
        hivott = utes[0][1].szin
        if hivott == inditas or hivott == allas.adu:
            return None
        poz = next((j for j, (u, _) in enumerate(utes) if u == allas.partner()), None)
        if poz is None:
            return None
        lap = utes[poz][1]
        # csak a színadás jel: ha a partner ütést próbált vinni, a lapja nem Smith
        if lap.szin != hivott or _uti(lap, [l for _, l in utes[:poz]], allas.adu):
            return None
        return i, lap
    return None


def partner_smith(allas: JatekAllas, jelzesek, leosztasok: list[Leosztas],
                  sulyok: list[float] | None = None) -> str | None:
    """
    A partner SMITH-jele (2026-10-23): a felvevő első hívásában (szan ellen,
    a rács szerint) a partner lapja az indítás színéről beszél. Hogy a lapja
    nagy volt-e vagy kicsi, azt a kezét nem látva a mintákból becsüljük: a
    minták hányadában volt ez a legkisebb lapja abban a színben (ahol csak
    egy lapja volt, ott nem jelzés). Visszaad: 'VALT' (váltsunk) / 'FOLYTAT'
    (folytassuk az indítás színét) / None (nincs jel, vagy nem egyértelmű).
    """
    if not jelzesek or not leosztasok:
        return None
    if hasattr(jelzesek, "nincs_jelzes") and jelzesek.nincs_jelzes(allas.kontraktus.szint,
                                                                    allas.felvetel):
        return None
    if _racs_jel(jelzesek, "FELVEVO_HIV", allas.felvetel, True) != "SMITH":
        return None
    su = smith_utes(allas)
    if su is None:
        return None
    i, lap = su
    p = allas.partner()
    elotte = {l for utes in allas.utesek[:i] for _, l in utes}
    kicsi = osszes = 0.0
    for lo, w in zip(leosztasok, sulyok or [1.0] * len(leosztasok)):
        akkor = [l for l in lo.kezek[p].lapok if l.szin == lap.szin and l not in elotte]
        if len(akkor) < 2:
            continue
        osszes += w
        if lap == min(akkor, key=lambda l: l.rang):
            kicsi += w
    if not osszes:
        return None
    nagy_jo = dict(getattr(jelzesek, "modszer", {}) or {}).get("SMITH", "NAGY_POZITIV") == "NAGY_POZITIV"
    if kicsi / osszes >= SMITH_BIZTOS:
        return "VALT" if nagy_jo else "FOLYTAT"
    if kicsi / osszes <= 1 - SMITH_BIZTOS:
        return "FOLYTAT" if nagy_jo else "VALT"
    return None


def _sorozat_teteje(lap: Lap, allas: JatekAllas, legalis: list[Lap], stat) -> Lap:
    """
    FIGURA_SOROZAT a saját játékban: ha nem ütésre teszünk figurát (aláteszünk
    vagy dobunk), a zárt sorozatunk tetejét (DB-ből a D-t) — a partner így
    olvas belőle. Csak egyenértékű, az elemzés szerint ugyanannyit érő lappal.
    """
    akt = allas.aktualis
    elotte = [l for _, l in akt]
    if not akt or lap.ertek not in FIGURAK or _uti(lap, elotte, allas.adu):
        return lap
    kez = set(allas.lathato[allas.ules])
    lement = {l for _, l in allas.lejatszott}
    jobb = [l for l in legalis if l.szin == lap.szin and l.rang > lap.rang
            and _egyenerteku(l, lap, kez, lement)
            and (not stat or (l in stat and lap in stat
                              and stat[l].ertek >= stat[lap].ertek - 1e-9))]
    return max(jobb, key=lambda l: l.rang) if jobb else lap


# INDÍTÁSI ELVEK (2026-10-24, a szerkesztő döntései a Pavlicek-mérés után)
# Egy felvétel LOPÁSRA ÉPÜL, ha a felvevő a DD szerint legalább ennyivel több
# ütést visz a színfelvételben, mint ugyanazon a szinten szanban; a leosztás
# lopásos, ha a minták legalább felében ilyen.
LOPASOS_KULONBSEG = 2
LOPASOS_ARANY = 0.5


def _asz_alol(lap: Lap, kez, allas: JatekAllas, jelzesek) -> Lap:
    """ASZ_ALOL: színfelvétel ellen ász alól nem indulunk — az ásszal (a
    partner színében is; az aduban nem). A partner nem számít rá, és az ászt a felvevőnél
    feltételezve hibás lapot tesz."""
    if not allas.adu or lap.szin == allas.adu or not jelzesek \
            or not hasattr(jelzesek, "merlegeles") or not jelzesek.merlegeles("ASZ_ALOL"):
        return lap                           # az aduszínben az ász alóli kis adu rendben
    asz = Lap(lap.szin, "A")
    return asz if lap != asz and asz in kez else lap


def _dublo_tiltott(lap: Lap, kez, allas: JatekAllas, jelzesek) -> bool:
    """
    DUBLO_INDULAS: színfelvétel ellen figura nélküli dublóból (a felső lapja
    nem Á, K vagy D, és nem B10) nem indulunk szlem ellen — a lopáshoz előbb
    két ütést kell nyerni, az már a bukás —, és szan-jellegű (nem lopásra
    épülő) felvétel ellen sem: ott a hosszú színből kell ütéseket fejleszteni,
    a dubló csak időt veszít vagy ütést ad. A DD ezt nem látja: benne a
    partner mindig tudja, mikor kell visszahívni.
    """
    if not allas.adu or lap.szin == allas.adu or not jelzesek \
            or not hasattr(jelzesek, "merlegeles") or not jelzesek.merlegeles("DUBLO_INDULAS"):
        return False
    szin = sorted((l for l in kez if l.szin == lap.szin), key=lambda l: -l.rang)
    if len(szin) != 2:
        return False
    if szin[0].ertek in "AKQ" or (szin[0].ertek == "J" and szin[1].ertek == "T"):
        return False
    if allas.kontraktus.szint >= 6:
        return True
    return allas.lopasos_arany is not None and allas.lopasos_arany < LOPASOS_ARANY


def gem_vagy_szlem(k) -> bool:
    """Gém- vagy szlemszintű vállalás (szan 3+, nemes 4+, minor 5+)."""
    return (k.szin == "NT" and k.szint >= 3) or (k.szin in "HS" and k.szint >= 4) or k.szint >= 5


def felvetel_hiheto(allas: JatekAllas, kov) -> float | None:
    """
    FELVETEL_HIHETO (2026-10-24): indulásnál, az ellenfél önként licitált,
    kontrázatlan gémje vagy szleme ellen az egy bukás súlya (a sor `suly`-a;
    két vagy több bukás: a négyzete) — különben None. A Pavlicek-partikon a
    kibic gém és szlem ellen kétszer annyi bukást várt, mint ahány lett: a
    licit pontsávjaiból sorsolt kezek gyengébbek a valódinál (a jó játékos a
    gémet teljesíthetőnek látott lappal licitálja: illeszkedés, elosztás,
    kontrollok). Részszerződés és kontrázott vállalás ellen a becslés rendben volt.
    """
    if not kov or allas.lejatszott or not allas.vedo or allas.kontraktus.kontra:
        return None
    if not kov.van(allas.felvevo, "FELVETEL_HIHETO") or not gem_vagy_szlem(allas.kontraktus):
        return None
    return kov.suly.get("FELVETEL_HIHETO", 0.6)


def hiheto_suly(ered, cel: int, suly: float) -> float:
    """Egy minta súlya: a felvevő DD-ütése a legjobb védekezés mellett (a
    legjobb indulással) — teljesül: 1; egy bukás: suly; több: suly²."""
    try:
        felv = min(e.felvevo_osszesen for e in ered)
    except (AttributeError, ValueError):
        return 1.0
    buk = cel - felv
    return 1.0 if buk <= 0 else suly ** min(buk, 2)


def _dublo_kell_jelleg(allas: JatekAllas, jelzesek) -> bool:
    """Kell-e indulásnál a leosztás jellege (van-e tiltható dublónk)."""
    if allas.lejatszott or not allas.adu or allas.kontraktus.szint >= 6 or not jelzesek \
            or not hasattr(jelzesek, "merlegeles") or not jelzesek.merlegeles("DUBLO_INDULAS"):
        return False
    kez = allas.lathato.get(allas.ules) or []
    allas_ = JatekAllas.__new__(JatekAllas)
    allas_.__dict__.update(allas.__dict__)
    allas_.lopasos_arany = 0.0
    return any(_dublo_tiltott(l, kez, allas_, jelzesek) for l in kez)


def _sajat_kodok(jelzesek) -> set[str]:
    """Amit a kibic maga is betart (a `kovetkeztetes:` sorok `sajat: true`-ja)."""
    return {s["kovetkeztetes"] for s in (getattr(jelzesek, "kovetkeztetes_sorok", None) or [])
            if s.get("sajat")}


def _legolcsobb(lap: Lap, jok: list[Lap], allas: JatekAllas,
                kodok: set[str] = frozenset(KOVETKEZTETES_KODOK)) -> Lap:
    """
    Ellenjátékban, ha a lapunk VISZI az ütést (az eddigiek ellen): a jó lapok
    közül a vele egyenértékűek legkisebbike; negyedik kézben a legolcsóbb jó
    nyerő lap. Így a partner a lapunkból következtethet (amit mi is teszünk az
    övéből) — a felvevőnek nem segítünk, csak a valóságot mutatjuk.
    """
    akt = allas.aktualis
    elotte = [l for _, l in akt]
    # csak harmadik és negyedik kézben: második kézben a lap jelzés (lapszám)
    if len(akt) < 2 or not _uti(lap, elotte, allas.adu):
        return lap
    kez = set(allas.lathato[allas.ules])
    lement = {l for _, l in allas.lejatszott}
    if len(akt) == 3 and "LEGOLCSOBB_NYERO" in kodok:
        nyerok = [l for l in jok if _uti(l, elotte, allas.adu)]
        return min(nyerok, key=lambda l: (l.szin != lap.szin, l.rang)) if nyerok else lap
    if "LEGKISEBB_EGYENERTEKU" not in kodok:
        return lap
    egyenlok = [l for l in jok if l.szin == lap.szin and _uti(l, elotte, allas.adu)
                and _egyenerteku(l, lap, kez, lement)]
    return min(egyenlok or [lap], key=lambda l: l.rang)


def dontes(allas: JatekAllas, jelzesek=None, stat: dict[Lap, LapStat] | None = None) -> Dontes:
    d = _dontes(allas, jelzesek, stat)
    if allas.vedo and "FIGURA_SOROZAT" in _sajat_kodok(jelzesek):
        lap = _sorozat_teteje(d.lap, allas, list(allas.legalis), stat)
        if lap != d.lap:
            d = Dontes(lap, d.indok + "; a sorozat teteje (FIGURA_SOROZAT)", szabaly=d.szabaly,
                       helyzet=d.helyzet, jo=d.jo)
    return d


def _dontes(allas: JatekAllas, jelzesek=None, stat: dict[Lap, LapStat] | None = None) -> Dontes:
    legalis = list(allas.legalis)
    jo = _jok(stat, legalis)

    def utes_kulcs(l):                      # a pontozás szerinti várható érték (DD nélkül egyenlők)
        return stat[l].ertek if stat and l in stat else 0.0

    # FELVEVŐ (vagy az asztal): a DD legjobbja, azonos értékből a legkisebb
    if not allas.vedo:
        lap = max(jo, key=lambda l: (utes_kulcs(l), -l.rang))
        return Dontes(lap, "a legtöbb ütést hozó lap", helyzet="FELVEVO", jo=jo)

    akt = allas.aktualis
    kez = allas.lathato[allas.ules]
    modszer = dict(jelzesek.modszer) if jelzesek else {}

    # --- HÍVÁS (új ütés): színenként a megállapodás lapja, a színt a DD dönti
    if not akt:
        helyzet = "INDITAS" if not allas.lejatszott else "HIVAS"
        konv: dict[Lap, str] = {}
        if jelzesek:
            for sz in SZINEK:
                szinben = [l for l in kez if l.szin == sz]
                if not szinben:
                    continue
                try:
                    r, sor = jelzesek.indito_lap(_lapsor(szinben), allas.felvetel, helyzet)
                except Exception:          # noqa: BLE001 — a megállapodás hibája nem állíthatja meg
                    r, sor = None, None
                if r:
                    lap_ = Lap(sz, r)
                    if helyzet == "INDITAS":
                        uj = _asz_alol(lap_, kez, allas, jelzesek)
                        if uj != lap_:
                            konv[uj] = "MERLEGELES/ASZ_ALOL"
                            continue
                    konv[lap_] = sor.kulcs if sor else ""
        # INDÍTÓ KIJÁTSZÁS: itt még nincs igazi információ (az asztal sem
        # látszik), a szabály ERŐS: a lap mindig a megállapodásé, a DD csak a
        # SZÍNT választja (a megállapodás lapjainak értéke szerint), és csak a
        # biztosan rossz lapot vétózza meg. Így egy ász nem nyerhet az üres
        # figura alóli 4. lap ellen pusztán a minta zajával.
        if helyzet == "INDITAS" and jelzesek:
            elso = _szin_elsobbseg(allas, jelzesek, kez, stat)
            if elso is not None:
                return elso
        if helyzet == "INDITAS" and konv:
            jeloltek = [l for l in konv if not stat or l not in stat
                        or stat[l].osztaly != "BIZTOSAN_ROSSZ"]
            szabad = [l for l in jeloltek if not _dublo_tiltott(l, kez, allas, jelzesek)]
            if szabad and len(szabad) < len(jeloltek):
                jeloltek = szabad
                lap = max(jeloltek, key=lambda l: (utes_kulcs(l),
                                                   len([x for x in kez if x.szin == l.szin])))
                mi = "szlem" if allas.kontraktus.szint >= 6 else "szan-jellegű felvétel"
                return Dontes(lap, f"indító kijátszás: a megállapodás szerinti lap; {mi} ellen "
                                   "nem dublóból (DUBLO_INDULAS)", szabaly=konv[lap],
                              helyzet=helyzet, jo=jo)
            if jeloltek:
                lap = max(jeloltek, key=lambda l: (utes_kulcs(l),
                                                   len([x for x in kez if x.szin == l.szin])))
                return Dontes(lap, "indító kijátszás: a megállapodás szerinti lap"
                              + ("; a színt az elemzés választotta" if stat else ""),
                              szabaly=konv[lap], helyzet=helyzet, jo=jo)
        kerese = jelzesek.merlegeles("PARTNER_KERESE") \
            if helyzet == "HIVAS" and jelzesek and hasattr(jelzesek, "merlegeles") else None
        kert = partner_kert_szine(allas, jelzesek) if kerese else None
        kertben = _partnersegben(stat, [l for l in legalis if kert and l.szin == kert], jo, kerese)
        if kertben:
            lap = next((l for l in kertben if l in konv), None) or max(
                kertben, key=lambda l: (round(utes_kulcs(l), 6),
                                        l.rang if l.ertek in FIGURAK else -l.rang))
            return Dontes(lap, "menet közbeni hívás: a partner dobással kért színe"
                          + (" (az elemzés szerint ez is jó lap)" if lap in jo else
                             " (a partnerség kedvéért, az elemzés szerint alig rosszabb)"),
                          szabaly=kerese["kulcs"], helyzet=helyzet, jo=jo)

        def legjobb_a_szinben(sz):
            lapok = [l for l in legalis if l.szin == sz]
            k = next((l for l in lapok if l in konv), None)
            if k is not None and (not stat or k in jo):
                return k, True
            return max(lapok, key=lambda l: (round(utes_kulcs(l), 6),
                                             l.rang if l.ertek in FIGURAK else -l.rang)), False

        if helyzet == "HIVAS" and stat:
            # A SZÍNT AZ ELEMZÉS VÁLASZTJA (2026-10-23, a szerkesztő döntése): a
            # színek a legjobb lapjuk értéke szerint; a megállapodás csak a
            # színen belül dönt a lapról, színt csak a gyakorlatilag egyforma
            # (SZIN_EGYENLO-n belüli) színek közül választhat. A fred-mérésben a
            # megállapodás négyszer választott a „jó” lapok közül olyan színt,
            # amely a DD szerint rossz volt.
            szin_ertek = {}
            for sz in SZINEK:
                ert = [stat[l].ertek for l in legalis if l.szin == sz and l in stat
                       and stat[l].osztaly != "BIZTOSAN_ROSSZ"]
                if ert:
                    szin_ertek[sz] = max(ert)
            if szin_ertek:
                legjobb = max(szin_ertek.values())
                # a partner Smith-jele: váltsunk / folytassuk az indítás színét —
                # a partnerség kedvéért, ha az elemzés nem mond neki jelentősen
                # (a PARTNER_KERESE tűrésénél többel) ellent
                smith = allas.partner_smith if kerese else None
                if smith:
                    inditas = allas.lejatszott[0][1].szin
                    from .jelzes import MERLEGELES_TURES
                    tures = float(kerese.get("tures", MERLEGELES_TURES.get("PARTNER_KERESE", 0.0)))
                    kert_szinek = [sz for sz in szin_ertek
                                   if (sz != inditas) == (smith == "VALT")
                                   and szin_ertek[sz] >= legjobb - tures - 1e-9]
                    if kert_szinek:
                        sz = max(kert_szinek, key=lambda x: szin_ertek[x])
                        lap, _ = legjobb_a_szinben(sz)
                        mit = "vált" if smith == "VALT" else "folytatja az indítás színét"
                        return Dontes(lap, f"menet közbeni hívás: a partner Smith-jele szerint {mit}"
                                      + ("" if szin_ertek[sz] >= legjobb - SZIN_EGYENLO else
                                         " (a partnerség kedvéért, az elemzés szerint alig rosszabb)"),
                                      szabaly=kerese["kulcs"], helyzet=helyzet, jo=jo)
                egyformak = [sz for sz, e in szin_ertek.items() if e >= legjobb - SZIN_EGYENLO]
                jelolt = [legjobb_a_szinben(sz) for sz in egyformak]
                konvben = [l for l, k in jelolt if k]
                if konvben:
                    lap = max(konvben, key=lambda l: (utes_kulcs(l),
                                                      len([x for x in kez if x.szin == l.szin])))
                    return Dontes(lap, "menet közbeni hívás: a színt az elemzés választotta, "
                                       "a lapot a megállapodás", szabaly=konv[lap],
                                  helyzet=helyzet, jo=jo)
                lap = max((l for l, _ in jelolt), key=lambda l: (round(utes_kulcs(l), 6),
                                                                l.rang if l.ertek in FIGURAK else -l.rang))
                return Dontes(lap, "menet közbeni hívás: a színt az elemzés választotta "
                                   "(a megállapodás lapja nem jó lap — a legjobb lap)",
                              helyzet=helyzet, jo=jo)
        jo_konv = [l for l in jo if l in konv]
        if jo_konv:
            lap = max(jo_konv, key=lambda l: (utes_kulcs(l), len([x for x in kez if x.szin == l.szin])))
            return Dontes(lap, ("indító kijátszás" if helyzet == "INDITAS" else "menet közbeni hívás")
                          + ": a megállapodás szerinti lap a jó lapok közül",
                          szabaly=konv[lap], helyzet=helyzet, jo=jo)
        lap = max(jo, key=lambda l: (round(utes_kulcs(l), 6),
                                     l.rang if l.ertek in FIGURAK else -l.rang))
        return Dontes(lap, ("indító kijátszás" if helyzet == "INDITAS" else "menet közbeni hívás")
                      + ": a megállapodás lapja nem jó lap — a legjobb lap",
                      helyzet=helyzet, jo=jo)

    hivott = akt[0][1].szin
    hivo = akt[0][0]
    szinben = [l for l in kez if l.szin == hivott]
    elso_felvevo_hivas = (vonal(hivo) == vonal(allas.felvevo) and not any(
        vonal(u[0][0]) == vonal(allas.felvevo) for u in allas.utesek[:-1] if u))

    # „szlem ellen nem jelzünk” (jelzésrendszer-sor): színadásnál és dobásnál
    # a legkisebb jó lap, a rács nem él
    tilt = jelzesek.nincs_jelzes(allas.kontraktus.szint, allas.felvetel) \
        if jelzesek and hasattr(jelzesek, "nincs_jelzes") else None

    # --- SZÍNADÁS MÁSODIK KÉZBEN: a jelzésrendszer `helyzet: MASODIK_KEZ` sora
    # (pl. dubló figurából a figura). A DD itt vak: a lap értéke sokszor az,
    # hogy UTÁNA mi tudunk mindent (ütésben maradunk, látjuk a lapokat) — a
    # nyílt lapos elemzésben az információnak nincs ára. Ezért a szabály nyer,
    # ha a lap nem biztosan rossz.
    if szinben and len(akt) == 1 and jelzesek:
        hivo_lap = akt[0][1]
        fig = max(szinben, key=lambda l: l.rang)
        asztal_lapjai = [l for l in allas.lathato.get(allas.asztal, []) if l.szin == hivott]
        if akt[0][0] == allas.asztal:
            asztal_lapjai = asztal_lapjai + [hivo_lap]
        kornyezet = {
            "asztal": "ELOTTUNK" if akt[0][0] == allas.asztal else "UTANUNK",
            # az asztal lapjai a 10-es és a figuránk között (a hívott lappal együtt)
            "kozbenso": sum(1 for l in asztal_lapjai if 10 <= l.rang < fig.rang),
            "hivott": "NAGY" if hivo_lap.rang >= 10 else "KICSI"}
        try:
            r, sor = jelzesek.indito_lap(_lapsor(szinben), allas.felvetel, "MASODIK_KEZ",
                                         kornyezet=kornyezet)
        except Exception:                  # noqa: BLE001
            r, sor = None, None
        if r and sor and sor.helyzet == "MASODIK_KEZ":
            lap = Lap(hivott, r)
            if lap in allas.legalis and (lap != fig or _uti(lap, [hivo_lap], allas.adu)) and (
                    not stat or lap not in stat or stat[lap].osztaly != "BIZTOSAN_ROSSZ"):
                return Dontes(lap, "második kéz: " + (sor.megjegyzes or "a megállapodás lapja"),
                              szabaly=sor.kulcs, helyzet="SZINADAS", jo=jo)

    # --- MÉRLEGELÉS: A PARTNER KÉRÉSE (`merlegeles: PARTNER_KERESE`). Ha a partner
    # dobással kért egy színt, és nálunk van belőle, ütést veszünk (lopunk,
    # átvesszük az ütését), hogy mi hívhassuk — ha az elemzés szerint ez
    # legfeljebb a sor tűrésével rosszabb: a partnerség kedvéért.
    kerese_ = jelzesek.merlegeles("PARTNER_KERESE") \
        if jelzesek and hasattr(jelzesek, "merlegeles") and stat and len(akt) >= 2 else None
    kert_ = partner_kert_szine(allas, jelzesek) if kerese_ else None
    if kert_ and kert_ != hivott and any(l.szin == kert_ for l in kez):
        elotte = [l for _, l in akt]
        nyerok = _partnersegben(stat, [l for l in legalis if _uti(l, elotte, allas.adu)
                                       and l.szin != kert_], jo, kerese_)
        if nyerok and _nyero(akt, allas.adu)[0] != allas.ules:
            lap = min(nyerok, key=lambda l: (l.szin != hivott, l.rang))
            sajat_ = _sajat_kodok(jelzesek)
            if sajat_ and lap.szin == hivott:
                lap = _legolcsobb(lap, [l for l in nyerok if l.szin == hivott], allas, sajat_)
            mit = "lopunk" if lap.szin != hivott else "ütést veszünk"
            return Dontes(lap, f"mérlegelés: a partner kért színe ({_szep(Lap(kert_, '2'))[0]}) — "
                               f"{mit}, hogy mi hívhassuk"
                          + ("" if lap in jo else " (a partnerség kedvéért, az elemzés szerint alig rosszabb)"),
                          szabaly=kerese_["kulcs"], helyzet="SZINADAS" if lap.szin == hivott else "DOBAS",
                          jo=jo)

    # --- MÉRLEGELÉS: ÁTVÉTEL (a jelzésrendszer `merlegeles: ATVETEL` sora). A DD
    # a partnert is mindentudónak hiszi: ha mindegy, ki viszi az ütést, a
    # folytatást rábízza. A valóságban jobb, ha MI folytatunk, amikor tudjuk,
    # mit kell: a partner ütését nyerő lappal átvesszük, ha ez az elemzés
    # szerint semmibe sem kerül.
    atv = jelzesek.merlegeles("ATVETEL") if jelzesek and hasattr(jelzesek, "merlegeles") else None
    if atv and stat and szinben and len(akt) >= 2 and \
            _nyero(akt, allas.adu)[0] == allas.partner():
        elotte = [l for _, l in akt]
        nyerok = [l for l in jo if l.szin == hivott and _uti(l, elotte, allas.adu)]
        tobbi = [l for l in jo if l not in nyerok]
        if nyerok and (not tobbi or max(utes_kulcs(l) for l in nyerok)
                       >= max(utes_kulcs(l) for l in tobbi) - PAROS_MIN):
            lap = min(nyerok, key=lambda l: l.rang)
            sajat_ = _sajat_kodok(jelzesek)
            if sajat_:
                lap = _legolcsobb(lap, nyerok, allas, sajat_)
            return Dontes(lap, "mérlegelés: a partner ütését átvesszük (az elemzés szerint "
                               "mindegy), és mi folytatunk", szabaly=atv["kulcs"],
                          helyzet="SZINADAS", jo=jo)

    # --- SZÍNADÁS: a rács jele dönti, magas vagy alacsony lap a jók közül
    if szinben:
        jok_szinben = [l for l in jo if l.szin == hivott] or jo
        sajat = _sajat_kodok(jelzesek)
        if tilt:
            lap = min(jok_szinben, key=lambda l: l.rang)
            if sajat:
                lap = _legolcsobb(lap, jok_szinben, allas, sajat)
            return Dontes(lap, f"színadás: {tilt['szint']} szintű kontraktus ellen nem jelzünk "
                               "— a legkisebb jó lap", szabaly=tilt["kulcs"],
                          helyzet="SZINADAS", jo=jo)
        racs_h = "PARTNER_INDIT" if hivo == allas.partner() else "FELVEVO_HIV"
        jel = _racs_jel(jelzesek, racs_h, allas.felvetel, elso_felvevo_hivas)
        if jel == "SMITH":
            indito_szin = allas.lejatszott[0][1].szin
            akar = any(l.ertek in "AKQ" for l in kez if l.szin == indito_szin)
        else:
            akar = any(l.ertek in "AKQ" for l in szinben) and len(szinben) >= 2
        irany = _magas_vagy_alacsony(jel, modszer, akar, len(szinben))
        lap = _valaszt_iranyban(jok_szinben, irany)
        if sajat and len(akt) >= 2 and _uti(lap, [l for _, l in akt], allas.adu):
            # harmadik / negyedik kézben ütést viszünk: nem jelzünk, a legkisebb egyenértékű / legolcsóbb nyerő lap
            olcso = _legolcsobb(lap, jok_szinben, allas, sajat)
            return Dontes(olcso, "színadás: az ütést a legolcsóbb (egyenértékűek közül a "
                                 "legkisebb) jó lappal visszük", helyzet="SZINADAS", jo=jo)
        if len(jok_szinben) == 1:
            return Dontes(lap, "színadás: egyetlen jó lap", helyzet="SZINADAS", jo=jo)
        nev = {"KERES": "kérés", "ATTITUD": "attitűd", "LAPSZAM": "lapszám",
               "MARADEK": "maradék lapszám", "SMITH": "Smith"}.get(jel or "", "")
        return Dontes(lap, (f"színadás: {nev} — {'magas' if irany == 'MAGAS' else 'alacsony'} lap a jók közül"
                            if irany else "színadás: a legkisebb jó lap"),
                      szabaly=f"RACS/{racs_h}" if irany else None, helyzet="SZINADAS", jo=jo)

    # --- DOBÁS (vagy lopás): ha a jók között adu van és a DD azt mondja, az
    adu_jo = [l for l in jo if allas.adu and l.szin == allas.adu]
    nem_adu = [l for l in jo if l not in adu_jo]
    if adu_jo and (not nem_adu or max(utes_kulcs(l) for l in adu_jo) > max(utes_kulcs(l) for l in nem_adu)):
        lap = min(adu_jo, key=lambda l: l.rang)
        return Dontes(lap, "lopás: a legkisebb jó adu", helyzet="DOBAS", jo=jo)
    jel = None if tilt else _racs_jel(jelzesek, "DOBAS", allas.felvetel, False)
    jeloltek = nem_adu or jo
    if jel == "PREF" and modszer.get("PREF") == "EGYENES":
        # egyenes: kis lap kéri a dobott színt, nagy nem kéri — a legerősebb
        # (nem adu) színünket kérjük, a leggyengébből dobunk
        erosseg = {sz: _hcp([l for l in kez if l.szin == sz]) for sz in SZINEK if sz != allas.adu}
        kert = max(erosseg, key=lambda sz: (erosseg[sz], sum(1 for l in kez if l.szin == sz)))
        nem_kert = [l for l in jeloltek if l.szin != kert and l.ertek not in FIGURAK]
        if nem_kert:
            gyenge = min({l.szin for l in nem_kert}, key=lambda sz: erosseg.get(sz, 0))
            lap = max((l for l in nem_kert if l.szin == gyenge), key=lambda l: l.rang)
            return Dontes(lap, "dobás: egyenes preferencia — nagy lap: ezt a színt nem kérem",
                          szabaly="RACS/DOBAS", helyzet="DOBAS", jo=jo)
        kertben = [l for l in jeloltek if l.szin == kert and l.ertek not in FIGURAK]
        if kertben:
            lap = min(kertben, key=lambda l: l.rang)
            return Dontes(lap, "dobás: egyenes preferencia — kis lap: ezt a színt kérem",
                          szabaly="RACS/DOBAS", helyzet="DOBAS", jo=jo)
    # egyéb (pl. Lavinthal — még nincs): a leggyengébb színből a legkisebb jó lap
    lap = min(jeloltek, key=lambda l: (_hcp([x for x in kez if x.szin == l.szin]), l.rang))
    if tilt:
        return Dontes(lap, f"dobás: {tilt['szint']} szintű kontraktus ellen nem jelzünk — a "
                           "leggyengébb színből a legkisebb jó lap", szabaly=tilt["kulcs"],
                      helyzet="DOBAS", jo=jo)
    return Dontes(lap, "dobás: a leggyengébb színből a legkisebb jó lap", helyzet="DOBAS", jo=jo)


# --- Egyben ------------------------------------------------------------------------

@dataclass
class Eredmeny:
    dontes: Dontes
    stat: dict[Lap, LapStat] | None
    mintak: int = 0
    lazitott: bool = False
    dd_hiba: str | None = None
    ms: int = 0
    kimerito: bool = False
    ismeretlen: int = 0
    tures: float = JO_TURES
    kizart_jatek: int = 0
    leertekelt: dict = field(default_factory=dict)
    pontozas: str = "IMP"
    megallt: str = ""               # BIZTOS / IDO / MAX / KIMERITO / ELFOGYOTT
    osszevont: bool = False         # kimerítő elemzés a kis lapok összevonásával
    igazitott: list[str] = field(default_factory=list)  # a licitjüket a lapokhoz igazítottuk
    lopasos_arany: float | None = None  # indulásnál: a minták hányadában épül a felvétel lopásra
    terites: object | None = None   # terites.Terites, ha a felvevő terít (claim)


# Terítés (2026-10-24): a felvevő oldal hívásánál, ha a biztos terv (motor/terites.py)
# az összes hátralévő ütést hozza — vagy annyit, amennyit a DD egyik mintában sem
# múl felül (tovább játszva sem lenne több) —, a válasz mellé terítési ajánlat megy
# (meta.kibic.claim). A lap a terv első lapja. KIBIC_TERITES=0: kikapcsolva.
TERITES = os.getenv("KIBIC_TERITES", "1").strip() != "0"


def jatek_dontes(allas: JatekAllas, jelzesek=None, kenyszertar: dict | None = None,
                 dd_fv=None, ido_keret_s: float = 6.0, db: int = 40,
                 mag: int | None = None, valoszinu: dict | None = None) -> Eredmeny:
    """A négy lépés egyben. Ha egyetlen szabályos lap van, nincs mit számolni."""
    start = time.time()
    if len(allas.legalis) == 1:
        lap = next(iter(allas.legalis))
        return Eredmeny(Dontes(lap, "kényszerű lap", helyzet="KENYSZER", jo=[lap]), None)
    tr = None
    if TERITES and not allas.vedo and not allas.aktualis:
        from .terites import terites
        tr = terites(allas)
        if tr is not None and tr.mind and tr.elso in allas.legalis:
            return Eredmeny(Dontes(tr.elso, "terítés: minden hátralévő ütés biztos",
                                   szabaly="TERITES", helyzet="FELVEVO", jo=[tr.elso]),
                            None, ms=int((time.time() - start) * 1000), terites=tr)
    stat, n, lazitott, hiba = None, 0, False, None
    kimerito, ismeretlen, tures, kizart_jatek, leertekelt = False, 0, JO_TURES, 0, {}
    if not allas.partner_szinek:
        allas.partner_szinek = partner_szinei(allas, kenyszertar)
    megallt = ""
    osszevont = False
    igazitott: list[str] = []
    jelleg = None
    try:
        if dd_fv is None:
            from ..solver.dds import lap_elemzes as dd_fv
        kov = kovetkeztetes_beallitas(allas, jelzesek, [u for u in ULESEK if u not in allas.lathato],
                                      valoszinu)
        jatszott = [str(l) for _, l in allas.lejatszott]
        gy = DDGyujto(allas, allas.pontozas)
        # indulásnál, ha van tiltható dublónk: a leosztás jellege (lopásra épül-e)
        jelleg = [0.0, 0.0] if _dublo_kell_jelleg(allas, jelzesek) else None
        hiheto = felvetel_hiheto(allas, kov)
        szan_k = Kontraktus(allas.kontraktus.szint, "NT", "", allas.kontraktus.felvevo)
        # 1. köteg; ha kimerítő, ez az összes elosztás
        koteg = min(db, KOTEG) if db > MIN_MINTA else db
        k = 0
        while True:
            m = mintavetel(allas, kenyszertar, db=koteg,
                           mag=None if mag is None else mag + k,
                           max_proba=max(4000, 30 * koteg), kovetkeztetes=kov)
            if k == 0:
                if allas.vedo and not allas.aktualis and allas.lejatszott:
                    allas.partner_smith = partner_smith(allas, jelzesek, m.leosztasok, m.sulyok)
                kimerito, ismeretlen = m.kimerito, m.ismeretlen
                osszevont = m.osszevont
                igazitott = list(m.igazitott)
                # a tűrés a bizonytalansággal arányos; kimerítő elemzésnél nincs minta-zaj
                tures = 0.0 if kimerito else JO_TURES * min(1.0, ismeretlen / TURES_TELJES_ISMERETLEN)
            lazitott = lazitott or m.lazitott
            kizart_jatek += m.kizart_jatek
            for kod, x in m.leertekelt.items():
                leertekelt[kod] = leertekelt.get(kod, 0) + x
            if not m.leosztasok:
                megallt = megallt or "ELFOGYOTT"
                break
            sulyok = m.sulyok or [1.0] * len(m.leosztasok)
            ido_le = False
            # sok mintázatnál (kis lapok összevonva) a véletlen sorrendű teljes
            # sokaságon is megállhat, ha a döntés eldőlt
            menet_kozben = kimerito and len(m.leosztasok) > KIMERITO_HATAR
            for lo, w in zip(m.leosztasok, sulyok):
                if gy.n >= 6 and time.time() - start > ido_keret_s:
                    ido_le = True
                    break
                ered = dd_fv(lo, jatszott, allas.kontraktus)
                if hiheto is not None:
                    w *= hiheto_suly(ered, 6 + allas.kontraktus.szint, hiheto)
                gy.hozzaad(ered, w)
                if jelleg is not None:
                    try:
                        szin_u = min(e.felvevo_osszesen for e in ered)
                        szan_u = min(e.felvevo_osszesen for e in dd_fv(lo, jatszott, szan_k))
                        jelleg[0] += w
                        if szin_u - szan_u >= LOPASOS_KULONBSEG:
                            jelleg[1] += w
                    except (AttributeError, ValueError):
                        jelleg = None
                if menet_kozben and gy.n >= MIN_MINTA and gy.n % KOTEG == 0 and gy.biztos():
                    megallt = "BIZTOS"
                    break
            k += 1
            if kimerito:
                if gy.n < len(m.leosztasok):        # nem nézte meg mindet: van minta-zaj
                    tures = JO_TURES * min(1.0, ismeretlen / TURES_TELJES_ISMERETLEN)
                    megallt = megallt or "IDO"
                else:
                    megallt = "KIMERITO"
                break
            if ido_le:
                megallt = "IDO"
                break
            if gy.n >= db:
                megallt = "MAX"
                break
            if gy.n >= MIN_MINTA and gy.biztos():
                megallt = "BIZTOS"
                break
            koteg = min(KOTEG, db - gy.n)
        n = gy.n
        if n:
            stat = gy.stat(tures, paros=bool(allas.lejatszott))
    except ImportError as e:            # nincs DDS (endplay)
        hiba = str(e)
    except LejatszasHiba:
        raise
    except Exception as e:              # noqa: BLE001 — a DD hibája: a megállapodás marad
        hiba = f"{type(e).__name__}: {e}"
        stat = None
    if jelleg and jelleg[0]:
        allas.lopasos_arany = jelleg[1] / jelleg[0]
    d = dontes(allas, jelzesek, stat)
    # részleges terítés: ha egyik mintában sem lenne több ütés, mint a biztos terv
    if tr is not None and stat and \
            max(s.utes for s in stat.values()) <= tr.utesek + 1e-9:
        if tr.elso is not None and tr.elso in allas.legalis:
            d = Dontes(tr.elso, "terítés: tovább játszva sem lenne több ütés",
                       szabaly="TERITES", helyzet="FELVEVO", jo=[tr.elso])
    else:
        tr = None
    return Eredmeny(d, stat, n, lazitott, hiba, int((time.time() - start) * 1000),
                    kimerito, ismeretlen, tures, kizart_jatek, leertekelt,
                    allas.pontozas, megallt, osszevont, igazitott, allas.lopasos_arany, tr)


def magyarazat(e: Eredmeny) -> str:
    """Rövid, KÉZ NÉLKÜLI magyarázat a válaszba (a lapok osztálya csak a metában)."""
    d = e.dontes
    if d.helyzet == "KENYSZER":
        return "Kényszerű lap."
    if e.terites is not None and e.terites.mind:
        return "Terítés: minden hátralévő ütés biztos."
    alap = d.indok[:1].upper() + d.indok[1:]
    if e.stat and e.kimerito:
        return f"{alap} (mind a(z) {e.mintak} lehetséges elosztás double dummy elemzése alapján)."
    if e.stat:
        return f"{alap} ({e.mintak} lehetséges leosztás double dummy elemzése alapján)."
    return f"{alap} (elemzés nélkül: {e.dd_hiba or 'nincs DDS'})."


def meta(e: Eredmeny, reszletes: bool = False) -> dict:
    ki = {"situation": e.dontes.helyzet, "samples": e.mintak, "relaxed": e.lazitott,
          "exhaustive": e.kimerito, "unknown_cards": e.ismeretlen,
          "play_inference_excluded": e.kizart_jatek,
          "inference_weighted": dict(e.leertekelt),
          "tolerance": round(e.tures, 3),
          "scoring": e.pontozas, "stopped": e.megallt,
          "small_cards_merged": e.osszevont, "bidding_adjusted": e.igazitott,
          "ruff_based_share": None if e.lopasos_arany is None else round(e.lopasos_arany, 3),
          "rule": e.dontes.szabaly, "dd_error": e.dd_hiba, "elapsed_ms": e.ms}
    if e.terites is not None:
        from .terites import szoveg
        t = e.terites
        ki["claim"] = {"tricks": t.utesek, "remaining": t.hatralevo, "total_tricks": t.osszes,
                       "statement": szoveg(t)}
    if e.stat:
        db = {"JO": 0, "TALAN": 0, "BIZTOSAN_ROSSZ": 0}
        for s in e.stat.values():
            db[s.osztaly] += 1
        ki["classes"] = db
        if reszletes:       # tanító mód: laponként (a kéz lapjai! — élesben nem megy ki)
            ki["cards"] = {str(l): {"class": s.osztaly, "tricks": round(s.utes, 2),
                                    "value": round(s.ertek, 3),
                                    "loss": round(s.veszt, 2), "worse_share": round(s.rossz, 2)}
                           for l, s in sorted(e.stat.items(), key=lambda x: -x[1].utes)}
    return ki
