"""
Mintaillesztő motor.

A `doc/mintanyelv.md` szerinti mintákat illeszti valódi licitmenetekre.

A megoldás kulcsa: NEM közvetlenül a mintát illesztjük a licitmenetre,
hanem előbb a licitmenetet KANONIZÁLJUK ugyanabba a jelölésbe, amiben a
minták vannak. Onnantól az illesztés token-token összevetés, azonos
ábécén — sokkal kevesebb hibalehetőséggel.

    licitmenet + ülés  ->  "1NT-2C"      (pároslicit, ha nem volt közbeszólás)
                       ->  "1D (2C) 2H"  (kompetitív, ha volt)

Amit a motor tud:
  * változókötés (M, m, A, B, E) — ismételt változó UGYANAZT a színt jelenti
  * származtatott színek: oM (másik nemes), om (másik minor),
    Q (a negyedik szín: az egyetlen, amit még senki nem mondott)
  * helyettesítők kompetitív alakban: (*), (?), ..
  * specifikusság-alapú ütközésfeloldás
  * minta kibontása konkrét szekvenciákra (a licitmenet_index táblához)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import product

from ..domain import ULESEK, kovetkezo_ules, vonal

# A LICITÁLÁS HÁROM ÁGA. Nem külön rendszerek: ugyanannak a
# konvenciókártyának a három fejezete, és a minta alakja MÁR MEGMONDJA,
# melyikről van szó — csak eddig nem neveztük meg.
#
#   PAROS      mi kezdtünk, ők végig hallgatnak      "1NT-2C"
#   KUZDELMI   mi kezdtünk, ők belelicitáltak        "1D (2C) 2H"
#   VEDEKEZO   ŐK kezdtek                            "(1S) 2C"
#   BARMELYIK  a minta `..`-vel kezdődik: nem dönthető el, és nem is kell
#
# A gyakorlati haszna a MÉRÉS: a lefedettséget áganként külön kell nézni.
# Egy "17%-os lefedettség" semmit nem mond, ha kiderül, hogy a páros ág
# 40%, a küzdelmi 2%, a védekező 0%.
AGAK = ("PAROS", "KUZDELMI", "VEDEKEZO", "BARMELYIK")

SZINEK = ("C", "D", "H", "S")          # emelkedő rangsorban
NEMESEK = ("H", "S")
MINOROK = ("C", "D")
JELENTESEK = ("NT",) + SZINEK

# Változók és a lehetséges kötéseik
VALTOZOK = {"M": NEMESEK, "m": MINOROK,
            "A": SZINEK, "B": SZINEK, "E": SZINEK}
SZARMAZTATOTT = ("oM", "om", "Q")

# INDEXELT SZÍNVÁLTOZÓK — a fésű miatt (lásd doc/mintanyelv.md 0.4).
#
#   I1, I2, ...  az ELLENFÉL által ígért színek, emelkedő rangsorban
#   V1, V2, ...  a fennmaradó (SZABAD) színek, ugyanúgy rangsorban
#
# Ezek NEM szabadon kötődnek, mint az M vagy az A: a KÉNYSZERTÁRBÓL
# oldódnak fel, mielőtt az illesztés elindul (helyzet.fesu_kotesek).
# Ha az ellenfél licitje nem mutat konkrét színeket, a kötés elmarad,
# és a szabály egyszerűen nem illeszkedik — ami helyes: fésűzni csak
# ismert színek ellen lehet.
#
# Az INDEX a lényeg: az `I1`-re adott válasz a `V1`, az `I2`-re a `V2`.
# Két rendezett lista összefésülése — innen a konvenció neve.
INDEXELT = ("I", "V")
INDEX_RE = re.compile(r"^([IV])([1-4])$")
HELYETTESITOK = ("*", "?")

# A `N` a szan ELFOGADOTT rövidítése (a LICREN és a legtöbb magyar
# rendszerleírás így írja); belül mindig `NT`-re normalizáljuk.
# SZINTJELÖLÉSEK:
#   1..7  konkrét szint
#   n     bármilyen szint (illesztésnél megengedő, feloldásnál nem elég)
#   +     A LEGKISEBB SZABAD LICIT az adott színben. A fésű cue-bidje
#         ilyen: "menj fel az ellenfél színére" — hogy ez 3C vagy 4C,
#         az a licitállástól függ, nem a szabálytól.
TOKEN_RE = re.compile(
    r"^(?:(P|X|XX)|([1-7n+])(NT|N|[CDHS]|M|m|A|B|E|oM|om|Q|[IV][1-4]))$")


class MintaHiba(ValueError):
    """Hibás minta a tudásbázisban."""


# --- Token ------------------------------------------------------------

@dataclass(frozen=True)
class Token:
    """Egy licit a mintában vagy a kanonizált menetben."""
    hivas: str | None = None      # P / X / XX, ha nem szín-licit
    szint: str | None = None      # '1'..'7' vagy 'n'
    szin: str | None = None       # konkrét, változó vagy származtatott
    ellenfel: bool = False        # zárójelben volt-e
    helyettesito: str | None = None   # '*' vagy '?'

    def __str__(self) -> str:
        if self.helyettesito:
            mag = self.helyettesito
        elif self.hivas:
            mag = self.hivas
        else:
            mag = f"{self.szint}{self.szin}"
        return f"({mag})" if self.ellenfel else mag

    @property
    def konkret(self) -> bool:
        """Nem tartalmaz változót, származtatottat vagy helyettesítőt."""
        if self.helyettesito or self.szint in ("n", "+"):
            return False
        return self.szin is None or self.szin in JELENTESEK


def _token_parse(darab: str, ellenfel: bool) -> Token:
    d = darab.strip()
    if d in HELYETTESITOK:
        if not ellenfel:
            raise MintaHiba(f"A helyettesítő csak ellenfélnél állhat: {d!r}")
        return Token(ellenfel=True, helyettesito=d)
    m = TOKEN_RE.match(d)
    if not m:
        raise MintaHiba(f"Értelmezhetetlen token: {d!r}")
    hivas, szint, szin = m.group(1), m.group(2), m.group(3)
    if hivas:
        return Token(hivas=hivas, ellenfel=ellenfel)
    if szin == "N":
        szin = "NT"
    return Token(szint=szint, szin=szin, ellenfel=ellenfel)


# --- Minta ------------------------------------------------------------

@dataclass
class Minta:
    nyers: str
    tokenek: list[Token] = field(default_factory=list)
    paroslicit: bool = True
    barmennyi: set[int] = field(default_factory=set)  # a '..' pozíciói

    @property
    def specifikussag(self) -> int:
        """
        Konkrét szín 4, kötött változó 2, származtatott 2, helyettesítő 0.
        A hosszabb minta specifikusabb, ezért összegzünk.
        """
        p = 0
        for t in self.tokenek:
            if t.helyettesito:
                continue
            if t.hivas:
                p += 4
                continue
            p += 4 if t.szin in JELENTESEK else 2
            p += 2 if t.szint not in ("n", "+") else (1 if t.szint == "+" else 0)
        return p

    @property
    def ag(self) -> str:
        """
        A licitálás melyik ágára vonatkozik ez a minta? SZÁRMAZTATOTT:
        a minta alakjából adódik, nem külön adat.
        """
        if self.paroslicit:
            return "PAROS"
        if not self.tokenek:
            return "BARMELYIK"
        if 0 in self.barmennyi:
            return "BARMELYIK"      # `..`-vel kezdődik: az eleje ismeretlen
        return "VEDEKEZO" if self.tokenek[0].ellenfel else "KUZDELMI"

    def __str__(self) -> str:
        if self.paroslicit:
            return "-".join(str(t) for t in self.tokenek)
        return " ".join(str(t) for t in self.tokenek)


def minta_parse(s: str) -> Minta:
    """
    Minta beolvasása. A kötőjeles alak PÁROSLICIT (az ellenfelek végig
    passzolnak); a szóközös, zárójeles alak KOMPETITÍV.
    """
    s = (s or "").strip()
    if not s:
        raise MintaHiba("Üres minta")
    van_kotojel = "-" in s
    van_zarojel = "(" in s
    if van_kotojel and van_zarojel:
        raise MintaHiba(f"Kevert jelölés (kötőjel ÉS zárójel): {s!r}")

    if van_kotojel:
        tokenek = [_token_parse(d, False) for d in s.split("-") if d.strip()]
        return Minta(nyers=s, tokenek=tokenek, paroslicit=True)

    # Egyetlen saját licit (NYITÁS: "1NT", "2C"): pároslicit. Korábban
    # kötőjel híján kompetitívnek számított, ezért a nyitások a KUZDELMI
    # ágba kerültek (a LICREN_STAND "32 küzdelmi" sora is ez volt).
    darabok = s.split()
    if not van_zarojel and len(darabok) == 1 and darabok[0] != "..":
        return Minta(nyers=s, tokenek=[_token_parse(darabok[0], False)],
                     paroslicit=True)

    # Kompetitív alak
    tokenek: list[Token] = []
    barmennyi: set[int] = set()
    for darab in s.split():
        if darab == "..":
            barmennyi.add(len(tokenek))
            continue
        if darab.startswith("(") and darab.endswith(")"):
            tokenek.append(_token_parse(darab[1:-1], True))
        else:
            tokenek.append(_token_parse(darab, False))
    # "1H (P) 1S" UGYANAZ, mint "1H-1S": ha mi kezdtünk, és az ellenfél
    # minden licitje passz, az pároslicit. Kompetitív alakban hagyva
    # SOHA nem illeszkedne (a kanonizálás az ilyen licitmenetet kötőjeles
    # alakra hozza), és a kulcsa is eltérne a kötőjeles párjáétól.
    if (tokenek and not barmennyi and not tokenek[0].ellenfel
            and all(t.hivas == "P" for t in tokenek if t.ellenfel)):
        sajat = [t for t in tokenek if not t.ellenfel]
        return Minta(nyers=s, tokenek=sajat, paroslicit=True)
    return Minta(nyers=s, tokenek=tokenek, paroslicit=False,
                 barmennyi=barmennyi)


def minta_norm(s: str) -> str:
    """A minta egységes szöveges alakja: "1H (P) 1S" -> "1H-1S"."""
    s = (s or "").strip()
    try:
        m = minta_parse(s)
    except MintaHiba:
        return s
    return str(m) if m.paroslicit and "(" in s else s


# --- A licitmenet kanonizálása ---------------------------------------

def kanonizal(licitek: list[dict], ules: str,
              veg: int | None = None) -> tuple[str, list[Token]]:
    """
    Egy valódi licitmenet átírása a mintanyelv jelölésébe, az `ules`
    vonalának szemszögéből, a `veg` indexű licitig bezárólag.

    Visszaad: (szöveges alak, tokenek).

    Ha az ellenfél végig passzolt, PÁROSLICIT alakot ad (csak a mi
    licitjeink, kötőjellel). Ha bárhol megszólalt, KOMPETITÍV alakot
    (minden akció, az ellenfélé zárójelben).
    """
    veg = len(licitek) - 1 if veg is None else veg
    resz = licitek[:veg + 1]
    # A NYITÁS ELŐTTI PASSZOK nem részei a mintának: a mintanyelv az első
    # érdemi licittel kezdődik ("1H-1S", "(1C) X"). Ha bennhagyjuk őket,
    # a harmadik/negyedik kézből nyitás és a válasz passzolt partner
    # után SOHA nem illeszkedik ("Nyitás: csak akkor illik, ha még nem
    # licitáltunk" — a partner passza pedig "licitnek" látszana).
    # Az ülés (passzolt kéz) a teljes licitmenetből, az Allas-ból
    # továbbra is kiolvasható, a helyzeti feltételek onnan dolgoznak.
    elso = next((i for i, b in enumerate(resz)
                 if (b.get("licit") or "").upper() not in ("PASS", "P")),
                len(resz))
    resz = resz[elso:]
    mienk = vonal(ules)

    kompetitiv = any(vonal(b["ules"]) != mienk
                     and (b.get("licit") or "").upper() not in ("PASS", "P")
                     for b in resz)

    tokenek: list[Token] = []
    for b in resz:
        licit = (b.get("licit") or "").upper()
        ellenfel = vonal(b["ules"]) != mienk
        if licit in ("PASS", "P"):
            norm = "P"
        elif licit in ("X", "DBL", "*"):
            norm = "X"
        elif licit in ("XX", "RDBL", "**"):
            norm = "XX"
        else:
            norm = licit
        if not kompetitiv:
            # Pároslicit: az ellenfél passzai kimaradnak
            if ellenfel:
                continue
            tokenek.append(_token_parse(norm, False))
        else:
            tokenek.append(_token_parse(norm, ellenfel))

    szoveg = ("-".join(str(t) for t in tokenek) if not kompetitiv
              else " ".join(str(t) for t in tokenek))
    return szoveg, tokenek


def menet_ag(tokenek: list[Token]) -> str:
    """
    Egy KANONIZÁLT menet ága (a `Minta.ag` párja a valódi licitmenetre).
    Ezzel mérhető, hogy egy gyűjteményben hány helyzet esik melyik ágba —
    és hogy a rendszerünk melyiket fedi le.
    """
    if not tokenek:
        return "PAROS"                       # nyitás: még mi kezdünk
    if not any(t.ellenfel for t in tokenek):
        return "PAROS"
    return "VEDEKEZO" if tokenek[0].ellenfel else "KUZDELMI"


def szin_kotesbol(nev: str, kotesek: dict[str, str] | None) -> str | None:
    """
    Egy színváltozó konkrét színe a kötésekből — a SZÁRMAZTATOTTAKKAL
    együtt: `oM` a kötött nemes párja, `om` a kötött minoré. A
    kéz-feltétel és a jelentés is ezen keresztül oldja fel a `@oM`-et.
    """
    k = kotesek or {}
    if nev in k:
        return k[nev]
    if nev == "oM" and k.get("M") in NEMESEK:
        return NEMESEK[1] if k["M"] == NEMESEK[0] else NEMESEK[0]
    if nev == "om" and k.get("m") in MINOROK:
        return MINOROK[1] if k["m"] == MINOROK[0] else MINOROK[0]
    return None


# --- Illesztés --------------------------------------------------------

@dataclass
class Talalat:
    minta: Minta
    kotesek: dict[str, str]        # M -> 'H', A -> 'D', ...
    specifikussag: int

    def kotes_szoveg(self) -> str:
        return ",".join(f"{k}={v}" for k, v in sorted(self.kotesek.items()))


def _negyedik_szin(tokenek: list[Token], kotesek: dict[str, str]) -> str | None:
    """A `Q` értéke: az egyetlen szín, amit még senki nem mondott."""
    mondott = set()
    for t in tokenek:
        if t.szin in SZINEK:
            mondott.add(t.szin)
        elif t.szin in kotesek and kotesek[t.szin] in SZINEK:
            mondott.add(kotesek[t.szin])
    maradek = [sz for sz in SZINEK if sz not in mondott]
    return maradek[0] if len(maradek) == 1 else None


def _szin_feloldas(t: Token, kotesek: dict[str, str],
                   eddigi: list[Token]) -> set[str]:
    """Milyen konkrét színeket engedhet meg ez a token az adott kötések mellett?"""
    sz = t.szin
    if sz in JELENTESEK:
        return {sz}
    if sz in kotesek:
        return {kotesek[sz]}
    if sz in VALTOZOK:
        return set(VALTOZOK[sz])
    if sz == "oM":
        m = kotesek.get("M")
        return {NEMESEK[0] if m == NEMESEK[1] else NEMESEK[1]} if m else set()
    if sz == "om":
        m = kotesek.get("m")
        return {MINOROK[0] if m == MINOROK[1] else MINOROK[1]} if m else set()
    if sz == "Q":
        q = _negyedik_szin(eddigi, kotesek)
        return {q} if q else set()
    if isinstance(sz, str) and INDEX_RE.match(sz):
        # I1/I2/V1/V2: csak előre megadott kötésből oldható fel (fentebb
        # már kiderült volna). Kötés nélkül a szabály nem illeszkedik.
        return set()
    return set()


def _legolcsobb_szint(szin: str, eddigi: list[Token]) -> str:
    """A `szin` legolcsóbb szintje az eddigi utolsó színlicit fölött."""
    rend = ("C", "D", "H", "S", "NT")
    for t in reversed(eddigi):
        if t.szint and t.szint.isdigit() and t.szin in rend:
            szint = int(t.szint)
            return str(szint if rend.index(szin) > rend.index(t.szin) else szint + 1)
    return "1"


def _token_illik(minta_t: Token, menet_t: Token, kotesek: dict[str, str],
                 eddigi: list[Token]) -> dict[str, str] | None:
    """Illik-e a mintatoken a menettokenre? Visszaadja a BŐVÍTETT kötéseket."""
    if minta_t.ellenfel != menet_t.ellenfel:
        return None
    if minta_t.helyettesito == "*":
        return dict(kotesek)
    if minta_t.helyettesito == "?":
        return dict(kotesek) if menet_t.szin else None
    if minta_t.hivas or menet_t.hivas:
        return dict(kotesek) if minta_t.hivas == menet_t.hivas else None
    if minta_t.szint not in ("n", "+") and minta_t.szint != menet_t.szint:
        return None

    lehet = _szin_feloldas(minta_t, kotesek, eddigi)
    if menet_t.szin not in lehet:
        return None
    # "+": a LEGOLCSÓBB licit abban a színben — az előzményben is csak az
    # illik rá (különben pl. az 1M-2M-4M is "1M-2M-+A" volna, A = M).
    if minta_t.szint == "+" and menet_t.szint != _legolcsobb_szint(menet_t.szin, eddigi):
        return None

    uj = dict(kotesek)
    if minta_t.szin in VALTOZOK and minta_t.szin not in uj:
        uj[minta_t.szin] = menet_t.szin
    elif minta_t.szin == "Q" and "Q" not in uj:
        uj["Q"] = menet_t.szin            # a negyedik szín: a feltételnek is kell
    return uj


def negyedik_kotes(elozmeny: list[Token], kotesek: dict[str, str]) -> dict[str, str]:
    """
    A kötések a `Q`-val (a negyedik szín: amit az előzményben még senki
    nem mondott) — hogy a kéz-feltétel is hivatkozhasson rá (`fogas: [Q]`).
    """
    if "Q" in kotesek:
        return kotesek
    q = _negyedik_szin(elozmeny, kotesek)
    return dict(kotesek, Q=q) if q else kotesek


def illeszkedik(minta: Minta, menet_tokenek: list[Token],
                elo_kotes: dict[str, str] | None = None) -> Talalat | None:
    """
    Illik-e a minta a kanonizált licitmenetre?

    A minta a menet ELEJÉTŐL illeszkedik, és a VÉGÉIG kell tartania:
    a minta utolsó tokenje az a licit, amit a bejegyzés definiál.

    Az `elo_kotes` KÍVÜLRŐL hozott kötéseket visz be — ma az indexelt
    színváltozókat (I1/I2/V1/V2), amiket nem a minta köt meg, hanem a
    kényszertár: "az ellenfél által ígért színek rangsorban".
    """
    # Az ELV-minta (".."-tal kezdődik, ellenfél-token nélkül) a partner és
    # a saját licitjeiről szól: az ellenfél PASSZA közöttük átlátszó,
    # ahogy a pároslicitben is ("4S (P) 4NT" = "4S-4NT"). Így nem kell
    # minden elvet kétszer leírni.
    if 0 in minta.barmennyi and not any(t.ellenfel for t in minta.tokenek):
        menet_tokenek = [t for t in menet_tokenek
                         if not (t.ellenfel and t.hivas == "P")]
    if minta.paroslicit and any(t.ellenfel for t in menet_tokenek):
        return None
    if not minta.paroslicit and not any(t.ellenfel for t in menet_tokenek):
        # Kompetitív minta csak kompetitív menetre illik
        if any(t.ellenfel for t in minta.tokenek):
            return None

    def rekurziv(mi: int, li: int, kotesek: dict[str, str]):
        if mi == len(minta.tokenek):
            return kotesek if li == len(menet_tokenek) else None
        # '..' : tetszőleges számú akció kihagyása
        if mi in minta.barmennyi:
            for atugrott in range(0, len(menet_tokenek) - li + 1):
                jelolt = Minta(minta.nyers, minta.tokenek, minta.paroslicit,
                               {p for p in minta.barmennyi if p != mi})
                r = _folytat(jelolt, mi, li + atugrott, kotesek, menet_tokenek)
                if r is not None:
                    return r
            return None
        if li >= len(menet_tokenek):
            return None
        uj = _token_illik(minta.tokenek[mi], menet_tokenek[li], kotesek,
                          menet_tokenek[:li])
        if uj is None:
            return None
        return rekurziv(mi + 1, li + 1, uj)

    def _folytat(m: Minta, mi: int, li: int, kotesek, menet):
        if mi == len(m.tokenek):
            return kotesek if li == len(menet) else None
        if li >= len(menet):
            return None
        uj = _token_illik(m.tokenek[mi], menet[li], kotesek, menet[:li])
        if uj is None:
            return None
        return _folytat(m, mi + 1, li + 1, uj, menet)

    kotesek = rekurziv(0, 0, dict(elo_kotes or {}))
    if kotesek is None:
        return None
    return Talalat(minta, kotesek, minta.specifikussag)


def legjobb_talalat(mintak: list[Minta], menet_tokenek: list[Token],
                    prioritasok: dict[str, int] | None = None
                    ) -> tuple[Talalat | None, list[Talalat]]:
    """
    Az összes illeszkedő minta közül a LEGSPECIFIKUSABB nyer.
    Visszaad: (győztes, minden találat). Ha két azonos rangú találat van,
    az ütközést a hívó jelezheti — a tudásbázis kétértelmű.
    """
    prioritasok = prioritasok or {}
    talalatok = []
    for m in mintak:
        t = illeszkedik(m, menet_tokenek)
        if t:
            talalatok.append(t)
    if not talalatok:
        return None, []
    talalatok.sort(
        key=lambda t: (prioritasok.get(t.minta.nyers, 0), t.specifikussag),
        reverse=True)
    return talalatok[0], talalatok


# --- Kibontás (a licitmenet_index táblához) --------------------------

def kibont(minta: Minta, max_db: int = 200) -> list[tuple[str, str]]:
    """
    A minta konkrét szekvenciákra bontása.
    Visszaad: [(szekvencia, kötések), ...]

    Ez nemcsak gyors keresést ad, hanem EMBERI ELLENŐRZÉST is:
    egy paranccsal megnézhető, mit fed le pontosan egy minta.
    """
    valtozok = [t.szin for t in minta.tokenek
                if t.szin in VALTOZOK]
    egyedi = list(dict.fromkeys(valtozok))
    if minta.barmennyi or any(t.helyettesito for t in minta.tokenek) \
            or any(t.szint == "n" for t in minta.tokenek):
        return []          # végtelen vagy túl nagy kibontás
    if any(t.szin and INDEX_RE.match(t.szin) for t in minta.tokenek):
        return []          # I/V csak futásidőben, a kényszertárból oldható fel

    ki: list[tuple[str, str]] = []
    for ertekek in product(*(VALTOZOK[v] for v in egyedi)):
        kotes = dict(zip(egyedi, ertekek))
        # Az "akármelyik szín" változók (A, B, E) mellékszínek: az adu (M)
        # színével nem bontjuk ki őket (a `mellekszin:` ugyanezt köti ki).
        if "M" in kotes and any(kotes.get(v) == kotes["M"] for v in ("A", "B", "E")):
            continue
        darabok, jo = [], True
        epitett: list[Token] = []
        for i, t in enumerate(minta.tokenek):
            if t.hivas:
                darabok.append(t.hivas)
                continue
            lehet = _szin_feloldas(t, kotes,
                                   _tokenek_kotessel(minta.tokenek[:i], kotes))
            if len(lehet) != 1:
                jo = False
                break
            szin = next(iter(lehet))
            szint = _legolcsobb_szint(szin, epitett) if t.szint == "+" else t.szint
            if int(szint) > 7:
                jo = False
                break
            darabok.append(f"{szint}{szin}")
            epitett.append(Token(None, szint, szin, t.ellenfel))
        if not jo:
            continue
        szoveg = ("-".join(darabok) if minta.paroslicit else " ".join(darabok))
        ki.append((szoveg, ",".join(f"{k}={v}" for k, v in sorted(kotes.items()))))
        if len(ki) >= max_db:
            break
    return ki


def _tokenek_kotessel(tokenek: list[Token], kotes: dict[str, str]) -> list[Token]:
    ki = []
    for t in tokenek:
        ki.append(Token(t.hivas, t.szint, kotes.get(t.szin, t.szin),
                        t.ellenfel, t.helyettesito))
    return ki


# --- FOLYTATÁS "mint X után" (átirányítás) ------------------------------
#
# Egy szabály jelentésében `folytatas: {mint: "2NT", pont: 2}`: az ezzel a
# licittel végződő menet UGYANÚGY folytatódik, mint a megadott menet (a
# 2♣-2♦-2NT után mint a 2NT nyitás után). A `pont` az eltolás: az
# átirányított menet utolsó licitálója ennyivel erősebb (a partnere
# pontjához ennyit adunk, az övéből ennyit levonunk), így a folytatás
# ponthatárai ugyanazok maradnak.

def alias_elozmenyek(aliasok: list[tuple[Minta, str, float]],
                     elozmeny: list[Token]) -> list[tuple[list[Token], float]]:
    """
    A licitmenet (kanonizált tokenek, a soron következő licit ELŐTT)
    átirányított változatai: [(tokenek, pont_eltolás a soron következő
    licitálónak), ...]. Csak pároslicitben (az ellenfél végig passzolt).
    """
    if any(t.ellenfel for t in elozmeny):
        return []
    ki = []
    for forras, cel, eltolas in aliasok:
        n = len(forras.tokenek)
        if len(elozmeny) < n:
            continue
        tal = illeszkedik(forras, elozmeny[:n])
        if tal is None:
            continue
        try:
            cel_m = minta_parse(cel)
        except MintaHiba:
            continue
        uj: list[Token] = []
        for t in cel_m.tokenek:
            if t.hivas:
                uj.append(Token(hivas=t.hivas))
                continue
            sz = t.szin if t.szin in JELENTESEK else szin_kotesbol(t.szin, tal.kotesek)
            if sz is None or t.szint in (None, "n", "+"):
                uj = []
                break
            uj.append(Token(szint=t.szint, szin=sz))
        if not uj or (n - len(uj)) % 2:
            continue
        # a soron következő licitáló maga-e az átirányított licit gazdája
        o_maga = (len(elozmeny) - (n - 1)) % 2 == 0
        ki.append((uj + list(elozmeny[n:]), -eltolas if o_maga else eltolas))
    return ki


def aliasok_sorokbol(sorok) -> list[tuple[Minta, str, float]]:
    """A `folytatas` jelentésű sorokból: [(forrás-minta, cél, eltolás)]."""
    ki = []
    for s in sorok:
        f = (getattr(s, "jelentes", None) or {}).get("folytatas")
        if not f or not getattr(s, "minta", None):
            continue
        cel, eltolas = (f, 0.0) if isinstance(f, str) else (f.get("mint"), float(f.get("pont") or 0))
        if any(m_.nyers == s.minta and c_ == str(cel) and e_ == eltolas
               for m_, c_, e_ in ki):
            continue               # ugyanaz a menet több sorban (pl. zónánként)
        try:
            ki.append((minta_parse(s.minta), str(cel), eltolas))
        except MintaHiba:
            continue
    return ki
