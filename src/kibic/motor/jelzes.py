"""
Kártyajelzési megállapodások: jelzésrendszer, feloldás, indító lap.

A licit mintájára itt is SOROKBAN él a megállapodás (doc/terv-jelzesnyelv-
2026-10-20.md, rendszerek/jelzesek/README.md):

  JELZÉSRENDSZER  mint a licitrendszer: ALAPRENDSZER (pl. SZEGEDI_MRAZ),
                  RENDSZER (pl. MOHA_STAND: hivatkozik egy alaprendszerre,
                  felülír, kihagy, kizár), vagy KONVENCIÓ.
  SOR             minden elem egy sor, KULCCSAL — ugyanaz a két tengely,
                  mint a licitmenetben (szabaly_fajta és ág):
                    FAJTA (a sor szerepe, mint a licitnél)
                      SZABALY   megállapodás
                      ELV       általános elv (lehet mérlegelő)
                      KIVETEL   egy elv alól kivesz egy esetet (szabályként él)
                      KIHAGYAS  egy örökölt kulcs ebben a rendszerben nem él
                    TERÜLET (miről szól; a licit `ag`-ja helyett)
                      INDITAS     indító kijátszás (a partner színe is)
                      HIVAS       menet közbeni hívás
                      JELZES      a rács: MIT jelzünk, milyen sorrendben
                      MODSZER     HOGYAN adjuk a jelzést (pl. kis lap kér)
                      KULONLEGES  különleges helyzet
                      LICIT       indítást irányító licit
  FELOLDÁS        a licitével azonos (motor/feloldas.py): szélességi bejárás,
                  azonos kulcsból a KISEBB mélységű nyer, azonos mélységben az
                  előbb hivatkozott; a KIHAGYAS lefoglalja a kulcsot; a
                  kizárás a kizáró rendszer ALATTI fában hat (más úton a
                  kizárt még beléphet).

Az indító lapot a feloldott SZABALY-sorok közül a LEGKONKRÉTABB illeszkedő
választja (több konkrét lap a mintában, több feltétel); egyenlőségnél a
közelebbi rendszer, azon belül a sorszám. Ez a MEGÁLLAPODÁS (amit a partner
olvas); hogy egy partiban érdemes-e eltérni tőle, az mérlegelés (DD,
mérlegelő elvek) — az a lejátszó modulé.

Lapjelölés: belül angol betűk (A K Q J T 9 … 2), a YAML-ban a magyar
is jó (Á K D B 10). A minta `x`-e kis lap (10 és lejjebb).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

RANGOK = "AKQJT98765432"
FIGURAK = set("AKQJ")
_MAGYAR = {"Á": "A", "D": "Q", "B": "J", "10": "T"}
_SZEP = {"A": "Á", "Q": "D", "J": "B", "T": "10"}

# MASODIK_KEZ (2026-10-21): színadás második kézben (pl. dubló figurából a figura)
HELYZETEK = ("INDITAS", "PARTNER_SZINE", "HIVAS", "MASODIK_KEZ")
FELVETELEK = ("SZIN", "SZAN")
ALLAPOTOK = ("ELFOGADOTT", "JAVASOLT", "FELULVIZSGALANDO", "JEGELT")
RENDSZER_FAJTAK = ("ALAPRENDSZER", "RENDSZER", "KONVENCIO")
SOR_FAJTAK = ("SZABALY", "ELV", "KIVETEL", "KIHAGYAS")          # mint a licitmenetben
TERULETEK = ("INDITAS", "HIVAS", "SZINADAS", "JELZES", "MODSZER", "KULONLEGES", "LICIT")
TERULET_NEV = {"INDITAS": "indítás", "HIVAS": "menet közbeni hívás", "SZINADAS": "színadás",
               "JELZES": "jelzés (rács)",
               "MODSZER": "módszer", "KULONLEGES": "különleges helyzet", "LICIT": "licit"}
# Milyen állapotú sorok élnek: élesben csak az elfogadott, teszt módban a
# javasolt és a felülvizsgálandó is; a jegelt soha. A kártya mindent mutat
# a jegelten kívül (a jóvá nem hagyottat kérdőjellel).
SZINTEK = {"ELES": ("ELFOGADOTT",),
           "TESZT": ("ELFOGADOTT", "JAVASOLT", "FELULVIZSGALANDO"),
           "KARTYA": ("ELFOGADOTT", "JAVASOLT", "FELULVIZSGALANDO")}
CELOK = ("FIG", "KER", "LSZ", "PREF", "TIPUS", "NINCS")
# A jelzési rács sorai és a jeltípusok (a WBF-kártya "Signals in order of
# priority" táblázata). A `?` végű érték feltételezés: a forrás nem
# mondja ki, a kártyán kérdőjellel jelenik meg.
# VEDO_HIV: menet közben MI hívunk (nem az indítás) — a hívott lap mit jelez
RACS_HELYZETEK = ("PARTNER_INDIT", "FELVEVO_HIV", "DOBAS", "VEDO_HIV")
JELEK = ("KERES", "LAPSZAM", "MARADEK", "PREF", "SMITH", "ATTITUD")
# A beépített lapválasztók (kódban). Ami ezeken kívül névvel áll a `lap:`
# helyén, az TECHNIKA: a jelzésrendszer egy sora definiálja (esetekre bontva).
# Következtetések a lejátszásból (a jelzésrendszer `kovetkeztetes:` sorai).
KOVETKEZTETESEK = (
    "LEGKISEBB_EGYENERTEKU",   # 3./4. kézben, ha ütést próbál vinni: az egyenértékűek legkisebbike
    "LEGOLCSOBB_NYERO",        # 4. kézben: a legolcsóbb nyerő lap
    "FIGURA_SOROZAT",          # a nem ütésre tett (dobott) figura zárt sorozat teteje, vagy szingli
    "PARTNER_INDITASA",        # a partner indító lapja a megállapodás szerinti lap
    "PARTNER_DOBASA",          # a partner első dobása egy színben a dobási jel szerint (kér / nem kér)
    "LICIT_PONTHATAR",         # a licit pontsávja nem éles határ: `tures` ponton belül, `suly` pontonként
    "LICIT_KIZARAS",           # amit a licitjével KIZÁRT (a passz: nincs nyitóereje / válasza)
    "FELVETEL_HIHETO",         # az önként licitált gém / szlem jellemzően teljesíthető lappal megy
)
# A következtetés súlya (2026-10-21): az ellentmondó elosztás ennyit ér a
# mintában (0 = kizárjuk). A lapból levont két régi következtetés alapból
# kizár, a jelzésekből levontak alapból csak leértékelnek (a partner is
# tévedhet, kényszerhelyzetben lehet).
KOVETKEZTETES_SULY = {"LEGKISEBB_EGYENERTEKU": 0.0, "LEGOLCSOBB_NYERO": 0.0, "FIGURA_SOROZAT": 0.1,
                      "PARTNER_INDITASA": 0.2, "PARTNER_DOBASA": 0.25,
                      "LICIT_PONTHATAR": 0.5, "LICIT_KIZARAS": 0.2, "FELVETEL_HIHETO": 0.6}
# akiknél a kibic maga is így játszik (a `sajat:` csak itt értelmes)
KOVETKEZTETES_SAJAT = ("LEGKISEBB_EGYENERTEKU", "LEGOLCSOBB_NYERO", "FIGURA_SOROZAT")
# MÉRLEGELŐ ELVEK a döntésben (2026-10-21) — ahol az elemzés (DD) vak, mert a
# partnert is mindentudónak hiszi. A jelzésrendszer `merlegeles:` sora
# kapcsolja be; sor nélkül nem élnek.
MERLEGELESEK = (
    "ATVETEL",        # ha az elemzés szerint mindegy: a partner ütését nyerő lappal átvesszük, és mi folytatunk
    "PARTNER_KERESE", # a partner kérése (dobással kért szín, Smith): menet közben aszerint hívunk
    "ASZ_ALOL",       # színfelvétel ellen ász alól nem indulunk: az ásszal (a partner színében is)
    "DUBLO_INDULAS",  # színfelvétel ellen dublóból csak figurával; szlem és szan-jellegű leosztás ellen
)
# A mérlegelés tűrése a pontozás egységében (IMP-ben IMP, MP-ben ütés):
# ennyivel rosszabb lapot is vállalunk a partnerség kedvéért (az elemzés átlaga szerint).
MERLEGELES_TURES = {"PARTNER_KERESE": 0.25}
KOVETKEZTETES_FORRASOK = ("PARTNER", "ELLENJATEKOSOK", "FELVEVO")
# Az indító kijátszás színének elsőbbségei és beépített kivételeik.
SZINVALASZTASOK = ("PARTNER_SZINE",)
SZINVALASZTAS_KIVETELEK = (
    "NINCS_LAP",          # nincs lapunk a partner színében
    "KIS_SZINGLI",        # egyetlen kis lap (9 vagy kisebb) a partner színében
    "SAJAT_EROS_SZIN",    # szan ellen: saját 5+ lapos szín, legalább két figurával, köztük Á vagy K
    "LOPAS",              # szín ellen: saját szingli (nem adu, nem a partneré), és 1-3 adunk
)
BEEPITETT_VALASZTOK = ("LEGKISEBB", "LEGNAGYOBB", "NAGYOBB", "LEGNAGYOBB_NELKULOZHETO",
                       "LEGNAGYOBB_KISLAP", "SOROZAT_TETEJE")


class JelzesHiba(ValueError):
    pass


# --- Lapok -------------------------------------------------------------

def lap_kod(s: str) -> str:
    s = str(s).strip().upper()
    s = _MAGYAR.get(s, s)
    if s == "1" or s not in RANGOK:
        raise JelzesHiba(f"ismeretlen lap: {s!r}")
    return s


def lapok(szoveg: str) -> list[str]:
    """'KD93', 'K Q 9 3', 'KQ93', 'Á10x'-ből rendezett rangsor (x nélkül)."""
    s = str(szoveg).upper().replace(" ", "").replace("10", "T")
    ki = [_MAGYAR.get(c, c) for c in s]
    for c in ki:
        if c not in RANGOK:
            raise JelzesHiba(f"ismeretlen lap: {c!r} ({szoveg!r})")
    if len(set(ki)) != len(ki):
        raise JelzesHiba(f"kétszer szereplő lap: {szoveg!r}")
    return sorted(ki, key=RANGOK.index)


def szep(lap: str) -> str:
    return _SZEP.get(lap, lap)


def szep_szin(lapsor: list[str]) -> str:
    return "".join(szep(c) for c in lapsor)


# --- Lapállás-minta ----------------------------------------------------
#
#   AK+      ász-király és utána bármi (AK, AK52, AKQ3)
#   KQx      király-dáma és pontosan egy kis lap
#   KJT(x)   KJ10, esetleg egy kis lappal
#   xxx      három kis lap (figura nélkül)
#   *        bármi (ilyenkor a `hossz` és a `legalabb` szűr)

_TOKEN = re.compile(r"\(x\)|10|[AKQJT2-9ÁDBx]|\+|\*")


@dataclass(frozen=True)
class Minta:
    szoveg: str
    lapok: tuple[str, ...] = ()       # a kötelező konkrét lapok, sorrendben
    x_min: int = 0                    # ennyi kis lap kell legalább
    x_max: int | None = 0             # legfeljebb (None: korlátlan)
    barmi: bool = False
    van_x: bool = False               # van-e `x` a mintában (akkor a többi is kis lap)

    @staticmethod
    def parse(szoveg: str) -> "Minta":
        s = str(szoveg).strip()
        if s in ("", "*"):
            return Minta(szoveg="*", barmi=True)
        tokenek = _TOKEN.findall(s)
        if "".join(tokenek) != s.replace(" ", ""):
            raise JelzesHiba(f"hibás lapállás-minta: {szoveg!r}")
        konkret, xmin, xmax, x_utan = [], 0, 0, False
        for t in tokenek:
            if t == "x":
                xmin += 1
                xmax = None if xmax is None else xmax + 1
                x_utan = True
            elif t == "(x)":
                xmax = None if xmax is None else xmax + 1
                x_utan = True
            elif t == "+":
                xmax = None
            elif t == "*":
                raise JelzesHiba(f"a `*` csak önmagában állhat: {szoveg!r}")
            else:
                if x_utan:
                    raise JelzesHiba(f"konkrét lap kis lap után: {szoveg!r}")
                konkret.append(lap_kod(t))
        if konkret != sorted(konkret, key=RANGOK.index) or len(set(konkret)) != len(konkret):
            raise JelzesHiba(f"a minta lapjai csökkenő sorrendben legyenek: {szoveg!r}")
        return Minta(szoveg=s, lapok=tuple(konkret), x_min=xmin, x_max=xmax,
                     van_x=x_utan)

    def illik(self, lapsor: list[str]) -> bool:
        if self.barmi:
            return True
        n = len(self.lapok)
        if tuple(lapsor[:n]) != self.lapok:
            return False
        maradek = lapsor[n:]
        # `AK+`: a sorozat után bármi jöhet (AKQ3 is); `Kxx`, `KQx+`: a
        # kis lap nem lehet figura (KJx nem Kxx)
        if self.van_x and any(c in FIGURAK for c in maradek):
            return False
        if len(maradek) < self.x_min:
            return False
        return self.x_max is None or len(maradek) <= self.x_max


# --- Hossz- és hézag-feltétel -----------------------------------------------

def _hossz(spec) -> tuple[int, int]:
    if spec in (None, ""):
        return 1, 13
    s = str(spec).strip()
    m = re.fullmatch(r"(\d+)(\+|-|)(?:-(\d+))?", s)
    if not m:
        raise JelzesHiba(f"hibás hossz: {spec!r}")
    lo = int(m.group(1))
    if m.group(3):
        return lo, int(m.group(3))
    if m.group(2) == "+":
        return lo, 13
    if m.group(2) == "-":
        return 1, lo
    return lo, lo


def _hezag(spec) -> tuple[int, int] | None:
    """`hezag: "1-"` (legfeljebb 1), `"2+"`, `"0"`, `"0-1"` -> (alsó, felső)."""
    if spec in (None, ""):
        return None
    m = re.fullmatch(r"(\d+)(\+|-|)(?:-(\d+))?", str(spec).strip())
    if not m:
        raise JelzesHiba(f"hibás hézag: {spec!r}")
    lo = int(m.group(1))
    if m.group(3):
        return lo, int(m.group(3))
    if m.group(2) == "+":
        return lo, 11
    if m.group(2) == "-":
        return 0, lo
    return lo, lo


def hezag(lapsor: list[str]) -> int | None:
    """
    Hány rang HIÁNYZIK a 2. és a 3. lap között (KD10x: 1 — a bubi; KD9x: 2;
    KDBx: 0). Három lapnál rövidebb színben nincs értelme: None.
    """
    if len(lapsor) < 3:
        return None
    return RANGOK.index(lapsor[2]) - RANGOK.index(lapsor[1]) - 1


# --- Lapválasztó -------------------------------------------------------
#
#   K                    ezt a lapot (a mintának tartalmaznia kell)
#   LEGKISEBB / LEGNAGYOBB / NAGYOBB (= legnagyobb, dublóból)
#   FELULROL(n)          a felülről n-edik (ha nincs annyi lap: a legkisebb)
#   LEGNAGYOBB_NELKULOZHETO   indításnál: a legnagyobb nem figura lap (10 és
#                        lejjebb); menet közbeni hívásnál (HIVAS) a finomabb
#                        definíció: legnagyobb_nelkulozheto()
#   LEGNAGYOBB_KISLAP    a legnagyobb kis lap (10 és lejjebb) — pl. a Moha
#                        lapszám-hívása: „3 kis lapból a legnagyobb”
#   PARATLAN_PAROS(A;B)  páratlan számú lapból A, párosból B
#   SOROZAT_TETEJE       a minta első érintkező lappárjának felső lapja
#                        (AK+ -> Á, AQJ+ -> D, KT9+ -> 10); több mintás sorhoz

def sorozat_teteje(minta: "Minta") -> str | None:
    lp = minta.lapok
    for a, b in zip(lp, lp[1:]):
        if RANGOK.index(b) == RANGOK.index(a) + 1:
            return a
    return None


def _valaszt(valaszto: str, lapsor: list[str], minta: "Minta | None" = None,
             helyzet: str = "INDITAS") -> str:
    v = valaszto.strip()
    if v == "SOROZAT_TETEJE":
        t = sorozat_teteje(minta) if minta else None
        if t is None or t not in lapsor:
            raise JelzesHiba(f"nincs sorozat a mintában: {minta.szoveg if minta else '?'}")
        return t
    m = re.fullmatch(r"PARATLAN_PAROS\((.+);(.+)\)", v)
    if m:
        return _valaszt(m.group(1) if len(lapsor) % 2 else m.group(2), lapsor,
                        helyzet=helyzet)
    m = re.fullmatch(r"FELULROL\((\d+)\)", v)
    if m:
        n = int(m.group(1))
        return lapsor[n - 1] if len(lapsor) >= n else lapsor[-1]
    if v == "LEGKISEBB":
        return lapsor[-1]
    if v in ("LEGNAGYOBB", "NAGYOBB"):
        return lapsor[0]
    if v == "LEGNAGYOBB_NELKULOZHETO":
        if helyzet == "HIVAS":            # a játék közbeni hívás definíciója
            return legnagyobb_nelkulozheto(lapsor)
        kicsik = [c for c in lapsor if c not in FIGURAK]
        return kicsik[0] if kicsik else lapsor[0]
    if v == "LEGNAGYOBB_KISLAP":
        kicsik = [c for c in lapsor if c not in FIGURAK]
        return kicsik[0] if kicsik else lapsor[-1]
    lap = lap_kod(v)
    if lap not in lapsor:
        raise JelzesHiba(f"a választott lap ({szep(lap)}) nincs a kézben: "
                         f"{szep_szin(lapsor)}")
    return lap


def _szomszed_van(lap: str, lapsor: list[str]) -> bool:
    """Van-e a kézben a lap közvetlen szomszédja (sorozat része-e)."""
    i = RANGOK.index(lap)
    return ((i > 0 and RANGOK[i - 1] in lapsor)
            or (i + 1 < len(RANGOK) and RANGOK[i + 1] in lapsor))


def legnagyobb_nelkulozheto(lapsor: list[str]) -> str:
    """
    A legnagyobb NÉLKÜLÖZHETŐ lap MENET KÖZBENI HÍVÁSNÁL (2026-10-21; az
    indító kijátszásra nem vonatkozik, ott a legnagyobb nem figura lap):
    a figurák nem nélkülözhetők; a legnagyobb kis lap az, KIVÉVE ha az egy
    magában álló (nem sorozatbeli) 10-es vagy 9-es — az fontos szerepet
    kaphat (pl. a jobbunkon leterülő asztal villájában), ilyenkor a
    második legnagyobb. (A 8-as is lehet ilyen: az mérlegelés, nem szabály.)
    """
    kicsik = [c for c in lapsor if c not in FIGURAK]
    if not kicsik:
        return lapsor[-1]
    t = kicsik[0]
    if t in ("T", "9") and len(kicsik) > 1 and not _szomszed_van(t, lapsor):
        return kicsik[1]
    return t


def valaszto_ellenoriz(valaszto: str) -> None:
    v = str(valaszto).strip()
    m = re.fullmatch(r"PARATLAN_PAROS\((.+);(.+)\)", v)
    if m:
        for resz in (m.group(1), m.group(2)):
            if technika_nev(resz.strip()):
                raise JelzesHiba(f"technika nem lehet a PARATLAN_PAROS-on belül: {resz}")
            valaszto_ellenoriz(resz)
        return
    if re.fullmatch(r"FELULROL\(\d+\)", v) or v in BEEPITETT_VALASZTOK:
        return
    if technika_nev(v):
        return                    # egy TECHNIKA-sor neve: a feloldás nézi meg, van-e
    lap_kod(v)


def technika_nev(v: str) -> bool:
    """Technika-hivatkozás-e (nem beépített választó, nem lap)."""
    return bool(re.fullmatch(r"[A-Z][A-Z0-9_]{3,39}", v)) and v not in BEEPITETT_VALASZTOK


# --- Lapválasztó szabály (a SZABALY-sor lefordított alakja) -------------

@dataclass(frozen=True)
class Sor:
    """Egy SZABALY-sor egy mintája: ezzel illeszt a motor."""
    helyzet: str
    felvetel: str                     # SZIN | SZAN | *
    minta: Minta
    valaszto: str
    cel: str = "FIG"
    hossz: tuple[int, int] = (1, 13)
    legalabb: str | None = None       # van-e legalább ilyen magas lap
    kontextus: str | None = None      # pl. IGERT_HAROM: csak ha a licit ezt mondta
    hezag: tuple[int, int] | None = None   # a 2. és 3. lap közti hiányzó rangok
    # második kéz (MASODIK_KEZ): az asztal helye és lapjai
    asztal: str | None = None              # ELOTTUNK (az asztal hívott) / UTANUNK
    kozbenso: tuple[int, int] | None = None   # az asztal lapjai a 10-es és a figuránk között (a hívottal)
    hivott: str | None = None              # NAGY (10-es vagy nagyobb) / KICSI
    allapot: str = "ELFOGADOTT"
    megjegyzes: str | None = None
    eredet: str = "?"                 # melyik jelzésrendszerből jön
    kulcs: str = ""
    sorrend: int = 0                  # a feloldott sorrendben hányadik (kisebb: közelebbi)

    @property
    def konkretsag(self) -> int:
        """Minél nagyobb, annál konkrétabb: ez nyer, ha több sor illik."""
        k = len(self.minta.lapok) * 10 + self.minta.x_min
        if self.kontextus:
            k += 5
        if self.legalabb:
            k += 2
        if self.hezag:
            k += 2
        if self.asztal:
            k += 2
        if self.kozbenso:
            k += 2
        if self.hivott:
            k += 1
        if self.hossz != (1, 13):
            k += 3 if self.hossz[0] == self.hossz[1] else 1
        return k

    def illik(self, lapsor: list[str], felvetel: str, helyzet: str,
              kontextus: set[str], kornyezet: dict | None = None) -> bool:
        k = kornyezet or {}
        if self.asztal and k.get("asztal") != self.asztal:
            return False
        if self.kozbenso and not (k.get("kozbenso") is not None
                                  and self.kozbenso[0] <= k["kozbenso"] <= self.kozbenso[1]):
            return False
        if self.hivott and k.get("hivott") != self.hivott:
            return False
        if self.helyzet != helyzet:
            return False
        if self.felvetel not in ("*", felvetel):
            return False
        if self.kontextus and self.kontextus not in kontextus:
            return False
        if not self.hossz[0] <= len(lapsor) <= self.hossz[1]:
            return False
        if self.legalabb and RANGOK.index(lapsor[0]) > RANGOK.index(self.legalabb):
            return False
        if self.hezag:
            h = hezag(lapsor)
            if h is None or not self.hezag[0] <= h <= self.hezag[1]:
                return False
        if self.valaszto in RANGOK and self.valaszto not in lapsor:
            return False
        return self.minta.illik(lapsor)


# --- Jelzésrendszer-sor --------------------------------------------------

_KOD = re.compile(r"[A-Z0-9_]{2,40}")
# szöveges sorok: a YAML kulcsszava -> (kulcs-előtag, fajta, terület)
_SZOVEGES = {"elv": ("ELV", "ELV", None), "kivetel": ("KIVETEL", "KIVETEL", None),
             "kulonleges": ("KULONLEGES", "SZABALY", "KULONLEGES"),
             "licit": ("LICIT", "SZABALY", "LICIT")}


@dataclass
class JSor:
    """
    Egy sor, ahogy a YAML-ban és az adatbázisban (jelzesmenet) áll.
    `adat` a sor tartalma kanonikus alakban — ez kerül az adatbázisba, és
    ennek változása alapján dönti el az import, hogy a jóváhagyás marad-e.
    """
    fajta: str                        # SZABALY / ELV / KIVETEL / KIHAGYAS
    kulcs: str
    adat: dict
    fejezet: str | None = None
    seq: int = 0
    terulet: str | None = None        # INDITAS / HIVAS / JELZES / MODSZER / KULONLEGES / LICIT
    allapot: str = "JAVASOLT"
    allapot_yamlbol: bool = False     # a YAML kimondta-e (az import ezt tiszteli)
    megjegyzes: str | None = None
    jegyzet: str | None = None
    eredet: str = "?"
    melyseg: int = 0
    jovahagyta: str | None = None

    def tartalom(self) -> str:
        return json.dumps(self.adat, ensure_ascii=False, sort_keys=True)

    @property
    def alak(self) -> str:
        """A tartalom alakja: LAP (melyik lapot), RACS, MODSZER, SZOVEG, KIHAGYAS."""
        a = self.adat
        if "kihagy" in a:
            return "KIHAGYAS"
        if "lap" in a:
            return "LAP"
        if "racs" in a:
            return "RACS"
        if "modszer" in a:
            return "MODSZER"
        if "technika" in a:
            return "TECHNIKA"
        if "nincs_jelzes" in a:
            return "NINCS_JELZES"
        if "szinvalasztas" in a:
            return "SZINVALASZTAS"
        if "kovetkeztetes" in a:
            return "KOVETKEZTETES"
        if "merlegeles" in a:
            return "MERLEGELES"
        return "SZOVEG"

    @property
    def szabaly_fajta(self) -> str:     # a licit feloldás nevén is
        return self.fajta

    def szabalyok(self) -> list[Sor]:
        """Lapválasztó sornál (SZABALY vagy KIVETEL) a mintánként lefordított illesztők."""
        if self.alak != "LAP" or self.fajta not in ("SZABALY", "KIVETEL"):
            return []
        a = self.adat
        return [Sor(helyzet=a["helyzet"], felvetel=a["felvetel"], minta=Minta.parse(m),
                    valaszto=a["lap"], cel=a.get("cel", "FIG"), hossz=_hossz(a.get("hossz")),
                    legalabb=a.get("legalabb"), kontextus=a.get("kontextus"),
                    hezag=_hezag(a.get("hezag")),
                    asztal=a.get("asztal"), kozbenso=_hezag(a.get("kozbenso")),
                    hivott=a.get("hivott"),
                    allapot=self.allapot, megjegyzes=self.megjegyzes,
                    eredet=self.eredet, kulcs=self.kulcs)
                for m in a["minta"]]


def _szabaly_kulcs(a: dict) -> str:
    k = f"{a['helyzet']}/{a['felvetel']}/{'|'.join(a['minta'])}"
    if a.get("hossz"):
        k += f"/h{a['hossz']}"
    if a.get("legalabb"):
        k += f"/{a['legalabb']}+"
    if a.get("hezag"):
        k += f"/g{a['hezag']}"
    for m in ("asztal", "kozbenso", "hivott"):
        if a.get(m):
            k += f"/{m}={a[m]}"
    if a.get("kontextus"):
        k += f"/{a['kontextus']}"
    return k


def _szabaly_adat(d: dict) -> dict:
    helyzet = str(d.get("helyzet") or "INDITAS")
    if helyzet not in HELYZETEK:
        raise JelzesHiba(f"a `helyzet` {HELYZETEK} egyike legyen")
    felv = str(d.get("felvetel") or "*")
    if felv not in FELVETELEK + ("*",):
        raise JelzesHiba("a `felvetel` SZIN, SZAN vagy * legyen")
    valaszto = str(d["lap"]).strip()
    valaszto_ellenoriz(valaszto)
    if valaszto.upper() in _MAGYAR or len(valaszto) <= 2:
        valaszto = lap_kod(valaszto)
    cel = str(d.get("cel") or "FIG")
    if cel not in CELOK:
        raise JelzesHiba(f"a `cel` {CELOK} egyike legyen")
    mintak = d.get("minta", "*")
    mintak = [mintak] if isinstance(mintak, str) else list(mintak)
    if not mintak:
        raise JelzesHiba("üres `minta` lista")
    for m in mintak:
        mt = Minta.parse(m)
        if valaszto in RANGOK and not mt.barmi and valaszto not in mt.lapok:
            raise JelzesHiba(f"a választott lap ({szep(valaszto)}) nincs a mintában: {m}")
        if valaszto == "SOROZAT_TETEJE" and sorozat_teteje(mt) is None:
            raise JelzesHiba(f"SOROZAT_TETEJE, de nincs sorozat a mintában: {m}")
    a = {"helyzet": helyzet, "felvetel": felv, "minta": [str(m) for m in mintak],
         "lap": valaszto, "cel": cel}
    if d.get("hossz"):
        _hossz(d["hossz"])
        a["hossz"] = str(d["hossz"])
    if d.get("legalabb"):
        a["legalabb"] = lap_kod(d["legalabb"])
    if d.get("kontextus"):
        a["kontextus"] = str(d["kontextus"])
    if d.get("hezag") not in (None, ""):
        _hezag(d["hezag"])
        a["hezag"] = str(d["hezag"])
    if any(d.get(m) not in (None, "") for m in ("asztal", "kozbenso", "hivott")) \
            and helyzet != "MASODIK_KEZ":
        raise JelzesHiba("az `asztal`, `kozbenso`, `hivott` csak a MASODIK_KEZ helyzetben él")
    if d.get("asztal"):
        if str(d["asztal"]) not in ("ELOTTUNK", "UTANUNK"):
            raise JelzesHiba("az `asztal` ELOTTUNK vagy UTANUNK")
        a["asztal"] = str(d["asztal"])
    if d.get("kozbenso") not in (None, ""):
        _hezag(d["kozbenso"])
        a["kozbenso"] = str(d["kozbenso"])
    if d.get("hivott"):
        if str(d["hivott"]) not in ("NAGY", "KICSI"):
            raise JelzesHiba("a `hivott` NAGY vagy KICSI")
        a["hivott"] = str(d["hivott"])
    return a


def _racs_adat(d: dict) -> list[tuple[str, dict]]:
    h = str(d["racs"])
    if h not in RACS_HELYZETEK:
        raise JelzesHiba(f"a rács sora {RACS_HELYZETEK} egyike legyen: {h}")
    felv = str(d.get("felvetel") or "*")
    if felv not in FELVETELEK + ("*",):
        raise JelzesHiba("a `felvetel` SZIN, SZAN vagy * legyen")
    sorrend = int(d.get("sorrend") or 1)
    jel = str(d.get("jel") or "")
    kulonben = str(d["kulonben"]) if d.get("kulonben") else None
    for x in (jel, kulonben):
        if x is not None and x not in JELEK:
            raise JelzesHiba(f"ismeretlen jel: {x} ({JELEK})")
    ki = []
    for f in (FELVETELEK if felv == "*" else (felv,)):
        a = {"racs": h, "felvetel": f, "sorrend": sorrend, "jel": jel}
        if d.get("hossz"):
            _hossz(d["hossz"])
            a["hossz"] = str(d["hossz"])
        if d.get("mikor"):
            a["mikor"] = str(d["mikor"])
        if kulonben:
            a["kulonben"] = kulonben
        if d.get("feltetelezes"):
            a["feltetelezes"] = True
        ki.append((f"RACS/{h}/{f}/{sorrend}", a))
    return ki


def _esetek(x, hol: str) -> list[dict]:
    """Lapválasztás esetekre: `lap` vagy [{hossz?, legalabb?, lap}, …]."""
    if isinstance(x, str):
        x = [{"lap": x}]
    if not isinstance(x, list) or not x:
        raise JelzesHiba(f"{hol}: lap vagy esetek listája kell")
    ki = []
    for e in x:
        if not isinstance(e, dict) or "lap" not in e or set(e) - {"hossz", "legalabb", "lap"}:
            raise JelzesHiba(f"{hol}: egy eset: {{hossz?, legalabb?, lap}} — nem {e!r}")
        lap = str(e["lap"]).strip()
        valaszto_ellenoriz(lap)
        if lap.upper() in _MAGYAR or len(lap) <= 2:
            raise JelzesHiba(f"{hol}: konkrét lap nem lehet eset (minta nélkül): {lap}")
        a = {"lap": lap}
        if e.get("hossz"):
            _hossz(e["hossz"])
            a["hossz"] = str(e["hossz"])
        if e.get("legalabb"):
            a["legalabb"] = lap_kod(e["legalabb"])
        ki.append(a)
    return ki


def jsorok_dictbol(d: dict, fejezet: str | None, seq: int, eredet: str,
                   alap_allapot: str) -> list[JSor]:
    """Egy YAML-sor -> egy vagy több JSor (a `felvetel: *` rácssor kettő)."""
    hely = f"{eredet}: {d!r}"
    try:
        if not isinstance(d, dict):
            raise JelzesHiba("a sor szótár legyen")
        # par: (fajta, terület, kulcs, adat)
        if "kihagy" in d or "torol" in d:          # `torol:` a régi név
            k = str(d.get("kihagy") or d.get("torol"))
            par = [("KIHAGYAS", None, k, {"kihagy": k})]
        elif "racs" in d:
            par = [("SZABALY", "JELZES", k, a) for k, a in _racs_adat(d)]
        elif "modszer" in d:
            if not _KOD.fullmatch(str(d["modszer"])) or not ("ertek" in d or "hivas" in d):
                raise JelzesHiba("`modszer: KOD` és `ertek:` vagy `hivas:` kell")
            a = {"modszer": str(d["modszer"])}
            if "ertek" in d:
                a["ertek"] = str(d["ertek"])
            if "hivas" in d:          # hogyan adjuk ezt a jelet a HÍVOTT lappal
                a["hivas"] = _esetek(d["hivas"], "hivas")
            if d.get("szoveg"):
                a["szoveg"] = " ".join(str(d["szoveg"]).split())
            par = [("SZABALY", "MODSZER", f"MODSZER/{d['modszer']}", a)]
        elif "technika" in d:
            kod = str(d["technika"])
            if not technika_nev(kod):
                raise JelzesHiba(f"hibás technika-név: {kod!r}")
            a = {"technika": kod, "esetek": _esetek(d.get("esetek"), "esetek")}
            if d.get("szoveg"):
                a["szoveg"] = " ".join(str(d["szoveg"]).split())
            par = [("SZABALY", "MODSZER", f"TECHNIKA/{kod}", a)]
        elif "szinvalasztas" in d:
            # az indító kijátszás SZÍNÉNEK elsőbbsége (pl. a partner licitált
            # színe), a beépített kivételekkel; a lapot a színen belül a
            # megállapodás adja, a DD a biztosan rosszat vétózza
            kod = str(d["szinvalasztas"])
            if kod not in SZINVALASZTASOK:
                raise JelzesHiba(f"a `szinvalasztas` {SZINVALASZTASOK} egyike legyen")
            felv = str(d.get("felvetel") or "*")
            if felv not in FELVETELEK + ("*",):
                raise JelzesHiba("a `felvetel` SZIN, SZAN vagy * legyen")
            kiveve = [str(x) for x in (d.get("kiveve") or [])]
            rossz = [x for x in kiveve if x not in SZINVALASZTAS_KIVETELEK]
            if rossz:
                raise JelzesHiba(f"ismeretlen kivétel: {rossz} ({SZINVALASZTAS_KIVETELEK})")
            a = {"szinvalasztas": kod, "felvetel": felv, "kiveve": kiveve}
            if d.get("szoveg"):
                a["szoveg"] = " ".join(str(d["szoveg"]).split())
            par = [("SZABALY", "INDITAS", f"INDITAS/SZINVALASZTAS/{kod}", a)]
        elif "kovetkeztetes" in d:
            # KÖVETKEZTETÉS A LEJÁTSZÁSBÓL — nem rejtett tudás: a jelzésrendszer
            # sora mondja meg, mit, kitől, és hogy a kibic maga is így játszik-e
            kod = str(d["kovetkeztetes"])
            if kod not in KOVETKEZTETESEK:
                raise JelzesHiba(f"a `kovetkeztetes` {KOVETKEZTETESEK} egyike legyen")
            kitol = [str(x) for x in (d.get("kitol") or ["PARTNER"])]
            rossz = [x for x in kitol if x not in KOVETKEZTETES_FORRASOK]
            if rossz:
                raise JelzesHiba(f"ismeretlen `kitol`: {rossz} ({KOVETKEZTETES_FORRASOK})")
            a = {"kovetkeztetes": kod, "kitol": kitol,
                 "sajat": bool(d.get("sajat", True)) if kod in KOVETKEZTETES_SAJAT else False}
            if "suly" in d:
                try:
                    a["suly"] = float(d["suly"])
                except (TypeError, ValueError):
                    raise JelzesHiba("a `suly` szám legyen (0 = kizár, 1 = nem számít)") from None
                if not 0.0 <= a["suly"] <= 1.0:
                    raise JelzesHiba("a `suly` 0 és 1 között legyen")
            if "tures" in d:
                if kod != "LICIT_PONTHATAR":
                    raise JelzesHiba("`tures` csak a LICIT_PONTHATAR következtetésnél")
                try:
                    a["tures"] = int(d["tures"])
                except (TypeError, ValueError):
                    raise JelzesHiba("a `tures` egész pontszám legyen") from None
                if not 0 <= a["tures"] <= 5:
                    raise JelzesHiba("a `tures` 0 és 5 pont között legyen")
            if d.get("szoveg"):
                a["szoveg"] = " ".join(str(d["szoveg"]).split())
            par = [("ELV", "SZINADAS", f"KOVETKEZTETES/{kod}", a)]
        elif "merlegeles" in d:
            kod = str(d["merlegeles"])
            if kod not in MERLEGELESEK:
                raise JelzesHiba(f"a `merlegeles` {MERLEGELESEK} egyike legyen")
            a = {"merlegeles": kod}
            if "tures" in d:
                if kod not in MERLEGELES_TURES:
                    raise JelzesHiba(f"`tures` csak ezeknél: {tuple(MERLEGELES_TURES)}")
                try:
                    a["tures"] = float(d["tures"])
                except (TypeError, ValueError):
                    raise JelzesHiba("a `tures` ütésben megadott szám legyen (pl. 0.25)") from None
                if not 0.0 <= a["tures"] <= 1.0:
                    raise JelzesHiba("a `tures` 0 és 1 ütés között legyen")
            if d.get("szoveg"):
                a["szoveg"] = " ".join(str(d["szoveg"]).split())
            par = [("ELV", "SZINADAS", f"MERLEGELES/{kod}", a)]
        elif "nincs_jelzes" in d:
            # „szlem ellen nem jelzünk”: ilyen kontraktus ellen a színadás és a
            # dobás nem jelez (a legkisebb jó lap), a rács ott nem él
            kod = str(d["nincs_jelzes"])
            if not _KOD.fullmatch(kod):
                raise JelzesHiba(f"hibás kód: {kod!r}")
            felv = str(d.get("felvetel") or "*")
            if felv not in FELVETELEK + ("*",):
                raise JelzesHiba("a `felvetel` SZIN, SZAN vagy * legyen")
            lo, hi = _hossz(d.get("szint") or "1+")
            if not 1 <= lo <= hi:
                raise JelzesHiba(f"hibás szint: {d.get('szint')!r}")
            a = {"nincs_jelzes": kod, "szint": str(d.get("szint") or "1+"), "felvetel": felv}
            if d.get("szoveg"):
                a["szoveg"] = " ".join(str(d["szoveg"]).split())
            par = [("SZABALY", "JELZES", f"JELZES/NINCS/{kod}", a)]
        elif any(k in d for k in _SZOVEGES):
            kulcsszo = next(k for k in _SZOVEGES if k in d)
            elotag, fajta, terulet = _SZOVEGES[kulcsszo]
            kod = str(d[kulcsszo])
            if not _KOD.fullmatch(kod):
                raise JelzesHiba(f"hibás kód: {kod!r}")
            if not d.get("szoveg"):
                raise JelzesHiba("`szoveg` kell")
            a = {kulcsszo: kod, "szoveg": " ".join(str(d["szoveg"]).split())}
            if kulcsszo == "kivetel":
                if not _KOD.fullmatch(str(d.get("alol") or "")):
                    raise JelzesHiba("a kivételhez `alol: ELVKOD` kell (melyik elv alól)")
                a["alol"] = str(d["alol"])
            if d.get("merlegelo"):
                a["merlegelo"] = True
            if d.get("kartyan") is False:
                a["kartyan"] = False
            par = [(fajta, terulet, f"{elotag}/{kod}", a)]
        elif "lap" in d:
            a = _szabaly_adat(d)
            fajta = str(d.get("fajta") or "SZABALY")
            if fajta not in ("SZABALY", "KIVETEL"):
                raise JelzesHiba("lapválasztó sor fajtája SZABALY vagy KIVETEL")
            if fajta == "KIVETEL":
                if not _KOD.fullmatch(str(d.get("alol") or "")):
                    raise JelzesHiba("a kivételhez `alol: ELVKOD` kell (melyik elv alól)")
                a["alol"] = str(d["alol"])
            par = [(fajta, {"HIVAS": "HIVAS", "MASODIK_KEZ": "SZINADAS"}.get(a["helyzet"], "INDITAS"),
                    str(d.get("kulcs") or _szabaly_kulcs(a)), a)]
        else:
            raise JelzesHiba("ismeretlen sor (kihagy / racs / modszer / technika / elv / "
                             "kivetel / kulonleges / licit / lap)")
        if d.get("terulet"):
            if str(d["terulet"]) not in TERULETEK:
                raise JelzesHiba(f"a `terulet` {TERULETEK} egyike legyen")
            par = [(f, str(d["terulet"]), k, a) for f, _, k, a in par]
        allapot = str(d.get("allapot") or alap_allapot)
        if allapot not in ALLAPOTOK:
            raise JelzesHiba(f"az `allapot` {ALLAPOTOK} egyike legyen")
        return [JSor(fajta=f, terulet=t, kulcs=k, adat=a, fejezet=fejezet, seq=seq + i,
                     allapot=allapot, allapot_yamlbol="allapot" in d,
                     megjegyzes=d.get("megjegyzes"), jegyzet=d.get("jegyzet"),
                     eredet=eredet)
                for i, (f, t, k, a) in enumerate(par)]
    except (JelzesHiba, KeyError, ValueError, TypeError) as e:
        raise JelzesHiba(f"{hely}: {e}") from None


@dataclass
class Kizaras:
    kod: str
    fejezet: str | None = None


@dataclass
class JelzesRendszer:
    kod: str
    nev: str
    fajta: str = "ALAPRENDSZER"
    verzio: str = "0.1"
    forras: str | None = None
    leiras: str | None = None
    jegyzet: str | None = None
    fejezet_jegyzetek: dict = field(default_factory=dict)
    hivatkozasok: list[str] = field(default_factory=list)
    kizarasok: list[Kizaras] = field(default_factory=list)
    sorok: list[JSor] = field(default_factory=list)
    fajl: str = "?"


def rendszer_dictbol(adat: dict, fajl: str = "?") -> JelzesRendszer:
    if not isinstance(adat, dict) or "jelzesrendszer" not in adat:
        raise JelzesHiba(f"{fajl}: hiányzik a `jelzesrendszer:` blokk")
    meta = adat["jelzesrendszer"]
    kod = str(meta.get("kod") or "")
    if not _KOD.fullmatch(kod):
        raise JelzesHiba(f"{fajl}: a kód NAGYBETŰ/szám/_ legyen: {kod!r}")
    fajta = str(meta.get("fajta") or "ALAPRENDSZER")
    if fajta not in RENDSZER_FAJTAK:
        raise JelzesHiba(f"{fajl}: a `fajta` {RENDSZER_FAJTAK} egyike legyen")
    alap_allapot = str(meta.get("alap_allapot") or "JAVASOLT")
    if alap_allapot not in ALLAPOTOK:
        raise JelzesHiba(f"{fajl}: az `alap_allapot` {ALLAPOTOK} egyike legyen")
    r = JelzesRendszer(kod=kod, nev=str(meta.get("nev") or kod), fajta=fajta,
                       verzio=str(meta.get("verzio") or "0.1"), forras=meta.get("forras"),
                       leiras=" ".join(str(meta["leiras"]).split()) if meta.get("leiras") else None,
                       jegyzet=meta.get("jegyzet"), fajl=fajl)
    for h in adat.get("hivatkozasok") or []:
        k = str(h["kod"] if isinstance(h, dict) else h)
        if not _KOD.fullmatch(k) or k in r.hivatkozasok:
            raise JelzesHiba(f"{fajl}: hibás vagy kétszeres hivatkozás: {k!r}")
        r.hivatkozasok.append(k)
    for k in adat.get("kizarasok") or []:
        if isinstance(k, str):
            k = {"kod": k}
        if not _KOD.fullmatch(str(k.get("kod") or "")):
            raise JelzesHiba(f"{fajl}: hibás kizárás: {k!r}")
        r.kizarasok.append(Kizaras(kod=str(k["kod"]), fejezet=k.get("fejezet")))
    seq = 10
    blokkok = [(f.get("fejezet"), f) for f in adat.get("fejezetek") or []]
    if adat.get("sorok"):
        blokkok.append((None, {"sorok": adat["sorok"]}))
    for nev, blokk in blokkok:
        if nev and blokk.get("jegyzet"):
            r.fejezet_jegyzetek[nev] = " ".join(str(blokk["jegyzet"]).split())
        for d in blokk.get("sorok") or []:
            r.sorok.extend(jsorok_dictbol(d, nev, seq, kod, alap_allapot))
            seq += 10
    latott: dict[str, int] = {}
    for s in r.sorok:
        if s.kulcs in latott:
            raise JelzesHiba(f"{fajl}: kétszer szereplő kulcs: {s.kulcs}")
        latott[s.kulcs] = 1
    if not r.hivatkozasok and any(s.fajta == "KIHAGYAS" for s in r.sorok):
        raise JelzesHiba(f"{fajl}: kihagyni csak örökölt sort lehet — a rendszer nem hivatkozik semmire")
    return r


def rendszerek_betolt(utak) -> dict[str, JelzesRendszer]:
    """Fájlok és/vagy könyvtárak (rekurzívan *.yaml) -> {kod: JelzesRendszer}."""
    from pathlib import Path

    import yaml
    fajlok = []
    for u in utak:
        p = Path(u)
        fajlok += sorted(p.rglob("*.yaml")) if p.is_dir() else [p]
    ki: dict[str, JelzesRendszer] = {}
    for f in fajlok:
        with open(f, encoding="utf-8") as fh:
            for dok in yaml.safe_load_all(fh):
                if not dok:
                    continue
                r = rendszer_dictbol(dok, str(f))
                if r.kod in ki:
                    raise JelzesHiba(f"{f}: kétszer definiált jelzésrendszer: {r.kod}")
                ki[r.kod] = r
    return ki


# --- Feloldás ----------------------------------------------------------------

@dataclass
class Feloldas:
    kod: str
    sorok: list[JSor]                 # a feloldott sorok, a döntés sorrendjében
    lanc: list[tuple[str, int]]       # (kód, mélység) a bejárás sorrendjében
    felulirt: list[tuple[str, str, str]] = field(default_factory=list)  # (kulcs, nyertes, vesztes)
    torolt: list[tuple[str, str, str]] = field(default_factory=list)    # (kulcs, ki hagyta ki, kié volt)
    kizart: list[tuple[str, str | None, str]] = field(default_factory=list)  # (kód, fejezet, ki)
    hianyzo: list[str] = field(default_factory=list)
    korkoros: list[str] = field(default_factory=list)                   # "A -> B -> A"
    hatastalan_kizarasok: list[tuple[str, str, str | None]] = field(default_factory=list)
    kivetel_elv_nelkul: list[str] = field(default_factory=list)         # KIVETEL, de nincs ilyen elv

    @property
    def kihagyott(self):              # a szerkesztő nevén
        return self.torolt


def feloldas(kod: str, rendszerek: dict[str, JelzesRendszer],
             szint: str = "KARTYA", max_melyseg: int = 10) -> Feloldas:
    """
    UGYANAZ, mint a licit feloldása (motor/feloldas.py, feloldas_altalanos):

      * SZÉLESSÉGI bejárás: a rendszer saját sorai, aztán a hivatkozásai
        (a sorrendjükben), aztán azok hivatkozásai …;
      * egy kulcs azé, aki a bejárásban ELŐBB adta: a kisebb mélységűé,
        azonos mélységben az előbb hivatkozotté;
      * KIHAGYAS: lefoglalja a kulcsot, de nem kerül a sorok közé — a mélyebb
        (örökölt) sor így kiesik;
      * KIZÁRÁS: a kizáró rendszer ALATTI fában hat; egy egész rendszer
        kizárása után az más úton még beléphet;
      * ami ezen a szinten nem él (élesben a javasolt), az nem is ír felül;
      * egy rendszer csak egyszer lép be (körkörös hivatkozás: kimarad,
        és a `korkoros` listában látszik).
    Ami csak a licitnél van (téma, elv-sablon, feltételes `ha:` felülírás),
    az itt nincs.
    """
    elo = SZINTEK[szint]
    f = Feloldas(kod=kod, sorok=[], lanc=[])
    latott: set[str] = set()
    gazda: dict[str, str] = {}                 # kulcs -> a gazda rendszer
    kihagyo: dict[str, str] = {}               # kulcs -> aki kihagyta
    hatott: set[tuple] = set()
    osszes_kizaras: list[tuple[str, tuple]] = []
    kizart_fejezet: set[tuple] = set()
    sorban: list[tuple] = [(kod, 0, {}, ())]

    while sorban:
        k, m, kizart, ut = sorban.pop(0)
        if k in latott:
            if k in ut:
                f.korkoros.append(" -> ".join(ut + (k,)))
            continue
        if m > max_melyseg:
            raise JelzesHiba(f"túl mély hivatkozási lánc ({m}): {kod}")
        r = rendszerek.get(k)
        if r is None:
            if k not in f.hianyzo:
                f.hianyzo.append(k)
            continue
        if (k, None) in kizart:
            hatott.add((kizart[(k, None)], (k, None)))
            f.kizart.append((k, None, kizart[(k, None)]))
            continue                       # más úton még beléphet
        latott.add(k)
        f.lanc.append((k, m))
        for s in r.sorok:
            if s.allapot not in elo:
                continue
            fk = (k, s.fejezet or None)
            if s.fejezet and fk in kizart:
                hatott.add((kizart[fk], fk))
                if fk not in kizart_fejezet:
                    kizart_fejezet.add(fk)
                    f.kizart.append((k, s.fejezet, kizart[fk]))
                continue
            g = gazda.get(s.kulcs)
            if s.fajta == "KIHAGYAS":
                if g is None:
                    gazda[s.kulcs] = k
                    kihagyo[s.kulcs] = k
                continue
            if g is None:
                gazda[s.kulcs] = k
                f.sorok.append(JSor(**{**s.__dict__, "eredet": k, "melyseg": m}))
            elif kihagyo.get(s.kulcs) == g:
                f.torolt.append((s.kulcs, g, k))
            else:
                f.felulirt.append((s.kulcs, g, k))
        gyerek = dict(kizart)
        for kz in r.kizarasok:
            kk = (kz.kod, kz.fejezet or None)
            gyerek.setdefault(kk, k)
            osszes_kizaras.append((k, kk))
        for h in r.hivatkozasok:
            sorban.append((h, m + 1, gyerek, ut + (k,)))

    for ki, kk in osszes_kizaras:
        if (ki, kk) not in hatott:
            f.hatastalan_kizarasok.append((ki, kk[0], kk[1]))
    elvek = {s.adat.get("elv") for s in f.sorok if s.fajta == "ELV"}
    f.kivetel_elv_nelkul = [s.kulcs for s in f.sorok
                            if s.fajta == "KIVETEL" and s.adat.get("alol") not in elvek]
    return f


# --- A motor nézete ------------------------------------------------------------

@dataclass
class Jelzesek:
    """A feloldott jelzésrendszer: ezzel dolgozik a motor és a kártya."""
    rendszer: JelzesRendszer | None
    alapok: list[JelzesRendszer]      # amire közvetlenül épül
    sorok: list[Sor]
    racs: dict                        # {helyzet: {felvetel: [cella, ...]}}
    modszer: dict
    kulonleges: list[dict]
    licit_inditas: list[dict]
    elvek: list[dict]
    feloldas: Feloldas
    hianyzo: list[str] = field(default_factory=list)
    technikak: dict = field(default_factory=dict)   # {név: [eset, …]}
    hivas_modszer: dict = field(default_factory=dict)   # {jel: [eset, …]} — a hívott lappal
    nincs_jelzes_sorok: list = field(default_factory=list)   # „szlem ellen nem jelzünk”
    szinvalasztas_sorok: list = field(default_factory=list)  # az indulás színének elsőbbsége
    kovetkeztetes_sorok: list = field(default_factory=list)  # következtetések a lejátszásból
    merlegeles_sorok: list = field(default_factory=list)     # mérlegelő elvek a döntésben

    def merlegeles(self, kod: str) -> dict | None:
        return next((m for m in self.merlegeles_sorok if m["merlegeles"] == kod), None)

    def szinvalasztas(self, kod: str, felvetel: str) -> dict | None:
        for x in self.szinvalasztas_sorok:
            if x["szinvalasztas"] == kod and x["felvetel"] in ("*", felvetel):
                return x
        return None

    def nincs_jelzes(self, szint: int, felvetel: str) -> dict | None:
        """Az a sor, amely szerint ez ellen a kontraktus ellen NEM jelzünk."""
        for x in self.nincs_jelzes_sorok:
            lo, hi = _hossz(x["szint"])
            if lo <= szint <= hi and x["felvetel"] in ("*", felvetel):
                return x
        return None
    figyelmeztetesek: list[str] = field(default_factory=list)

    @property
    def lanc(self) -> list[str]:
        return [k for k, _ in self.feloldas.lanc]

    def jeloltek(self, lapsor, felvetel: str, helyzet: str = "INDITAS", kontextus=(),
                 kornyezet: dict | None = None):
        """Minden illeszkedő sor, a döntés sorrendjében (az első nyer)."""
        if isinstance(lapsor, str):
            lapsor = lapok(lapsor)
        if not lapsor:
            raise JelzesHiba("üres szín")
        if felvetel not in FELVETELEK:
            raise JelzesHiba(f"a felvétel SZIN vagy SZAN: {felvetel}")
        kont = set(kontextus or ())
        ki = [s for s in self.sorok if s.illik(lapsor, felvetel, helyzet, kont, kornyezet)]
        return sorted(ki, key=lambda s: (-s.konkretsag, s.sorrend))

    def indito_lap(self, lapsor, felvetel: str, helyzet: str = "INDITAS",
                   kontextus=(), csak_elfogadott: bool = False, kornyezet: dict | None = None):
        """
        (lap, Sor): a legkonkrétabb illeszkedő sor lapja; (None, None), ha
        nincs. A PARTNER_SZINE helyzetben, ha nincs rá sor, az INDITAS él.
        """
        if isinstance(lapsor, str):
            lapsor = lapok(lapsor)
        for h in [helyzet] + (["INDITAS"] if helyzet == "PARTNER_SZINE" else []):
            for s in self.jeloltek(lapsor, felvetel, h, kontextus, kornyezet):
                if csak_elfogadott and s.allapot != "ELFOGADOTT":
                    continue
                return _valaszt(s.valaszto, lapsor, s.minta, s.helyzet), s
        return None, None


def jelzesek(kod: str | None, rendszerek: dict[str, JelzesRendszer],
             szint: str = "KARTYA") -> Jelzesek | None:
    """A feloldott jelzésrendszer a motornak és a kártyának."""
    if not kod:
        return None
    f = feloldas(kod, rendszerek, szint)
    sorok: list[Sor] = []
    racs: dict = {}
    modszer: dict = {}
    tetelek = {"ELV": [], "KULONLEGES": [], "LICIT": []}
    technikak = {s.adat["technika"]: s for s in f.sorok if s.alak == "TECHNIKA"}
    hivas_modszer: dict = {}
    nincs: list[dict] = []
    szinval: list[dict] = []
    kovetk: list[dict] = []
    merl: list[dict] = []
    figy: list[str] = []
    for s in f.sorok:
        if s.alak == "LAP":
            for sz in s.szabalyok():
                for x in _kifejt(sz, technikak, figy):
                    sorok.append(Sor(**{**x.__dict__, "sorrend": len(sorok)}))
        elif s.alak == "RACS":
            a = s.adat
            racs.setdefault(a["racs"], {}).setdefault(a["felvetel"], []).append(
                {"jel": a["jel"], "mikor": a.get("mikor"), "kulonben": a.get("kulonben"),
                 "sorrend": a["sorrend"], "hossz": a.get("hossz"),
                 "feltetelezes": bool(a.get("feltetelezes")) or s.allapot != "ELFOGADOTT"})
        elif s.alak == "MODSZER":
            if s.adat.get("ertek"):
                modszer[s.adat["modszer"]] = s.adat["ertek"]
            if s.adat.get("hivas"):
                hivas_modszer[s.adat["modszer"]] = s.adat["hivas"]
        elif s.alak == "KOVETKEZTETES":
            kovetk.append({**s.adat, "kulcs": s.kulcs, "allapot": s.allapot})
            if s.adat.get("szoveg"):
                tetelek["ELV"].append({"szoveg": s.adat["szoveg"], "kod": s.adat["kovetkeztetes"],
                                       "fajta": "ELV", "terulet": "SZINADAS",
                                       "rendszer": s.eredet, "allapot": s.allapot,
                                       "kartyan": False})
        elif s.alak == "MERLEGELES":
            merl.append({**s.adat, "kulcs": s.kulcs, "allapot": s.allapot})
            if s.adat.get("szoveg"):
                tetelek["ELV"].append({"szoveg": s.adat["szoveg"], "kod": s.adat["merlegeles"],
                                       "fajta": "ELV", "terulet": "SZINADAS",
                                       "rendszer": s.eredet, "allapot": s.allapot})
        elif s.alak == "SZINVALASZTAS":
            szinval.append({**s.adat, "kulcs": s.kulcs, "allapot": s.allapot})
            if s.adat.get("szoveg"):
                tetelek["ELV"].append({"szoveg": s.adat["szoveg"], "kod": s.adat["szinvalasztas"],
                                       "fajta": "SZABALY", "terulet": "INDITAS",
                                       "rendszer": s.eredet, "allapot": s.allapot})
        elif s.alak == "NINCS_JELZES":
            nincs.append({**s.adat, "kulcs": s.kulcs, "allapot": s.allapot})
            if s.adat.get("szoveg"):         # a kártyán az elvek között
                tetelek["ELV"].append({"szoveg": s.adat["szoveg"], "kod": s.adat["nincs_jelzes"],
                                       "fajta": "SZABALY", "terulet": "JELZES",
                                       "rendszer": s.eredet, "allapot": s.allapot})
        elif s.alak == "SZOVEG":
            # elvek és kivételeik együtt (a kivétel az elve után áll a kártyán)
            hova = ("KULONLEGES" if s.terulet == "KULONLEGES" and s.fajta == "SZABALY" else
                    "LICIT" if s.terulet == "LICIT" and s.fajta == "SZABALY" else "ELV")
            tetelek[hova].append({**s.adat, "kod": s.kulcs.split("/", 1)[1], "fajta": s.fajta,
                                  "terulet": s.terulet, "rendszer": s.eredet,
                                  "allapot": s.allapot})
    for felv in racs.values():
        for f_ in felv:
            felv[f_].sort(key=lambda c: c["sorrend"])
    # MENET KÖZBENI HÍVÁS: a rács (mit jelzünk) + a módszer (hogyan, a hívott
    # lappal) + a technikák (a módszer lapválasztói) -> lapválasztó sorok
    sorok += _hivas_sorok(f.sorok, technikak, figy, kezdo=len(sorok))
    for t, ts in technikak.items():
        for e in ts.adat["esetek"]:
            if technika_nev(e["lap"]) and e["lap"] not in technikak:
                figy.append(f"ismeretlen technika: {e['lap']} (a {t} esete)")
    # a kivétel az elve mögé kerül
    rend = {e["kod"]: i for i, e in enumerate(tetelek["ELV"]) if e["fajta"] == "ELV"}
    tetelek["ELV"].sort(key=lambda e: (rend.get(e.get("alol") or e["kod"], 999),
                                       e["fajta"] == "KIVETEL"))
    r = rendszerek.get(kod)
    return Jelzesek(rendszer=r,
                    alapok=[rendszerek[h] for h in (r.hivatkozasok if r else [])
                            if h in rendszerek],
                    sorok=sorok, racs=racs, modszer=modszer,
                    kulonleges=tetelek["KULONLEGES"], licit_inditas=tetelek["LICIT"],
                    elvek=tetelek["ELV"], feloldas=f, hianyzo=list(f.hianyzo),
                    technikak={k: v.adat["esetek"] for k, v in technikak.items()},
                    hivas_modszer=hivas_modszer, nincs_jelzes_sorok=nincs,
                    szinvalasztas_sorok=szinval, kovetkeztetes_sorok=kovetk,
                    merlegeles_sorok=merl,
                    figyelmeztetesek=list(dict.fromkeys(figy)))


_JEL_CEL = {"ATTITUD": "KER", "KERES": "KER", "LAPSZAM": "LSZ", "MARADEK": "LSZ",
            "PREF": "PREF", "SMITH": "KER"}


def _metszet(h1: tuple[int, int], h2: tuple[int, int]) -> tuple[int, int] | None:
    lo, hi = max(h1[0], h2[0]), min(h1[1], h2[1])
    return (lo, hi) if lo <= hi else None


def _kifejt(sor: Sor, technikak: dict, figy: list[str], ut: tuple = ()) -> list[Sor]:
    """
    Ha a sor lapválasztója TECHNIKA, esetekre bontja (a feltételek metszete:
    hossz, legalább-lap); a beépített választót változatlanul hagyja.
    """
    v = sor.valaszto
    if not technika_nev(v):
        return [sor]
    t = technikak.get(v)
    if t is None:
        figy.append(f"ismeretlen technika: {v} ({sor.kulcs})")
        return []
    if v in ut:
        figy.append(f"körkörös technika: {' -> '.join(ut + (v,))}")
        return []
    ki: list[Sor] = []
    for e in t.adat["esetek"]:
        h = _metszet(sor.hossz, _hossz(e.get("hossz")))
        if h is None:
            continue
        leg = sor.legalabb
        if e.get("legalabb") and (leg is None or RANGOK.index(e["legalabb"]) < RANGOK.index(leg)):
            leg = e["legalabb"]
        allapot = sor.allapot if sor.allapot != "ELFOGADOTT" else t.allapot
        uj = Sor(**{**sor.__dict__, "hossz": h, "legalabb": leg, "valaszto": e["lap"],
                    "allapot": allapot, "kulcs": f"{sor.kulcs} › {t.kulcs}"})
        ki += _kifejt(uj, technikak, figy, ut + (v,))
    return ki


def _hivas_sorok(sorok: list[JSor], technikak: dict, figy: list[str], kezdo: int) -> list[Sor]:
    """
    A menet közbeni hívás lapválasztói a rácsból: a VEDO_HIV cella 1. jele
    (pl. ATTITUD, LAPSZAM) + a MODSZER/<jel> sor `hivas:` esetei + technikák.
    """
    modszer = {s.adat["modszer"]: s for s in sorok if s.alak == "MODSZER"}
    ki: list[Sor] = []
    for s in sorok:
        a = s.adat
        if s.alak != "RACS" or a["racs"] != "VEDO_HIV" or a["sorrend"] != 1:
            continue
        m = modszer.get(a["jel"])
        if m is None or not m.adat.get("hivas"):
            figy.append(f"a menet közbeni hívás jele {a['jel']}, de a MODSZER/{a['jel']} "
                        "nem mondja meg, melyik lapot hívjuk (`hivas:`)")
            continue
        allapot = next((x.allapot for x in (s, m) if x.allapot != "ELFOGADOTT"), "ELFOGADOTT")
        for e in m.adat["hivas"]:
            h = _metszet(_hossz(a.get("hossz")), _hossz(e.get("hossz")))
            if h is None:
                continue
            alap = Sor(helyzet="HIVAS", felvetel=a["felvetel"], minta=Minta.parse("*"),
                       valaszto=e["lap"], cel=_JEL_CEL.get(a["jel"], "FIG"), hossz=h,
                       legalabb=e.get("legalabb"), allapot=allapot,
                       megjegyzes=f"menet közben: {_JEL_SZOVEG[a['jel']]}",
                       eredet=s.eredet, kulcs=f"{s.kulcs} › {m.kulcs}")
            for x in _kifejt(alap, technikak, figy):
                ki.append(Sor(**{**x.__dict__, "sorrend": kezdo + len(ki)}))
    return ki


# --- A rendszer profilja (a licitrendszer YAML-jában: `jelzesek:`) ------------

def profil_kod(d, hely: str = "?") -> str | None:
    """`jelzesek: MOHA_STAND` vagy `jelzesek: {rendszer: MOHA_STAND}`."""
    if not d:
        return None
    if isinstance(d, str):
        kod = d
    elif isinstance(d, dict) and d.get("rendszer"):
        kod = str(d["rendszer"])
    else:
        raise JelzesHiba(f"{hely}: `jelzesek: KOD` vagy `jelzesek: {{rendszer: KOD}}`")
    if not _KOD.fullmatch(kod):
        raise JelzesHiba(f"{hely}: hibás jelzésrendszer-kód: {kod!r}")
    return kod


# --- Emberi nyelvű sorleírás (CLI, szerkesztő) --------------------------------

_HELYZET_SZOVEG = {"INDITAS": "Indítás", "PARTNER_SZINE": "A partner színében",
                   "HIVAS": "Menet közbeni hívás", "MASODIK_KEZ": "Második kézben (színadás)"}
_FELV_SZOVEG = {"SZIN": "szín ellen", "SZAN": "szan ellen", "*": "szín és szan ellen"}
_RACS_SZOVEG = {"PARTNER_INDIT": "a partner indít", "FELVEVO_HIV": "a felvevő hív",
                "VEDO_HIV": "menet közben mi hívunk",
                "DOBAS": "első dobás"}
_JEL_SZOVEG = {"KERES": "kérés", "ATTITUD": "attitűd", "LAPSZAM": "lapszám",
               "MARADEK": "maradék lapszám",
               "PREF": "preferencia", "SMITH": "Smith"}
_VALASZTO_SZOVEG = {
    "LEGKISEBB": "a legkisebb", "LEGNAGYOBB": "a legnagyobb", "NAGYOBB": "a nagyobb",
    "LEGNAGYOBB_NELKULOZHETO": "a legnagyobb nélkülözhető",
    "LEGNAGYOBB_KISLAP": "a legnagyobb kis lap",
    "SOROZAT_TETEJE": "a sorozat teteje"}


def esetek_szoveg(esetek: list[dict]) -> str:
    """[{hossz, legalabb, lap}] -> "6+ lapból felülről a 3.; 5 lapból a legkisebb; …"."""
    reszek = []
    for e in esetek:
        felt = []
        if e.get("hossz"):
            felt.append(f"{e['hossz']} lapból")
        if e.get("legalabb"):
            felt.append("figurával" if e["legalabb"] == "J" else f"legalább {szep(e['legalabb'])}-sal")
        reszek.append((" ".join(felt) + " " if felt else ("különben " if reszek else ""))
                      + valaszto_szoveg(e["lap"]))
    return "; ".join(reszek)


def valaszto_szoveg(v: str) -> str:
    m = re.fullmatch(r"PARATLAN_PAROS\((.+);(.+)\)", v)
    if m:
        return (f"páratlanból {valaszto_szoveg(m.group(1))}, "
                f"párosból {valaszto_szoveg(m.group(2))}")
    m = re.fullmatch(r"FELULROL\((\d+)\)", v)
    if m:
        return f"felülről a {m.group(1)}."
    if v in _VALASZTO_SZOVEG:
        return _VALASZTO_SZOVEG[v]
    if technika_nev(v):
        return f"„{v}” (technika)"
    return szep(v)


def sor_szoveg(s: JSor) -> str:
    a = s.adat
    if s.alak == "LAP":
        felt = []
        if a.get("hossz"):
            felt.append(f"{a['hossz']} lap")
        if a.get("legalabb"):
            felt.append(f"van legalább {szep(a['legalabb'])}")
        if a.get("hezag"):
            lo, hi = _hezag(a["hezag"])
            felt.append("a 2. és 3. lap között "
                        + (f"legfeljebb {hi} hely" if lo == 0 else
                           f"legalább {lo} hely" if hi >= 11 else f"{lo}-{hi} hely"))
        if a.get("kontextus"):
            felt.append(a["kontextus"])
        if a.get("asztal"):
            felt.append("az asztal " + ("előttünk (ő hívott)" if a["asztal"] == "ELOTTUNK"
                                        else "utánunk"))
        if a.get("kozbenso"):
            felt.append(f"az asztalon {a['kozbenso']} lap a 10-es és a figuránk között")
        if a.get("hivott"):
            felt.append("nagy lapot hívtak" if a["hivott"] == "NAGY" else "kis lapot hívtak")
        mintak = ", ".join(m.replace("T", "10").replace("Q", "D").replace("J", "B")
                           .replace("A", "Á") for m in a["minta"] if m != "*")
        return (("Kivétel (a(z) " + a["alol"] + " elv alól): " if s.fajta == "KIVETEL" else "")
                + f"{_HELYZET_SZOVEG[a['helyzet']]} {_FELV_SZOVEG[a['felvetel']]}"
                + (f" — {mintak}" if mintak else "")
                + (f" ({', '.join(felt)})" if felt else "")
                + f": {valaszto_szoveg(a['lap'])}")
    if s.alak == "RACS":
        t = (f"Jelzés: {_RACS_SZOVEG[a['racs']]}, {_FELV_SZOVEG[a['felvetel']]}"
             + (f" ({a['hossz']} lap)" if a.get("hossz") else "")
             + f", {a['sorrend']}.: {_JEL_SZOVEG[a['jel']]}")
        if a.get("mikor"):
            t += f" ({a['mikor']}"
            t += f"; különben {_JEL_SZOVEG[a['kulonben']]})" if a.get("kulonben") else ")"
        return t
    if s.alak == "MODSZER":
        from .kartya import MODSZER_SZOVEG     # a kártya szövegei (lusta import: körbe hivatkozna)
        cim = {"LAPSZAM_ALAP": "A lapszám alapja"}.get(a["modszer"], a["modszer"].capitalize()
                                                         if a["modszer"] not in _JEL_SZOVEG
                                                         else _JEL_SZOVEG[a["modszer"]])
        cim = cim[:1].upper() + cim[1:]
        t = f"Módszer — {cim}"
        if a.get("ertek"):
            ert = MODSZER_SZOVEG.get(a["modszer"], {}).get(a["ertek"], a["ertek"])
            t += f": {ert} [{a['ertek']}]"
        if a.get("hivas"):
            t += ("; " if a.get("ertek") else ": ") + "hívásnál " + esetek_szoveg(a["hivas"])
        return t
    if s.alak == "TECHNIKA":
        return (f"Technika — {a['technika']}: {esetek_szoveg(a['esetek'])}"
                + (f" ({a['szoveg']})" if a.get("szoveg") else ""))
    if s.alak == "KIHAGYAS":
        return f"Kihagyja az örökölt sort: {a['kihagy']}"
    if s.alak == "KOVETKEZTETES":
        kod = a["kovetkeztetes"]
        nev = {"LEGKISEBB_EGYENERTEKU": "harmadik-negyedik kézben az egyenértékűek legkisebbike",
               "LEGOLCSOBB_NYERO": "negyedik kézben a legolcsóbb nyerő lap",
               "FIGURA_SOROZAT": "a nem ütésre tett (dobott) figura zárt sorozat teteje, vagy szingli",
               "PARTNER_INDITASA": "az indító lap a megállapodás szerinti lap",
               "PARTNER_DOBASA": "az első dobás egy színben a dobási jel szerint kér vagy nem kér",
               "LICIT_PONTHATAR": f"a licit pontsávja {a.get('tures', 2)} pontig puha határ",
               "LICIT_KIZARAS": "amit a licitjével kizárt (pl. a passz: nem volt válaszereje)",
               "FELVETEL_HIHETO": "az önként licitált (kontrázatlan) gém és szlem jellemzően "
                                  "teljesíthető lappal megy: ahol a DD szerint bukik, kisebb súly "
                                  "(egy bukás: a súly, kettő vagy több: a négyzete)"
               }.get(kod, kod)
        kitol = {"PARTNER": "a partner", "ELLENJATEKOSOK": "az ellenjátékosok",
                 "FELVEVO": "a felvevő"}
        suly = a.get("suly", KOVETKEZTETES_SULY.get(kod, 0.0))
        sulyszoveg = ("; ami ellentmond, kizárjuk" if suly == 0 else
                      f"; pontonként {suly:g} súllyal" if kod == "LICIT_PONTHATAR" else
                      f"; ami ellentmond, {suly:g} súllyal marad")
        return (f"Következtetés: {nev} — kitől: {', '.join(kitol[x] for x in a['kitol'])}"
                + sulyszoveg
                + ("; a kibic maga is így játszik" if a["sajat"] else "")
                + (f" — {a['szoveg']}" if a.get("szoveg") else ""))
    if s.alak == "MERLEGELES":
        nev = {"ATVETEL": "ha az elemzés szerint mindegy, a partner ütését nyerő lappal "
                          "átvesszük, és mi folytatjuk",
               "ASZ_ALOL": "színfelvétel ellen ász alól nem indulunk: az ásszal (a partner színében is)",
               "DUBLO_INDULAS": "színfelvétel ellen a dublóból indulás (figura nélkül) szlem és "
                                "szan-jellegű (nem lopásra épülő) felvétel ellen nem",
               "PARTNER_KERESE": "a partner kérése: a dobással kért színt hívjuk menet közben "
                                 "(és ütést veszünk érte: lopunk, átveszünk), a Smith-jele "
                                 "szerint váltunk vagy folytatjuk az indítás színét — ha az "
                                 f"elemzés szerint legfeljebb {a.get('tures', MERLEGELES_TURES['PARTNER_KERESE']):g} "
                                 "egységgel rosszabb (IMP-ben IMP, MP-ben ütés)"}.get(a["merlegeles"], a["merlegeles"])
        return (f"Mérlegelés: {nev}" + (f" — {a['szoveg']}" if a.get("szoveg") else ""))
    if s.alak == "SZINVALASZTAS":
        nev = {"PARTNER_SZINE": "a partner licitált színe"}.get(a["szinvalasztas"], a["szinvalasztas"])
        kiv = {"NINCS_LAP": "nincs lapunk benne", "KIS_SZINGLI": "egyetlen kis lap",
               "SAJAT_EROS_SZIN": "saját hosszú erős szín (szan ellen)",
               "LOPAS": "saját lopási esély rövid aduval (szín ellen)"}
        return (f"Indulás: {nev} elsőbbséget élvez, {_FELV_SZOVEG[a['felvetel']]}"
                + (f"; kivéve: {', '.join(kiv.get(x, x) for x in a['kiveve'])}" if a["kiveve"] else "")
                + (f" — {a['szoveg']}" if a.get("szoveg") else ""))
    if s.alak == "NINCS_JELZES":
        return (f"Nincs jelzés: {a['szint']} szintű kontraktus ellen, {_FELV_SZOVEG[a['felvetel']]}"
                + (f" — {a['szoveg']}" if a.get("szoveg") else ""))
    if s.fajta == "KIVETEL":
        cim = f"Kivétel (a(z) {a['alol']} elv alól)"
    elif s.fajta == "ELV":
        cim = "Elv"
    else:
        cim = {"KULONLEGES": "Különleges helyzet",
               "LICIT": "Indítást irányító licit"}.get(s.terulet or "", "Szabály")
    return f"{cim}{' (mérlegelő)' if a.get('merlegelo') else ''}: {a['szoveg']}"
