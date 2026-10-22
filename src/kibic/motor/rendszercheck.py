"""
RENDSZER-ELLENŐRZÉS: van-e ELLENTMONDÁS a (feloldott) szabálylistában?

Két szabály ellentmond egymásnak, ha
    * UGYANABBAN a licithelyzetben,
    * UGYANARRA a kézre
    * mindkettő teljesül,
    * KÜLÖNBÖZŐ licitet javasolnak,
    * és a döntési sorrend (specifikusság, prioritás) sem dönt köztük.

Ilyenkor a kibic "bizonytalan" lesz, és valójában a feldolgozási sorrend
választ — ez a legcsendesebb hibafajta, mert a licit ettől még
értelmesnek látszik. Formálisan nehéz eldönteni (a feltételek
kifejezésfák, zónával, színváltozókkal), ezért MINTAVÉTELLEL mérünk:

    1. minden szabály mintájából kiolvassuk az ELŐZMÉNYT (a minta az
       utolsó token nélkül), és konkrét licitmenetté bontjuk;
    2. a menet alapján a soron következő játékos korábbi licitjeiből
       kényszert számolunk (propagálás), és OLYAN kezeket húzunk, amik
       ezzel összeférnek — így nem vizsgálunk lehetetlen helyzetet;
    3. minden kézre lefuttatjuk a licitmotort döntés nélkül (MERLEGELO),
       és megnézzük a jelölteket.

Amit jelent:
    UTKOZES      egy helyzetben a legjobb rangú jelöltek több különböző
                 licitet adnak — ezt JAVÍTANI kell (prioritás / feltétel);
    ARNYEKOLT    a szabály teljesült, de SOHA nem nyert — lehet
                 szándékos (tartalék), de gyakran elírás;
    NEM_TELJESULT a helyzet előállt, de a szabály egyszer sem teljesült —
                 talán túl szűk, vagy a korábbi licitek kizárják;
    ELLENORIZHETETLEN  a minta nem bontható konkrét menetre (`..`, `*`).

A modul adatbázis nélkül is fut: YAML-forrásokból közvetlenül
(`feloldas_forrasokbol`), így import ELŐTT ellenőrizhető a rendszer.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from ..domain import Kez, Lap, kovetkezo_ules
from ..domain.kartya import LAPOK
from .feloldas import Feloldas, Sor, feloldas_altalanos
from .kifejezes import rendszer_kontextus
from .licital import Licitmotor
from .minta import Minta, MintaHiba, kanonizal, kibont, minta_parse
from .propagal import Propagalo

PAKLI = [Lap(sz, e) for sz in "SHDC" for e in LAPOK]


def _HCP(k: Kez) -> float:
    from ..domain import ERTEKELOK
    return float(ERTEKELOK["HCP"](k))
BELIK = ("NONE", "NS", "EW", "ALL")


# --- YAML-forrás -> Sor (a feloldáshoz) -------------------------------

def sor_forrasbol(s, rendszer_kod: str, melyseg: int, sorszam: int) -> Sor:
    """Egy `impex.rendszer_yaml.SzabalySor` -> `feloldas.Sor`."""
    x = Sor(sorszam, 0, rendszer_kod, melyseg, s.kulcs, s.minta,
            s.alfejezet, s.prioritas, s.specifikussag, s.feltetel,
            s.feltetel_szoveg, s.magyarazat, s.forsz, s.ismeretlen)
    x.jelentes = s.jelentes
    x.ha_feltetel = s.ha_feltetel
    x.ha_feltetel_szoveg = getattr(s, "ha_feltetel_szoveg", None)
    x.elvaras = s.elvaras
    x.magyarazat_en = s.magyarazat_en
    x.dontesi_mod = s.dontesi_mod
    x.szabaly_fajta = s.szabaly_fajta
    x.ag = s.ag
    x.alert = s.alert
    x.fejezet = s.fejezet
    x.forras = s.forras_hely
    return x


def _hasznalhato(allapot: str | None, csak_elfogadott: bool) -> bool:
    """
    A YAML-ban az állapot többnyire nincs megadva: az import dönti el
    (új sor = JAVASOLT). Az ellenőrzés alapból a TESZT MÓD szerint dolgozik:
    minden sort néz, ami nem ELVETETT és nem JEGELT.
    """
    if csak_elfogadott:
        return allapot == "ELFOGADOTT"
    return allapot not in ("ELVETETT", "JEGELT")


def feloldas_forrasokbol(forrasok: dict, kod: str,
                         csak_elfogadott: bool = False,
                         kulso=None) -> tuple[Feloldas, list[str]]:
    """
    Feloldás YAML-forrásokból, ugyanazzal a logikával, mint az
    adatbázisé. `kulso(kod) -> (sorok, hivatkozott kódok) | None`: a
    YAML-ban nem szereplő rendszerek (pl. az SQL-lel betöltött FESU).
    Visszaad: (feloldás, hiányzó rendszerek listája).
    """
    hianyzo: list[str] = []
    szamlalo = iter(range(1, 10**9))

    def sorok_fn(k: str, melyseg: int) -> list[Sor]:
        if k in forrasok:
            return [sor_forrasbol(s, k, melyseg, next(szamlalo))
                    for s in forrasok[k].sorok
                    if _hasznalhato(s.allapot, csak_elfogadott)]
        if kulso is not None:
            r = kulso(k)
            if r is not None:
                return r[0]
        hianyzo.append(k)
        return []

    def hiv_fn(k: str) -> list:
        if k in forrasok:
            alap = [forrasok[k].alapja] if forrasok[k].alapja else []
            return alap + [(h.kod, h.beallitas) if getattr(h, "beallitas", None) else h.kod
                           for h in forrasok[k].hivatkozasok if h.aktiv]
        if kulso is not None:
            r = kulso(k)
            if r is not None:
                return r[1]
        return []

    def kizarasok_fn(k: str) -> list[tuple[str, str | None]]:
        if k in forrasok:
            return [(x.kod, x.fejezet) for x in forrasok[k].kizarasok]
        return []

    def tema_fn(k: str) -> str | None:
        if k in forrasok and forrasok[k].fajta == "KONVENCIO":
            return forrasok[k].tema
        return None

    def alapja_fn(k: str) -> str | None:
        return forrasok[k].alapja if k in forrasok else None

    def sablon_fn(k: str) -> dict | None:
        if k in forrasok and forrasok[k].fajta == "ELV_SABLON":
            return forrasok[k].sablon or {}
        return None

    return (feloldas_altalanos(kod, sorok_fn, hiv_fn, 10, kizarasok_fn,
                               tema_fn, alapja_fn, sablon_fn), hianyzo)


# --- Helyzetek ---------------------------------------------------------

def _menet_mintabol(tokenek, paroslicit: bool
                    ) -> tuple[list[dict], str, str] | None:
    """
    Egy konkrét (kibontott) előzmény -> (valódi licitmenet, a soron
    következő MI ülésünk, osztó). A mi vonalunk mindig É-D.

    Pároslicitben É nyit, és az ellenfél végig passzol. Kompetitív
    alakban minden akció szerepel, sorban; ha az első ellenfélé, K az
    osztó. A zárójeleknek váltakozniuk kell (mi, ők, mi, ...), különben
    a minta nem valódi licitmenet.
    """
    licitek: list[dict] = []
    if paroslicit:
        u = "N"
        for t in tokenek:
            licitek.append({"ules": u, "licit": t})
            u = kovetkezo_ules(u)
            licitek.append({"ules": u, "licit": "P"})
            u = kovetkezo_ules(u)
        return licitek, u, "N"
    oszto = "E" if tokenek[0][1] else "N"
    u = oszto
    for t, ellenfel in tokenek:
        if ellenfel != (u in ("E", "W")):
            return None
        licitek.append({"ules": u, "licit": t})
        u = kovetkezo_ules(u)
    if u in ("E", "W"):
        return None               # nem mi következünk
    return licitek, u, oszto


@dataclass
class Helyzet:
    kulcs: str                     # a kibontott előzmény szövege
    licitek: list[dict]
    ules: str
    oszto: str = "N"
    szabalyok: list = field(default_factory=list)   # (Minta, Sor)


def helyzetek(sorok: list[Sor]) -> tuple[dict[str, Helyzet], list[str]]:
    """Minden szabály előzményének konkrét licitmenetei, helyzetenként."""
    ki: dict[str, Helyzet] = {}
    ellenorizhetetlen: list[str] = []
    for s in sorok:
        try:
            m = minta_parse(s.minta)
        except MintaHiba:
            ellenorizhetetlen.append(f"{s.minta} (hibás minta)")
            continue
        elozo_tok = m.tokenek[:-1]
        if not elozo_tok:
            valtozatok = [("", [])]
        else:
            elozo = Minta(m.nyers, elozo_tok, m.paroslicit,
                          {p for p in m.barmennyi if p < len(elozo_tok)})
            kib = kibont(elozo)
            if not kib:
                ellenorizhetetlen.append(s.minta)
                continue
            valtozatok = []
            for szoveg, _ in kib:
                if m.paroslicit:
                    valtozatok.append((szoveg, szoveg.split("-")))
                else:
                    # a kibontás a zárójeleket elhagyja: a minta tokenjeiből
                    # tesszük vissza, melyik akció az ellenfélé
                    darabok = szoveg.split(" ")
                    if len(darabok) != len(elozo_tok):
                        ellenorizhetetlen.append(s.minta)
                        continue
                    par = [(d, t.ellenfel) for d, t in zip(darabok, elozo_tok)]
                    szoveg = " ".join(f"({d})" if e else d for d, e in par)
                    valtozatok.append((szoveg, par))
        for szoveg, tok in valtozatok:
            if szoveg in ki:
                continue
            if not tok:
                ki[szoveg] = Helyzet(szoveg, [], "N")
                ki["P P"] = Helyzet("P P", [{"ules": "S", "licit": "P"},
                                            {"ules": "W", "licit": "P"}],
                                    "N", "S")
                continue
            menet = _menet_mintabol(tok, m.paroslicit)
            if menet is None:
                ellenorizhetetlen.append(f"{s.minta} (nem valódi menet: {szoveg})")
                continue
            licitek, ules, oszto = menet
            ki[szoveg] = Helyzet(szoveg, licitek, ules, oszto)
            if oszto == "N":
                # ugyanez 3. kézből nyitva (a partner passzolt kéz): így az
                # ülésfüggő szabályok (pl. Drury) is vizsgálatot kapnak
                elo = [{"ules": "S", "licit": "P"}, {"ules": "W", "licit": "P"}]
                ki["P P " + szoveg] = Helyzet("P P " + szoveg, elo + licitek,
                                              ules, "S")
    return ki, ellenorizhetetlen


# --- Kézhúzás a korábbi licitjeinkhez igazítva ------------------------

def _kez_huzas(rnd: random.Random, ig, db: int, max_proba: int) -> list[Kez]:
    ki: list[Kez] = []
    for _ in range(max_proba):
        lapok = rnd.sample(PAKLI, 13)
        k = Kez(frozenset(lapok))
        if ig is not None:
            if not ig.pont_min <= _HCP(k) <= ig.pont_max:
                continue
            if any(not ig.hossz(sz)[0] <= k.hossz(sz) <= ig.hossz(sz)[1]
                   for sz in "SHDC"):
                continue
        ki.append(k)
        if len(ki) >= db:
            break
    return ki


# --- Az ellenőrzés -----------------------------------------------------

@dataclass
class Utkozes:
    helyzet: str
    licitek: tuple[str, ...]
    mintak: tuple[str, ...]
    db: int
    pelda: str


@dataclass
class CheckEredmeny:
    helyzet_db: int = 0
    kez_db: int = 0
    utkozesek: list[Utkozes] = field(default_factory=list)
    arnyekolt: list[str] = field(default_factory=list)
    nem_teljesult: list[str] = field(default_factory=list)
    ellenorizhetetlen: list[str] = field(default_factory=list)
    keves_minta: list[str] = field(default_factory=list)
    eldonthetetlen: int = 0
    sorrendi_felulirasok: list[str] = field(default_factory=list)
    hibas_mintak: list[str] = field(default_factory=list)

    @property
    def rendben(self) -> bool:
        return not self.utkozesek and not self.hibas_mintak

    def jelentes(self, reszletes: bool = False) -> str:
        s = [f"{self.helyzet_db} helyzet, {self.kez_db} kéz vizsgálva."]
        if self.hibas_mintak:
            s.append(f"\nHIBÁS MINTA ({len(self.hibas_mintak)}):")
            s += [f"  {x}" for x in self.hibas_mintak]
        s.append(f"\nÜTKÖZÉS ({len(self.utkozesek)}):"
                 + ("  nincs" if not self.utkozesek else ""))
        for u in sorted(self.utkozesek, key=lambda u: -u.db):
            s.append(f"  [{u.helyzet or 'nyitás'}]  {' / '.join(u.licitek)}"
                     f"  ({u.db} kézen)  szabályok: {', '.join(u.mintak)}")
            s.append(f"      pl.: {u.pelda}")
        if self.sorrendi_felulirasok:
            s.append(f"\nCSAK A KÁRTYA SORRENDJE DÖNT ({len(self.sorrendi_felulirasok)}):")
            s += [f"  {x}" for x in self.sorrendi_felulirasok]
        s.append(f"\nÁRNYÉKOLT, sosem nyer ({len(self.arnyekolt)})"
                 + (":" if reszletes else " — részletek: --reszletes"))
        if reszletes:
            s += [f"  {x}" for x in self.arnyekolt]
        s.append(f"NEM TELJESÜLT a mintában ({len(self.nem_teljesult)})"
                 + (":" if reszletes else ""))
        if reszletes:
            s += [f"  {x}" for x in self.nem_teljesult]
        s.append(f"KEVÉS MINTA ({len(self.keves_minta)}), "
                 f"ELLENŐRIZHETETLEN ({len(self.ellenorizhetetlen)}), "
                 f"ELDÖNTHETETLEN kiértékelés: {self.eldonthetetlen}")
        if reszletes:
            s += [f"  kevés: {x}" for x in self.keves_minta]
            s += [f"  ellenőrizhetetlen: {x}" for x in self.ellenorizhetetlen]
        return "\n".join(s)


def ellenoriz(sorok: list[Sor], paramtar=None, kez_db: int = 200,
              mag: int = 1, max_proba: int = 60000,
              feloldas: Feloldas | None = None) -> CheckEredmeny:
    rnd = random.Random(mag)
    er = CheckEredmeny()
    if feloldas is not None:
        er.sorrendi_felulirasok = list(feloldas.sorrendi_felulirasok)

    motor_teljes = Licitmotor(sorok, rendszer_kontextus(paramtar),
                              mod="MERLEGELO")
    er.hibas_mintak = list(motor_teljes.hibas_mintak)
    prop = Propagalo(sorok, paramtar)

    hely, er.ellenorizhetetlen = helyzetek(sorok)
    teljesult: Counter = Counter()
    nyert: Counter = Counter()
    legyozte: dict[int, Counter] = defaultdict(Counter)
    vizsgalt: set[int] = set()

    for kulcs, h in sorted(hely.items()):
        # csak az ebben a helyzetben illeszkedő szabályok (gyorsítás)
        try:
            _, elozmeny = (kanonizal(h.licitek, h.ules) if h.licitek
                           else ("", []))
        except Exception:          # noqa: BLE001
            continue
        reteg = [(m, s) for m, s in motor_teljes.szabalyok
                 if Licitmotor._elozmeny_illesztes(m, elozmeny) is not None]
        if not reteg:
            continue
        er.helyzet_db += 1
        motor = Licitmotor([], rendszer_kontextus(paramtar), mod="MERLEGELO")
        motor.szabalyok = reteg
        for _, s in reteg:
            vizsgalt.add(id(s))

        # a MI korábbi licitjeink kényszere -> olyan kezek, amik ehhez illenek
        tar = prop.kenyszertar(h.licitek, oszto=h.oszto).kenyszertar \
            if h.licitek else None
        ig = tar[h.ules] if tar else None
        kezek = _kez_huzas(rnd, ig, kez_db, max_proba)
        if len(kezek) < kez_db // 4:
            er.keves_minta.append(f"{kulcs or 'nyitás'}: {len(kezek)} kéz")
        utk: dict[tuple, list] = defaultdict(list)
        for k in kezek:
            beli = rnd.choice(BELIK)
            from .helyzet import Allas
            allas = Allas(ules=h.ules, beliallas=beli, licitek=list(h.licitek),
                          oszto=h.oszto, kenyszertar=tar or {})
            d = motor.licital(h.licitek, h.ules, k, beliallas=beli,
                              oszto=h.oszto, allas=allas)
            er.kez_db += 1
            er.eldonthetetlen += d.eldonthetetlen
            if not d.jeloltek:
                continue
            for j in d.jeloltek:
                teljesult[id(j.sor)] += 1
            rang = lambda j: (j.minta_specifikussag, j.sor.prioritas)  # noqa: E731
            legjobb = max(rang(j) for j in d.jeloltek)
            elol = [j for j in d.jeloltek if rang(j) == legjobb]
            licitek = tuple(sorted({j.licit for j in elol}))
            if len(licitek) > 1 and all((getattr(j.sor, "jelentes", None) or {})
                                        .get("alulrol") for j in elol):
                # szándékos "alulról": a legolcsóbb nyer (Bánky), nem ütközés
                from .licital import licit_rang
                also = min(licitek, key=licit_rang)
                elol = [j for j in elol if j.licit == also]
                licitek = (also,)
            if len(licitek) > 1:
                mintak = tuple(sorted({j.sor.minta for j in elol}))
                utk[(licitek, mintak)].append(k)
            else:
                for j in elol:
                    nyert[id(j.sor)] += 1
                gyoztes = elol[0].sor.minta
                for j in d.jeloltek:
                    if rang(j) != legjobb:
                        legyozte[id(j.sor)][gyoztes] += 1
        for (licitek, mintak), kl in utk.items():
            er.utkozesek.append(Utkozes(kulcs, licitek, mintak, len(kl),
                                        kl[0].pbn() if hasattr(kl[0], "pbn")
                                        else str(kl[0])))

    for _, s in motor_teljes.szabalyok:
        if id(s) not in vizsgalt:
            continue
        nev = f"{s.minta}  [{s.rendszer_kod}]"
        if teljesult[id(s)] == 0:
            er.nem_teljesult.append(nev)
        elif nyert[id(s)] == 0:
            kik = ", ".join(f"{k} ({n}x)" for k, n in
                            legyozte[id(s)].most_common(3))
            er.arnyekolt.append(f"{nev}  <- {kik}" if kik else nev)
    return er
