"""
LICITRENDSZER YAML-FORRÁSBÓL.

A rendszerek és konvenciók KANONIKUS alakja olvasható YAML-fájl a
`rendszerek/yaml/` alatt; az adatbázis `licitmenet` sorai ebből
SZÁRMAZNAK (`python -m kibic.cli.rendszerimport`). Így a rendszer
verziókövethető, átnézhető, és bármikor újraépíthető.

A LÉNYEG: EGY LEÍRÁS, KÉT KIMENET
---------------------------------
Egy szabály kéz-leírásából (`pont`, `hossz`, `elosztas`, `vagy` ...)
egyszerre áll elő

    * a `feltetel` — MIKOR licitálható (a licitmotor ezt értékeli ki);
    * a `jelentes` — MIT ÍGÉR, ha elhangzott (a kényszertár ebből épül).

Így a kettő nem csúszhat szét: amit a kibic licitál, azt ugyanúgy is
érti, ha a partnere mondja.

A FORMÁTUM
----------
    rendszer:
      kod: KIBICEGY_STAND
      nev: Kibic egyesület standard
      fajta: ALAPRENDSZER             # / KONVENCIO / RENDSZER / GYUJTEMENY / RENDSZERCSALAD
      csalad: NATURAL
      verzio: "0.1"
      leiras: ...
      forras: rendszerek/kibic_standard_1.0.doc
    parameterek: {PONT_METRIKA: P_HCP}
    hivatkozasok:                     # SORREND SZÁMÍT: az előbbi nyer
      - STAYMAN
      - {kod: MULTI, aktiv: false}
    fejezetek:
      - fejezet: Az 1NT indulás
        szabalyok:
          - minta: 1NT
            pont: 15-17
            elosztas: BAL
            magyarazat: 15-17 FP, egyenletes

Szabálykulcsok (mind opcionális, kivéve a `minta`-t):

    minta       mintanyelv (doc/mintanyelv.md)
    pont        figurapont-sáv: "15-17", "12+", "0-7", "5" — vagy zónánként:
                {O: "8+", A: "9+", M: "10+", S: "11+"}
                (O: csak ők bellben, A: senki, M: mindkét vonal, S: csak mi)
    ap          asztali pont-sáv (figurapont + rövidségpont) fit utáni emeléshez:
                4+ adunál 5-3-1 (sikén 5, szingli 3, dubló 1), 3 adunál 3-2-1
    hossz       {S: "5+", H: "0-3", M: "4+", oM: "0-3"}  (változó is lehet)
                ZÁRÓJELES LEHETŐSÉG: {H: "(4)5+"} — a rendszer 5+ lapot ír,
                de 4 lappal is LEHET. Két sor lesz belőle: az 5+ rendes
                szabály; a 4 lapos csak akkor, ha a `lehetoseg:` feltétele
                teljesül — ha nincs ilyen, MÉRLEGELŐ jelölt (a szabály nem
                dönt helyette).
    lehetoseg   a zárójeles lehetőség feltétele: kéz-kulcsok + `ha`
                (+ `prioritas`, `magyarazat`), pl.
                {ha: {ules: [3, 4]}, pont: {O: "8-11"}, hossz: {S: "3+"}}
    rel         színviszonyok: ["S>=H", "D>C"]
    elosztas    BAL | NEM_BAL | ["4333", "5332"] (rendezett alakok)
    szkor       A / M / S / O   (a kéz-feltételbe megy: zónafüggő sáv)
    vagy        alternatívák listája, mindegyik a fenti kulcsokkal
    feltetel    nyers kifejezésfa, ÉS-sel hozzáfűzve
    jelentes    nyers jelentés-kiegészítés (felülírja a számítottat)
    tagad       ["NEMES4"] — a jelentésbe
    forsz       NEM / EGY_MENET / GEMFORSZ / SZLEMFORSZ / KIZARO
    elvaras     SEMMI / VALASZ / VALASSZ / KORRIGALJ / DONTS / PASSZOLJ
    ha          helyzeti feltétel: {ules: [3,4], szkor: O, ag: KUZDELMI,
                                    partner_forszol: false,
                                    legfeljebb: 4H, nyers: {...}}
    lapok       ["CA", "CK"] — ezek nála vannak
    nincs       ["SA", "HK"] — ezek nincsenek nála
    fohonor     {S: "2+"} — A/K/D darabszám a színben
    figura      {S: "4+"} — figurapont a színben
    aszok       "1" / "0-1" — az ászok száma
    fogas       [H, S] — fogás ezekben (Ax, Kx, Dxx, Bxxx)
    nincs_fogas [H]    — nincs fogás
    alert       true vagy rövid szöveg (akkor az a magyarázat is)
    kihagy      true — csak MÓDOSÍTOTT konvencióban: az alap ezen a
                kulcson lévő szabálya ebben a változatban nem él (KIHAGYAS
                sor; a régi neve `torol`, az is jó)
    kivalt      true — bármely konvencióban: a kártyán MÖGÖTTE álló
                rendszer ezen a kulcson lévő szabályát ez a konvenció
                kiváltja (pl. a fedőkereső invit a rövidszín-gémkísérletet)
    mellekszin  [A, B] — ezek a színváltozók nem az adu (M) színe
    licit_alatt "4M" — a most definiált licit e határ alatt van (gém alatt)
    igeret      {ap: also} / {pont: felso} — a lap az eddig ÍGÉRT saját
                sáv alsó felében (legfeljebb a közepe) / felső felében /
                tetején (max);
                a sávot a kényszertár adja, nem kell kézzel beírni
    alulrol     true — ha több ilyen licit is illik, a legolcsóbb (Bánky);
                szándékos, az ellenőrző nem jelzi ütközésnek
    jegyzet     tartós magyarázat a szerkesztőnek: MIÉRT ilyen a szabály
                (a szerkesztő mindig mutatja). Van rendszer- és
                fejezet-szintű `jegyzet:` is.
    magyarazat, en, nyers, alfejezet, kulcs, prioritas (alap 50),
    dontesi_mod, fajta (SZABALY/ELV/KIVETEL), allapot

FAJTÁK (019)
------------
    ALAPRENDSZER  emberi forrásból, sok szabállyal; hivatkozhat konvenciókra
                  ("Staymant játszunk")
    KONVENCIO     egy konkrét probléma megoldása; `tema:` — az azonos témájúak
                  egymás alternatívái; nem hivatkozik semmire
    RENDSZER      amit egy pár játszik: CSAK hivatkozások (+ kártya, paraméterek)
    GYUJTEMENY    csak hivatkozások, a kényelem kedvéért
    RENDSZERCSALAD (024) egy rendszercsalád ÁLTALÁNOS rendszere (pl. erős
                  treff): nyitások és a legfontosabb válaszok — ezzel érti a
                  kibic egy ismeretlen pár licitjeit, ha csak a családját
                  tudja. A kódja a `csalad` értéke (STRONG_CLUB …).
A régi nevek (LICITRENDSZER, KONVENCIOKARTYA) is elfogadottak, és az újra
fordulnak.

MÓDOSÍTOTT KONVENCIÓ / VÁLTOZAT (020):

    rendszer: {kod: MOHA_LEBENSOHL, fajta: KONVENCIO,
               alapja: LEBENSOHL, viszony: MODOSITAS}   # vagy VALTOZAT

Az alap minden szabálya él, kivéve amit a módosítás azonos kulccsal
felülír, vagy `torol: true`-val kivesz. A téma az alapé, ha nincs saját.

KIZÁRÁS (csak RENDSZER és GYUJTEMENY): "ezt játsszuk, ennek kivételével".
A kizárás a rendszer ALATTI teljes fában hat, és erősebb a beemelésnél:

    hivatkozasok:
      - {kod: MOHA_KUZDELMI, kiveve: [MULTI_LANDY]}   # ugyanaz, mint lent
    kizarasok:
      - MULTI_LANDY                                    # egy konvenció / gyűjtemény
      - {kod: KIBICEGY_STAND, fejezet: "A 2♣ indulás"} # egy fejezete

Egy-egy szabályt nem lehet kizárni (lyukat hagyna): azt felül kell írni.

A modul NEM nyúl adatbázishoz: tiszta fordító. Az írás a
`cli/rendszerimport.py` dolga, az ellenőrzés a `motor/rendszercheck.py`-é.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..motor.kifejezes import ismeretlen_jelzok, leiras
from ..motor.minta import MintaHiba, minta_norm, minta_parse

SZINEK = ("S", "H", "D", "C")
VALTOZO_SZINEK = ("M", "m", "A", "B", "E", "oM", "om", "Q")
FAJTAK = ("ALAPRENDSZER", "KONVENCIO", "RENDSZER", "GYUJTEMENY", "RENDSZERCSALAD",
          "ELV_SABLON")
REGI_FAJTAK = {"LICITRENDSZER": "ALAPRENDSZER", "KONVENCIOKARTYA": "RENDSZER"}
CSAK_HIVATKOZAS = ("RENDSZER", "GYUJTEMENY")     # saját szabály nélkül
CSALADOK = ("NATURAL", "STRONG_CLUB", "ACOL", "PRECISION", "POLISH", "EGYEB")
# 2026-10-02: a PRECISION nem család, hanem az erős treff család rendszere.
# Az adatbázis enumjában (és a régi game.systems-ben) megmarad, de a YAML
# már nem használhatja családként; a vonal-feloldás STRONG_CLUB-ra fordítja.
CSALAD_ALIAS = {"PRECISION": "STRONG_CLUB"}
FORSZOK = ("NEM", "EGY_MENET", "GEMFORSZ", "SZLEMFORSZ", "KIZARO")
ELVARASOK = ("SEMMI", "VALASZ", "VALASSZ", "KORRIGALJ", "DONTS", "PASSZOLJ")
DONTESI_MODOK = ("SORREND", "SPECIFIKUSSAG", "MERLEGELO")
SZABALY_FAJTAK = ("SZABALY", "ELV", "KIVETEL")
VISZONYOK = ("VALTOZAT", "MODOSITAS")
ALLAPOTOK = ("JAVASOLT", "ELFOGADOTT", "ELVETETT", "FELULVIZSGALANDO", "JEGELT")
SZKOROK = ("A", "M", "S", "O")

# Az egyenletes elosztás a magyar rendszerleírások szerint
BAL_ALAKOK = ("4333", "4432", "5332")

ALAP_PRIORITAS = 50
YAML_SPECIFIKUSSAG = 100

_SZABALY_KULCSOK = {
    "minta", "pont", "hossz", "rel", "elosztas", "szkor", "vagy",
    "feltetel", "jelentes", "tagad", "forsz", "elvaras", "ha", "alert",
    "magyarazat", "en", "nyers", "alfejezet", "kulcs", "prioritas",
    "dontesi_mod", "fajta", "allapot", "megjegyzes",
    "lapok", "nincs", "fohonor", "figura", "fogas", "nincs_fogas", "aszok",
    "specifikussag", "ap", "lehetoseg", "torol", "kihagy", "jegyzet",
    "minoseg", "fele_a_szinben", "fedoutes", "vesztok", "szin_vesztok",
    "mellekszin", "licit_alatt", "alulrol", "kivalt", "igeret",
    "kulcslapok", "adu_dama", "kulcs_adu", "kulcs_kizart", "kontroll", "invit", "elfogad",
    "licit_felett", "licit_gem", "nem_adu", "adu_szin", "nem_rkc", "szlem", "ot_biztos",
    "kontrollok", "nanopont", "kulonbozo", "folytatas", "onallo_adu",
    "maradek_vesztok", "osszesen", "leghosszabb", "fit",
    "jatekutes", "gyorsutes", "gemeselyes", "splinter_tamogatas",
    "fogas_maradek", "nincs_fit", "ures_figura", "ketseg", "korr_pont", "gyenge_fogas", "help_fogas",
    "gem_eselytelen", "eros_fogas", "leghosszabb_partner_szin", "misfit",
}
_KEZ_KULCSOK = {"pont", "ap", "hossz", "rel", "elosztas", "szkor", "vagy",
                "feltetel", "lapok", "nincs", "fohonor", "figura", "fogas",
                "nincs_fogas", "aszok", "minoseg", "fele_a_szinben", "fedoutes",
                "vesztok", "szin_vesztok", "mellekszin", "licit_alatt",
                "igeret", "kulcslapok", "adu_dama", "kulcs_adu", "kulcs_kizart", "kontroll",
                "licit_felett", "licit_gem", "nem_adu", "adu_szin", "nem_rkc",
                "szlem", "ot_biztos", "kontrollok", "nanopont", "kulonbozo",
                "onallo_adu", "maradek_vesztok", "osszesen", "leghosszabb", "fit",
                "jatekutes", "gyorsutes", "gemeselyes", "splinter_tamogatas",
                "fogas_maradek", "nincs_fit", "ures_figura", "ketseg", "korr_pont",
                "gyenge_fogas", "help_fogas", "gem_eselytelen", "eros_fogas",
                "leghosszabb_partner_szin", "misfit"}

# A lap minősége (LAPMINOSEG = jó jelek − rossz jelek, lásd 023_lapminoseg.sql)
_MINOSEG = {"jo": (">=", 2), "rossz": ("<=", -2),
            "nem_jo": ("<=", 1), "nem_rossz": (">=", -1)}
_SZIN_MAGYAR = {"S": "pikk", "H": "kőr", "D": "káró", "C": "treff"}
_SZIN_FOGAS = {"S": "pikkben", "H": "kőrben", "D": "káróban", "C": "treffben"}
_MINOSEG_SZOVEG = {"lapminőség >= 2": "jó lap", "lapminőség <= -2": "rossz lap",
                   "lapminőség <= 1": "nem jó lap", "lapminőség >= -1": "nem rossz lap"}


class ForrasHiba(ValueError):
    """Hibás YAML-forrás. Az üzenet megnevezi a fájlt és a szabályt."""


# --- Eredmény-adatszerkezetek -----------------------------------------

@dataclass
class Hivatkozas:
    kod: str
    aktiv: bool = True
    seq: int = 0
    # ELV-SABLON példányosítása (2026-10-05): hol érvényes (minták, amelyek
    # UTÁN az elv él) és a paraméterek felülírása. Üres: általános érvényű,
    # alapértékekkel.
    ervenyes: list[str] = field(default_factory=list)
    parameterek: dict = field(default_factory=dict)
    # az elv a saját területén kiváltja a kártyán mögötte álló sorokat
    kivalt: bool = True

    @property
    def beallitas(self) -> dict | None:
        """A példány beállítása (adatbázisba: hivatkozas_beallitas JSON)."""
        if not self.ervenyes and not self.parameterek and self.kivalt:
            return None
        b: dict = {}
        if not self.kivalt:
            b["kivalt"] = False
        if self.ervenyes:
            b["ervenyes"] = list(self.ervenyes)
        if self.parameterek:
            b["parameterek"] = dict(self.parameterek)
        return b


@dataclass
class Kizaras:
    """Kizárás a rendszer alatti fából: egy rendszer, vagy egy fejezete."""
    kod: str
    fejezet: str | None = None


@dataclass
class SzabalySor:
    """Egy `licitmenet` sor, adatbázisba írásra kész alakban."""
    seq: int
    fejezet: str | None
    alfejezet: str | None
    minta: str
    kulcs: str
    specifikussag: int
    prioritas: int
    feltetel: dict
    feltetel_szoveg: str
    jelentes: dict
    ha_feltetel: dict | None
    magyarazat: str | None
    magyarazat_en: str | None
    alert: bool
    forsz: str
    elvaras: str
    dontesi_mod: str
    szabaly_fajta: str
    ismeretlen: str | None
    ag: str
    allapot: str | None          # None: az importáló dönt (megőrzés)
    nyers_szoveg: str | None
    forras_hely: str             # "fajl.yaml: 1NT-2C" — hibaüzenetekhez
    jegyzet: str | None = None   # tartós magyarázat a szerkesztőnek
    ha_feltetel_szoveg: str | None = None   # a `ha:` emberi szövege


@dataclass
class RendszerForras:
    kod: str
    nev: str = ""
    fajta: str = "KONVENCIO"
    csalad: str = "EGYEB"
    csalad_megadva: bool = False        # a YAML kimondta-e (RENDSZER-nél kötelező)
    verzio: str = "0.1"
    leiras: str | None = None
    leiras_en: str | None = None
    nev_en: str | None = None
    forras: str | None = None
    parameterek: dict[str, str] = field(default_factory=dict)
    hivatkozasok: list[Hivatkozas] = field(default_factory=list)
    kizarasok: list[Kizaras] = field(default_factory=list)
    tema: str | None = None
    alapja: str | None = None           # módosított konvenció / változat
    viszony: str | None = None
    jegyzet: str | None = None          # a rendszer / konvenció jegyzete
    fejezet_jegyzetek: dict = field(default_factory=dict)
    sorok: list[SzabalySor] = field(default_factory=list)
    fajlok: list[str] = field(default_factory=list)
    # A konvenciókártya szöveges része (indulások, jelzések, stílus ...),
    # ami nem a licitszabályokból generálódik. Lásd motor/kartya.py.
    kartya: dict = field(default_factory=dict)
    # A kártyajelzési profil: melyik jelzésrendszert játssza
    # ({"rendszer": "MOHA_STAND"}; motor/jelzes.py, rendszerek/jelzesek/)
    jelzesek: dict = field(default_factory=dict)
    jelzesek_ir: bool = False           # az import írja-e (ha a jelzésrendszerek is betöltődtek)
    # ELV_SABLON: {"szoveg": a szerkesztő megfogalmazása, "parameterek":
    # {KOD: {"alap": …, "tartomany": …, "leiras": …}}}
    sablon: dict = field(default_factory=dict)


# --- Kis elemzők -------------------------------------------------------

_SAV_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)?\s*(?:(-)\s*(\d+(?:\.\d+)?)?|(\+))?\s*$")



# fele_a_szinben: az üres dáma/bubi leértékelése (színenként), 2026-10-05
FELE_URES_LEVONAS = 0.5

def sav(s) -> tuple[float | None, float | None]:
    """
    "15-17" -> (15, 17);  "12+" -> (12, None);  "0-7" -> (0, 7);
    "5" -> (5, 5);  "-7" -> (None, 7).
    """
    if isinstance(s, (int, float)):
        return float(s), float(s)
    m = _SAV_RE.match(str(s))
    if not m or (m.group(1) is None and m.group(3) is None):
        raise ForrasHiba(f"Értelmezhetetlen sáv: {s!r} (pl. '15-17', '12+', '5')")
    lo = float(m.group(1)) if m.group(1) is not None else None
    if m.group(4):                       # "12+"
        return lo, None
    if m.group(2):                       # "15-17" vagy "-7" vagy "5-"
        hi = float(m.group(3)) if m.group(3) is not None else None
        return lo, hi
    return lo, lo                        # "5"


def _szin_kod(nev: str) -> str:
    """A kifejezésfában: konkrét szín maradhat, a változó `@`-os lesz."""
    if nev in SZINEK:
        return nev
    if nev in VALTOZO_SZINEK:
        return "@" + nev
    raise ForrasHiba(f"Ismeretlen szín vagy színváltozó: {nev!r}")


def _lap(x, hely: str) -> str:
    """'SA', 'CK' — szín + figura, a kifejezésfa `LAP` jelölése. Változós
    színnel is: 'AA' = az A színváltozó ásza, 'MK' = az adu (M) királya."""
    x = str(x).strip()
    if len(x) >= 2 and x[:-1] in VALTOZO_SZINEK and x[-1].upper() in "AKQJT98765432":
        return f"@{x[:-1]}:{x[-1].upper()}"
    x = x.upper()
    if len(x) != 2 or x[0] not in SZINEK or x[1] not in "AKQJT98765432":
        raise ForrasHiba(f"{hely}: hibás lapjelölés: {x!r} (pl. 'SA', 'CK')")
    return x


def _fogas_fa(sz: str, hely: str) -> dict:
    """
    FOGÁS (stopper) közelítése: Ax, Kx(x), Dxx, Bxxx vagy bármelyik
    négyes+ szín honőrrel. A pontos megítélés a lejátszásé; itt csak a
    licitdöntéshez kell egy tisztességes küszöb.
    """
    if sz in VALTOZO_SZINEK:          # színváltozó is (pl. Q, a negyedik szín)
        lap = lambda e: _osszevet({"t": "LAP", "lap": f"@{sz}:{e}"}, "=", 1)  # noqa: E731
        h = {"t": "SZIN", "szin": "@" + sz}
    elif sz not in SZINEK:
        raise ForrasHiba(f"{hely}: a `fogas` csak színre vagy színváltozóra megy: {sz!r}")
    else:
        lap = lambda e: _osszevet({"t": "LAP", "lap": sz + e}, "=", 1)  # noqa: E731
        h = {"t": "SZIN", "szin": sz}
    return {"t": "VAGY", "gy": [
        lap("A"),
        {"t": "ES", "gy": [lap("K"), _osszevet(h, ">=", 2)]},
        {"t": "ES", "gy": [lap("Q"), _osszevet(h, ">=", 3)]},
        {"t": "ES", "gy": [lap("J"), _osszevet(h, ">=", 4)]},
    ]}


def _szam(v):
    return int(v) if float(v).is_integer() else v


# --- Kifejezésfa-építők ------------------------------------------------

def _osszevet(bal: dict, op: str, v) -> dict:
    return {"t": "OSSZE", "op": op, "bal": bal,
            "jobb": {"t": "SZAM", "v": _szam(v)}}


def _sav_fa(ert: dict, lo, hi) -> list[dict]:
    ki = []
    if lo is not None:
        ki.append(_osszevet(ert, ">=", lo))
    if hi is not None:
        ki.append(_osszevet(ert, "<=", hi))
    return ki


def _es(gy: list[dict]) -> dict:
    gy = [g for g in gy if g and g.get("t") != "IGAZ"]
    if not gy:
        return {"t": "IGAZ"}
    return gy[0] if len(gy) == 1 else {"t": "ES", "gy": gy}


_REL_RE = re.compile(r"^\s*(\w+)\s*(>=|<=|>|<|=)\s*(\w+)\s*$")


def _elosztas_alakok(e) -> tuple[list[str], bool]:
    """(alakok, tagadott?)"""
    if isinstance(e, str):
        if e.upper() == "BAL":
            return list(BAL_ALAKOK), False
        if e.upper() == "NEM_BAL":
            return list(BAL_ALAKOK), True
        return [e], False
    if isinstance(e, list):
        return [str(x) for x in e], False
    raise ForrasHiba(f"Értelmezhetetlen elosztás: {e!r}")


def _kez_fa(spec: dict, hely: str) -> dict:
    """Egy kéz-leírás -> feltétel-kifejezésfa."""
    gy: list[dict] = []
    if "pont" in spec:
        gy.append(_pont_fa(spec["pont"], {"t": "ERT", "kod": "HCP"}, hely))
    if "ap" in spec:
        gy.append(_pont_fa(spec["ap"], {"t": "ERT", "kod": _ap_kod(spec)}, hely))
    for nev, s in (spec.get("hossz") or {}).items():
        lo, hi = sav(s)
        gy += _sav_fa({"t": "SZIN", "szin": _szin_kod(str(nev))}, lo, hi)
    for r in spec.get("rel") or []:
        m = _REL_RE.match(str(r))
        if not m:
            raise ForrasHiba(f"{hely}: értelmezhetetlen színviszony: {r!r}")
        gy.append({"t": "OSSZE", "op": m.group(2),
                   "bal": {"t": "SZIN", "szin": _szin_kod(m.group(1))},
                   "jobb": {"t": "SZIN", "szin": _szin_kod(m.group(3))}})
    if "elosztas" in spec:
        alakok, tagad = _elosztas_alakok(spec["elosztas"])
        for a in alakok:
            if not re.fullmatch(r"\d{4}", a) or sum(map(int, a)) != 13:
                raise ForrasHiba(f"{hely}: hibás elosztás-alak: {a!r}")
        fa = {"t": "VAGY", "gy": [{"t": "ELOSZTAS", "alak": a,
                                   "rendezett": True} for a in alakok]}
        if len(alakok) == 1:
            fa = fa["gy"][0]
        gy.append({"t": "NEM", "gy": [fa]} if tagad else fa)
    for lap in spec.get("lapok") or []:          # ezek a lapok nála vannak
        gy.append(_osszevet({"t": "LAP", "lap": _lap(lap, hely)}, "=", 1))
    for lap in spec.get("nincs") or []:          # ezek NINCSENEK nála
        gy.append(_osszevet({"t": "LAP", "lap": _lap(lap, hely)}, "=", 0))
    for nev, s_ in (spec.get("fohonor") or {}).items():
        # a három felső honőrből (A, K, D) hány van a színben
        sz = _szin_kod(str(nev))                 # változóval is (M, A …)
        lo, hi = sav(s_)
        jel = (lambda e: f"{sz}:{e}") if sz.startswith("@") else (lambda e: sz + e)
        ossz = {"t": "OSSZEG", "gy": [{"t": "LAP", "lap": jel(e)}
                                      for e in "AKQ"]}
        gy += _sav_fa(ossz, lo, hi)
    for nev, s_ in (spec.get("figura") or {}).items():
        # figurapont EGY színben
        lo, hi = sav(s_)
        gy += _sav_fa({"t": "SZINFIG", "szin": _szin_kod(str(nev))}, lo, hi)
    if "minoseg" in spec:                        # jó / rossz lap
        m = str(spec["minoseg"])
        if m not in _MINOSEG:
            raise ForrasHiba(f"{hely}: a `minoseg` {sorted(_MINOSEG)} egyike legyen")
        op, v = _MINOSEG[m]
        gy.append({"t": "OSSZE", "bal": {"t": "ERT", "kod": "LAPMINOSEG"},
                   "op": op, "jobb": {"t": "SZAM", "v": v}})
    for nev, s_ in (spec.get("fedoutes") or {}).items():
        # fedőütés a megadott adu mellett (pl. {M: "2-3"}; kifejezes.fedoutes)
        lo, hi = sav(s_)
        gy += _sav_fa({"t": "FEDO", "adu": _szin_kod(str(nev))}, lo, hi)
    if spec.get("leghosszabb"):                  # ez (az egyik) leghosszabb színe
        gy.append({"t": "LEGHOSSZABB", "szin": _szin_kod(str(spec["leghosszabb"]))})
    if "maradek_vesztok" in spec:                # saját vesztők − a partner biztos fedői
        lo, hi = sav(spec["maradek_vesztok"])
        gy += _sav_fa({"t": "MARADEK_VESZTO"}, lo, hi)
    for mit, s_ in (spec.get("osszesen") or {}).items():
        # {ap: 25+}: a saját AP + a partner ígért MAXIMUMA (gémesély);
        # {ap_biztos: 25+}: + a partner ígért MINIMUMA (biztos gém)
        if mit not in ("ap", "pont", "ap_biztos", "pont_biztos"):
            raise ForrasHiba(f"{hely}: `osszesen` pl. {{ap: 25+}} / {{ap_biztos: 25+}}")
        lo, hi = sav(s_)
        n_ = {"t": "OSSZESEN", "mit": "AP" if mit.startswith("ap") else "PONT", "adu": "@M"}
        if mit.endswith("_biztos"):
            n_["biztos"] = True
        gy += _sav_fa(n_, lo, hi)
    for sz_, s_ in (spec.get("fit") or {}).items():
        # {A: 9+}: a saját hossz + a partner BIZTOSAN ígért minimuma (LoTT)
        lo, hi = sav(s_)
        gy += _sav_fa({"t": "FIT_HOSSZ", "szin": _szin_kod(str(sz_))}, lo, hi)
    if spec.get("onallo_adu"):                   # önállóan játszható adu (adu_esely.py)
        oa = spec["onallo_adu"]
        oa = oa if isinstance(oa, dict) else {oa: None}
        for sz_, k_ in oa.items():
            n_ = {"t": "ONALLO_ADU", "szin": _szin_kod(str(sz_))}
            if k_ is not None:
                n_["kuszob"] = float(k_)
            gy.append(n_)
    if "nanopont" in spec:                       # nano-pont: A = 3, K = 2, D = 1
        lo, hi = sav(spec["nanopont"])
        gy += _sav_fa({"t": "ERT", "kod": "NANO"}, lo, hi)
    if "kontroll" in spec:                       # kontroll: A = 2, K = 1
        lo, hi = sav(spec["kontroll"])
        gy += _sav_fa({"t": "ERT", "kod": "KONTROLL"}, lo, hi)
    if "kulcslapok" in spec:                     # pl. [0, 3]: 0 vagy 3 kulcslap
        ertekek = spec["kulcslapok"]
        ertekek = ertekek if isinstance(ertekek, list) else [ertekek]
        # `kulcs_adu: C`: a kulcslap-adu a licitből (pl. a 3NT utáni 4m
        # ORKC), nem a kényszertár megállapodott fitjéből
        k_adu = {"adu": str(spec["kulcs_adu"])} if spec.get("kulcs_adu") else {}
        if spec.get("kulcs_kizart"):             # EXCLUSION: e szín ásza nem számít
            k_adu["kizart"] = _szin_kod(str(spec["kulcs_kizart"]))
        agak = [_osszevet({"t": "KULCSLAP", **k_adu}, "=", int(v)) for v in ertekek]
        gy.append(agak[0] if len(agak) == 1 else {"t": "VAGY", "gy": agak})
    if "adu_dama" in spec:                       # true / false
        k_adu = {"adu": str(spec["kulcs_adu"])} if spec.get("kulcs_adu") else {}
        gy.append(_osszevet({"t": "ADU_DAMA", **k_adu}, "=", 1 if spec["adu_dama"] else 0))
    ig_spec = dict(spec.get("igeret") or {})
    hatar_ = ig_spec.pop("hatar", None)          # a határ helye a sávban (0-1)
    for mit, fele in ig_spec.items():
        # a lap az eddig ÍGÉRT saját sáv alsó/felső felében (kényszertárból)
        if mit not in ("pont", "ap") or fele not in ("also", "felso", "max"):
            raise ForrasHiba(f"{hely}: `igeret` pl. {{ap: also}}, {{pont: felso}}, {{ap: max}}")
        n_ = {"t": "IGERET_FELE", "mit": "AP" if mit == "ap" else "PONT",
              "fele": fele, "adu": "@M"}
        if hatar_ is not None:
            n_["hatar"] = float(hatar_)
        gy.append(n_)
    kul = spec.get("kulonbozo") or []            # két színváltozó más-más szín
    for i, a_ in enumerate(kul):
        for b_ in kul[i + 1:]:
            gy.append({"t": "KULONBOZO", "a": _szin_kod(str(a_)), "b": _szin_kod(str(b_))})
    for nev in spec.get("mellekszin") or []:     # nem az adu (M) színe
        gy.append({"t": "KULONBOZO", "a": _szin_kod(str(nev)), "b": "@M"})
    for kulcs_, mod in (("licit_alatt", "alatt"), ("licit_felett", "felett"),
                        ("licit_gem", "pont")):
        v_ = spec.get(kulcs_)
        if v_ == "gem":                          # a megállapodott adu géméhez képest
            gy.append({"t": "LICIT_ALATT", "gem": True, "mod": mod})
        elif v_ == "otos":                       # az adu 5-ös szintje alatt
            gy.append({"t": "LICIT_ALATT", "gem": True, "mod": "otos_alatt"})
        elif v_ == "lezaras":                    # a GI szintje (3M / 4m) alatt
            gy.append({"t": "LICIT_ALATT", "gem": True, "mod": "lezaras_alatt"})
        elif isinstance(v_, dict) and "gem" in v_:   # {gem: A}: az A szín géme
            gy.append({"t": "LICIT_ALATT", "gem": True, "mod": mod,
                       "szin": _szin_kod(str(v_["gem"]))})
        elif isinstance(v_, dict) and "lezaras" in v_ and kulcs_ == "licit_alatt":
            # {lezaras: B}: a B színű GI szintje (3M / 4m) alatt
            gy.append({"t": "LICIT_ALATT", "gem": True, "mod": "lezaras_alatt",
                       "szin": _szin_kod(str(v_["lezaras"]))})
    if spec.get("kontrollok"):
        gy.append({"t": "KONTROLLOK"})
    for nev in spec.get("nem_adu") or []:
        gy.append({"t": "NEM_ADU", "szin": _szin_kod(str(nev))})
    for nev in spec.get("adu_szin") or []:
        gy.append({"t": "AZ_ADU", "szin": _szin_kod(str(nev))})
    if spec.get("nem_rkc"):
        gy.append({"t": "NEM_RKC"})
    if "szlem" in spec:
        if spec["szlem"] not in ("igen", "talan", "nem", "nem_kizart"):
            raise ForrasHiba(f"{hely}: `szlem` igen / talan / nem / nem_kizart legyen")
        gy.append({"t": "SZLEMJELLEG", "ertek": spec["szlem"]})
    if spec.get("ot_biztos"):
        # `ot_biztos: vesztok` — a vesztő-számítással is (a két kéz
        # vesztőinek összege legfeljebb 13: 24 − összeg >= 11 ütés)
        gy.append({"t": "OT_BIZTOS", "mod": "vesztok"} if spec["ot_biztos"] == "vesztok"
                  else {"t": "OT_BIZTOS"})
    if "licit_alatt" in spec and isinstance(spec["licit_alatt"], str) \
            and spec["licit_alatt"] not in ("gem", "lezaras", "otos"):     # pl. "4M"
        m_ = re.fullmatch(r"([1-7])(NT|\w+)", str(spec["licit_alatt"]))
        if not m_:
            raise ForrasHiba(f"{hely}: hibás `licit_alatt`: {spec['licit_alatt']!r} (pl. \"4M\")")
        gy.append({"t": "LICIT_ALATT", "szint": int(m_.group(1)),
                   "szin": "NT" if m_.group(2) == "NT" else _szin_kod(m_.group(2))})
    if "ketseg" in spec:                         # a partner rövid egy színben, amit nem fogok kétszeresen
        n_ = {"t": "KETSEG"}
        gy.append(n_ if spec["ketseg"] else {"t": "NEM", "gy": [n_]})
    if "korr_pont" in spec:                      # FP + hosszúsági pont − 0.5 × üres figura
        lo, hi = sav(spec["korr_pont"])
        gy += _sav_fa({"t": "KORR_PONT", "levonas": 0.5}, lo, hi)
    if "leghosszabb_partner_szin" in spec:       # a partner színei közül ebben vagyok a leghosszabb
        gy.append({"t": "LEGHOSSZABB_PARTNER_SZIN", "szin": _szin_kod(str(spec["leghosszabb_partner_szin"]))})
    for sz in spec.get("eros_fogas") or []:      # biztos fogás: ász, vagy kétszeres
        gy.append({"t": "EROS_FOGAS", "szin": _szin_kod(str(sz))})
    if "gem_eselytelen" in spec:                 # a gémforsz megszűnése (KENYSZER elv)
        v = spec["gem_eselytelen"]
        n_ = {"t": "GEM_ESELYTELEN"}
        if isinstance(v, dict):
            for kk in ("nemes_fit_min", "minor_gem_ero"):
                if kk in v:
                    n_[kk] = v[kk]
            v = True
        gy.append(n_ if v else {"t": "NEM", "gy": [n_]})
    if "help_fogas" in spec:                     # van fogásom a partner HELP-színében
        n_ = {"t": "HELP_FOGAS"}
        gy.append(n_ if spec["help_fogas"] else {"t": "NEM", "gy": [n_]})
    if "gyenge_fogas" in spec:                   # valamelyik ígért fogásom gyenge (nem A, nem kétszeres)
        n_ = {"t": "GYENGE_FOGAS"}
        gy.append(n_ if spec["gyenge_fogas"] else {"t": "NEM", "gy": [n_]})
    if "ures_figura" in spec:                    # üres D/B (A, K nélkül, <=3 lapos színben) száma
        lo, hi = sav(spec["ures_figura"])
        gy += _sav_fa({"t": "URES_FIGURA"}, lo, hi)
    if "vesztok" in spec:                        # vesztőütés az egész kézben (zónás is)
        gy.append(_pont_fa(spec["vesztok"], {"t": "VESZTO"}, hely))
    if "jatekutes" in spec:                      # játékütés (J_KLASSZIKUS), zónás is
        gy.append(_pont_fa(spec["jatekutes"], {"t": "ERT", "kod": "J_KLASSZIKUS"}, hely))
    if "gyorsutes" in spec:                      # gyorsütés (AK=2, AQ=1,5, A=1, KQ=1, Kx=0,5)
        gy.append(_pont_fa(spec["gyorsutes"], {"t": "ERT", "kod": "GYORSUTES"}, hely))
    if "gemeselyes" in spec:                     # gémesély (kifejezes.gemesely)
        n_ = {"t": "GEMESELY"}
        gy.append(n_ if spec["gemeselyes"] else {"t": "NEM", "gy": [n_]})
    if spec.get("splinter_tamogatas"):           # feltételezett 8 lapos nemes fit
        gy.append({"t": "SPLINTER_FIT"})
    if "misfit" in spec:                         # 0-1 lap a partner tudott 5+ lapos színében
        n_ = {"t": "MISFIT"}
        gy.append(n_ if spec["misfit"] else {"t": "NEM", "gy": [n_]})
    for nev, s_ in (spec.get("szin_vesztok") or {}).items():
        lo, hi = sav(s_)                         # vesztőütés egy színben
        gy += _sav_fa({"t": "VESZTO", "szin": _szin_kod(str(nev))}, lo, hi)
    if "fele_a_szinben" in spec:                 # a figurapont legalább fele ott
        sz = _szin_kod(str(spec["fele_a_szinben"]))
        # A szerkesztő (2026-10-05): a máshol elszórt ÜRES dáma/bubi (Dxx, Bxx,
        # Dx … ász és király nélkül) leértékelve számít — színenként 0,5-tel
        # kevesebb —, hogy a 4-5 pont a színben (Á, ÁB, KD) ne „üsse ki”
        # három Dxx vagy egy Kxx és két Bxx.
        gy.append({"t": "OSSZE", "bal": {"t": "SZINFIG", "szin": sz}, "op": ">=",
                   "jobb": {"t": "OSSZEG", "jelek": [-1], "gy": [
                       {"t": "ERT", "kod": "HCP", "szorzo": 0.5},
                       {"t": "URES_FIGURA", "szorzo": FELE_URES_LEVONAS * 0.5}]}})
    if "aszok" in spec:                          # az ászok száma
        lo, hi = sav(spec["aszok"])
        gy += _sav_fa({"t": "OSSZEG", "gy": [{"t": "LAP", "lap": sz + "A"}
                                             for sz in SZINEK]}, lo, hi)
    for sz in spec.get("fogas") or []:
        gy.append(_fogas_fa(str(sz), hely))
    if "fogas_maradek" in spec:                  # fogás minden még le nem fedett színben
        v = spec["fogas_maradek"]
        n_ = {"t": "FOGAS_MARADEK"}
        if isinstance(v, dict):
            n_["termeszetes"] = v.get("termeszetes", True)
            v = True
        gy.append(n_ if v else {"t": "NEM", "gy": [n_]})
    if "nincs_fit" in spec:                      # színtalálkozás nincs (sehol min+ lap)
        v = spec["nincs_fit"]
        if isinstance(v, dict) and set(v) - {"sablon"}:
            n_ = {"t": "NINCS_FIT", "min": v.get("min", 8)}
            if "szinek" in v:
                n_["szinek"] = v["szinek"]
        else:
            n_ = {"t": "NINCS_FIT", "min": 8 if v is True else v}
        gy.append(n_)
    for sz in spec.get("nincs_fogas") or []:
        gy.append({"t": "NEM", "gy": [_fogas_fa(str(sz), hely)]})
    if "szkor" in spec:
        sz = str(spec["szkor"])
        if sz not in SZKOROK:
            raise ForrasHiba(f"{hely}: a szkor A/M/S/O lehet, nem {sz!r}")
        gy.append({"t": "SZKOR", "ertek": sz})
    if "vagy" in spec:
        agak = spec["vagy"]
        if not isinstance(agak, list) or not agak:
            raise ForrasHiba(f"{hely}: a `vagy` nem üres lista legyen")
        gy.append({"t": "VAGY", "gy": [_kez_fa(a, hely) for a in agak]})
    if spec.get("feltetel"):
        gy.append(spec["feltetel"])
    return _es(gy)


def _param_csp(ertek: dict) -> dict:
    """{param: KOD, alap: 10, eltolas: -1} -> PARAM csomópont (alapértékkel)."""
    n = {"t": "PARAM", "kod": str(ertek["param"])}
    if "alap" in ertek:
        n["alap"] = float(ertek["alap"])
    if ertek.get("eltolas"):
        n["eltolas"] = float(ertek["eltolas"])
    return n


def _pont_fa(ertek, ert: dict, hely: str) -> dict:
    """
    Pontsáv, vagy zónánként: {O: "8+", A: "9+", M: "10+", S: "11+"}, vagy
    PARAMÉTERREL (2026-10-02): {param: SZABAD_LICIT_MIN, alap: 10} = legalább
    a paraméter értéke (rendszer / pár szerint állítható; `eltolas: -1`:
    eggyel kevesebb).
    """
    if isinstance(ertek, dict) and "param" in ertek:
        return {"t": "OSSZE", "op": ">=", "bal": ert, "jobb": _param_csp(ertek)}
    if isinstance(ertek, dict):
        agak = []
        for sz, s_ in ertek.items():
            if str(sz) not in SZKOROK:
                raise ForrasHiba(f"{hely}: zónás pontsávban a kulcs A/M/S/O, "
                                 f"nem {sz!r}")
            lo, hi = sav(s_)
            agak.append(_es([{"t": "SZKOR", "ertek": str(sz)}]
                            + _sav_fa(ert, lo, hi)))
        return agak[0] if len(agak) == 1 else {"t": "VAGY", "gy": agak}
    lo, hi = sav(ertek)
    return _es(_sav_fa(ert, lo, hi))


_ZONA_NEV = {"O": "ők bellben", "A": "senki", "M": "mindenki bellben",
             "S": "mi bellben"}


def _zonas_szoveg(ertek: dict, mit: str) -> str:
    return f"{mit} zónától függően: " + " · ".join(
        f"{v} ({_ZONA_NEV.get(str(k), k)})" for k, v in ertek.items())


def _tomor(feltetel: dict, kez: dict) -> str:
    """A feltétel emberi szövege; a zónás pontsáv tömören."""
    szoveg = leiras(feltetel)
    for kulcs, mit, ert in (("pont", "figurapont", {"t": "ERT", "kod": "HCP"}),
                            ("ap", "asztali pont", {"t": "ERT", "kod": _ap_kod(kez)})):
        if isinstance(kez.get(kulcs), dict) and "param" not in kez[kulcs]:
            hosszu = leiras(_pont_fa(kez[kulcs], ert, "?"))
            szoveg = szoveg.replace(hosszu, _zonas_szoveg(kez[kulcs], mit))
    # "pikk hossz >= 4 és pikk hossz <= 4" -> "pikk hossz = 4"
    # A/K/D darabszám egy színben (fohonor) -> "felső honőr (… színben)"
    szoveg = re.sub(r"nála van a (\S+) szín ásza \+ nála van a \1 szín királya \+ "
                    r"nála van a \1 szín dámája", r"felső honőr (\1 színben)", szoveg)
    szoveg = re.sub(r"nála van a\(z\) ([CDHS])A \+ nála van a\(z\) \1K \+ "
                    r"nála van a\(z\) \1Q",
                    lambda m_: f"felső honőr ({_SZIN_MAGYAR[m_.group(1)]} színben)", szoveg)
    for hosszu, rovid in _MINOSEG_SZOVEG.items():
        szoveg = szoveg.replace(hosszu, rovid)
    # a fogás négy ágú fája -> "fogás a kőrben" (2026-10-05: a szerkesztőben
    # olvashatatlan volt)
    szoveg = re.sub(
        r"\(nála van a\(z\) ([CDHS])A = 1 vagy \(nála van a\(z\) \1K = 1 és \S+ hossz >= 2\) "
        r"vagy \(nála van a\(z\) \1Q = 1 és \S+ hossz >= 3\) vagy \(nála van a\(z\) \1J = 1 "
        r"és \S+ hossz >= 4\)\)",
        lambda m_: f"fogás a {_SZIN_FOGAS[m_.group(1)]}", szoveg)
    szoveg = re.sub(
        r"\(nála van a (\{\w+\}) szín ásza = 1 vagy \(nála van a \1 szín királya = 1 és \1 hossz >= 2\) "
        r"vagy \(nála van a \1 szín dámája = 1 és \1 hossz >= 3\) vagy \(nála van a \1 szín bubija = 1 "
        r"és \1 hossz >= 4\)\)", r"fogás a \1 színben", szoveg)
    szoveg = re.sub(r"figurapont a (\S+) színben >= figurapont\*0\.5",
                    r"a figurapont legalább fele a \1 színben", szoveg)
    # "figurapont >= 11 és figurapont <= 11" -> "figurapont = 11"
    szoveg = re.sub(r"(\S+ hossz|figurapont|asztali pont|fedőütés \([^)]*\)"
                    r"|vesztőütés(?: a \S+ színben)?) >= "
                    r"(\d+(?:\.\d+)?) és \1 <= \2(?![\d.])",
                  r"\1 = \2", szoveg)
    # "fedőütés (…) >= 2 és fedőütés (…) <= 3" -> "fedőütés (…) 2-3"
    return re.sub(r"(asztali pont|fedőütés \([^)]*\)|felső honőr \([^)]*\)"
                  r"|vesztőütés(?: a \S+ színben)?) >= "
                  r"(\d+(?:\.\d+)?) és \1 <= "
                    r"(\d+(?:\.\d+)?)\b", r"\1 \2-\3", szoveg)


def _pont_hatarok(ertek) -> tuple[float | None, float | None]:
    """A jelentéshez: a zónás sávok uniója (a partner a zónát is látja,
    de a kényszertár egyelőre zóna nélkül számol — a tágabb sáv biztos)."""
    if isinstance(ertek, dict) and "param" in ertek:
        return _param_csp(ertek), None     # a jelentésben is a paraméter (helyzet.ertek)
    if isinstance(ertek, dict):
        savok = [sav(v) for v in ertek.values()]
        los = [lo for lo, _ in savok]
        his = [hi for _, hi in savok]
        return (None if None in los else min(los),
                None if None in his else max(his))
    return sav(ertek)


def _ap_kod(spec: dict) -> str:
    """Adupont: 4+ adunál 5-3-1, egyébként (3 adu) 3-2-1."""
    for s_ in (spec.get("hossz") or {}).values():
        lo, _ = sav(_zarojel_nelkul(s_))
        if lo is not None and lo >= 4:
            return "AP_531"
    return "AP_321"


_ZAROJEL_RE = re.compile(r"^\s*\((\d+)\)\s*(.+)$")


def _zarojel_nelkul(s_) -> str:
    """ "(4)5+" -> "5+" """
    m = _ZAROJEL_RE.match(str(s_))
    return m.group(2) if m else s_


# --- Jelentés ----------------------------------------------------------

def _kez_jelentes(spec: dict) -> dict:
    """
    Egy kéz-leírás ígérete. Csak az megy bele, ami BIZTOSAN következik
    (a kényszertár "mi lehet"): a `rel` és a nyers `feltetel` kimarad.
    """
    j: dict = {}
    if "pont" in spec or "ap" in spec:
        if "pont" in spec:
            lo, hi = _pont_hatarok(spec["pont"])
        else:                     # asztali pont: a figurapont legfeljebb ennyi
            lo, hi = None, _pont_hatarok(spec["ap"])[1]
        p = {}
        if lo is not None:
            p["min"] = lo if isinstance(lo, dict) else _szam(lo)
        if hi is not None:
            p["max"] = _szam(hi)
        if p:
            j["pont"] = p
    for _, s_ in (spec.get("fedoutes") or {}).items():   # a fedőütés is ígéret
        lo, hi = sav(s_)
        fd = {}
        if lo is not None:
            fd["min"] = _szam(lo)
        if hi is not None:
            fd["max"] = _szam(hi)
        if fd:
            j["fedo"] = fd
    if "ap" in spec:                  # az asztali pont-sáv maga is ígéret
        lo, hi = _pont_hatarok(spec["ap"])
        a = {}
        if lo is not None:
            a["min"] = _szam(lo)
        if hi is not None:
            a["max"] = _szam(hi)
        if a:
            j["ap"] = a
    hossz: dict = {}
    for nev, s in (spec.get("hossz") or {}).items():
        lo, hi = sav(s)
        kulcs = str(nev) if str(nev) in SZINEK else "@" + str(nev)
        h = {}
        if lo is not None:
            h["min"] = int(lo)
        if hi is not None:
            h["max"] = int(hi)
        if h:
            hossz[kulcs] = h
    if "elosztas" in spec:
        alakok, tagad = _elosztas_alakok(spec["elosztas"])
        if not tagad:
            lo = min(min(int(c) for c in a) for a in alakok)
            hi = max(max(int(c) for c in a) for a in alakok)
            for sz in SZINEK:
                h = hossz.setdefault(sz, {})
                h["min"] = max(h.get("min", 0), lo)
                h["max"] = min(h.get("max", 13), hi)
    if hossz:
        j["hossz"] = hossz
    if "vagy" in spec:
        agak = [_kez_jelentes(a) for a in spec["vagy"]]
        if agak and all(agak):
            j["vagy"] = agak
    return j


def _ha_fa(ha, hely: str) -> dict | None:
    if not ha:
        return None
    if not isinstance(ha, dict):
        raise ForrasHiba(f"{hely}: a `ha` szótár legyen")
    gy = []
    for k, v in ha.items():
        if k == "ules":
            gy.append({"t": "ULES", "ertek": v if isinstance(v, list) else [v]})
        elif k == "szkor":
            lista = v if isinstance(v, list) else [v]
            agak = [{"t": "SZKOR", "ertek": str(x)} for x in lista]
            gy.append(agak[0] if len(agak) == 1 else {"t": "VAGY", "gy": agak})
        elif k == "ag":
            gy.append({"t": "AG", "ertek": v})
        elif k == "adu":                   # megállapodott adu: nemes/minor/barmely/szín
            if v not in ("nemes", "minor", "barmely", "nincs") and v not in SZINEK:
                raise ForrasHiba(f"{hely}: `adu` nemes / minor / barmely / nincs / C D H S legyen")
            gy.append({"t": "ADU", "fajta": v})
        elif k == "gemforsz":              # gémforszban vagyunk-e
            # `volt`: volt gémforsz a vonalon (a kvázi gémforsz határától
            # függetlenül — pl. a gémforsz megszűnésének elve, KENYSZER)
            gy.append({"t": "GEMFORSZ", "ertek": True, "volt": True} if v == "volt"
                      else {"t": "GEMFORSZ", "ertek": bool(v)})
        elif k == "partner_gi":            # a partner utolsó licitje géminvit
            n = {"t": "PARTNER_GI"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "en_nyilatkoztam":       # licitáltam-e már (nem passzt)
            n = {"t": "NYILATKOZOTT", "ki": "en"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "partner_szin":          # a partner 4+ (vagy {A: 5}: 5+) lapot ígért
            parok = v.items() if isinstance(v, dict) else [(v, 4)]
            for sz_, db in parok:
                # biztos: a partner TUDOTTAN ígérte (a nyitott sáv nem elég)
                gy.append({"t": "IGERT", "ki": "p", "mit": "HOSSZ", "biztos": True,
                           "szin": _szin_kod(str(sz_)), "op": ">=", "v": int(db)})
        elif k == "en_igertem":            # én TUDOTTAN 4+ (vagy {B: 6}: 6+) lapot ígértem
            parok = v.items() if isinstance(v, dict) else [(v, 4)]
            for sz_, db in parok:
                gy.append({"t": "IGERT", "ki": "en", "mit": "HOSSZ", "biztos": True,
                           "szin": _szin_kod(str(sz_)), "op": ">=", "v": int(db)})
        elif k == "ellenfel_szin":         # az ellenfél TUDOTTAN 4+ (vagy {A: 5}: 5+) lapot ígért
            parok = v.items() if isinstance(v, dict) else [(v, 4)]
            for sz_, db in parok:
                gy.append({"t": "IGERT", "ki": "ok", "mit": "HOSSZ", "biztos": True,
                           "szin": _szin_kod(str(sz_)), "op": ">=", "v": int(db)})
        elif k == "negyedik_szin":         # a licit a negyedik szín (helyzet.py)
            n = {"t": "NEGYEDIK_SZIN"}
            if isinstance(v, dict) and "min_szint" in v:
                n["min_szint"] = int(v["min_szint"])
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "partner_negyedik":      # a partner utolsó licitje a negyedik szín
            n = {"t": "PARTNER_NEGYEDIK"}
            if isinstance(v, dict) and "szint" in v:   # {szint: 3}: ezen a szinten
                n["szint"] = int(v["szint"])
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "ugras":                 # a licit ugrás-e (nem a legolcsóbb szinten)
            n = {"t": "UGRAS"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "partner_ugrott":        # a partner utolsó licitje ugrás volt-e
            n = {"t": "PARTNER_UGROTT"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "partner_kulcslicitelt":  # a partner utolsó licitje kulcslicit volt-e
            n = {"t": "PARTNER_KULCSLICIT"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "eros_ugras":            # ugrás új színben második megszólalásként: erő
            n = {"t": "EROS_UGRAS"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "en_nyitottam":          # a menet első licitje az enyém volt
            n = {"t": "EN_NYITOTTAM"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "gyenge_ugras":          # a gyenge ugrás elve: 1 = egyszeres, 2 = dupla ugrás
            if v not in (1, 2, True):
                raise ForrasHiba(f"{hely}: `gyenge_ugras` 1 (egyszeres) vagy 2 (dupla ugrás) legyen")
            gy.append({"t": "GYENGE_UGRAS", "lepes": 1 if v is True else int(v)})
        elif k == "splinter":              # ugrás új színben a partner nemesének 3-as szintje fölé
            n = {"t": "SPLINTER_HELYZET"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k in ("minor_igerve", "minor_nem_igerve"):
            # a 3NT utáni 4m (MOHA_3NT_4M): a minort a vonalunk tudottan
            # 4+ lappal ígérte, VAGY a 3NT előtt licitálta (indirekt ígéret)
            sz_ = _szin_kod(str(v))
            n = {"t": "VAGY", "gy": [
                {"t": "IGERT", "ki": "p", "mit": "HOSSZ", "biztos": True,
                 "szin": sz_, "op": ">=", "v": 4},
                {"t": "IGERT", "ki": "en", "mit": "HOSSZ", "biztos": True,
                 "szin": sz_, "op": ">=", "v": 4},
                {"t": "MONDVA_3NT_ELOTT", "szin": sz_}]}
            gy.append(n if k == "minor_igerve" else {"t": "NEM", "gy": [n]})
        elif k == "en_mondtam":            # ezt a színt én már bemondtam
            gy.append({"t": "MONDVA", "ki": "en", "szin": _szin_kod(str(v))})
        elif k == "ellenfel_licitalt":     # az ellenfél mondott-e már nem-passz licitet
            n = {"t": "NYILATKOZOTT", "ki": "ok"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "partner_forszol":
            n = {"t": "PARTNER_FORSZOL"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "ellenfel_csalad":       # az ellenfél rendszercsaládja (game.systems)
            lista = v if isinstance(v, list) else [v]
            for c in lista:
                if str(c) not in CSALADOK:
                    raise ForrasHiba(f"{hely}: `ellenfel_csalad` {CSALADOK} egyike legyen")
            gy.append({"t": "ELLENFEL_CSALAD", "ertek": [str(c) for c in lista]})
        elif k == "ellenfel_pont":         # valamelyik ellenfél TUDOTTAN ennyit ígért
            lo, hi = sav(v)
            if lo is not None:
                gy.append({"t": "IGERT", "ki": "ok", "mit": "PONT", "biztos": True,
                           "op": ">=", "v": float(lo)})
            if hi is not None:
                gy.append({"t": "IGERT", "ki": "ok", "mit": "PONT", "biztos": True,
                           "op": "<=", "v": float(hi)})
        elif k == "legfeljebb":             # "4H" vagy paraméterkód
            gy.append({"t": "LICIT_LEGFELJEBB", "hatar": str(v)})
        elif k == "fogasmutatas":           # a FOGÁSMUTATÁS elv helyzete (helyzet.py)
            n = {"t": "FOGASMUTATAS"}
            if isinstance(v, dict):
                for kk in ("fit_min", "termeszetes", "fit_szinek", "mod"):
                    if kk in v:
                        n[kk] = v[kk]
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "csak_partner_fogas":     # a színt csak a partner fogás-ígérete fedi
            gy.append({"t": "CSAK_PARTNER_FOGAS", "szin": _szin_kod(str(v))})
        elif k == "kenyszerito_passz":      # kényszerítő passz helyzete: elso / masodik / barmely
            sz_ = "barmely" if v is True else str(v)
            if sz_ not in ("elso", "masodik", "barmely"):
                raise ForrasHiba(f"{hely}: `kenyszerito_passz` elso / masodik / barmely legyen")
            gy.append({"t": "KENYSZERITO_PASSZ", "szerep": sz_})
        elif k == "help_utan":              # a HELP után: {ki: p|en}
            ki_ = v if isinstance(v, str) else "p"
            gy.append({"t": "HELP_UTAN", "ki": ki_})
        elif k == "en_3_szinten":           # mondtam-e már színt a 3-as szinten (leírás megtörtént)
            n = {"t": "EN_3_SZINTEN"}
            gy.append(n if v else {"t": "NEM", "gy": [n]})
        elif k == "ellenfel_szine":         # az ellenfél színe (kimondva vagy kontrával ígérve)
            gy.append({"t": "ELLENFEL_SZINE", "szin": _szin_kod(str(v))})
        elif k == "partner_nem_mondta":     # ezt a színt a partner még nem mondta
            gy.append({"t": "NEM", "gy": [{"t": "MONDVA", "ki": "p", "szin": _szin_kod(str(v))}]})
        elif k == "nem_mondtam":            # ezt a színt én még nem mondtam
            gy.append({"t": "NEM", "gy": [{"t": "MONDVA", "ki": "en", "szin": _szin_kod(str(v))}]})
        elif k == "fogasmutatas_terulet":   # a fogásmutatás elv TERÜLETE (a kiváltáshoz)
            n = {"t": "FOGASMUTATAS", "terulet": True}
            if isinstance(v, dict):
                for kk in ("fit_min", "termeszetes", "fit_szinek"):
                    if kk in v:
                        n[kk] = v[kk]
            gy.append(n)
        elif k == "elv_kontextus":          # egy elv-példány érvényességi helyzete
            lista = v if isinstance(v, list) else [v]
            for m_ in lista:
                try:
                    minta_parse(minta_norm(str(m_)))
                except MintaHiba as e:
                    raise ForrasHiba(f"{hely}: hibás `elv_kontextus` minta: {e}") from e
            gy.append({"t": "ELV_KONTEXTUS", "mintak": [minta_norm(str(m_)) for m_ in lista]})
        elif k == "nyers":
            gy.append(v)
        else:
            raise ForrasHiba(f"{hely}: ismeretlen helyzeti kulcs: {k!r}")
    return _es(gy)


def _ha_szoveg(ha) -> str | None:
    """A `ha:` helyzeti feltétel emberi szövege ("3./4. kézben" …)."""
    if not ha or not isinstance(ha, dict):
        return None
    reszek = []
    for k, v in ha.items():
        if k == "ules":
            lista = v if isinstance(v, list) else [v]
            reszek.append("/".join(f"{x}." for x in lista) + " kézben")
        elif k == "szkor":
            lista = v if isinstance(v, list) else [v]
            reszek.append("zóna: " + " vagy ".join(_ZONA_NEV.get(str(x), str(x))
                                                   for x in lista))
        elif k == "ag":
            reszek.append(f"{str(v).lower()} ágon")
        elif k == "adu":
            reszek.append({"nemes": "megállapodott nemes adu mellett",
                           "minor": "megállapodott minor adu mellett",
                           "S": "megállapodott pikk adu mellett",
                           "H": "megállapodott kőr adu mellett",
                           "D": "megállapodott káró adu mellett",
                           "C": "megállapodott treff adu mellett",
                           "nincs": "még nincs megállapodott adu"}.get(
                               v, "megállapodott adu mellett"))
        elif k == "partner_gi":
            reszek.append("a partner géminvitet adott" if v else "a partner nem invitált")
        elif k == "en_nyilatkoztam":
            reszek.append("már licitáltam" if v else "még nem licitáltam")
        elif k == "partner_szin":
            parok = v.items() if isinstance(v, dict) else [(v, 4)]
            reszek += [f"a partner {db}+ lapot ígért: {_SZIN_MAGYAR.get(str(sz_), '{'+str(sz_)+'}')}"
                       for sz_, db in parok]
        elif k == "ellenfel_szin":
            parok = v.items() if isinstance(v, dict) else [(v, 4)]
            reszek += [f"az ellenfél {db}+ lapot ígért: {_SZIN_MAGYAR.get(str(sz_), '{'+str(sz_)+'}')}"
                       for sz_, db in parok]
        elif k == "ellenfel_licitalt":
            reszek.append("az ellenfél is licitált" if v else "az ellenfél még nem licitált")
        elif k == "negyedik_szin":
            reszek.append("a negyedik szín")
        elif k == "partner_negyedik":
            reszek.append("a partner a negyedik színt licitálta")
        elif k == "en_igertem":
            parok = v.items() if isinstance(v, dict) else [(v, 4)]
            reszek += [f"én {db}+ lapot ígértem: {_SZIN_MAGYAR.get(str(sz_), '{'+str(sz_)+'}')}"
                       for sz_, db in parok]
        elif k == "ugras":
            reszek.append("ugrással" if v else "nem ugrással")
        elif k == "partner_ugrott":
            reszek.append("a partner ugrott" if v else "a partner nem ugrott")
        elif k == "partner_kulcslicitelt":
            reszek.append("a partner kulcslicitet mondott" if v else "a partner nem mondott kulcslicitet")
        elif k == "eros_ugras":
            reszek.append("ugrás új színben második megszólalásként (erő)")
        elif k == "en_nyitottam":
            reszek.append("én nyitottam" if v else "nem én nyitottam")
        elif k == "gyenge_ugras":
            reszek.append(("dupla" if v == 2 else "egyszeres")
                          + " ugrás új színben, kényszer nélkül (gyenge ugrás-helyzet)")
        elif k == "splinter":
            reszek.append("ugrás új színben a partner nemese fölé (splinter-helyzet)")
        elif k == "en_mondtam":
            reszek.append(f"már mondtam: {_SZIN_MAGYAR.get(str(v), '{'+str(v)+'}')}")
        elif k == "minor_igerve":
            reszek.append(f"a {_SZIN_MAGYAR.get(str(v), str(v))} ígérve (4+ lap, vagy a 3NT előtt licitáltuk)")
        elif k == "minor_nem_igerve":
            reszek.append(f"a {_SZIN_MAGYAR.get(str(v), str(v))} nincs ígérve")
        elif k == "gemforsz":
            reszek.append("volt gémforsz" if v == "volt" else "gémforszban" if v else "nem gémforszban")
        elif k == "partner_forszol":
            reszek.append("a partner forszolt" if v else "a partner nem forszolt")
        elif k == "legfeljebb":
            reszek.append(f"legfeljebb {v} szintig")
        elif k == "fogasmutatas":
            mod = v.get("mod") if isinstance(v, dict) else None
            reszek.append({"lefedve": "fogásmutatás a 3NT felé, minden szín lefedve (gémforszban, "
                                      "színtalálkozás nélkül, 3NT alatt)",
                           "barmely": "fogásmutatás a 3NT felé (gémforszban, színtalálkozás "
                                      "nélkül, még 3NT alatt)",
                           "help": "negyedik szín, HELP (gémforszban, színtalálkozás nélkül, "
                                   "3NT alatt, az egyetlen le nem fedett színben)"}.get(
                mod, "fogásmutatás a 3NT felé (gémforszban, színtalálkozás nélkül, "
                     "3NT alatt, még le nem fedett színben)"))
        elif k == "csak_partner_fogas":
            reszek.append(f"a {_SZIN_MAGYAR.get(str(v), '{'+str(v)+'}')} színt csak a partner fogása fedi")
        elif k == "kenyszerito_passz":
            reszek.append({"elso": "kényszerítő passz helyzetében, elsőként",
                           "masodik": "a partner kényszerítő passza után"}.get(
                               str(v), "kényszerítő passz helyzetében"))
        elif k == "help_utan":
            reszek.append("a partner fogást kért (HELP)" if (v if isinstance(v, str) else "p") == "p"
                          else "fogást kértem (HELP), a partner felelt")
        elif k == "en_3_szinten":
            reszek.append("már mondtam színt a 3-as szinten" if v else "még nem mondtam színt a 3-as szinten")
        elif k == "ellenfel_szine":
            reszek.append(f"az ellenfél színe: {_SZIN_MAGYAR.get(str(v), '{'+str(v)+'}')}")
        elif k == "partner_nem_mondta":
            reszek.append(f"a partner még nem mondta: {_SZIN_MAGYAR.get(str(v), '{'+str(v)+'}')}")
        elif k == "nem_mondtam":
            reszek.append(f"még nem mondtam: {_SZIN_MAGYAR.get(str(v), '{'+str(v)+'}')}")
        elif k == "elv_kontextus":
            lista = v if isinstance(v, list) else [v]
            reszek.append(" / ".join(map(str, lista)) + " után")
        elif k == "fogasmutatas_terulet":
            reszek.append("gémforszban, színtalálkozás nélkül: új szín 3NT alatt "
                          "(a még le nem fedett színben), vagy szan 3NT-ig")
        elif k == "ellenfel_csalad":
            lista = v if isinstance(v, list) else [v]
            reszek.append("az ellenfél rendszere: " + " / ".join(map(str, lista)))
        elif k == "ellenfel_pont":
            reszek.append(f"az ellenfél {v} pontot ígért")
        elif k == "nyers":
            reszek.append(leiras(v))
    return " és ".join(reszek) or None


# --- Egy szabály -------------------------------------------------------

def _valaszt(spec: dict, kulcs: str, lehet: tuple, alap: str, hely: str) -> str:
    v = str(spec.get(kulcs, alap))
    if v not in lehet:
        raise ForrasHiba(f"{hely}: a `{kulcs}` értéke {lehet} egyike, nem {v!r}")
    return v


def szabalyok(spec: dict, seq: int, fejezet: str | None,
              fajl: str = "?") -> list[SzabalySor]:
    """
    Egy YAML-szabályból 1 vagy 2 sor:
      * `kihagy: true`           -> egy KIHAGYAS sor (módosított konvencióban;
                                    a régi neve `torol: true`);
      * zárójeles lapszám "(4)5+" -> a rendes sor (5+) ÉS a lehetőség sora
        (4 lap + a `lehetoseg:` feltétele; ha az nincs: MÉRLEGELŐ jelölt);
      * egyébként                -> egy sor.
    """
    if not isinstance(spec, dict) or "minta" not in spec:
        raise ForrasHiba(f"{fajl}: minden szabálynak kell `minta`: {spec!r}")
    # "1H (P) 1S" -> "1H-1S": így a kulcsa is azonos a kötőjeles párjáéval
    spec = {**spec, "minta": minta_norm(str(spec["minta"]))}
    hely = f"{fajl}: {spec['minta']}"
    if spec.get("kihagy") or spec.get("torol") or spec.get("kivalt"):
        return [_torles(spec, seq, fejezet, fajl)]
    if "lehetoseg" in spec and not isinstance(spec["lehetoseg"], dict):
        raise ForrasHiba(f"{hely}: a `lehetoseg` szótár legyen")
    zarojeles = {k: v for k, v in (spec.get("hossz") or {}).items()
                 if _ZAROJEL_RE.match(str(v))}
    pontos = {mezo: z for mezo in ("pont", "ap")
              if (z := _pont_zarojel(spec.get(mezo), hely))}
    if not zarojeles and not pontos:
        if spec.get("lehetoseg"):
            raise ForrasHiba(f"{hely}: `lehetoseg` csak zárójeles értékkel "
                             f"értelmes, pl. hossz: {{H: \"(4)5+\"}} vagy "
                             f"pont: \"8-10(11)\"")
        return [szabaly(spec, seq, fejezet, fajl)]
    if len(zarojeles) + len(pontos) > 1:
        raise ForrasHiba(f"{hely}: szabályonként egy zárójeles érték lehet")

    lh = dict(spec.get("lehetoseg") or {})
    # Van `lehetoseg:` -> a szabály dönt (`{}` = feltétel nélkül); nincs,
    # vagy `merlegelo: true` -> a mérlegelés dönti el (pl. "rossz 11 pont",
    # amíg nincs rá mérhető feltétel).
    van_feltetel = "lehetoseg" in spec and not lh.pop("merlegelo", False)
    alap_opt = {k: v for k, v in spec.items() if k not in ("lehetoseg",)}
    # változatok: (a lehetőség-sor eltérése, kulcs-utótag, "mivel", honnan)
    if zarojeles:
        (szin, ertek), = zarojeles.items()
        m = _ZAROJEL_RE.match(str(ertek))
        opcio, alap = int(m.group(1)), m.group(2)
        alap_lo, _ = sav(alap)
        if alap_lo is None or opcio >= alap_lo:
            raise ForrasHiba(f"{hely}: a zárójeles érték a rendes minimum alatt "
                             f"legyen: {ertek!r}")
        fo = dict(spec, hossz=dict(spec["hossz"], **{szin: alap}))
        hossz = dict(spec["hossz"])
        hossz[szin] = f"{opcio}-{int(alap_lo) - 1}"
        for k, v in (lh.pop("hossz", None) or {}).items():
            hossz[k] = v
        valtozatok = [({"hossz": hossz}, f"{szin}{opcio}", f"{opcio} lappal",
                       f"zárójeles lapszámából ({ertek}) keletkezett. A rendes sor "
                       f"az {alap} lapot fedi le; ez a {opcio} lapos esetet")]
    else:
        (mezo, (ertek, opciok, alap)), = pontos.items()
        fo = dict(spec, **{mezo: alap})
        nev, jel = (("pont", "P") if mezo == "pont" else ("asztali pont", "AP"))
        valtozatok = [({mezo: str(o)}, f"{jel}{o}", f"{o} {nev}tal",
                       f"zárójeles {nev}értékéből ({ertek}) keletkezett. A rendes "
                       f"sor a {alap} {nev}ot fedi le; ez a {o} {nev}os esetet")
                      for o in opciok]
    fo.pop("lehetoseg", None)
    sorok = [szabaly(fo, seq, fejezet, fajl)]

    if "ha" in lh:
        alap_opt["ha"] = dict(spec.get("ha") or {}, **lh.pop("ha"))
    kez_lh = {k: v for k, v in lh.items() if k in _KEZ_KULCSOK}
    for k in kez_lh:
        lh.pop(k)
    lh_magyarazat = lh.pop("magyarazat", None)
    lh_jegyzet = lh.pop("jegyzet", None)
    lh_prioritas = lh.pop("prioritas", None)
    if lh:
        raise ForrasHiba(f"{hely}: a `lehetoseg`-ben ismeretlen kulcs: {sorted(lh)}")
    for i, (elteres, utotag, mivel, mit) in enumerate(valtozatok):
        opt = dict(alap_opt, **elteres)
        opt.update(kez_lh)          # a lehetőség pontosítja (pl. csökkentett erő)
        if lh_magyarazat:
            opt["magyarazat"] = lh_magyarazat
        opt["jegyzet"] = lh_jegyzet or (
            f"LEHETŐSÉG-SOR — a „{spec['minta']}” szabály {mit}, "
            + ("a `lehetoseg:` feltételével." if van_feltetel else
               "feltétel nélkül — ezért MÉRLEGELŐ: nem a szabály dönt, hanem a "
               "mérlegelés.")
            + " Külön sor kell, mert más a feltétele és a prioritása.")
        opt["kulcs"] = str(spec.get("kulcs") or spec["minta"]).strip() + f"~{utotag}"
        opt["prioritas"] = int(lh_prioritas if lh_prioritas is not None
                               else int(spec.get("prioritas", ALAP_PRIORITAS)) - 1)
        if not van_feltetel:          # feltétel nélkül: a mérlegelés dönt
            opt["dontesi_mod"] = "MERLEGELO"
        opt["magyarazat"] = opt.get("magyarazat") or (
            f"{spec.get('magyarazat') or spec['minta']} — lehetőség: {mivel}")
        if "magyarazat" in spec and not lh_magyarazat:
            opt["magyarazat"] = f"{spec['magyarazat']} — lehetőség: {mivel}"
        sorok.append(szabaly(opt, seq + 5 + i, fejezet, fajl))
    return sorok


_SAV_ZAROJEL_RE = re.compile(
    r"^\s*(?:\((\d+)\))?\s*(\d[\d.\s+-]*?)\s*(?:\((\d+)\))?\s*$")


def _pont_zarojel(v, hely: str = "?") -> tuple | None:
    """
    Zárójeles pont- vagy asztali pontsáv: a zárójeles érték LEHETŐSÉG, nem a
    rendszer része; mindkét oldalon lehet.
      "(11)12-21" -> ("(11)12-21", [11], "12-21")
      "8-10(11)"  -> ("8-10(11)",  [11], "8-10")
      "(5)6(7)"   -> ("(5)6(7)",   [5, 7], "6")
    """
    if not isinstance(v, str) or "(" not in v:
        return None
    m = _SAV_ZAROJEL_RE.match(v)
    if not m or (m.group(1) is None and m.group(3) is None):
        raise ForrasHiba(f"{hely}: értelmezhetetlen zárójeles sáv: {v!r}")
    alap = m.group(2).strip()
    lo, hi = sav(alap)
    opciok = []
    if m.group(1) is not None:
        o = int(m.group(1))
        if lo is None or o >= lo:
            raise ForrasHiba(f"{hely}: a zárójeles érték a sáv alatt legyen: {v!r}")
        opciok.append(o)
    if m.group(3) is not None:
        o = int(m.group(3))
        if hi is None or o <= hi:
            raise ForrasHiba(f"{hely}: a zárójeles érték a sáv fölött legyen: {v!r}")
        opciok.append(o)
    return v, opciok, alap


def _torles(spec: dict, seq: int, fejezet: str | None, fajl: str) -> SzabalySor:
    minta_szoveg = minta_norm(str(spec["minta"]))
    hely = f"{fajl}: {minta_szoveg}"
    tobb = set(spec) - {"minta", "kulcs", "kihagy", "torol", "kivalt", "megjegyzes",
                        "magyarazat", "jegyzet"}
    if tobb:
        raise ForrasHiba(f"{hely}: a kihagyó sorban csak minta/kulcs/megjegyzes "
                         f"lehet, nem {sorted(tobb)}")
    try:
        m = minta_parse(minta_szoveg)
    except MintaHiba as e:
        raise ForrasHiba(f"{hely}: hibás minta: {e}") from e
    return SzabalySor(
        seq=seq, fejezet=fejezet, alfejezet=None, minta=minta_szoveg,
        kulcs=str(spec.get("kulcs") or minta_szoveg),
        specifikussag=YAML_SPECIFIKUSSAG, prioritas=0,
        feltetel={"t": "IGAZ"},
        feltetel_szoveg=("(ezt a konvenció kiváltja)" if spec.get("kivalt")
                         else "(kivéve ebből a változatból)"),
        jelentes={"kivalt": True} if spec.get("kivalt") else {}, ha_feltetel=None,
        magyarazat=spec.get("magyarazat") or (
            "Ezt a licitet ez a konvenció kiváltja" if spec.get("kivalt")
            else "Ebben a változatban nincs ilyen licit"),
        magyarazat_en=None, alert=False, forsz="NEM", elvaras="SEMMI",
        dontesi_mod="SORREND", szabaly_fajta="KIHAGYAS", ismeretlen=None,
        ag=m.ag, allapot=None, nyers_szoveg=None, forras_hely=hely)


def szabaly(spec: dict, seq: int, fejezet: str | None,
            fajl: str = "?") -> SzabalySor:
    if not isinstance(spec, dict) or "minta" not in spec:
        raise ForrasHiba(f"{fajl}: minden szabálynak kell `minta`: {spec!r}")
    minta_szoveg = minta_norm(str(spec["minta"]))
    hely = f"{fajl}: {minta_szoveg}"
    ismeretlen = set(spec) - _SZABALY_KULCSOK
    if ismeretlen:
        raise ForrasHiba(f"{hely}: ismeretlen kulcs(ok): {sorted(ismeretlen)}")
    for v in (spec.get("hossz") or {}).values():
        if _ZAROJEL_RE.match(str(v)):
            raise ForrasHiba(f"{hely}: zárójeles lapszám csak a `szabalyok()`-on át")
    if _pont_zarojel(spec.get("pont"), hely) or _pont_zarojel(spec.get("ap"), hely):
        raise ForrasHiba(f"{hely}: zárójeles pont csak a `szabalyok()`-on át")
    try:
        m = minta_parse(minta_szoveg)
    except MintaHiba as e:
        raise ForrasHiba(f"{hely}: hibás minta: {e}") from e

    kez = {k: v for k, v in spec.items() if k in _KEZ_KULCSOK}
    feltetel = _kez_fa(kez, hely)
    jelentes = _kez_jelentes(kez)
    if spec.get("tagad"):
        jelentes["tagad"] = list(spec["tagad"])
    forsz = _valaszt(spec, "forsz", FORSZOK, "NEM", hely)
    jelentes["forsz"] = forsz            # mindig van: így minden sor "ért"
    if spec.get("jelentes"):
        jelentes.update(spec["jelentes"])
    f_ = spec.get("folytatas")
    if f_:
        # "mint X után": {mint: "2NT", pont: 2} vagy csak "2NT"
        f_ = {"mint": f_} if isinstance(f_, str) else dict(f_)
        try:
            minta_parse(str(f_.get("mint")))
        except MintaHiba as e:
            raise ForrasHiba(f"{hely}: hibás `folytatas`: {e}") from e
        jelentes["folytatas"] = {"mint": str(f_["mint"]), "pont": float(f_.get("pont") or 0)}
    # GÉMINVIT és ELFOGADÁS: az elfogadott invit gémforszt teremt. Kulccsal
    # (`invit: true`, `elfogad: true`), vagy a szövegből: "invit" /
    # "géminvit" — de nem "szleminvit", "invit alatti", "legfeljebb invit",
    # és nem a válasz rá ("fogadja az invitet").
    _al = spec.get("alert")
    szoveg = f"{spec.get('magyarazat') or ''} {_al if isinstance(_al, str) else ''}".lower()
    gi = spec.get("invit")
    if gi is None:
        gi = bool(re.search(r"\b(gém)?invit\b", szoveg)) and not re.search(
            r"szleminvit|invit alatti|legfeljebb invit|max\.? invit", szoveg)
    if gi:
        jelentes["gi"] = True
    elf = spec.get("elfogad")
    if elf is None:
        elf = "fogadja az invitet" in szoveg and "nem fogadja" not in szoveg
    if elf:
        jelentes["elfogad"] = True
    if spec.get("alulrol"):
        # több illeszkedő licit közül a LEGOLCSÓBB (Bánky) — szándékos,
        # ezért az ellenőrző nem jelzi ütközésnek
        jelentes["alulrol"] = True

    alert = spec.get("alert", False)
    magyarazat = spec.get("magyarazat")
    if isinstance(alert, str):
        magyarazat = magyarazat or alert
        alert = True

    allapot = spec.get("allapot")
    if allapot is not None and allapot not in ALLAPOTOK:
        raise ForrasHiba(f"{hely}: az `allapot` {ALLAPOTOK} egyike legyen")

    jelzok = ismeretlen_jelzok(feltetel)
    return SzabalySor(
        seq=seq, fejezet=fejezet, alfejezet=spec.get("alfejezet"),
        minta=minta_szoveg, kulcs=str(spec.get("kulcs") or minta_szoveg),
        # A YAML-rendszerekben a PRIORITÁS dönt: a licitmotor rangsora
        # (specifikusság, prioritás), és a minta-specifikusság különböző
        # licitek között értelmetlen (egy konkrét "3C" mindig legyőzne egy
        # változós "3oM"-et). Ezért minden YAML-sor azonos specifikusságú.
        specifikussag=int(spec.get("specifikussag", YAML_SPECIFIKUSSAG)),
        prioritas=int(spec.get("prioritas", ALAP_PRIORITAS)),
        feltetel=feltetel, feltetel_szoveg=_tomor(feltetel, kez)[:1000],
        jelentes=jelentes, ha_feltetel=_ha_fa(spec.get("ha"), hely),
        ha_feltetel_szoveg=_ha_szoveg(spec.get("ha")),
        magyarazat=(str(magyarazat)[:500] if magyarazat else None),
        magyarazat_en=(str(spec["en"])[:500] if spec.get("en") else None),
        alert=bool(alert), forsz=forsz,
        elvaras=_valaszt(spec, "elvaras", ELVARASOK, "SEMMI", hely),
        dontesi_mod=_valaszt(spec, "dontesi_mod", DONTESI_MODOK, "SORREND", hely),
        szabaly_fajta=_valaszt(spec, "fajta", SZABALY_FAJTAK, "SZABALY", hely),
        ismeretlen=(",".join(sorted(jelzok))[:120] if jelzok else None),
        ag=m.ag, allapot=allapot,
        nyers_szoveg=spec.get("nyers"), forras_hely=hely,
        jegyzet=(str(spec["jegyzet"]).strip() if spec.get("jegyzet") else None))


# --- Fájlok és könyvtárak ---------------------------------------------

def _yaml():
    try:
        import yaml
    except ImportError as e:        # pragma: no cover
        raise ForrasHiba("A YAML-forráshoz kell a PyYAML: "
                         "pip install pyyaml") from e
    return yaml


def forras_dict(adat: dict, fajl: str = "?",
                gyujto: dict[str, RendszerForras] | None = None
                ) -> dict[str, RendszerForras]:
    """Egy betöltött YAML-dokumentum beolvasztása a gyűjtőbe."""
    gyujto = {} if gyujto is None else gyujto
    if not isinstance(adat, dict) or "rendszer" not in adat:
        raise ForrasHiba(f"{fajl}: hiányzik a `rendszer:` blokk")
    meta = adat["rendszer"]
    kod = str(meta.get("kod") or "").strip()
    if not re.fullmatch(r"[A-Z0-9_]{2,40}", kod):
        raise ForrasHiba(f"{fajl}: a rendszer kódja NAGYBETŰ/szám/_ legyen: {kod!r}")
    r = gyujto.setdefault(kod, RendszerForras(kod=kod))
    r.fajlok.append(fajl)
    for mezo in ("nev", "verzio", "leiras", "leiras_en", "nev_en", "forras",
                 "jegyzet"):
        if meta.get(mezo) and not getattr(r, mezo):
            setattr(r, mezo, str(meta[mezo]))
    if "fajta" in meta:
        fajta = REGI_FAJTAK.get(meta["fajta"], meta["fajta"])
        if fajta not in FAJTAK:
            raise ForrasHiba(f"{fajl}: a `fajta` {FAJTAK} egyike legyen")
        r.fajta = fajta
    if meta.get("tema"):
        r.tema = str(meta["tema"]).strip()[:120]
    if meta.get("alapja"):
        r.alapja = str(meta["alapja"]).strip()
        v = str(meta.get("viszony") or "MODOSITAS")
        if v not in VISZONYOK:
            raise ForrasHiba(f"{fajl}: a `viszony` {VISZONYOK} egyike legyen")
        r.viszony = v
    elif meta.get("viszony"):
        raise ForrasHiba(f"{fajl}: `viszony` csak `alapja` mellett értelmes")
    if "csalad" in meta:
        if meta["csalad"] in CSALAD_ALIAS:
            raise ForrasHiba(
                f"{fajl}: a(z) {meta['csalad']} nem rendszercsalád, hanem a(z) "
                f"{CSALAD_ALIAS[meta['csalad']]} család egyik rendszere — "
                f"`csalad: {CSALAD_ALIAS[meta['csalad']]}`")
        if meta["csalad"] not in CSALADOK:
            raise ForrasHiba(f"{fajl}: a `csalad` {CSALADOK} egyike legyen")
        r.csalad_megadva = True
        r.csalad = meta["csalad"]
    r.nev = r.nev or kod
    for k, v in (adat.get("parameterek") or {}).items():
        r.parameterek[str(k)] = str(v)
    if adat.get("kartya"):
        if not isinstance(adat["kartya"], dict):
            raise ForrasHiba(f"{fajl}: a `kartya` szótár legyen")
        r.kartya.update(adat["kartya"])
    if adat.get("jelzesek"):
        from ..motor.jelzes import JelzesHiba, profil_kod
        try:
            r.jelzesek = {"rendszer": profil_kod(adat["jelzesek"], fajl)}
        except JelzesHiba as e:
            raise ForrasHiba(str(e)) from e
    if adat.get("sablon"):
        sb = adat["sablon"]
        if not isinstance(sb, dict) or not sb.get("szoveg"):
            raise ForrasHiba(f"{fajl}: a `sablon` szótár legyen, `szoveg`-gel")
        pars = sb.get("parameterek") or {}
        if not isinstance(pars, dict):
            raise ForrasHiba(f"{fajl}: a `sablon.parameterek` szótár legyen")
        for pk, pv in pars.items():
            if not re.fullmatch(r"[A-Z0-9_]{2,40}", str(pk)) or not isinstance(pv, dict) \
                    or "alap" not in pv:
                raise ForrasHiba(f"{fajl}: a sablon-paraméter NAGYBETŰS kód legyen, "
                                 f"`alap` értékkel: {pk!r}")
        r.sablon = {"szoveg": str(sb["szoveg"]).strip(),
                    "parameterek": {str(k): dict(v) for k, v in pars.items()}}
        if sb.get("terulet"):
            # az elv TERÜLETE: ahol él, ott a kártyán mögötte álló sorok nem
            # (a régi, sorokra bontott licitek) — helyzeti feltétel, a
            # most definiált licittel (_licit)
            r.sablon["terulet"] = _ha_fa(sb["terulet"], f"{fajl}: sablon.terulet")
            r.sablon["terulet_szoveg"] = _ha_szoveg(sb["terulet"])
    for h in adat.get("hivatkozasok") or []:
        hv = Hivatkozas(kod=h) if isinstance(h, str) else \
            Hivatkozas(kod=str(h["kod"]), aktiv=bool(h.get("aktiv", True)))
        if isinstance(h, dict) and (h.get("ervenyes") or h.get("parameterek")):
            erv = _lista(h.get("ervenyes"), fajl, "ervenyes")
            for m_ in erv:
                try:
                    minta_parse(minta_norm(str(m_)))
                except MintaHiba as e:
                    raise ForrasHiba(f"{fajl}: {hv.kod}: hibás `ervenyes` minta: {e}") from e
            hv.ervenyes = [minta_norm(str(m_)) for m_ in erv]
            if h.get("parameterek") and not isinstance(h["parameterek"], dict):
                raise ForrasHiba(f"{fajl}: {hv.kod}: a `parameterek` szótár legyen")
            hv.parameterek = dict(h.get("parameterek") or {})
        if isinstance(h, dict) and h.get("kivalt") is False:
            hv.kivalt = False
        if any(x.kod == hv.kod for x in r.hivatkozasok):
            raise ForrasHiba(f"{fajl}: kétszer hivatkozott rendszer: {hv.kod}")
        hv.seq = len(r.hivatkozasok) + 1
        r.hivatkozasok.append(hv)
        if isinstance(h, dict) and h.get("kiveve"):
            for k in _lista(h["kiveve"], fajl, "kiveve"):
                r.kizarasok.append(_kizaras(k, fajl))
    for k in _lista(adat.get("kizarasok"), fajl, "kizarasok"):
        r.kizarasok.append(_kizaras(k, fajl))

    seq = (max((s.seq for s in r.sorok), default=0) // 10 + 1) * 10
    for fej in adat.get("fejezetek") or []:
        nev = fej.get("fejezet")
        if fej.get("jegyzet"):
            r.fejezet_jegyzetek[nev or ""] = str(fej["jegyzet"]).strip()
        for spec in fej.get("szabalyok") or []:
            r.sorok.extend(szabalyok(spec, seq, nev, fajl))
            seq += 10
    for spec in adat.get("szabalyok") or []:
        r.sorok.extend(szabalyok(spec, seq, None, fajl))
        seq += 10
    return gyujto


def _lista(x, fajl: str, mezo: str) -> list:
    if not x:
        return []
    if isinstance(x, (str, dict)):
        return [x]
    if not isinstance(x, list):
        raise ForrasHiba(f"{fajl}: a `{mezo}` lista legyen")
    return x


def _kizaras(k, fajl: str) -> Kizaras:
    if isinstance(k, str):
        return Kizaras(kod=k.strip())
    if isinstance(k, dict) and k.get("kod"):
        fej = k.get("fejezet")
        return Kizaras(kod=str(k["kod"]).strip(),
                       fejezet=str(fej).strip() if fej else None)
    raise ForrasHiba(f"{fajl}: hibás kizárás: {k!r} — kód, vagy {{kod, fejezet}}")


def fajtak_ellenorzese(gyujto: dict[str, RendszerForras], hierarchia: bool = True) -> None:
    """
    Mit tartalmazhat az egyes fajta (019). Az összes fájl beolvasása UTÁN
    fut, mert egy rendszer több fájlból is állhat (a fajta az egyikben van).
    """
    for r in gyujto.values():
        _fajta_ellenorzes(r, ", ".join(r.fajlok[:1]) or "?")
    for r in gyujto.values():             # a példányosítás csak elv-sablonra
        for h in r.hivatkozasok:
            c = gyujto.get(h.kod)
            if h.beallitas and c is not None and c.fajta != "ELV_SABLON":
                raise ForrasHiba(f"{', '.join(r.fajlok[:1]) or '?'}: `ervenyes` / "
                                 f"`parameterek` csak elv-sablon hivatkozásán lehet "
                                 f"({r.kod} → {h.kod}: {c.fajta})")
            if c is not None and c.fajta == "ELV_SABLON":
                ismeretlen = set(h.parameterek) - set(c.sablon.get("parameterek") or {})
                if ismeretlen:
                    raise ForrasHiba(f"{', '.join(r.fajlok[:1]) or '?'}: {r.kod} → {h.kod}: "
                                     f"ismeretlen sablon-paraméter: {sorted(ismeretlen)}")
    for r in gyujto.values():             # a téma öröklődik az alapról
        if r.alapja and not r.tema and r.alapja in gyujto:
            r.tema = gyujto[r.alapja].tema
    if hierarchia:
        hierarchia_ellenorzes(gyujto)


def alaprendszerei(gyujto: dict[str, "RendszerForras"], kod: str) -> tuple[list[str], bool]:
    """
    Egy RENDSZER alaprendszerei: az aktív hivatkozásai közül az
    ALAPRENDSZER-ek, a RENDSZER és GYUJTEMENY hivatkozásokon át is (a
    konvenciókon át nem). Második elem: volt-e a YAML-ban nem szereplő
    (adatbázisból jövő) hivatkozás — akkor a hiány nem biztos.
    """
    talalt: list[str] = []
    ismeretlen = False
    latott: set[str] = set()

    def bejar(k: str):
        nonlocal ismeretlen
        if k in latott:
            return
        latott.add(k)
        for h in gyujto[k].hivatkozasok:
            if not h.aktiv:
                continue
            c = gyujto.get(h.kod)
            if c is None:
                ismeretlen = True
            elif c.fajta == "ALAPRENDSZER":
                if h.kod not in talalt:
                    talalt.append(h.kod)
            elif c.fajta in ("RENDSZER", "GYUJTEMENY"):
                bejar(h.kod)
    bejar(kod)
    return talalt, ismeretlen


def hierarchia_ellenorzes(gyujto: dict[str, "RendszerForras"]) -> None:
    """
    RENDSZERCSALÁD → ALAPRENDSZER → RENDSZER (2026-10-02):
      * az ALAPRENDSZER-nek és a RENDSZER-nek kötelező a `csalad`;
      * a RENDSZER pontosan EGY alaprendszerre épül (aktív hivatkozás,
        közvetlenül vagy egy másik rendszeren / gyűjteményen át), és a
        családja az alaprendszeréé.
    """
    for r in gyujto.values():
        hol = ", ".join(r.fajlok[:1]) or "?"
        if r.fajta in ("ALAPRENDSZER", "RENDSZER") and not r.csalad_megadva:
            raise ForrasHiba(f"{hol}: a(z) {r.kod} {r.fajta}: kötelező a `csalad` "
                             f"({', '.join(c for c in CSALADOK if c not in CSALAD_ALIAS)})")
        if r.fajta != "RENDSZER":
            continue
        alapok, ismeretlen = alaprendszerei(gyujto, r.kod)
        if len(alapok) > 1:
            raise ForrasHiba(f"{hol}: a(z) {r.kod} rendszer több alaprendszerre épül "
                             f"({', '.join(alapok)}) — pontosan egy kell")
        if not alapok and not ismeretlen:
            raise ForrasHiba(f"{hol}: a(z) {r.kod} rendszer nem hivatkozik "
                             f"alaprendszerre — pontosan egy kell")
        if alapok and gyujto[alapok[0]].csalad != r.csalad:
            raise ForrasHiba(f"{hol}: a(z) {r.kod} családja ({r.csalad}) nem egyezik az "
                             f"alaprendszeréével ({alapok[0]}: {gyujto[alapok[0]].csalad})")


def _fajta_ellenorzes(r: RendszerForras, fajl: str) -> None:
    if r.fajta in CSAK_HIVATKOZAS and r.sorok:
        raise ForrasHiba(
            f"{fajl}: a(z) {r.kod} {r.fajta}, csak hivatkozásokból állhat — "
            f"a saját szabályait tedd egy konvencióba vagy alaprendszerbe")
    if r.kizarasok and r.fajta not in CSAK_HIVATKOZAS:
        raise ForrasHiba(
            f"{fajl}: kizárás csak RENDSZER-ben és GYUJTEMENY-ben lehet "
            f"({r.kod}: {r.fajta})")
    if r.fajta == "ELV_SABLON":
        if r.hivatkozasok:
            raise ForrasHiba(f"{fajl}: az elv-sablon ({r.kod}) nem hivatkozhat másra")
        if not r.sablon:
            raise ForrasHiba(f"{fajl}: az elv-sablonnak ({r.kod}) kell `sablon: {{szoveg: …}}`")
    elif r.sablon:
        raise ForrasHiba(f"{fajl}: `sablon` csak ELV_SABLON-nak lehet ({r.kod})")
    if r.fajta == "KONVENCIO" and r.hivatkozasok:
        raise ForrasHiba(f"{fajl}: a konvenció ({r.kod}) nem hivatkozhat "
                         f"másra — ha több konvenciót fog össze, legyen GYUJTEMENY")
    if r.tema and r.fajta != "KONVENCIO":
        raise ForrasHiba(f"{fajl}: `tema` csak konvenciónak lehet ({r.kod})")
    if r.alapja and r.fajta != "KONVENCIO":
        raise ForrasHiba(f"{fajl}: `alapja` csak konvenciónak lehet ({r.kod})")
    if r.alapja == r.kod:
        raise ForrasHiba(f"{fajl}: a konvenció nem lehet önmaga alapja")
    if r.fajta == "RENDSZERCSALAD" and (r.kod not in CSALADOK or r.csalad != r.kod):
        raise ForrasHiba(f"{fajl}: a rendszercsalád kódja egy `csalad` érték "
                         f"legyen {CSALADOK}, és a `csalad` önmaga ({r.kod})")
    if not r.alapja and any(s.szabaly_fajta == "KIHAGYAS"
                            and not (s.jelentes or {}).get("kivalt")
                            for s in r.sorok):
        raise ForrasHiba(f"{fajl}: `kihagy` (régen `torol`) csak módosított konvencióban "
                         f"(`alapja:`) lehet ({r.kod})")


def betolt(utak: list[str | Path]) -> dict[str, RendszerForras]:
    """Fájlok és/vagy könyvtárak (rekurzívan *.yaml) -> {kod: forrás}."""
    yaml = _yaml()
    fajlok: list[Path] = []
    for u in utak:
        p = Path(u)
        if p.is_dir():
            fajlok += sorted(p.rglob("*.yaml")) + sorted(p.rglob("*.yml"))
        else:
            fajlok.append(p)
    gyujto: dict[str, RendszerForras] = {}
    for f in fajlok:
        with open(f, encoding="utf-8") as fh:
            for dok in yaml.safe_load_all(fh):
                if dok:
                    forras_dict(dok, str(f), gyujto)
    fajtak_ellenorzese(gyujto)
    return gyujto


def import_sorrend(forrasok: dict[str, RendszerForras]) -> list[str]:
    """
    Topologikus sorrend: előbb a hivatkozott rendszerek (a HIVATKOZAS
    sorhoz kell az id-jük). Kör esetén hiba.
    """
    kesz: list[str] = []
    allapot: dict[str, int] = {}

    def bejar(kod: str, ut: list[str]):
        if allapot.get(kod) == 2:
            return
        if allapot.get(kod) == 1:
            raise ForrasHiba("Körkörös hivatkozás: " + " -> ".join(ut + [kod]))
        allapot[kod] = 1
        for h in forrasok[kod].hivatkozasok:
            if h.kod in forrasok:
                bejar(h.kod, ut + [kod])
        if forrasok[kod].alapja in forrasok:   # az alap előbb kell
            bejar(forrasok[kod].alapja, ut + [kod])
        for k in forrasok[kod].kizarasok:      # a KI sorhoz is kell az id
            if k.kod in forrasok:
                bejar(k.kod, ut + [kod])
        allapot[kod] = 2
        kesz.append(kod)

    for kod in sorted(forrasok):
        bejar(kod, [])
    return kesz
