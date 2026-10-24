"""
Jelentés-propagálás: a licitmenetből KÉNYSZERTÁR.

Ez a darab köti össze a licitrendszert a következtetéssel. Eddig a
motor annyit tudott, hogy egy szabály MIKOR licitálható (`feltetel`).
De a licit másik fele legalább ennyire fontos: ha elhangzott, MIT
TUDUNK MEG belőle — nemcsak a partnerről, hanem az ellenfelekről is,
ha ismerjük (vagy feltételezzük) a rendszerüket.

    1S  ->  a nyitó: 12-21 pont, 5+ pikk
    2C  ->  a közbeszóló: 8+ pont, 5+ treff
    X   ->  a válaszoló: 6+ pont, 4 kőr, tagadja a 4 pikket

A kényszertár "mi LEHET" — nem "mi valószínű". Ezért:

  * ha egy licitnek TÖBB lehetséges jelentése van (a szabálylista több
    sora illeszkedik), a kényszertárba a jelentések UNIÓJA megy, nem a
    metszete. Több lehetőség = GYENGÉBB kényszer, nem erősebb. Ez a
    leggyakoribb hiba az ilyen motorokban, és csendben rossz
    következtetésekhez vezet;
  * ha egyik szabály sem illeszkedik, a licit NEM SZŰKÍT semmit — és
    ezt megszámoljuk. A "hány licitet nem értettünk" szám a rendszer
    lefedettségének legőszintébb mérőszáma;
  * a passz nem nyilatkozat, de a passz UTÁN mondott licit igen, és a
    kényszertár emiatt ülésenként gyűlik, nem licitenként.

Az ágensprofil ("mi VALÓSZÍNŰ") erre ÉPÜL, nem ezt helyettesíti: a
kényszertár adja a lehetséges kezek halmazát, a profil súlyozza.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace

from ..domain import ULESEK, kovetkezo_ules
from .feloldas import Sor
from .alert_ertelmezes import alert_igeret, alert_szoveg
from .helyzet import Allas, Igeret
from .minta import (negyedik_kotes, alias_elozmenyek, aliasok_sorokbol, VALTOZOK, JELENTESEK, Minta, MintaHiba, Token, _szin_feloldas,
                    _token_illik, _token_parse, illeszkedik, kanonizal,
                    minta_parse)

# A `jelentes` JSON elfogadott kulcsai (a régi alak is megy)
_PONT_KULCSOK = ("pont", "hcp")
_HOSSZ_KULCSOK = ("hossz", "szinhossz")


class PropagalasHiba(ValueError):
    pass


# --- Egyetlen jelentés alkalmazása ------------------------------------

def _szam(v, paramtar, allas=None) -> float | None:
    """
    Szám, PARAMÉTERKÓD vagy HELYZETFÜGGŐ KIFEJEZÉS.

    A harmadik azért kell, mert az elvek küszöbe nem fix: "a
    szkórhelyzetnek és a magasságnak megfelelő erő". Ilyenkor a jelentés
    nem `{"min": 8}`, hanem egy kifejezésfa, amit a helyzet old fel.
    """
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        if allas is None:
            return None            # helyzet nélkül nem számolható
        from .helyzet import ertek as helyzet_ertek
        return helyzet_ertek(v, allas, paramtar)
    if paramtar is None:
        return None
    try:
        return float(paramtar.ertek(str(v)))
    except Exception:              # noqa: BLE001
        return None


def _szinkod(sz: str, kotesek: dict[str, str] | None) -> str | None:
    if not isinstance(sz, str):
        return None
    if sz.startswith("@"):
        from .minta import szin_kotesbol
        return szin_kotesbol(sz[1:], kotesek)
    return sz if sz in JELENTESEK else None


def alkalmaz(ig: Igeret, jelentes: dict,
             kotesek: dict[str, str] | None = None,
             paramtar=None, allas=None) -> Igeret:
    """
    Egy `jelentes` JSON beírása egy ígéretbe. Az ígéretet MÓDOSÍTJA és
    vissza is adja.

    Alak:
      {"pont":  {"min": 12, "max": "1NT_MAX"},
       "hossz": {"S": {"min": 5}, "@M": {"min": 4}},
       "tagad": ["NEMES4"],
       "forsz": "EGY_MENET"}

    A számok lehetnek PARAMÉTERKÓDOK — így a jelentés is adat marad, és
    a küszöbök egy helyen hangolhatók.
    """
    if not jelentes:
        return ig

    # ALTERNATÍVÁK: {"vagy": [{...}, {...}]}
    # A fésű cue-bidje például "gyenge VAGY gémforsz" — két diszjunkt
    # sáv. A kényszertár intervallumokból áll, ezért a köztük lévő LYUK
    # (az invit-sáv) elvész: az unió 0-40 lesz, nem "0-8 vagy 13+".
    # Ez ismert pontatlanság; a Propagalo megszámolja, hányszor fordul
    # elő, hogy tudjuk, mennyit veszítünk vele.
    alternativak = jelentes.get("vagy")
    if isinstance(alternativak, list) and alternativak:
        agak = [alkalmaz(deepcopy(ig), a, kotesek, paramtar, allas)
                for a in alternativak]
        egyesitett = egyesit(agak)
        egyesitett.nyilatkozott = True
        # a lejátszás mintavételének (2026-10-23): az ágak MEGMARADNAK — a kéznek
        # legalább egyet ki kell elégítenie (Michaels: pikk és treff VAGY káró)
        # (2026-10-24) csak valódi elágazásnál, és MÁSOLATTAL: egyetlen ágnál az
        # `egyesit` magát az ágat adja vissza — az önmagára hivatkozott (ciklus)
        egyesitett.alternativak = list(ig.alternativak) + ([deepcopy(agak)] if len(agak) > 1 else [])
        maradek = {k: v for k, v in jelentes.items() if k != "vagy"}
        return alkalmaz(egyesitett, maradek, kotesek, paramtar, allas) \
            if maradek else egyesitett

    for k in _PONT_KULCSOK:
        p = jelentes.get(k)
        if isinstance(p, dict):
            ig.szukit_pont(_szam(p.get("min"), paramtar, allas),
                           _szam(p.get("max"), paramtar, allas))

    if jelentes.get("fedo_plusz"):         # kulcslicit: +1 fedő (ász/király/rövidség)
        ig.fedo_plusz = float(jelentes["fedo_plusz"])
    for nyers_szin, sf in (jelentes.get("szin_fedo") or {}).items():
        # fedő egy színben: {"C": {"min": 1, "valoszinu": 2}}
        sz = _szinkod(nyers_szin, kotesek)
        if sz is None or not isinstance(sf, dict):
            continue
        lo = float(_szam(sf.get("min"), paramtar, allas) or 0)
        val = _szam(sf.get("valoszinu"), paramtar, allas)
        ig.szin_fedo[sz] = (lo, max(lo, float(val)) if val is not None else lo)
    f = jelentes.get("fedo")               # fedőütés-sáv
    if isinstance(f, dict):
        ig.szukit_fedo(_szam(f.get("min"), paramtar, allas),
                       _szam(f.get("max"), paramtar, allas))

    a = jelentes.get("ap")                 # asztali pont-sáv
    if isinstance(a, dict):
        ig.szukit_ap(_szam(a.get("min"), paramtar, allas),
                     _szam(a.get("max"), paramtar, allas))

    for k in _HOSSZ_KULCSOK:
        h = jelentes.get(k)
        if isinstance(h, dict):
            for nyers_szin, hatarok in h.items():
                sz = _szinkod(nyers_szin, kotesek)
                if sz is None or not isinstance(hatarok, dict):
                    continue
                lo = _szam(hatarok.get("min"), paramtar, allas)
                hi = _szam(hatarok.get("max"), paramtar, allas)
                ig.szukit_hossz(sz,
                                None if lo is None else int(lo),
                                None if hi is None else int(hi))

    for cimke in jelentes.get("tagad", []) or []:
        sz = _szinkod(str(cimke), kotesek)
        ig.tagad.add(sz if sz else str(cimke))

    if jelentes.get("forsz"):
        ig.forsz = str(jelentes["forsz"])
    if jelentes.get("gi"):
        ig.gi = True
    if jelentes.get("elfogad"):
        ig.elfogad = True
    for nyers_szin in jelentes.get("fogas") or []:   # fogás-ígéret (FOGASMUTATAS)
        sz = _szinkod(str(nyers_szin), kotesek)
        if sz:
            ig.fogas.add(sz)
    if jelentes.get("fogas_maradek") and allas is not None:
        # "fogás minden még le nem fedett színben" (a 3NT a fogásmutatás végén):
        # a licit ELŐTTI állásból számolva, a licitáló vonalának szemszögéből
        from .helyzet import SZINEK as _SZ
        fedett = allas.fedett_szinek("mi", bool(jelentes.get("fogas_termeszetes", True)))
        ig.fogas |= {sz for sz in _SZ if sz not in fedett}
    if jelentes.get("help"):               # negyedik szín: fogást kér ebben a színben
        hsz = _szinkod(str(jelentes["help"]), kotesek)
        if hsz:
            ig.help_szin = hsz
    if jelentes.get("gf_hatar"):           # kvázi gémforsz: eddig a licitig kötelez
        ig.gf_hatar = str(jelentes["gf_hatar"])
    kl = jelentes.get("kulcslap")          # kulcslap-válasz (a spirál kiindulópontja)
    if isinstance(kl, dict) and kl.get("adu"):
        sz = _szinkod(str(kl["adu"]), kotesek)
        if sz:
            ig.kulcslap = {"adu": sz, "ertek": [int(x) for x in kl.get("ertek") or []],
                           "dama": kl.get("dama")}
            if kl.get("kizart"):                   # exclusion: e szín ásza nélkül
                ig.kulcslap["kizart"] = _szinkod(str(kl["kizart"]), kotesek)

    return ig


def fogas_feltetelbol(fa) -> list[str]:
    """
    A kéz-feltétel FOGÁS-ágai (a YAML `fogas: [X]` négyágú fája: A / Kx /
    Dxx / Bxxx), csak az ÉS-láncon (ami biztosan teljesül): ["H", "@om"].
    Futás közben olvassuk ki — a tárolt `jelentes` nem változik, így a
    meglévő jóváhagyások sem (az import aláírása a jelentést is nézi).
    """
    ki: list[str] = []
    if not isinstance(fa, dict):
        return ki
    t = fa.get("t")
    if t == "ES":
        for g in fa.get("gy") or []:
            ki += fogas_feltetelbol(g)
    elif t == "VAGY":
        gy = fa.get("gy") or []
        if len(gy) == 4 and isinstance(gy[0], dict) and gy[0].get("t") == "OSSZE":
            lap = (gy[0].get("bal") or {}).get("lap")
            if isinstance(lap, str) and lap.endswith("A"):
                sz = lap[:-1]
                ki.append(sz[:-1] if sz.endswith(":") else sz)
    return ki


def egyesit(valtozatok: list[Igeret]) -> Igeret:
    """
    Több lehetséges jelentés UNIÓJA: a legtágabb, ami mindegyiket
    magában foglalja.

    Ez az episztemikusan helyes irány. Ha a licit jelenthet A-t vagy
    B-t, akkor MINDKETTŐ lehetséges, tehát a kényszernek mindkettőt
    engednie kell. A metszet csak akkor volna jó, ha a licit egyszerre
    ígérné A-t ÉS B-t.
    """
    if not valtozatok:
        return Igeret()
    if len(valtozatok) == 1:
        return valtozatok[0]

    ki = Igeret(nyilatkozott=True)
    ki.pont_min = min(v.pont_min for v in valtozatok)
    ki.pont_max = max(v.pont_max for v in valtozatok)
    ki.ap_min = min(v.ap_min for v in valtozatok)
    ki.ap_max = max(v.ap_max for v in valtozatok)
    ki.fedo_min = min(v.fedo_min for v in valtozatok)
    ki.fedo_plusz = min(v.fedo_plusz for v in valtozatok)
    ki.fedo_max = max(v.fedo_max for v in valtozatok)
    for sz in set.intersection(*(set(v.szin_fedo) for v in valtozatok)):
        ki.szin_fedo[sz] = (min(v.szin_fedo[sz][0] for v in valtozatok),
                            min(v.szin_fedo[sz][1] for v in valtozatok))
    szinek = {sz for v in valtozatok
              for sz in list(v.hossz_min) + list(v.hossz_max)}
    for sz in szinek:
        also = min(v.hossz(sz)[0] for v in valtozatok)
        felso = max(v.hossz(sz)[1] for v in valtozatok)
        if also > 0:
            ki.hossz_min[sz] = also
        if felso < 13:
            ki.hossz_max[sz] = felso
    # Csak az marad tagadva, amit MINDEN változat tagad.
    ki.tagad = set.intersection(*(v.tagad for v in valtozatok)) \
        if all(v.tagad for v in valtozatok) else set()
    forszok = {v.forsz for v in valtozatok}
    ki.forsz = forszok.pop() if len(forszok) == 1 else "NEM"
    ki.gi = all(v.gi for v in valtozatok)
    ki.elfogad = all(v.elfogad for v in valtozatok)
    # kulcslap-válasz: ha a változatok közül, amelyek kulcslapot jelentenek,
    # mind ugyanazt (a többi általános elv, pl. kulcslicit-sor, nem mond róla
    # semmit — a kulcslap-válasz sora a specifikusabb)
    ki.fogas = set.intersection(*(set(v.fogas) for v in valtozatok))
    hs = {v.help_szin for v in valtozatok}
    ki.help_szin = hs.pop() if len(hs) == 1 else None
    gh = {v.gf_hatar for v in valtozatok}
    ki.gf_hatar = gh.pop() if len(gh) == 1 else None
    kl = [v.kulcslap for v in valtozatok if v.kulcslap is not None]
    if kl and all(k == kl[0] for k in kl):
        ki.kulcslap = dict(kl[0])
    return ki


# --- Jelentés a kéz-feltételből ---------------------------------------
#
# A LICREN-importból jött szabályoknak NINCS `jelentes` mezője, csak
# `feltetel`-e (mikor licitálható). A propagálás eddig kihagyta ezeket,
# ezért egy LICREN-rendszerben EGYETLEN licitet sem értett meg — a 1NT
# nyitást sem. Pedig a feltétel nagy része közvetlenül kiolvasható
# ígéret: "kőr > 4 és HCP >= 12" -> 5+ kőr, 12+ pont.
#
# Csak azt olvassuk ki, ami BIZTOSAN következik a feltételből (a
# kényszertár "mi lehet", nem "mi valószínű"): ÉS-ágak metszete, VAGY-ágak
# alternatívája, minden más (NEM, LEGALÁBB, szín-szín összevetés)
# kimarad — az csak gyengébb, nem hamis kényszert ad.

# Pontmetrikák, amelyek a figurapontnál SOSEM kisebbek (HCP + nemnegatív
# többlet). Ezeknél a felső korlát HCP-re is igaz, az alsó nem.
_HCP_FELETTI = {"P_HOSSZ", "P_HOSSZ5", "P_AP321", "P_AP531", "TOTAL_POINTS",
                "ZAR", "HCP_DIST", "AP_321", "AP_531"}
_HCP_PONTOS = {"HCP", "P_HCP"}
_MEGFORDIT = {">": "<", "<": ">", ">=": "<=", "<=": ">=", "=": "="}


def _konstans(csp):
    """Szám vagy paraméterkód; minden más None."""
    if not isinstance(csp, dict):
        return None
    if csp.get("t") == "SZAM":
        return float(csp["v"])
    if csp.get("t") == "PARAM":
        return str(csp["kod"])
    return None


def _valtozo(csp, metrika):
    """('hossz', szín) | ('pont', 'PONTOS'|'FELSO') | None"""
    if not isinstance(csp, dict):
        return None
    t = csp.get("t")
    if t == "SZIN" and isinstance(csp.get("szin"), str):
        return ("hossz", csp["szin"])      # "@M" is mehet: az alkalmaz köti
    if t == "ERT" and float(csp.get("szorzo", 1)) == 1:
        kod = str(csp.get("kod", ""))
        if kod.startswith("@"):
            kod = (metrika or {}).get(kod[1:], "")
        if kod in _HCP_PONTOS:
            return ("pont", "PONTOS")
        if kod in _HCP_FELETTI:
            return ("pont", "FELSO")
    return None


def _hatar_ir(ki: dict, valt, also=None, felso=None) -> None:
    fajta, mi = valt
    if fajta == "pont":
        if mi == "FELSO":
            also = None                    # HCP-re csak a felső igaz
        cel = ki.setdefault("pont", {})
    else:
        cel = ki.setdefault("hossz", {}).setdefault(mi, {})
    if also is not None:
        cel["min"] = also if "min" not in cel or not isinstance(
            cel["min"], (int, float)) or not isinstance(also, (int, float)) \
            else max(cel["min"], also)
    if felso is not None:
        cel["max"] = felso if "max" not in cel or not isinstance(
            cel["max"], (int, float)) or not isinstance(felso, (int, float)) \
            else min(cel["max"], felso)


def _osszevetes(ki: dict, valt, op: str, c) -> None:
    szam = isinstance(c, float)
    if op == ">":
        _hatar_ir(ki, valt, also=(int(c) + 1) if szam else c)
    elif op == ">=":
        _hatar_ir(ki, valt, also=c)
    elif op == "<":
        _hatar_ir(ki, valt, felso=(int(c) - 1 if c == int(c) else int(c))
                  if szam else c)
    elif op == "<=":
        _hatar_ir(ki, valt, felso=c)
    elif op == "=":
        _hatar_ir(ki, valt, also=c, felso=c)


def jelentes_feltetelbol(csp: dict | None, metrika: dict | None = None,
                         keszletek: dict | None = None,
                         _mely: int = 0) -> dict:
    """Egy kéz-feltétel fából a biztosan következő ígéret (`jelentes`)."""
    ki: dict = {}
    if not isinstance(csp, dict) or _mely > 20:
        return ki
    t = csp.get("t")

    if t == "ES":
        for g in csp.get("gy", []):
            r = jelentes_feltetelbol(g, metrika, keszletek, _mely + 1)
            for k in ("pont",):
                if k in r:
                    _hatar_ir(ki, ("pont", "PONTOS"),
                              r[k].get("min"), r[k].get("max"))
            for sz, h in r.get("hossz", {}).items():
                _hatar_ir(ki, ("hossz", sz), h.get("min"), h.get("max"))
            if "vagy" in r:
                ki.setdefault("_vagyok", []).append(r["vagy"])
        # Több VAGY-csoport ÉS-e: csak az elsőt visszük tovább (a többi
        # elhagyása gyengít, de nem hamisít).
        vagyok = ki.pop("_vagyok", None)
        if vagyok:
            ki["vagy"] = vagyok[0]
        return ki

    if t == "VAGY":
        agak = [jelentes_feltetelbol(g, metrika, keszletek, _mely + 1)
                for g in csp.get("gy", [])]
        # Ha bármelyik ág semmit nem ígér, a VAGY sem ígér semmit.
        if not agak or any(not a for a in agak):
            return {}
        return {"vagy": agak}

    if t == "KESZLET":
        kod = str(csp.get("kod", ""))
        if kod.startswith("@"):
            kod = (metrika or {}).get(kod[1:], "")
        fa = (keszletek or {}).get(kod)
        return jelentes_feltetelbol(fa, metrika, keszletek, _mely + 1) \
            if fa else {}

    if t == "OSSZE":
        op = csp.get("op")
        bal, jobb = csp.get("bal"), csp.get("jobb")
        valt, c = _valtozo(bal, metrika), _konstans(jobb)
        if valt is None or c is None:
            valt, c = _valtozo(jobb, metrika), _konstans(bal)
            op = _MEGFORDIT.get(op)
        if valt is not None and c is not None and op:
            _osszevetes(ki, valt, op, c)
        return ki

    if t == "INTERV":
        valt = _valtozo(csp.get("kif"), metrika)
        mn = csp.get("min")
        mx = csp.get("max")
        mn = _konstans(mn) if isinstance(mn, dict) else \
            (float(mn) if mn is not None else None)
        mx = _konstans(mx) if isinstance(mx, dict) else \
            (float(mx) if mx is not None else None)
        if valt is not None:
            _hatar_ir(ki, valt, also=mn, felso=mx)
        return ki

    return ki                               # NEM, LEGALABB, ...: nincs biztos


# --- A menet végigolvasása --------------------------------------------

@dataclass
class Eredmeny:
    """A propagálás kimenete — a kényszertár és a mérőszámai."""
    kenyszertar: dict[str, Igeret] = field(default_factory=dict)
    ertett: int = 0            # hány licitre találtunk szabályt
    nem_ertett: list[str] = field(default_factory=list)
    tobbertelmu: list[str] = field(default_factory=list)
    ellentmondas: list[str] = field(default_factory=list)
    alertbol: list[str] = field(default_factory=list)   # az alert szövegéből értett
    # licitenként (a menet indexe szerint): {"honnan", "igeret", "db"} —
    # a megértés-jelentéshez, ugyanabból az állapotból, amiből a tár épült
    licitenkent: dict = field(default_factory=dict)
    # KIZÁRÁSOS KÖVETKEZTETÉS (kovetkeztetes.py): VALÓSZÍNŰ tudás ülésenként,
    # és licitenként, mit zárt ki a licit — külön a biztos kényszertártól
    kovetkeztetett: dict = field(default_factory=dict)
    kovetkeztetes_licitenkent: dict = field(default_factory=dict)

    @property
    def lefedettseg(self) -> float:
        n = self.ertett + len(self.nem_ertett)
        return self.ertett / n if n else 0.0

    def osszefoglalo(self) -> str:
        s = (f"{self.ertett} licit értve, {len(self.nem_ertett)} nem "
             f"({self.lefedettseg:.0%})")
        if self.tobbertelmu:
            s += f", {len(self.tobbertelmu)} többértelmű"
        if self.ellentmondas:
            s += f", ELLENTMONDÁS: {', '.join(self.ellentmondas)}"
        return s


class Propagalo:
    """
    Egy rendszer szabálylistájából kényszertárat épít egy licitmenetre.

    Ugyanaz a szabálylista használható mindkét vonalra, vagy külön-külön
    (az ellenfélre a feltételezett rendszerükkel) — ezért a `licital`
    hívása ülésenként, a saját szemszögből történik.
    """

    def __init__(self, sorok: list[Sor], paramtar=None,
                 ellenfel: "Propagalo | None" = None,
                 sajat_vonal: str | None = None,
                 csaladok: dict[str, str | None] | None = None):
        """
        `ellenfel` + `sajat_vonal` (NS/EW): az ELLENFÉL licitjeit a saját
        rendszerük (vagy rendszercsaládjuk) szabályai szerint értjük — a
        kényszertár róluk így reális. Nélküle mindenkit a saját
        rendszerünk szerint értünk (a régi működés).
        `csaladok`: {"NS": család, "EW": család} — a helyzeti feltételekhez
        (`ha: {ellenfel_csalad: …}`).
        """
        self.paramtar = paramtar
        self.sorok = sorok                 # a kizárásos következtetéshez (licitmotor)
        self.ellenfel = ellenfel
        self.sajat_vonal = sajat_vonal
        self.csaladok = dict(csaladok or {})
        if ellenfel is not None:
            ellenfel.csaladok = self.csaladok
        # Két réteg, mint a Licitmotorban: az ELV csak akkor ad
        # jelentést, ha a licitre nincs konkrét megállapodásunk.
        self.szabalyok: list[tuple[Minta, Sor]] = []
        self.elvek: list[tuple[Minta, Sor]] = []
        self.hibas_mintak: list[str] = []
        # Hány szabály jelentését olvastuk ki a feltételből (nem volt
        # saját `jelentes`-e) — a LICREN-rendszereknél ez a zöm.
        self.szarmaztatott_jelentes = 0
        metrika = (paramtar.metrika_terkep()
                   if hasattr(paramtar, "metrika_terkep") else {})
        keszletek = getattr(paramtar, "keszletfak", None) or {}
        for s in sorok:
            if not s.minta:
                continue
            if not s.jelentes and s.feltetel:
                szarm = jelentes_feltetelbol(s.feltetel, metrika, keszletek)
                if szarm:
                    # Másolat: a feloldott Sor a gyorsítótárban él, nem
                    # írjuk felül a kanonikus (DB-ből jött) mezőt.
                    s = replace(s, jelentes=szarm)
                    self.szarmaztatott_jelentes += 1
            if not s.jelentes or s.jelentes.get("csak_dontes"):
                continue           # jelentés nélküli (vagy csak döntési) szabály nem propagál
            try:
                parolt = (minta_parse(s.minta), s)
            except MintaHiba as e:
                self.hibas_mintak.append(f"{s.minta}: {e}")
                continue
            elv = getattr(s, "szabaly_fajta", "SZABALY") == "ELV"
            (self.elvek if elv else self.szabalyok).append(parolt)
        self.aliasok = aliasok_sorokbol(sorok)

    def motor_ules(self, ules: str) -> "Propagalo":
        """Melyik vonal szabályai értik ennek az ülésnek a licitjeit."""
        from ..domain import vonal
        if self.ellenfel is not None and self.sajat_vonal \
                and vonal(ules) != self.sajat_vonal:
            return self.ellenfel
        return self

    def ertelmez(self, elozo_licitek: list[dict], ules: str, licit: str,
                 eddigi_tar: dict[str, Igeret] | None = None,
                 oszto: str | None = None, alert=None) -> tuple[list[Igeret], str | None]:
        """
        Egy licit lehetséges jelentései, és honnan tudjuk (2026-10-02):

          * a saját vonalunk licitje: a mi rendszerünk ("SAJAT");
          * az ellenfélé: (1) az ő ismert rendszerük / családjuk
            ("ELLENFEL"), (2) az asztalnál kapott magyarázat — az alert
            szövege ("ALERT"), (3) ha egyik sem mond semmit: a mi
            rendszerünk szerint, természetesen ("SAJAT").

        Az alert a saját rendszerünk ELŐTT jön: ha az ellenfél elmondta, mit
        jelent a licitjük, az erősebb, mint amit mi jelentenénk vele.
        """
        from ..domain import vonal
        ellenfele = bool(self.sajat_vonal) and vonal(ules) != self.sajat_vonal
        if not ellenfele:
            return self._jelentesek(elozo_licitek, ules, licit, eddigi_tar, oszto), "SAJAT"
        motor = self.motor_ules(ules)
        if motor is not self:
            v = motor._jelentesek(elozo_licitek, ules, licit, eddigi_tar, oszto)
            if v:
                return v, "ELLENFEL"
        ai = alert_igeret(alert_szoveg(alert), licit)
        if ai is not None:
            return [ai], "ALERT"
        v = self._jelentesek(elozo_licitek, ules, licit, eddigi_tar, oszto)
        return v, ("SAJAT" if v else None)

    # -- fő belépő --

    def kenyszertar(self, licitek: list[dict],
                    oszto: str | None = None,
                    beliallas: str = "NONE",
                    kovetkeztet_ulesek: set[str] | None = None,
                    kovetkeztetes_ms: int = 0) -> Eredmeny:
        """
        A teljes menet végigolvasása. Minden licitnél megnézzük, melyik
        szabály illeszkedik a LICITÁLÓ szemszögéből, és a jelentését
        beírjuk az ő ígéretébe.
        """
        er = Eredmeny(kenyszertar={u: Igeret() for u in ULESEK})
        snapshots: dict[int, tuple] = {}
        kovetkeztet = bool(kovetkeztet_ulesek) and kovetkeztetes_ms > 0

        for i, elem in enumerate(licitek):
            u = elem.get("ules")
            licit = str(elem.get("licit", "")).upper()
            if u not in ULESEK or not licit:
                continue
            if licit in ("P", "PASS"):
                if kovetkeztet:    # a passz sem ígér semmit — de KIZÁR
                    snapshots[i] = (deepcopy(er.kenyszertar), deepcopy(er.kenyszertar[u]))
                continue           # a passz nem nyilatkozat
            elotte = deepcopy(er.kenyszertar) if kovetkeztet else None
            # A jelentést a licit ELŐTTI állapotból olvassuk ("licitáltam-e
            # már" a mostanit még nem számolja); utána nyilatkozott.
            valtozatok, honnan = self.ertelmez(licitek[:i], u, licit,
                                               er.kenyszertar, oszto,
                                               elem.get("alert"))
            if honnan == "ALERT":
                er.alertbol.append(f"{u}:{licit}")
            er.kenyszertar[u].nyilatkozott = True
            er.licitenkent[i] = {"honnan": honnan, "db": len(valtozatok),
                                 "igeret": egyesit(valtozatok) if valtozatok else None}
            # SZÍN-e a színlicit (Moha, 2026-10-04): a kérdés, relé, transzfer,
            # lépcsőválasz formálisan szín, de nem ígér benne lapot. A licit
            # elemébe írjuk, hogy a későbbi helyzeti feltételek (pl. "a 3NT
            # előtt licitáltuk a minort") lássák; None = nem értettük.
            if licit[:1].isdigit() and licit[1:] in ("C", "D", "H", "S"):
                elem["szin_hossz_min"] = (egyesit(valtozatok).hossz(licit[1:])[0]
                                          if valtozatok else None)
            if not valtozatok:
                er.nem_ertett.append(f"{u}:{licit}")
                continue
            # KULCSLICIT volt-e (minden értelmezése +fedőt mutat): a partner
            # „udvariassági” kulcslicitjéhez (MOHA_SZLEM, 2026-10-21)
            if any(v.fedo_plusz > 0 for v in valtozatok):
                elem["kulcslicit"] = True
            er.ertett += 1
            if len(valtozatok) > 1:
                er.tobbertelmu.append(f"{u}:{licit}")

            uj = egyesit(valtozatok)
            # GÉMFORSZ az ELFOGADOTT invit után is: ha a partner utolsó
            # licitje géminvit volt, és erre gémet vagy afölött licitálunk,
            # kényszerítő licitet adunk, vagy a szabály maga mondja, hogy
            # elfogadja — onnan a vonal gémforszban van.
            partner = _partner_ules(u)
            if er.kenyszertar[partner].gi and _elfogadja(
                    licit, uj, _adu_most(er.kenyszertar, u, licitek[:i], oszto)):
                er.kenyszertar[u].gemforsz = True
                er.kenyszertar[partner].gemforsz = True
            _osszefesul(er.kenyszertar[u], uj)
            if len(valtozatok) > 1:
                # a változatok a saját (szabályon belüli `vagy:`) ágaikkal együtt
                er.kenyszertar[u].alternativak.append([deepcopy(x) for x in valtozatok])
            elif valtozatok and valtozatok[0].alternativak:
                er.kenyszertar[u].alternativak.extend(deepcopy(valtozatok[0].alternativak))
            if er.kenyszertar[u].ellentmondas:
                er.ellentmondas.append(f"{u}:{licit}")
            elif kovetkeztet:
                snapshots[i] = (elotte, deepcopy(er.kenyszertar[u]))

        if kovetkeztet and snapshots:
            from ..domain import vonal
            from .kovetkeztetes import kovetkeztetes_futtat
            ulesek = {u for u in kovetkeztet_ulesek
                      if self.sajat_vonal is None or vonal(u) == self.sajat_vonal
                      or self.ellenfel is not None}
            norm = [{"ules": e.get("ules"), "licit": str(e.get("licit", "")).upper()
                     .replace("PASS", "P")} for e in licitek]
            er.kovetkeztetett, er.kovetkeztetes_licitenkent = kovetkeztetes_futtat(
                self, norm, snapshots, ulesek, oszto, beliallas, kovetkeztetes_ms)
        return er

    # -- a licit lehetséges jelentései --

    def _jelentesek(self, elozo_licitek: list[dict], ules: str, licit: str,
                    eddigi_tar: dict[str, Igeret] | None = None,
                    oszto: str | None = None) -> list[Igeret]:
        return [ig for _, ig in self.jelentes_sorokkal(
            elozo_licitek, ules, licit, eddigi_tar, oszto)]

    def jelentes_sorokkal(self, elozo_licitek: list[dict], ules: str,
                          licit: str,
                          eddigi_tar: dict[str, Igeret] | None = None,
                          oszto: str | None = None) -> list[tuple]:
        """
        Mint a `_jelentesek`, de a jelentést adó SZABÁLYSORRAL együtt:
        [(Sor, Igeret), ...]. A licit-magyarázathoz kell (alert, szöveg,
        melyik konvencióból jön) — kéz nélkül, csak a megállapodásból.
        """
        """
        Minden szabály, aminek a mintája az eddigi menetre illeszkedik
        ÉS az utolsó tokenje épp ez a licit. A helyzeti feltétel
        (`ha_feltetel`) itt is szűr: ami a helyzetben nem volna
        licitálható, az nem is jelenthet semmit.
        """
        try:
            _, elozmeny = (kanonizal(elozo_licitek, ules)
                           if elozo_licitek else ("", []))
        except Exception:          # noqa: BLE001
            return []

        allas = Allas(ules=ules, licitek=list(elozo_licitek), oszto=oszto,
                      kenyszertar=deepcopy(eddigi_tar) if eddigi_tar else {},
                      csaladok=self.csaladok)
        # A fésű-kötések (I1/I2/V1/V2) az EDDIGI kényszertárból jönnek:
        # mire ez a licit elhangzik, az ellenfél már megmutatta a
        # színeit. Ezért a propagálás sorrendje számít.
        elo_kotes = allas.fesu_kotesek()

        # Előbb a konkrét réteg; az elvek csak akkor, ha az néma maradt.
        reteg = self._illeszkedok(self.szabalyok, elozmeny, elo_kotes,
                                  licit, allas)
        if not reteg and self.aliasok:
            # FOLYTATÁS "mint X után": az átirányított menet szabályai, a
            # ponthatárok visszatolásával (a licitáló valódi pontja)
            for uj_elozmeny, eltolas in alias_elozmenyek(self.aliasok, elozmeny):
                for sor, ig in self._illeszkedok(self.szabalyok, uj_elozmeny,
                                                 elo_kotes, licit, allas):
                    if eltolas:
                        if ig.pont_min > 0:
                            ig.pont_min = max(0.0, ig.pont_min - eltolas)
                        if ig.pont_max < 40:
                            ig.pont_max = max(0.0, ig.pont_max - eltolas)
                    reteg.append((sor, ig))
        if not reteg and elozo_licitek:
            # ZAVARTALAN MENET (2026-10-24): az ellenfél akciói nem zavartak
            # meg — a licit a páros menet szerinti jelentését tartja; a szan
            # fogást ígér az ellenfél licitált színében
            from .minta import zavartalan_menet
            zm = zavartalan_menet(elozo_licitek, ules, licit)
            if zm is not None:
                reteg = self._illeszkedok(self.szabalyok, zm[0], elo_kotes,
                                          licit, allas)
                if licit.upper().endswith("NT") and zm[1]:
                    for _, ig_ in reteg:
                        ig_.fogas |= set(zm[1])
        if not reteg:
            reteg = self._illeszkedok(self.elvek, elozmeny, elo_kotes,
                                      licit, allas)
        return reteg

    def _illeszkedok(self, reteg, elozmeny, elo_kotes, licit, allas):
        ki: list[tuple] = []
        defi = (definialo(self.szabalyok, elozmeny, elo_kotes, allas,
                          self.paramtar)
                if reteg is self.elvek else None)
        for minta, sor in reteg:
            tal = self._elozmeny_illesztes(minta, elozmeny, elo_kotes)
            if tal is None:
                continue
            # Az ELHANGZOTT licitet illesztjük a minta utolsó tokenjére,
            # nem fordítva. Ez azért fontos, mert a propagálásnál a licit
            # ISMERT, és megköti a minta változóját: az `1A` minta az
            # elhangzott `1S`-re illeszkedik A=S kötéssel. A fordított
            # irány (a mintából előállítani a licitet) kötetlen
            # változónál kudarcot vall — és ezzel némán elvesznek a
            # legegyszerűbb szabályok is.
            kotesek = self._licit_illik(minta.tokenek[-1], licit, tal,
                                        elozmeny, allas)
            if kotesek is not None:
                kotesek = negyedik_kotes(elozmeny, kotesek)
            if kotesek is None:
                continue
            if sor.ha_feltetel is not None:
                from .helyzet import kiertekel as helyzet_kiertekel
                # LÉTEZIK-KÖTÉS (2026-10-19, mint a Licitmotorban): a csak a
                # feltételben szereplő színváltozó „van olyan szín”-t jelent;
                # az első kötés, amelyre a helyzet nem hamis, a jelentésé is.
                from .licital import _hivatkozik
                from .minta import VALTOZOK
                szabad = [v for v in VALTOZOK if v not in kotesek
                          and (_hivatkozik(sor.ha_feltetel, v) or _hivatkozik(sor.feltetel, v))]
                jeloltek = [kotesek]
                for v in szabad:
                    jeloltek = [dict(k_, **{v: sz}) for k_ in jeloltek for sz in VALTOZOK[v]]
                talalt = None
                for k_ in jeloltek:
                    hk = dict(k_, _licit=licit)
                    if defi is not None:
                        hk["_definialt"] = defi
                    if helyzet_kiertekel(sor.ha_feltetel, allas, hk,
                                         self.paramtar) is not False:
                        talalt = k_
                        break
                if talalt is None:
                    continue
                kotesek = talalt
            if getattr(sor, "elnyomo", None):
                from .helyzet import kiertekel as helyzet_kiertekel
                if any(helyzet_kiertekel(e, allas, dict(kotesek, _licit=licit), self.paramtar) is True
                       for e in sor.elnyomo):
                    continue
            # A `mellekszin:` (A nem az adu) szerkezeti feltétel, nem a
            # kézről szól: a jelentésnél is szűr (az "1M-2M-+A" nem
            # jelentheti a 3M-et).
            if not _szerkezet_rendben(sor.feltetel, kotesek):
                continue
            ig_ = alkalmaz(Igeret(nyilatkozott=True), deepcopy(sor.jelentes),
                           kotesek, self.paramtar, allas)
            for nyers in fogas_feltetelbol(sor.feltetel):   # fogás-ígéret a feltételből
                sz_ = _szinkod(nyers, kotesek)
                if sz_:
                    ig_.fogas.add(sz_)
            if defi is not None and _gyenge_ugras_fa(sor.ha_feltetel):
                self._gyenge_ugras_plafon(ig_, licit, elozmeny, elo_kotes, allas)
            ki.append((sor, ig_))
        # Amit a licit ÍGÉR, azt a rendes szabályok mondják meg: a
        # mérlegelő lehetőség-sor (pl. "5 asztali ponttal is") nem tágítja
        # az ígéretet, ha van rendes jelentés is.
        # A TARTALÉK jelentés (pl. az emelés általános elve) csak akkor
        # számít, ha semmi konkrétabb nem értelmezte a licitet.
        konkret = [(s_, ig) for s_, ig in ki
                   if not (getattr(s_, "jelentes", None) or {}).get("tartalek")]
        ki = konkret or ki
        rendes = [(s_, ig) for s_, ig in ki
                  if getattr(s_, "dontesi_mod", "SORREND") != "MERLEGELO"]
        return rendes or ki

    def _gyenge_ugras_plafon(self, ig, licit, elozmeny, elo_kotes, allas):
        """
        A gyenge ugrás NEM erő: kevesebb, mint amennyi az alacsonyabb
        (definiált) licithez kell ugyanebben a színben. A pontplafon így a
        rendszerből jön, nem beégetett szám.
        """
        kov = allas.kovetkezo_licit(licit[1:])
        if kov is None:
            return
        also = f"{kov[0]}{kov[1]}"
        minimumok = [i.pont_min for _, i in self._illeszkedok(
            self.szabalyok, elozmeny, elo_kotes, also, allas) if i.pont_min > 0]
        if minimumok:
            ig.szukit_pont(maximum=min(minimumok) - 1)

    # -- segédek (a Licitmotor-ral azonos logika) --

    @staticmethod
    def _elozmeny_illesztes(minta: Minta, elozmeny: list[Token],
                            elo_kotes: dict[str, str] | None = None
                            ) -> dict | None:
        """
        Az `elo_kotes` előre megadott kötéseket visz be (I1/I2/V1/V2).
        Ha a minta indexelt változót használ, de nincs rá kötés, az
        illesztés elbukik — fésűzni csak ismert színek ellen lehet.
        """
        if not minta.tokenek:
            return None
        elozo = Minta(minta.nyers, minta.tokenek[:-1], minta.paroslicit,
                      {p for p in minta.barmennyi
                       if p < len(minta.tokenek) - 1})
        if not elozo.tokenek:
            if 0 in minta.barmennyi:       # ".. 4NT": bármilyen előzmény után
                return dict(elo_kotes or {})
            return dict(elo_kotes or {}) if not elozmeny else None
        tal = illeszkedik(elozo, elozmeny, elo_kotes)
        return tal.kotesek if tal else None

    @classmethod
    def _licit_illik(cls, t: Token, licit: str, kotesek: dict[str, str],
                     elozmeny: list[Token], allas=None
                     ) -> dict[str, str] | None:
        """
        Illik-e az elhangzott `licit` a minta utolsó tokenjére? Ha igen,
        visszaadja a BŐVÍTETT kötéseket (a változó megkötve), különben
        None.
        """
        if t.ellenfel or t.helyettesito:
            return None
        try:
            menet_t = _token_parse(licit, False)
        except MintaHiba:
            return None

        if t.szint == "+":
            # "a legkisebb szabad licit ebben a színben" — a színt a
            # kötés adja, a szintet az állás; mindkettőnek stimmelnie kell.
            kot = dict(kotesek)
            if t.szin in VALTOZOK and t.szin not in kot:
                # szabad változó ("..-+A"): a színt az elhangzott licit köti
                sz_ = licit[1:].upper()
                sz_ = "NT" if sz_ in ("N", "NT") else sz_
                if sz_ not in VALTOZOK[t.szin]:
                    return None
                kot[t.szin] = sz_
            var = cls._licit_feloldas(t, kot, elozmeny, allas)
            return kot if var == licit else None

        return _token_illik(t, menet_t, kotesek, elozmeny)

    @staticmethod
    def _licit_feloldas(t: Token, kotesek: dict[str, str],
                        elozmeny: list[Token], allas=None) -> str | None:
        if t.ellenfel or t.helyettesito:
            return None
        if t.hivas:
            return t.hivas
        if t.szint == "n":
            return None

        if t.szin in JELENTESEK:
            szin = t.szin
        else:
            lehet = _szin_feloldas(t, kotesek, elozmeny)
            if len(lehet) != 1:
                return None
            szin = next(iter(lehet))

        if t.szint == "+":
            # A LEGKISEBB SZABAD LICIT ebben a színben (fésű-cue-bid).
            if allas is None:
                return None
            kov = allas.kovetkezo_licit(szin)
            return None if kov is None else f"{kov[0]}{kov[1]}"
        return f"{t.szint}{szin}"



def _gyenge_ugras_fa(fa) -> bool:
    """Van-e a helyzeti feltételben GYENGE_UGRAS csomópont?"""
    if not isinstance(fa, dict):
        return False
    if fa.get("t") == "GYENGE_UGRAS":
        return True
    return any(_gyenge_ugras_fa(g) for g in fa.get("gy", []) or [])


def definialo(szabalyok, elozmeny, elo_kotes, allas, paramtar=None):
    """
    `hivas -> bool`: van-e a KONKRÉT rétegben (SZABALY/KIVETEL) olyan sor,
    amely ebben a helyzetben ezt a hívást definiálja (a minta illik, a
    helyzeti feltétel nem hamis). A gyenge ugrás elve kérdezi (2026-10-02,
    Moha): „mondhatnánk a színt alacsonyabban — és arra van szabály”, de
    maga az ugrás nincs konkrétan definiálva. Hívásonként gyorsítótáraz.
    """
    from .helyzet import kiertekel as helyzet_kiertekel
    tar: dict[str, bool] = {}

    def van(hivas: str) -> bool:
        if hivas in tar:
            return tar[hivas]
        tar[hivas] = False                     # rekurzió ellen
        ered = False
        for minta, sor in szabalyok:
            tal = Propagalo._elozmeny_illesztes(minta, elozmeny, elo_kotes)
            if tal is None:
                continue
            k = Propagalo._licit_illik(minta.tokenek[-1], hivas, tal,
                                       elozmeny, allas)
            if k is not None:
                k = negyedik_kotes(elozmeny, k)
            if k is None:
                continue
            hk = dict(k, _licit=hivas)
            if sor.ha_feltetel is not None and helyzet_kiertekel(
                    sor.ha_feltetel, allas, hk, paramtar) is False:
                continue
            if getattr(sor, "elnyomo", None) and any(
                    helyzet_kiertekel(e, allas, hk, paramtar) is True
                    for e in sor.elnyomo):
                continue
            ered = True
            break
        tar[hivas] = ered
        return ered
    return van

def _osszefesul(cel: Igeret, uj: Igeret) -> None:
    """
    Egy ülés korábbi és mostani ígéretének METSZETE. Itt a metszet a
    helyes: a játékosnak MINDEN licitje igaz kell legyen egyszerre.
    (A több lehetséges jelentés uniója egy szinttel lejjebb, az
    `egyesit`-ben történik.)
    """
    cel.nyilatkozott = True
    cel.szukit_pont(uj.pont_min if uj.pont_min > 0 else None,
                    uj.pont_max if uj.pont_max < 40 else None)
    cel.szukit_ap(uj.ap_min if uj.ap_min > 0 else None,
                  uj.ap_max if uj.ap_max < 40 else None)
    cel.szukit_fedo(uj.fedo_min if uj.fedo_min > 0 else None,
                    uj.fedo_max if uj.fedo_max < 99 else None)
    if uj.fedo_plusz:                  # a kulcslicitek fedői ÖSSZEADÓDNAK
        cel.fedo_min += uj.fedo_plusz
    for sz, (lo, val) in uj.szin_fedo.items():
        r_lo, r_val = cel.szin_fedo.get(sz, (0.0, 0.0))
        cel.szin_fedo[sz] = (max(r_lo, lo), max(r_val, val))
    for sz, v in uj.hossz_min.items():
        cel.szukit_hossz(sz, minimum=v)
    for sz, v in uj.hossz_max.items():
        cel.szukit_hossz(sz, maximum=v)
    cel.tagad |= uj.tagad
    cel.fogas |= uj.fogas              # a fogás-ígéretek összeadódnak
    if uj.gf_hatar:
        cel.gf_hatar = uj.gf_hatar
    cel.help_szin = uj.help_szin       # csak a legutóbbi licit HELP-je számít
    cel.forsz = uj.forsz
    cel.gi = uj.gi                     # az UTOLSÓ licit számít
    if uj.forsz == "GEMFORSZ":
        cel.gemforsz = True


def _partner_ules(u: str) -> str:
    return {"N": "S", "S": "N", "E": "W", "W": "E"}[u]


def _adu_most(tar: dict, ules: str, licitek: list[dict], oszto) -> str | None:
    """A megállapodott adu ebben a pillanatban (a kényszertár szerint)."""
    allas = Allas(ules=ules, licitek=list(licitek), oszto=oszto, kenyszertar=tar)
    return allas.adu()


def _elfogadja(licit: str, ig: Igeret, adu: str | None = None) -> bool:
    """
    Elfogadja-e ez a licit a partner géminvitjét (azaz gémforszt teremt)?
    A szerkesztő szabálya (2026-09-30):
      * gém vagy afölötti licit: elfogadja;
      * a saját összeemelt színünk a géminvit szintjén (3M, 4m): elutasítja;
      * ALATTA (ha van még licittér): további invit (F1), nem GF;
      * FÖLÖTTE, de gém alatt: GF.
    """
    from .licital import licit_rang
    if getattr(ig, "elfogad", False):
        return True
    if licit in ("P", "X", "XX"):
        return False
    if adu:
        gem = f"4{adu}" if adu in ("H", "S") else f"5{adu}"
        lezaras = f"3{adu}" if adu in ("H", "S") else f"4{adu}"
        if licit_rang(licit) >= licit_rang(gem) or licit == "3NT":
            return True
        if licit == lezaras:
            return False
        return licit_rang(licit) > licit_rang(lezaras)
    return licit == "3NT" or licit_rang(licit) >= licit_rang("4H")


def _szerkezet_rendben(fa, kotesek: dict) -> bool:
    """A feltételfa KULONBOZO csomópontjai (ÉS-ágon) teljesülnek-e a
    kötésekkel? Más csomópontot nem néz (azok a kézről szólnak)."""
    if not isinstance(fa, dict):
        return True
    t = fa.get("t")
    if t == "KULONBOZO":
        def sz(x):
            return kotesek.get(x[1:]) if isinstance(x, str) and x.startswith("@") else x
        a, b = sz(fa["a"]), sz(fa["b"])
        return a is None or b is None or a != b
    if t == "ES":
        return all(_szerkezet_rendben(g, kotesek) for g in fa.get("gy", []))
    return True


def allas_kenyszertarral(licitek: list[dict], ules: str,
                         propagalo: "Propagalo | None" = None,
                         beliallas: str = "NONE",
                         oszto: str | None = None) -> Allas:
    """
    Kényelmi belépő: kész `Allas`, feltöltött kényszertárral — ezt kapja
    a helyzeti feltétel kiértékelője és (később) az LLM-réteg promptja.
    """
    allas = Allas(ules=ules, beliallas=beliallas, licitek=list(licitek),
                  oszto=oszto)
    if propagalo is not None:
        er = propagalo.kenyszertar(licitek, oszto)
        allas.kenyszertar = er.kenyszertar
    return allas
