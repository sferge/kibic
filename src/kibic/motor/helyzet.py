"""
A licithelyzet és a HELYZETI feltétel kiértékelése.

MIÉRT KELL: a `feltetel` a saját lapról szól ("legalább 12 figurapont,
ötös pikk"). A kompetitív megállapodások viszont majdnem mindig a
HELYZETRE hivatkoznak:

    "fésű: addig, ameddig a saját színünk gém alatt belicitálható"
    "negatív kontra 2S-ig"
    "kedvezőtlen zónában nem"
    "csak akkor, ha a partner még nem nyilatkozott"

Ezek egyike sem a kézről szól. Ezért a `licitmenet.ha_feltetel`
(014_kompetitiv.sql) ugyanolyan kifejezésfa, mint a `feltetel`, csak a
csomópontjai az ÁLLÁSRA kérdeznek — és az `Allas` az, ami válaszol.

Két dolgot tart nyilván:

  * ami LÁTHATÓ: ki mit licitált, melyik szín mondva van, hol tart a
    szint, él-e kontra — ez a licitmenetből közvetlenül kiolvasható;
  * ami KÖVETKEZTETETT: mit ígért ezzel, amit mondott — ez a
    KÉNYSZERTÁR, és a szabályok `jelentes` mezőjéből épül
    (jelentés-propagálás).

A kettő különválasztása szándékos. A látható rész mindig biztos; a
kényszertár annyit ér, amennyit a rendszer leírása. Ha a motor rosszul
licitál, ebből a kettősségből azonnal látszik, hogy a licitmenetet
értette-e félre vagy a megállapodást.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..domain import ULESEK, kovetkezo_ules, vonal

SZINEK = ("C", "D", "H", "S")             # emelkedő rangsorban
JELENTESEK = ("C", "D", "H", "S", "NT")
NEMESEK = ("H", "S")
MINOROK = ("C", "D")

# Hányadik szinten kezdődik a gém az egyes jelentésekben.
GEMSZINT = {"C": 5, "D": 5, "H": 4, "S": 4, "NT": 3}

HIVASOK = ("P", "X", "XX")


class HelyzetHiba(ValueError):
    pass


# --- Ígéret: egy játékos kényszerei -----------------------------------

@dataclass
class Igeret:
    """
    Amit EGY játékosról tudunk a licitjeiből. "Mi LEHET" — nem "mi
    valószínű"; az utóbbi az ágensprofil dolga.

    Minden mező nyitott intervallum, amíg nem szűkül. A `tagad` halmaz
    azokat a színeket/tulajdonságokat gyűjti, amiket a licit KIZÁRT —
    ez legalább olyan fontos, mint amit ígért.
    """
    pont_min: float = 0.0
    pont_max: float = 40.0
    # asztali pont (fit utáni emelésnél ezt ígéri a licit, nem a figurapontot)
    ap_min: float = 0.0
    ap_max: float = 40.0
    # fedőütés (ász, király, sikén, szingli) — ha a licit kimondta
    fedo_min: float = 0.0
    fedo_max: float = 99.0
    fedo_plusz: float = 0.0           # ez a licit ennyi TOVÁBBI fedőt mutat (kulcslicit)
    # fedő EGY színben: {szín: (legalább, valószínű)} — pl. a 2/1 után lassan
    # emelő válaszoló első színe "nagyon jó": 1, de inkább 2 fedő
    szin_fedo: dict[str, tuple[float, float]] = field(default_factory=dict)
    hossz_min: dict[str, int] = field(default_factory=dict)
    hossz_max: dict[str, int] = field(default_factory=dict)
    tagad: set[str] = field(default_factory=set)
    nyilatkozott: bool = False        # mondott-e nem-passz licitet
    forsz: str = "NEM"                # az UTOLSÓ licitjének forsz-állapota
    gemforsz: bool = False            # volt-e gémforsz licitje (a vonal GF-ban van)
    gi: bool = False                  # az UTOLSÓ licitje géminvit volt-e
    elfogad: bool = False             # a licit a partner invitjét elfogadja
    # kulcslap-VÁLASZ (RKC/ORKC): {"adu": "C", "ertek": [0, 3], "dama": None}
    # — csak a licitenkénti jelentésben él (a spirál innen indul)
    kulcslap: dict | None = None
    # FOGÁS-ígéret (2026-10-05, FOGASMUTATAS elv): azok a színek, amelyekben
    # a licitjei fogást ígértek (A, Kx, Dxx, Bxxx) — hosszt nem feltétlenül
    fogas: set[str] = field(default_factory=set)
    # KVÁZI GÉMFORSZ (2026-10-05, Moha 1M-2m): a gémforsz eddig a licitig
    # kötelez (pl. "4C": a 4-es szint, 4 minor már passzolható)
    gf_hatar: str | None = None
    # NEGYEDIK SZÍN = HELP: a szín, amelyben fogást kért (nincs fogása)
    help_szin: str | None = None
    # TÖBBÉRTELMŰ LICITEK (2026-10-21): licitenként a lehetséges jelentések
    # listája. A fenti mezők az UNIÓjukat tartják (ami biztos); a lejátszás
    # mintavétele ennél pontosabb: a kéznek legalább EGY változatot ki kell
    # elégítenie (pl. információs kontra: rövid káró + 3+ a többiben 12+-szal,
    # VAGY 20+ bármi — az unió csak annyi, hogy 12+).
    alternativak: list = field(default_factory=list)

    def hossz(self, szin: str) -> tuple[int, int]:
        return (self.hossz_min.get(szin, 0), self.hossz_max.get(szin, 13))

    def szukit_pont(self, minimum: float | None = None,
                    maximum: float | None = None) -> None:
        if minimum is not None:
            self.pont_min = max(self.pont_min, float(minimum))
        if maximum is not None:
            self.pont_max = min(self.pont_max, float(maximum))

    def szukit_ap(self, minimum: float | None = None,
                  maximum: float | None = None) -> None:
        if minimum is not None:
            self.ap_min = max(self.ap_min, float(minimum))
        if maximum is not None:
            self.ap_max = min(self.ap_max, float(maximum))

    def szukit_fedo(self, minimum: float | None = None,
                    maximum: float | None = None) -> None:
        if minimum is not None:
            self.fedo_min = max(self.fedo_min, float(minimum))
        if maximum is not None:
            self.fedo_max = min(self.fedo_max, float(maximum))

    def szukit_hossz(self, szin: str, minimum: int | None = None,
                     maximum: int | None = None) -> None:
        if minimum is not None:
            self.hossz_min[szin] = max(self.hossz_min.get(szin, 0), int(minimum))
        if maximum is not None:
            self.hossz_max[szin] = min(self.hossz_max.get(szin, 13), int(maximum))

    @property
    def ellentmondas(self) -> bool:
        """Kiderült-e, hogy a rendszer leírása inkonzisztens?"""
        if self.pont_min > self.pont_max:
            return True
        return any(self.hossz_min.get(sz, 0) > self.hossz_max.get(sz, 13)
                   for sz in SZINEK)

    def leiras(self) -> str:
        r = []
        if self.pont_min > 0 or self.pont_max < 40:
            r.append(f"{self.pont_min:g}-{self.pont_max:g} pont")
        for sz in ("S", "H", "D", "C"):
            lo, hi = self.hossz(sz)
            if lo > 0 or hi < 13:
                r.append(f"{sz}: {lo}-{hi}")
        if self.tagad:
            r.append("tagad: " + ", ".join(sorted(self.tagad)))
        if self.fogas:
            r.append("fogás: " + ", ".join(sz for sz in ("S", "H", "D", "C") if sz in self.fogas))
        return "; ".join(r) or "semmi"


def fogas_kezben(kez, sz: str) -> bool:
    """FOGÁS (stopper) a kézben: A, Kx, Dxx, Bxxx — ugyanaz a küszöb, mint a
    YAML `fogas:` kulcsáé (impex/rendszer_yaml._fogas_fa)."""
    lapok = {l.ertek for l in kez.lapok if l.szin == sz}
    n = kez.hossz(sz)
    return ("A" in lapok or ("K" in lapok and n >= 2) or ("Q" in lapok and n >= 3)
            or ("J" in lapok and n >= 4))


# --- Állás: a licitmenet a licitáló szemszögéből ----------------------

@dataclass
class Allas:
    """
    A licithelyzet, MINDIG a licitáló (`ules`) szemszögéből.

    A `licitek` az eddigi menet: [{"ules": "N", "licit": "1S"}, ...].
    A konstruktor ebből számol ki mindent, ami a helyzeti feltételekhez
    kell; a kényszertárat a hívó tölti fel (jelentés-propagálás).
    """
    ules: str = "N"
    beliallas: str = "NONE"
    licitek: list[dict] = field(default_factory=list)
    kenyszertar: dict[str, Igeret] = field(default_factory=dict)
    oszto: str | None = None
    # a vonalak rendszercsaládja ({"NS": "STRONG_CLUB", "EW": None}) — a
    # `ha: {ellenfel_csalad: …}` feltételhez
    csaladok: dict[str, str | None] = field(default_factory=dict)
    # VALÓSZÍNŰ tudás a kizárásos következtetésből (kovetkeztetes.py) — nem
    # biztos: a gémesély és a mintavétel használja, a biztos feltételek nem
    valoszinu: dict[str, "Igeret"] = field(default_factory=dict)

    # számított
    _mondott: dict[str, set[str]] = field(default_factory=dict, repr=False)
    _legmagasabb: tuple[int, str] | None = field(default=None, repr=False)
    _legmagasabb_ules: str | None = field(default=None, repr=False)
    _kontra: str = field(default="NINCS", repr=False)   # NINCS / MI / OK
    _rekontra: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        for u in ULESEK:
            self._mondott.setdefault(u, set())
            self.kenyszertar.setdefault(u, Igeret())
        for elem in self.licitek:
            self._feldolgoz(elem.get("ules"), str(elem.get("licit", "")).upper())

    # -- a menet feldolgozása --

    def _feldolgoz(self, u: str | None, licit: str) -> None:
        if u not in ULESEK or not licit:
            return
        licit = licit.replace("DBL", "X").replace("RDBL", "XX")
        licit = "NT" if licit == "N" else licit
        if licit == "P":
            return
        self.kenyszertar[u].nyilatkozott = True
        if licit == "X":
            self._kontra = "MI" if vonal(u) == vonal(self.ules) else "OK"
            self._rekontra = False
            return
        if licit == "XX":
            self._rekontra = True
            return
        szint, szin = self._bont(licit)
        if szint is None:
            return
        self._mondott[u].add(szin)
        self._legmagasabb = (szint, szin)
        self._legmagasabb_ules = u
        self._kontra = "NINCS"
        self._rekontra = False

    @staticmethod
    def _bont(licit: str) -> tuple[int | None, str]:
        if len(licit) < 2 or not licit[0].isdigit():
            return (None, "")
        szint = int(licit[0])
        szin = licit[1:].upper()
        szin = "NT" if szin in ("N", "NT") else szin
        if szin not in JELENTESEK or not 1 <= szint <= 7:
            return (None, "")
        return (szint, szin)

    # -- szerepek --

    @property
    def partner(self) -> str:
        return kovetkezo_ules(self.ules, 2)

    @property
    def bal(self) -> str:
        """LHO: a balkéz felőli ellenfél — utánunk licitál."""
        return kovetkezo_ules(self.ules, 1)

    @property
    def jobb(self) -> str:
        """RHO: a jobbkéz felőli ellenfél — előttünk licitált."""
        return kovetkezo_ules(self.ules, 3)

    def ulesek(self, ki: str) -> list[str]:
        """A `ki` szerepváltozó feloldása konkrét ülésekre."""
        return {
            "en":   [self.ules],
            "p":    [self.partner],
            "bal":  [self.bal],
            "jobb": [self.jobb],
            "mi":   [self.ules, self.partner],
            "ok":   [self.bal, self.jobb],
        }.get(ki, [])

    # -- a látható helyzet --

    @property
    def ules_szam(self) -> int:
        """
        Hányadik ülésben licitálunk (1-4)? Az osztótól számítva, a
        közbeszólásoktól függetlenül — ezt a nyitási szabályok kérik.
        """
        if self.oszto is None:
            return len(self.licitek) % 4 + 1
        return (ULESEK.index(self.ules) - ULESEK.index(self.oszto)) % 4 + 1

    @property
    def szint(self) -> int:
        """A pillanatnyi licitszint (0, ha még nem licitált senki)."""
        return self._legmagasabb[0] if self._legmagasabb else 0

    @property
    def szabad(self) -> bool:
        """
        Szabad licit? Igaz, ha a jobb kéz felőli ellenfél passzolt —
        vagyis nem kényszerből szólalunk meg.
        """
        for elem in reversed(self.licitek):
            if elem.get("ules") == self.jobb:
                return str(elem.get("licit", "")).upper() in ("P", "PASS")
        return True

    @property
    def kontra_allas(self) -> str:
        """NINCS / MI / OK — él-e kontra, és melyik vonalé."""
        return self._kontra

    @property
    def rekontrazva(self) -> bool:
        return self._rekontra

    def valodi_szinek(self, ki: str = "mi") -> set[str]:
        """
        A vonal „igazi” színei: amit a vonal valamelyik tagja színlicittel
        bemondott, ÉS (a kényszertár szerint) legalább 3 lapot ígért benne.
        A mesterséges licit (Stayman 2♣, transzfer) így nem számít.
        """
        ki_ = set()
        for u in self.ulesek(ki):
            ig = self.kenyszertar.get(u) if self.kenyszertar else None
            for sz in self._mondott.get(u, set()):
                if sz in SZINEK and ig is not None and ig.hossz(sz)[0] >= 3:
                    ki_.add(sz)
        return ki_

    def utolso_licit(self, ules: str) -> tuple[int, str | None]:
        """(index, hívás) — az ülés utolsó nem-passz hívása; (-1, None), ha nincs."""
        for i in range(len(self.licitek) - 1, -1, -1):
            e = self.licitek[i]
            if e.get("ules") == ules and str(e.get("licit", "")).upper() not in ("P", "PASS"):
                return i, str(e.get("licit")).upper()
        return -1, None

    def mondta(self, szin: str, ki: str) -> bool:
        return any(szin in self._mondott[u] for u in self.ulesek(ki))

    def gf_teljesult(self) -> bool:
        """
        KVÁZI GÉMFORSZ: a vonal gémforsza csak egy licitig (pl. 4♣-ig, azaz 4
        minorig) kötelez — ha a menet elérte, a gémforsz teljesült.
        """
        hatarok = [_licit_rang(str(ig.gf_hatar)) for u in (self.ules, self.partner)
                   if (ig := self.kenyszertar.get(u)) is not None
                   and getattr(ig, "gf_hatar", None)]
        hatarok = [h for h in hatarok if h is not None]
        if not hatarok or self._legmagasabb is None:
            return False
        most = _licit_rang(f"{self._legmagasabb[0]}{self._legmagasabb[1]}")
        return most is not None and most >= min(hatarok)

    def termeszetes_szinek(self, ki: str = "mi") -> set[str]:
        """
        A vonal TERMÉSZETESEN (színként) licitált színei: a licit jelentése
        legalább 2 lapot ígért benne (a propagálás írja a licit elemébe,
        `szin_hossz_min`); amit nem értettünk, azt természetesnek vesszük —
        mint a MONDVA_3NT_ELOTT-nél. A kérdés, relé, transzfer és a puszta
        fogásmutatás nem számít.
        """
        ulesek = set(self.ulesek(ki))
        ki_: set[str] = set()
        for e in self.licitek:
            h = str(e.get("licit", "")).upper()
            if e.get("ules") not in ulesek or not h[:1].isdigit() or h[1:] not in SZINEK:
                continue
            m = e.get("szin_hossz_min", None)
            if m is None or m >= 2:
                ki_.add(h[1:])
        return ki_

    def fedett_szinek(self, ki: str = "mi", termeszetes: bool = True) -> set[str]:
        """
        A FOGÁSMUTATÁS elvhez: a színek, amelyek a vonalunk szempontjából
        „le vannak fedve” — valamelyikünk fogást ígért benne, vagy (ha a
        `termeszetes` paraméter igaz) természetesen licitáltuk.
        """
        ki_: set[str] = set()
        for u in self.ulesek(ki):
            ig = self.kenyszertar.get(u) if self.kenyszertar else None
            if ig is not None:
                ki_ |= set(getattr(ig, "fogas", set()) or set())
        if termeszetes:
            ki_ |= self.termeszetes_szinek(ki)
        return ki_

    def nyilatkozott(self, ki: str) -> bool:
        return any(self.kenyszertar[u].nyilatkozott for u in self.ulesek(ki))

    def kovetkezo_licit(self, szin: str) -> tuple[int, str] | None:
        """
        A legkisebb LEGÁLIS licit az adott színben, vagy None, ha már
        nincs ilyen (7NT fölött).
        """
        if szin not in JELENTESEK:
            return None
        if self._legmagasabb is None:
            return (1, szin)
        szint, mag = self._legmagasabb
        if JELENTESEK.index(szin) > JELENTESEK.index(mag):
            return (szint, szin)
        return (szint + 1, szin) if szint < 7 else None

    def gem_alatt(self, szin: str) -> bool:
        """
        Még GÉM ALATT belicitálható-e a szín?

        Ez a fésű élettartamának mértéke: ameddig a saját színünket gém
        alatt meg lehet mondani, addig van értelme "van értékem, dönts"
        üzenetet küldeni. Fölötte már nem fésű-, hanem gémdöntés van.
        """
        kov = self.kovetkezo_licit(szin)
        return kov is not None and kov[0] < GEMSZINT[szin]

    @property
    def ag(self) -> str:
        """
        A licitálás melyik ágában vagyunk (minta.AGAK)?

          PAROS      mi kezdtünk, ők hallgatnak
          KUZDELMI   mi kezdtünk, ők belelicitáltak
          VEDEKEZO   ŐK kezdtek

        Ez nem három külön rendszer, hanem ugyanannak a konvenciókártyának
        a három fejezete — de a szabályok zöme csak az egyikben érvényes,
        és a lefedettséget is áganként kell mérni.
        """
        elso_ok = None
        elso_mi = None
        for elem in self.licitek:
            u = elem.get("ules")
            licit = str(elem.get("licit", "")).upper()
            if u not in ULESEK or licit in ("", "P", "PASS"):
                continue
            mienk = vonal(u) == vonal(self.ules)
            if mienk and elso_mi is None:
                elso_mi = True
            if not mienk and elso_ok is None:
                elso_ok = True
            if elso_mi or elso_ok:
                break
        if elso_ok and not elso_mi:
            return "VEDEKEZO"
        if elso_mi and any(vonal(e.get("ules", "N")) != vonal(self.ules)
                           and str(e.get("licit", "")).upper()
                           not in ("", "P", "PASS")
                           for e in self.licitek):
            return "KUZDELMI"
        return "PAROS"

    # -- a fésűhöz: rangsorolt színlisták a kényszertárból --

    def ismert_szinek(self, ki: str = "ok", min_hossz: int = 4) -> list[str]:
        """
        Mely színekre ígért a megnevezett fél legalább ennyi lapot?
        EMELKEDŐ rangsorban (treff < káró < kőr < pikk).

        Ez teszi a fésűt leírhatóvá: az ellenfél kétszínű licitje után a
        két ismert szín rangsorrendje adja a cue-bidek sorrendjét.
        """
        ulesek = self.ulesek(ki)
        return [sz for sz in SZINEK
                if any(self.kenyszertar[u].hossz(sz)[0] >= min_hossz
                       for u in ulesek)]

    def szabad_szinek(self, ki: str = "ok", min_hossz: int = 4) -> list[str]:
        """A fennmaradó színek, ugyanabban a rangsorban."""
        ismert = set(self.ismert_szinek(ki, min_hossz))
        return [sz for sz in SZINEK if sz not in ismert]

    def fesu_kotesek(self, ki: str = "ok", min_hossz: int = 4,
                     paros: bool = False) -> dict[str, str]:
        """
        Az `I1/I2/...` és `V1/V2/...` mintaváltozók kötése.

        A kötés MINDIG megtörténik, ha van ismert szín — az információs
        kontra elve például egyetlen ismert szín ellen szól. Hogy hány
        ismert szín KELL egy szabályhoz, az a `ha_feltetel` dolga
        (`ISMERT_SZINEK`), nem a kötésé: a fésű kettőt kér, az elv egyet.

        A `paros` a régi, szigorú viselkedés (a két lista hossza
        egyezzen); megtartva, mert a párosítás maga tényleg ezt kívánja.
        """
        ismert = self.ismert_szinek(ki, min_hossz)
        szabad = self.szabad_szinek(ki, min_hossz)
        if paros and len(ismert) != len(szabad):
            return {}
        kotes = {}
        for i, sz in enumerate(ismert, start=1):
            kotes[f"I{i}"] = sz
        for i, sz in enumerate(szabad, start=1):
            kotes[f"V{i}"] = sz
        return kotes

    def adu(self) -> str | None:
        """
        A MEGÁLLAPODOTT ADU: az a szín, amelyben a vonalunknak ismert 8+
        lapos fitje van (a kényszertár szerint — mindkét fél tudja).
        Több ilyen közül a nemes előbb, azon belül a hosszabb; egyenlőnél
        a magasabb rangú.
        """
        jeloltek = [(sz in NEMESEK, self.fit(sz), SZINEK.index(sz), sz)
                    for sz in SZINEK
                    if self.kenyszertar and self.fit(sz) >= 8]
        return max(jeloltek)[3] if jeloltek else None

    def fit(self, szin: str) -> int:
        """
        A vonalunk ISMERT össz-hossza a színben — a kényszertár alsó
        becslése. Csak a minimumokat adja össze: ami biztosan megvan.
        """
        return sum(self.kenyszertar[u].hossz(szin)[0]
                   for u in (self.ules, self.partner))


# --- HELYZETI numerikus kifejezés ------------------------------------
#
# FIGYELEM — EZZEL NEM A ZÓNÁT ÉS NEM A MAGASSÁGOT KEZELJÜK.
#
# Elsőre épp arra készült: "az elv a szkórhelyzetnek és a magasságnak
# megfelelő erőt kér", tehát írjunk küszöbképletet szintenkénti pótlékkal
# és zóna-súlyokkal. Ez zsákutca volt, és érdemes megjegyezni, miért:
#
#   * A MAGASSÁG nem pótlék. A 2-es magassághoz nyolc ütés kell hét
#     helyett — a szimuláció ezt magától tudja.
#   * A ZÓNA sem. Ugyanaz az áldozat mansban ŐK-bell ellen három
#     bukásig megéri, bellben ŐK-mans ellen csak egyig; ez a bukások és
#     a gémek pontértékéből jön ki, egyetlen szabály nélkül.
#
# Kézzel beírt súlyokkal a pontos számítást közelítettük volna — rosszul.
# Ahol a helyzet befolyásolja a döntést, ott MÉRLEGELÜNK
# (motor/merlegel.py), nem küszöböt hangolunk.
#
# Ami marad ennek a gépezetnek: olyan küszöbök, amiket a pontozás NEM ad
# meg magától, mert megállapodás kérdései (például egy konvenció
# hatóköre). Ilyenkor a jelentés és a kéz-feltétel számai lehetnek
# kifejezések is, nem csak konstansok vagy paraméterkódok:
#
#   {"t":"OSSZEG","gy":[
#       {"t":"PARAM","kod":"BELICIT_MIN"},
#       {"t":"SZORZAT","gy":[{"t":"SZINT_ERTEK","tol":1},
#                            {"t":"PARAM","kod":"MAGASSAG_POTLEK"}]},
#       {"t":"SZKOR_SULY","sulyok":{"S":2,"M":1,"A":0,"O":-1}}]}
#
# Magyarul: az alapkövetelmény, plusz minden szinttel egy pótlék, plusz
# a zóna szerinti kiigazítás (kedvezőtlen zónában többet kérünk,
# kedvezőben kevesebbet).

def ertek(csp, allas: "Allas", paramtar=None) -> float | None:
    """Egy helyzetfüggő numerikus kifejezés értéke."""
    if csp is None:
        return None
    if isinstance(csp, (int, float)):
        return float(csp)
    if isinstance(csp, str):                    # csupasz paraméterkód
        return _param(csp, paramtar)
    t = csp.get("t")

    if t == "SZAM":
        return float(csp["v"])
    if t == "PARAM":
        v = _param(csp["kod"], paramtar)
        if v is None and "alap" in csp:
            v = float(csp["alap"])
        return None if v is None else v + float(csp.get("eltolas", 0))
    if t == "SZINT_ERTEK":
        # A pillanatnyi licitszint (1-7). A `tol` levonható alap:
        # `{"tol":1}` a "hány szinttel vagyunk az 1-es fölött".
        return float(max(0, allas.szint - int(csp.get("tol", 0))))
    if t == "LICIT_MAGASSAG":
        # Finomabb, mint a szint: a licit helye a 35 elemű rangsorban.
        if allas._legmagasabb is None:
            return 0.0
        return float(_licit_rang(
            f"{allas._legmagasabb[0]}{allas._legmagasabb[1]}") or 0)
    if t == "SZKOR_SULY":
        return float(csp.get("sulyok", {}).get(_szkorhelyzet(allas), 0))
    if t == "OSSZEG":
        ossz = 0.0
        for g in csp.get("gy", []):
            e = ertek(g, allas, paramtar)
            if e is None:
                return None
            ossz += e
        return ossz
    if t == "SZORZAT":
        szorzat = 1.0
        for g in csp.get("gy", []):
            e = ertek(g, allas, paramtar)
            if e is None:
                return None
            szorzat *= e
        return szorzat
    if t == "MIN" or t == "MAX":
        ertekek = [ertek(g, allas, paramtar) for g in csp.get("gy", [])]
        if any(e is None for e in ertekek) or not ertekek:
            return None
        return min(ertekek) if t == "MIN" else max(ertekek)
    raise HelyzetHiba(f"Ismeretlen helyzeti kifejezés: {t!r}")


def _param(kod: str, paramtar) -> float | None:
    if paramtar is None:
        return None
    try:
        return float(paramtar.ertek(str(kod)))
    except Exception:              # noqa: BLE001
        return None


def ertek_leiras(csp) -> str:
    """Emberi nyelvű alak — ez megy az alertbe és a promptba."""
    if csp is None:
        return "?"
    if isinstance(csp, (int, float)):
        return f"{csp:g}"
    if isinstance(csp, str):
        return "{" + csp + "}"
    t = csp.get("t")
    if t == "SZAM":
        return f"{csp['v']:g}"
    if t == "PARAM":
        x = "{" + csp["kod"] + (f", alapból {csp['alap']:g}" if "alap" in csp else "") + "}"
        e = float(csp.get("eltolas", 0))
        return x + (f" {e:+g}" if e else "")
    if t == "SZINT_ERTEK":
        tol = int(csp.get("tol", 0))
        return "a licitszint" + (f" mínusz {tol}" if tol else "")
    if t == "LICIT_MAGASSAG":
        return "a licitmagasság"
    if t == "SZKOR_SULY":
        return "a zóna szerinti kiigazítás"
    if t == "OSSZEG":
        return "(" + " + ".join(ertek_leiras(g) for g in csp.get("gy", [])) + ")"
    if t == "SZORZAT":
        return "(" + " * ".join(ertek_leiras(g) for g in csp.get("gy", [])) + ")"
    if t in ("MIN", "MAX"):
        return (t.lower() + "("
                + ", ".join(ertek_leiras(g) for g in csp.get("gy", [])) + ")")
    return str(t)


# --- A helyzeti feltétel kiértékelése --------------------------------

def _szin(csp: dict, kotesek: dict[str, str] | None) -> str | None:
    """
    A csomópont színe. Lehet konkrét (S/H/D/C/NT) vagy a mintából kötött
    változó (@M, @m, @A...). A kötés a mintaillesztésből jön, így a
    helyzeti feltétel UGYANARRÓL a színről beszél, mint a minta.
    """
    sz = csp.get("szin")
    if sz is None:
        return None
    if isinstance(sz, str) and sz.startswith("@"):
        if not kotesek:
            return None
        from .minta import szin_kotesbol      # a származtatott is (oM, om)
        return szin_kotesbol(sz[1:], kotesek)
    return sz


def kiertekel(csp: dict, allas: Allas,
              kotesek: dict[str, str] | None = None,
              paramtar=None) -> bool | None:
    """
    A helyzeti feltételfa kiértékelése — háromértékű, mint a kézé.
    A None (ISMERETLEN) itt azt jelenti: a kötés vagy a kényszertár nem
    ad elég információt. Ez MÉRHETŐ, nem elnyelt hiba.
    """
    t = csp.get("t")

    # --- logikai csomópontok (a kifejezes.py-val azonos szemantika) ---
    if t in ("ES", "VAGY", "LEGALABB"):
        gyerekek = [kiertekel(g, allas, kotesek, paramtar)
                    for g in csp["gy"]]
        n = len(gyerekek)
        m = n if t == "ES" else 1 if t == "VAGY" \
            else int(csp.get("m", math.ceil(n / 2)))
        igaz = sum(1 for g in gyerekek if g is True)
        ismeretlen = sum(1 for g in gyerekek if g is None)
        if igaz >= m:
            return True
        if igaz + ismeretlen < m:
            return False
        return None

    if t == "NEM":
        e = kiertekel(csp["gy"][0], allas, kotesek, paramtar)
        return None if e is None else (not e)

    if t == "IGAZ":
        return True
    if t == "ISMERETLEN":
        return None

    # --- helyzeti csomópontok ---
    if t == "ULES":
        ertek = csp["ertek"]
        lista = ertek if isinstance(ertek, list) else [ertek]
        return allas.ules_szam in [int(x) for x in lista]

    if t == "SZKOR":
        return _szkorhelyzet(allas) == csp["ertek"]

    if t == "SZABAD":
        return allas.szabad

    if t == "SZINT":
        return _osszehasonlit(allas.szint, csp.get("op", "<="), csp["v"])

    if t == "LICIT_LEGFELJEBB":
        # "4 kőr magasságáig". A magyar rendszerleírások így fogalmaznak,
        # és ez NEM ugyanaz, mint a szint: a 4H beleszámít, a 4S már nem.
        # A határ lehet konkrét licit ("4H") vagy PARAMÉTERKÓD — az
        # utóbbi kell ahhoz, hogy a "meddig információs a kontra"
        # kérdés hangolható adat maradjon, ne beégetett érték.
        hatar = _licit_rang(csp["hatar"])
        if hatar is None and paramtar is not None:
            try:
                hatar = _licit_rang(str(paramtar.ertek(csp["hatar"])))
            except Exception:      # noqa: BLE001
                hatar = None
        if hatar is None:
            return None            # nem eldönthető, nem hiba
        if allas._legmagasabb is None:
            return True
        most = _licit_rang(f"{allas._legmagasabb[0]}{allas._legmagasabb[1]}")
        return most <= hatar if csp.get("bezarolag", True) else most < hatar

    if t == "AG":
        # A licitálás melyik ágában vagyunk? Az ELVEK jellemzően egy
        # ágra vonatkoznak ("védekező rendszerben a kontra...").
        ertek = csp["ertek"]
        lista = ertek if isinstance(ertek, list) else [ertek]
        return allas.ag in lista

    if t == "GEM_ALATT":
        sz = _szin(csp, kotesek)
        return None if sz is None else allas.gem_alatt(sz)

    if t == "MONDVA":
        sz = _szin(csp, kotesek)
        return None if sz is None else allas.mondta(sz, csp.get("ki", "ok"))

    if t == "ELLENFEL_KONTRAZOTT":
        # az ellenfél kontrázott-e a licitmenetben (a kontra nem teremt
        # fésű-helyzetet: nem feltétlenül ígéri a két színt — a szerkesztő)
        from ..domain import vonal as _vn
        return any(_vn(e.get("ules")) != _vn(allas.ules)
                   and str(e.get("licit", "")).upper() == "X" for e in allas.licitek)

    if t == "LEGOLCSOBB_SZINT":
        # a szín legolcsóbb (most mondható) licitje legfeljebb `max` szintű-e —
        # a fésű határa (a szerkesztő, 2026-10-22: mindkét színüket legfeljebb
        # a 3-as szinten tudjuk mondani)
        sz = _szin(csp, kotesek)
        if sz is None:
            return None
        kov = allas.kovetkezo_licit(sz)
        return kov is not None and kov[0] <= int(csp.get("max", 3))

    if t == "ELLENFEL_SZINE":
        # az ellenfél színe: amit 4+ lappal ígértek, vagy a kontrájukkal ígért
        # nemes, amit mi nem mondtunk (a szerkesztő, 2026-10-22)
        sz = _szin(csp, kotesek)
        if sz is None:
            return None
        from ..domain import vonal as _vn
        ok = [u for u in ULESEK if _vn(u) != _vn(allas.ules)]
        if allas.kenyszertar and any(allas.kenyszertar[u].hossz(sz)[0] >= 4
                                     for u in ok if allas.kenyszertar.get(u) is not None):
            return True
        kontrazott = any(e.get("ules") in ok and str(e.get("licit", "")).upper() == "X"
                         for e in allas.licitek)
        return bool(kontrazott and sz in NEMESEK and sz not in allas.termeszetes_szinek("mi"))

    if t == "MONDVA_3NT_ELOTT":
        # A vonalunk licitálta-e a színt SZÍNKÉNT a (mi) utolsó 3NT-nk ELŐTT — az
        # "indirekt ígéret" (Moha, 2026-10-04): 1♠-2♣-3NT-4♣-ben a 2♣
        # formálisan lehet rövid, de a 4♣ ismétlés hosszú treffet mutat.
        sz = _szin(csp, kotesek)
        if sz is None:
            return None
        mieink = (allas.ules, allas.partner)
        hatar = max((i for i, e in enumerate(allas.licitek)
                     if e.get("ules") in mieink
                     and str(e.get("licit", "")).upper() in ("3NT", "3N")), default=None)
        if hatar is None:
            return False
        # csak SZÍNKÉNT (nem kérdés, relé, transzfer, lépcsőválasz): a licit
        # jelentése legalább 2 lapot ígér benne (a propagálás írja be); amit
        # nem értettünk, azt természetesnek vesszük
        def szinkent(e) -> bool:
            h = e.get("szin_hossz_min")
            return h is None or h >= 2
        return any(e.get("ules") in mieink
                   and str(e.get("licit", "")).upper()[1:] == sz
                   and str(e.get("licit", "")).upper()[:1].isdigit()
                   and szinkent(e)
                   for e in allas.licitek[:hatar])

    if t == "NEGYEDIK_SZIN":
        # A most definiált licit a NEGYEDIK szín (2026-10-02, Moha): a vonal
        # már három igazi színt mondott, ez a negyedik, az ellenfél nem
        # mondta (akkor felüllicit volna), és a legolcsóbb licit benne.
        if not allas.kenyszertar:
            return None
        licit = (kotesek or {}).get("_licit")
        if not licit or not licit[0].isdigit() or licit[1:] not in SZINEK:
            return False
        szint, sz = int(licit[0]), licit[1:]
        if szint < int(csp.get("min_szint", 2)):
            return False
        v = allas.valodi_szinek("mi")
        # 3NT alatt, és csak egyszer: ha a vonal már mondta (mesterségesen) ezt a
        # színt, az újabb licit benne már nem a negyedik szín
        return (len(v) == 3 and sz not in v and not allas.mondta(sz, "ok")
                and not allas.mondta(sz, "mi")
                and _licit_rang(licit) < _licit_rang("3NT")
                and allas.kovetkezo_licit(sz) == (szint, sz))

    if t == "PARTNER_NEGYEDIK":
        # a partner utolsó licitje a negyedik szín volt (és azóta én nem szóltam)
        if not allas.kenyszertar:
            return None
        i, licit = allas.utolso_licit(allas.partner)
        j, _ = allas.utolso_licit(allas.ules)
        if licit is None or i < j or not licit[0].isdigit() or licit[1:] not in SZINEK:
            return False
        sz = licit[1:]
        if "szint" in csp and int(licit[0]) != int(csp["szint"]):
            return False
        v = allas.valodi_szinek("mi")
        return len(v) == 3 and sz not in v and not allas.mondta(sz, "ok")

    if t == "UGRAS":
        # a most definiált színlicit / szan ugrás-e (magasabb a legolcsóbb szintnél)
        licit = (kotesek or {}).get("_licit")
        if not licit or not licit[0].isdigit():
            return False
        szint, sz = int(licit[0]), licit[1:]
        kov = allas.kovetkezo_licit(sz)
        return kov is not None and szint > kov[0]

    if t == "PARTNER_KULCSLICIT":
        # a partner utolsó (nem passz) licitje kulcslicit volt-e (a
        # propagálás jelöli a licit elemében)
        i, lic = allas.utolso_licit(allas.partner)
        if not lic or not allas.licitek[i].get("kulcslicit"):
            return False
        # az adu színe (gém / leállás) és a szan nem kulcslicit
        return lic[1:] not in ("NT", allas.adu())

    if t == "PARTNER_UGROTT":
        # a partner utolsó (nem passz) licitje UGRÁS volt-e: magasabb, mint
        # a legolcsóbb licit abban a színben az akkori állásban
        i, lic = allas.utolso_licit(allas.partner)
        if lic is None or not lic[:1].isdigit():
            return False
        elozo = None
        for e in allas.licitek[:i]:
            h = str(e.get("licit", "")).upper()
            if h[:1].isdigit():
                elozo = _licit_rang(h)
        r = _licit_rang(lic)
        if r is None:
            return False
        sz = JELENTESEK.index(Allas._bont(lic)[1])
        if elozo is None:
            legolcsobb = sz
        else:
            legolcsobb = (elozo // 5) * 5 + sz
            if legolcsobb <= elozo:
                legolcsobb += 5
        return r > legolcsobb

    if t == "GYENGE_UGRAS":
        # A GYENGE UGRÁS ELVE (2026-10-02, Moha): ahol nem vagyunk
        # licitálásra kényszerítve, és egy színt alacsonyabban is
        # mondhatnánk (arra van szabály), de egy vagy két szinttel
        # magasabban mondjuk — az gyengeség (kizárás), nem többleterő.
        #   - új szín (senki nem mondta), most szólalok meg először,
        #   - pontosan `lepes` szintnyi ugrás (1: egyszeres, 2: dupla),
        #   - a partner nem forszolt, nem vagyunk gémforszban,
        #   - nem splinter-helyzet (az a konkrétabb elv),
        #   - az alacsonyabb licit a színben definiált, maga az ugrás nem.
        licit = (kotesek or {}).get("_licit")
        if not licit or not licit[0].isdigit() or licit[1:] not in SZINEK:
            return False
        if allas._legmagasabb is None:
            return False                       # nyitás: a blokknyitások világa
        szint, b = int(licit[0]), licit[1:]
        if any(b in allas._mondott.get(u, set()) for u in ULESEK):
            return False                       # nem új szín
        if allas.kenyszertar and allas.kenyszertar[allas.ules].nyilatkozott:
            return False                       # már licitáltam
        kov = allas.kovetkezo_licit(b)
        if kov is None or szint - kov[0] != int(csp.get("lepes", 1)):
            return False
        if kiertekel({"t": "PARTNER_FORSZOL"}, allas, kotesek, paramtar) is True:
            return False
        if kiertekel({"t": "GEMFORSZ"}, allas, kotesek, paramtar) is True:
            return False
        if kiertekel({"t": "SPLINTER_HELYZET"}, allas, kotesek, paramtar) is True:
            return False
        defi = (kotesek or {}).get("_definialt")
        if defi is None:
            return None                        # a szabálykészlet nélkül nem eldönthető
        return defi(f"{kov[0]}{kov[1]}") and not defi(licit)

    if t == "EN_LIMITALT":
        # a lapomat már limitáltam: az ígért sávom legfeljebb 4 pont széles
        # (pl. 1NT nyitás, 1m-1M-1NT 12-14) — a partner ennek ismeretében
        # döntött (a szerkesztő, 2026-10-25)
        en = allas.kenyszertar.get(allas.ules) if allas.kenyszertar else None
        if en is None or not en.nyilatkozott:
            return False
        return en.pont_max < 40 and en.pont_max - en.pont_min <= 4

    if t == "EROS_UGRAS":
        # A gyenge ugrás párja (2026-10-02, Moha): MÁSODIK (vagy későbbi)
        # megszólalásban az új színben tett egyszeres ugrás éppen hogy
        # PLUSZT ígér: gémforsz. Új szín, már licitáltam, egyszeres ugrás,
        # nem splinter-helyzet, nem limitáltam a lapom korábban (pont_max >= 15),
        # és maga az ugrás nincs konkrétan definiálva.
        licit = (kotesek or {}).get("_licit")
        if not licit or not licit[0].isdigit() or licit[1:] not in SZINEK:
            return False
        szint, b = int(licit[0]), licit[1:]
        if any(b in allas._mondott.get(u, set()) for u in ULESEK):
            return False
        if not (allas.kenyszertar and allas.kenyszertar[allas.ules].nyilatkozott):
            return False                       # első megszólalás: az a gyenge ugrás
        en = allas.kenyszertar[allas.ules]
        if en.pont_max < 15 or en.pont_max - en.pont_min <= 4:
            return False                       # már limitáltam a lapom (pl. 1NT nyitás / válasz)
        # a partner még nem licitált (pl. 1NT-(X)-P-(P)): nincs mire „erőt” mutatni
        pt = allas.kenyszertar.get(allas.partner)
        if pt is None or not any(e.get("ules") == allas.partner and
                                 str(e.get("licit", "")).upper() not in ("P", "PASS")
                                 for e in allas.licitek):
            return False
        kov = allas.kovetkezo_licit(b)
        if kov is None or szint - kov[0] != 1:
            return False
        if kiertekel({"t": "SPLINTER_HELYZET"}, allas, kotesek, paramtar) is True:
            return False
        defi = (kotesek or {}).get("_definialt")
        if defi is None:
            return None
        return not defi(licit)

    if t == "EN_NYITOTTAM":
        # a menet első nem-passz licitje az enyém volt
        for e in allas.licitek:
            if str(e.get("licit", "")).upper() not in ("P", "PASS", ""):
                return e.get("ules") == allas.ules
        return False

    if t == "SPLINTER_HELYZET":
        # Ugrás új színben a partner (tudott, 4+) nemesének 3-as szintje
        # fölé, de a géme alá (2026-10-02, Moha: splinter-elv).
        if not allas.kenyszertar:
            return None
        licit = (kotesek or {}).get("_licit")
        if not licit or not licit[0].isdigit() or licit[1:] not in SZINEK:
            return False
        szint, b = int(licit[0]), licit[1:]
        if b in allas._mondott.get(allas.ules, set()) | allas._mondott.get(allas.partner, set()):
            return False                       # nem új szín
        kov = allas.kovetkezo_licit(b)
        if kov is None or szint <= kov[0]:
            return False                       # nem ugrás
        p = allas.kenyszertar[allas.partner]
        for m in NEMESEK:
            if m == b or p.hossz(m)[0] < 4:
                continue
            if _licit_rang(f"3{m}") < _licit_rang(licit) < _licit_rang(f"4{m}"):
                return True
        return False

    if t == "NYILATKOZOTT":
        return allas.nyilatkozott(csp.get("ki", "p"))

    if t == "KONTRA_ALLAS":
        return allas.kontra_allas == csp["ertek"]

    if t == "REKONTRA":
        return allas.rekontrazva

    if t == "ISMERT_SZINEK":
        # Hány színt ígért a megnevezett fél? A fésű kettőt kér
        # (össze kell fésülni), az információs kontra elve egyet.
        db = len(allas.ismert_szinek(csp.get("ki", "ok"),
                                     int(csp.get("min_hossz", 4))))
        return _osszehasonlit(db, csp.get("op", "="), csp["db"])

    if t == "FIT":
        sz = _szin(csp, kotesek)
        if sz is None:
            return None
        return allas.fit(sz) >= int(csp.get("min", 8))

    if t == "IGERT":
        e = _igert(csp, allas, kotesek)
        # "biztos": csak a TUDOTT ígéret számít (a nyitott sáv: nem)
        return (e is True) if csp.get("biztos") and allas.kenyszertar else e

    if t == "ADU":
        # Van-e megállapodott adunk, és milyen? ("nemes" / "minor" / "barmely")
        if not allas.kenyszertar:
            return None
        adu = allas.adu()
        fajta = csp.get("fajta", "barmely")
        if fajta == "nincs":
            return adu is None
        if adu is None:
            return False
        return (fajta == "barmely" or adu == fajta
                or (fajta == "nemes" and adu in NEMESEK)
                or (fajta == "minor" and adu in MINOROK))

    if t == "ELLENFEL_CSALAD":
        # Az ellenfél vonalának rendszercsaládja (a MohaBridzs game.systems-éből)
        from ..domain import vonal
        mi = vonal(allas.ules)
        ok = "EW" if mi == "NS" else "NS"
        csalad = (allas.csaladok or {}).get(ok)
        if csalad is None:
            return False           # nem tudjuk: a családhoz kötött védekezés nem él
        cel = csp["ertek"]
        cel = cel if isinstance(cel, list) else [cel]
        return csalad in cel

    if t == "PARTNER_GI":
        # A partner utolsó licitje géminvit volt-e
        if not allas.kenyszertar:
            return None
        return bool(getattr(allas.kenyszertar.get(allas.partner), "gi", False))

    if t == "GEMFORSZ":
        # Gémforszban vagyunk-e: volt-e a vonalunkon gémforsz licit?
        if not allas.kenyszertar:
            return None
        van = any(getattr(allas.kenyszertar.get(u), "gemforsz", False)
                  for u in (allas.ules, allas.partner))
        # KVÁZI gémforsz: a határ (pl. 4m) elérésével megszűnik (a
        # szerkesztő, 2026-10-21) — minimális lappal passz jöhet. Megállapodott
        # NEMES adu mellett nem: ott a gém (4M) a cél, a 4m kulcslicit.
        if van and not csp.get("volt") and allas.gf_teljesult() and allas.adu() not in ("H", "S"):
            van = False
        return van if csp.get("ertek", True) else not van

    if t == "FOGASMUTATAS":
        # A FOGÁSMUTATÁS elv helyzete (elvek/fogasmutatas.yaml): gémforszban
        # vagyunk, nincs színtalálkozás (a vonalnak a `fit_szinek` egyikében
        # sincs tudott `fit_min`+ lapja), és a most definiált licit 3NT
        # alatti új szín a legolcsóbb szinten (nem ugrás) — amit a vonal még
        # nem fedett le, és az ellenfél sem mondott —, vagy szan legfeljebb
        # 3NT-ig (még 3NT alatt állunk).
        if not allas.kenyszertar:
            return None
        van_gf = any(getattr(allas.kenyszertar.get(u), "gemforsz", False)
                     for u in (allas.ules, allas.partner))
        if not van_gf:
            return False
        fit_min = int(csp.get("fit_min", 8))
        fit_szinek = NEMESEK if csp.get("fit_szinek", "nemes") == "nemes" else SZINEK
        if any(allas.fit(sz) >= fit_min for sz in fit_szinek):
            return False
        licit = (kotesek or {}).get("_licit")
        if not licit or not licit[0].isdigit():
            return False
        r, h = _licit_rang(licit), _licit_rang("3NT")
        most = allas._legmagasabb
        if most is not None and _licit_rang(f"{most[0]}{most[1]}") >= h:
            return False
        mod = csp.get("mod", "fogas")
        if mod == "barmely":       # bármely licit (pl. 4M), amíg 3NT alatt állunk
            return True
        if licit[1:] in ("NT", "N"):
            return r <= h
        sz = licit[1:]
        if sz not in SZINEK or r >= h or allas.kovetkezo_licit(sz) != (int(licit[0]), sz):
            return False
        fedett = allas.fedett_szinek("mi", bool(csp.get("termeszetes", True)))
        if mod == "lefedve":
            # minden szín le van fedve (a 3NT felé már nincs mit mutatni): a
            # színlicit itt leírás — ismétlés, második szín, kétség
            return all(x in fedett for x in SZINEK)
        if sz in fedett or allas.mondta(sz, "ok"):
            return False
        fedetlen = [x for x in SZINEK if x not in fedett]
        if csp.get("terulet"):
            return True            # a terület minden le nem fedett színt magáénak tekint
        if mod == "help":
            # az EGYETLEN még le nem fedett szín (a negyedik szín): fogáskérés
            return len(fedetlen) == 1
        # fogásmutatás: legalább két le nem fedett szín közül az egyik (ha
        # csak egy maradt, és van benne fogásom, a 3NT jön; ha nincs, HELP)
        return len(fedetlen) >= 2

    if t == "KENYSZERITO_PASSZ":
        # KÉNYSZERÍTŐ PASSZ HELYZET (FORSZPASSZ_KIBIC elv, 2026-10-12): az
        # ellenfél a GÉMÜNK fölé licitált (az utolsó nem-passz hívás az ő
        # licitjük, előtte a vonalunk gémet mondott), és (a) csak mi vagyunk
        # beliben, vagy (b) a vonalunkon elfogadott invit volt, vagy (c) a
        # vonalunkon gémforsz licit volt. A `szerep`: "elso" — a vonalunkról
        # még senki nem szólt a licitjük óta; "masodik" — a partner már
        # (kényszerítően) passzolt; "barmely".
        from ..domain import vonal as _vonal
        hiv = [(e.get("ules"), str(e.get("licit", "")).upper()) for e in allas.licitek]
        idx = next((i for i in range(len(hiv) - 1, -1, -1)
                    if hiv[i][1] not in ("P", "PASS")), None)
        if idx is None:
            return False
        mi = _vonal(allas.ules)
        u, h = hiv[idx]
        if _vonal(u) == mi or Allas._bont(h)[0] is None:
            return False                       # nem az ő licitjük (vagy kontra)
        szerep = "masodik" if any(x[0] == allas.partner for x in hiv[idx + 1:]) else "elso"
        cel = csp.get("szerep", "barmely")
        if cel != "barmely" and cel != szerep:
            return False
        sajat = next((x[1] for x in reversed(hiv[:idx])
                      if _vonal(x[0]) == mi and Allas._bont(x[1])[0] is not None), None)
        if sajat is None:
            return False
        szint, szin = Allas._bont(sajat)
        if szint < GEMSZINT[szin]:
            return False                       # nem gémet mondtunk
        if _szkorhelyzet(allas) == "S":
            return True                        # (a) mi beliben, ők mansban
        if not allas.kenyszertar:
            return None
        vonalunk = [allas.kenyszertar.get(x) for x in (allas.ules, allas.partner)]
        if any(getattr(ig, "elfogad", False) for ig in vonalunk if ig is not None):
            return True                        # (b) elfogadott invit
        return any(getattr(ig, "gemforsz", False) for ig in vonalunk if ig is not None)  # (c)

    if t == "HELP_UTAN":
        # a HELP (negyedik szín) után: a `ki` ("p" vagy "en") utolsó licitje
        # a HELP volt-e, és azóta a vonalunkon csak a válasz hangzott el
        u = allas.partner if csp.get("ki", "p") == "p" else allas.ules
        ig = allas.kenyszertar.get(u) if allas.kenyszertar else None
        hsz = getattr(ig, "help_szin", None)
        if not hsz:
            return False
        _, utolso = allas.utolso_licit(u)
        return bool(utolso) and utolso[1:] == hsz

    if t == "EN_3_SZINTEN":
        # mondtam-e már színt a 3-as szinten vagy följebb (a leírás megtörtént)
        return any(e.get("ules") == allas.ules
                   and str(e.get("licit", "")).upper()[:1].isdigit()
                   and int(str(e.get("licit"))[0]) >= 3
                   and str(e.get("licit", "")).upper()[1:] in SZINEK
                   for e in allas.licitek)

    if t == "CSAK_PARTNER_FOGAS":
        # A színt csak a partner fogás-ígérete fedi (a vonal nem licitálta
        # természetesen, és én sem ígértem benne fogást) — a „kétség”-hez.
        sz = _szin(csp, kotesek)
        if sz is None or not allas.kenyszertar:
            return None
        p = allas.kenyszertar.get(allas.partner)
        en = allas.kenyszertar.get(allas.ules)
        return (sz in (getattr(p, "fogas", set()) or set())
                and sz not in (getattr(en, "fogas", set()) or set())
                and sz not in allas.termeszetes_szinek("mi"))

    if t == "ELV_KONTEXTUS":
        # Egy elv-sablon példányának érvényességi helyzete: a vonal licitmenete
        # (pároslicit) ezek valamelyikével KEZDŐDIK, és azóta legalább egy
        # licit már elhangzott (a minta utáni folytatásra vonatkozik).
        from .minta import MintaHiba, illeszkedik, kanonizal, minta_parse
        try:
            _, tok = kanonizal(allas.licitek, allas.ules) if allas.licitek else ("", [])
        except Exception:          # noqa: BLE001
            return False
        for m in csp.get("mintak") or []:
            try:
                mp = minta_parse(str(m))
            except MintaHiba:
                continue
            n = len(mp.tokenek)
            if len(tok) >= n and illeszkedik(mp, tok[:n]) is not None:
                return True
        return False

    if t == "PARTNER_FORSZOL":
        # Kötelez-e a partner utolsó licitje, hogy ne passzoljunk? Csak ha
        # az utolsó érdemi licit az övé (ha az ellenfél közbeszólt, a
        # kényszer feloldódik), és a jelentése forszot mondott. A KIZARO
        # nem forsz: az a partner blokkja.
        utolso = next((e for e in reversed(allas.licitek)
                       if str(e.get("licit", "")).upper() not in ("P", "PASS")),
                      None)
        if utolso is None or utolso.get("ules") != allas.partner:
            return False
        ig = allas.kenyszertar.get(allas.partner) if allas.kenyszertar else None
        if ig is None or not ig.nyilatkozott:
            return None
        return ig.forsz in ("EGY_MENET", "GEMFORSZ", "SZLEMFORSZ")

    raise HelyzetHiba(f"Ismeretlen helyzeti csomópont: {t!r}")


def _igert(csp: dict, allas: Allas,
           kotesek: dict[str, str] | None) -> bool | None:
    """
    Kényszertár-lekérdezés: ígért-e a megnevezett játékos ennyit?

    FONTOS: a kényszertár a "mi LEHET" tára. Ha a licit nem szűkített,
    az intervallum nyitott marad, és a kérdés ISMERETLEN — nem HAMIS.
    Az a különbség, hogy nem tudunk róla, vagy tudjuk, hogy nincs.
    """
    ulesek = allas.ulesek(csp.get("ki", "p"))
    if not ulesek:
        return None
    mit = csp.get("mit", "PONT")
    op = csp.get("op", ">=")
    v = float(csp["v"])

    eredmenyek = []
    for u in ulesek:
        ig = allas.kenyszertar[u]
        if not ig.nyilatkozott:
            eredmenyek.append(False)      # aki passzolt, nem ígért semmit
            continue
        if mit == "PONT":
            also, felso = ig.pont_min, ig.pont_max
        elif mit == "HOSSZ":
            sz = _szin(csp, kotesek)
            if sz is None:
                return None
            also, felso = ig.hossz(sz)
        else:
            raise HelyzetHiba(f"Ismeretlen ígéret-fajta: {mit!r}")
        eredmenyek.append(_intervallum(also, felso, op, v))

    if any(e is True for e in eredmenyek):
        return True
    if any(e is None for e in eredmenyek):
        return None
    return False


def _intervallum(also: float, felso: float, op: str,
                 v: float) -> bool | None:
    """
    Egy [also, felso] intervallumról eldönteni, teljesíti-e a feltételt.
    IGAZ, ha az egész intervallum teljesíti; HAMIS, ha egyik pontja sem;
    ISMERETLEN, ha csak egy része — ilyenkor a licit nem szűkített eléggé.
    """
    if op in (">=", ">"):
        jo_also = also >= v if op == ">=" else also > v
        jo_felso = felso >= v if op == ">=" else felso > v
        return True if jo_also else (None if jo_felso else False)
    if op in ("<=", "<"):
        jo_felso = felso <= v if op == "<=" else felso < v
        jo_also = also <= v if op == "<=" else also < v
        return True if jo_felso else (None if jo_also else False)
    if op == "=":
        if also == felso == v:
            return True
        return None if also <= v <= felso else False
    raise HelyzetHiba(f"Ismeretlen operátor: {op!r}")


def _licit_rang(licit: str) -> int | None:
    """
    Egy licit helye a rangsorban: 1C = 0, 1D = 1, ... 7NT = 34.
    Ezzel a "4H magasságáig" alakú határ pontosan kifejezhető.
    """
    szint, szin = Allas._bont(str(licit).upper())
    if szint is None:
        return None
    return (szint - 1) * 5 + JELENTESEK.index(szin)


def _osszehasonlit(bal: float, op: str, jobb) -> bool:
    jobb = float(jobb)
    return {">": bal > jobb, "<": bal < jobb, ">=": bal >= jobb,
            "<=": bal <= jobb, "=": bal == jobb}[op]


def _szkorhelyzet(allas: Allas) -> str:
    """M / A / S / O — a LICREN zónajelölése (lásd kifejezes.Kontextus)."""
    from ..domain import beliben
    mi = beliben(allas.ules, allas.beliallas)
    ok = beliben(allas.bal, allas.beliallas)
    if mi and ok:
        return "M"
    if not mi and not ok:
        return "A"
    return "S" if mi else "O"


# --- Emberi nyelvű leírás --------------------------------------------

_SZIN_NEV = {"S": "pikk", "H": "kőr", "D": "káró", "C": "treff", "NT": "szan"}
_KI_NEV = {"en": "én", "p": "a partner", "bal": "a bal kéz",
           "jobb": "a jobb kéz", "mi": "a vonalunk", "ok": "az ellenfelek"}


def leiras(csp: dict) -> str:
    """A helyzeti feltétel ember által olvasható alakja."""
    t = csp.get("t")
    if t == "ES":
        return "(" + " és ".join(leiras(g) for g in csp["gy"]) + ")"
    if t == "VAGY":
        return "(" + " vagy ".join(leiras(g) for g in csp["gy"]) + ")"
    if t == "LEGALABB":
        return (f"(legalább {csp.get('m')} ezekből: "
                + "; ".join(leiras(g) for g in csp["gy"]) + ")")
    if t == "NEM":
        return "nem " + leiras(csp["gy"][0])
    if t == "ULES":
        e = csp["ertek"]
        return f"{e if not isinstance(e, list) else '/'.join(map(str, e))}. ülés"
    if t == "SZKOR":
        return {"M": "mindkét vonal beliben", "A": "senki nincs beliben",
                "S": "csak mi vagyunk beliben",
                "O": "csak ők vannak beliben"}.get(csp["ertek"], "?")
    if t == "SZABAD":
        return "szabad licit (jobbról passz)"
    if t == "SZINT":
        return f"a licitszint {csp.get('op','<=')} {csp['v']}"
    if t == "LICIT_LEGFELJEBB":
        return (f"a licit legfeljebb {csp['hatar']} magasságában jár"
                if csp.get("bezarolag", True)
                else f"a licit {csp['hatar']} alatt jár")
    if t == "AG":
        e = csp["ertek"]
        nevek = {"PAROS": "páros licit", "KUZDELMI": "küzdelmi helyzet",
                 "VEDEKEZO": "védekező vonalon"}
        lista = e if isinstance(e, list) else [e]
        return " vagy ".join(nevek.get(x, x) for x in lista)
    if t == "GEM_ALATT":
        return f"{_szinnev(csp)} még gém alatt mondható"
    if t == "ELLENFEL_KONTRAZOTT":
        return "az ellenfél kontrázott"
    if t == "LEGOLCSOBB_SZINT":
        return f"{_szinnev(csp)} legolcsóbb licitje legfeljebb {csp.get('max', 3)}-as szintű"
    if t == "ELLENFEL_SZINE":
        return f"az ellenfél színe (kimondva vagy kontrával ígérve): {_szinnev(csp)}"
    if t == "MONDVA":
        return f"{_KI_NEV.get(csp.get('ki','ok'),'?')} mondta a {_szinnev(csp)}t"
    if t == "MONDVA_3NT_ELOTT":
        return f"a vonalunk a 3NT előtt színként licitálta a {_szinnev(csp)}t"
    if t == "NEGYEDIK_SZIN":
        return "a licit a negyedik szín (a vonal három igazi színe után, a legolcsóbb)"
    if t == "PARTNER_NEGYEDIK":
        return "a partner a negyedik színt licitálta"
    if t == "UGRAS":
        return "ugrás (nem a legolcsóbb szinten)"
    if t == "PARTNER_KULCSLICIT":
        # a partner utolsó (nem passz) licitje kulcslicit volt-e (a
        # propagálás jelöli a licit elemében)
        i, lic = allas.utolso_licit(allas.partner)
        if not lic or not allas.licitek[i].get("kulcslicit"):
            return False
        # az adu színe (gém / leállás) és a szan nem kulcslicit
        return lic[1:] not in ("NT", allas.adu())

    if t == "PARTNER_UGROTT":
        return "a partner utolsó licitje ugrás volt"
    if t == "PARTNER_KULCSLICIT":
        return "a partner utolsó licitje kulcslicit volt"
    if t == "EROS_UGRAS":
        return "ugrás új színben második megszólalásként (erő, gémforsz)"
    if t == "EN_NYITOTTAM":
        return "én nyitottam"
    if t == "GYENGE_UGRAS":
        return ("gyenge ugrás-helyzet: új szín " + ("dupla" if int(csp.get("lepes", 1)) == 2
                else "egyszeres") + " ugrással, első megszólalásként, kényszer nélkül; "
                "az alacsonyabb licit definiált, az ugrás nem")
    if t == "SPLINTER_HELYZET":
        return "ugrás új színben a partner nemesének 3-as szintje fölé (gém alatt)"
    if t == "NYILATKOZOTT":
        return f"{_KI_NEV.get(csp.get('ki','p'),'?')} már nyilatkozott"
    if t == "KONTRA_ALLAS":
        return {"NINCS": "nincs élő kontra", "MI": "a mi kontránk él",
                "OK": "az ő kontrájuk él"}.get(csp["ertek"], "?")
    if t == "REKONTRA":
        return "rekontra van"
    if t == "ISMERT_SZINEK":
        return (f"{_KI_NEV.get(csp.get('ki','ok'),'?')} "
                f"{csp.get('op','=')}{csp['db']} színt ígért")
    if t == "FIT":
        return f"ismert {csp.get('min',8)}+ fit a {_szinnev(csp)}ben"
    if t == "ADU":
        f = csp.get("fajta")
        if f in SZINEK:
            return f"megállapodott adu: {_SZIN_HU[f]}"
        return {"nemes": "megállapodott nemes adu mellett",
                "minor": "megállapodott minor adu mellett"}.get(
                    f, "megállapodott adu mellett")
    if t == "GEMFORSZ":
        return "gémforszban" if csp.get("ertek", True) else "nem gémforszban"
    if t == "FOGASMUTATAS":
        fm = csp.get("fit_min", 8)
        fm = "{" + str(fm["sablon"]) + "}" if isinstance(fm, dict) and "sablon" in fm else fm
        mod = csp.get("mod", "fogas")
        if mod == "lefedve":
            return (f"fogásmutatás a 3NT felé, de már minden szín le van fedve: "
                    f"gémforszban, színtalálkozás nélkül ({fm}+ lapos fit nincs), 3NT alatt")
        if mod == "barmely":
            return (f"fogásmutatás a 3NT felé: gémforszban, színtalálkozás nélkül "
                    f"({fm}+ lapos fit nincs), még 3NT alatt")
        if mod == "help":
            return (f"negyedik szín (HELP): gémforszban, színtalálkozás nélkül ({fm}+ lapos "
                    f"fit nincs), 3NT alatt, az egyetlen még le nem fedett színben")
        return (f"fogásmutatás a 3NT felé: gémforszban, színtalálkozás nélkül "
                f"({fm}+ lapos fit nincs), 3NT alatt, "
                f"a még le nem fedett színben (vagy maga a 3NT)")
    if t == "ELV_KONTEXTUS":
        return "a(z) " + " / ".join(map(str, csp.get("mintak") or [])) + " után"
    if t == "CSAK_PARTNER_FOGAS":
        return f"a {_szinnev(csp)} színt csak a partner fogása fedi"
    if t == "EN_3_SZINTEN":
        return "mondtam már színt a 3-as szinten"
    if t == "KENYSZERITO_PASSZ":
        return {"elso": "kényszerítő passz helyzetében, elsőként",
                "masodik": "kényszerítő passz helyzetében, a partner kényszerítő passza után"}.get(
                    csp.get("szerep"), "kényszerítő passz helyzetében")
    if t == "HELP_UTAN":
        return ("a partner fogást kért (HELP)" if csp.get("ki", "p") == "p"
                else "fogást kértem (HELP)")
    if t == "PARTNER_GI":
        return "a partner géminvitet adott"
    if t == "ELLENFEL_CSALAD":
        cel = csp["ertek"] if isinstance(csp["ertek"], list) else [csp["ertek"]]
        return "az ellenfél rendszercsaládja: " + " / ".join(cel)
    if t == "IGERT":
        ki = _KI_NEV.get(csp.get("ki", "p"), "?")
        if csp.get("mit", "PONT") == "HOSSZ":
            return f"{ki} {csp.get('op','>=')}{csp['v']} lapot ígért a {_szinnev(csp)}ben"
        return f"{ki} {csp.get('op','>=')}{csp['v']} pontot ígért"
    if t == "IGAZ":
        return "mindig"
    if t == "ISMERETLEN":
        return "<eldönthetetlen>"
    return str(t)


_SZIN_HU = {"S": "pikk", "H": "kőr", "D": "káró", "C": "treff"}


def _szinnev(csp: dict) -> str:
    sz = csp.get("szin")
    if isinstance(sz, str) and sz.startswith("@"):
        return "{" + sz[1:] + "}"
    return _SZIN_NEV.get(sz, str(sz))
