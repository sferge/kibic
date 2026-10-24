"""
Kritérium-kifejezésfa és háromértékű kiértékelő.

MIÉRT KELL: a lapos `kriterium_keszlet` (kötelező + min_teljesul) nem
tudja ábrázolni az egymásba ágyazott ÉS/VAGY feltételeket, amilyeneket
a valódi rendszerleírások használnak:

    1N: ((F[12,14])&(L4>1)&(5>L1)) o ((F[11,13])&(L4>1)&...)

A megoldás: ÁLTALÁNOS KIFEJEZÉSFA, ahol a `LEGALABB(m)` az egyik
csomóponttípus. Ettől
    ÉS       = LEGALABB(n)  minden gyerekre
    VAGY     = LEGALABB(1)
    TÖBBSÉG  = LEGALABB(ceil(n/2))
vagyis a "döntsön több értékelés többsége" gondolat NEM különleges
eset, hanem a nyelv elsőrangú eleme.

HÁROMÉRTÉKŰ LOGIKA: a kiértékelés IGAZ / HAMIS / ISMERETLEN lehet.
Az ISMERETLEN azért kell, mert néhány LICREN-jelző képlete még nem
tisztázott (P = pont, i = indulóerő, j = játékütés). Így ahelyett, hogy
rossz képlettel csendben rossz döntést hoznánk, MEGSZÁMOLHATÓ, hány
szabály nem dönthető el — és ez a szám mutatja, mennyit ér a hiányzó
tudás.

A fa JSON-ként tárolódik a `licitmenet.feltetel` oszlopban.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from ..domain import ERTEKELOK, Kez, SZINEK, beliben, vonal

# Az ISMERETLEN érték jelölése
ISMERETLEN = None


class KifejezesHiba(ValueError):
    pass


# --- Kontextus --------------------------------------------------------

@dataclass
class Kontextus:
    """
    Amit a kéz mellett tudni kell a kiértékeléshez.
    A `parametertar` a motor.kriterium.Parametertar példánya (opcionális).
    """
    ules: str = "N"
    beliallas: str = "NONE"
    parametertar: object = None
    # Nevesített kritérium-készletek, ha a fa hivatkozik rájuk
    keszletek: dict = field(default_factory=dict)
    # A licithelyzet (motor.helyzet.Allas). Ez teszi lehetővé, hogy a
    # KÉZ-feltétel küszöbe a HELYZETTŐL függjön: "a szkórhelyzetnek és a
    # magasságnak megfelelő erő" nem fix szám.
    allas: object = None
    # A MINTÁBÓL hozott színkötések: M -> 'H', I1 -> 'C', V1 -> 'H', ...
    # Enélkül a kéz-feltétel nem tud a mintában kötött színről beszélni:
    # az `1M-2M` szabály feltétele csak konkrét színt nevezhetne meg,
    # holott épp az a lényeg, hogy AMIT a partner mondott.
    kotesek: dict = field(default_factory=dict)
    # LOGIKAI metrikák feloldása konkrét értékelőre.
    # A `@PONT` alakú hivatkozás azt jelenti: "az a metrika, amit ez a
    # rendszer 'pont' alatt ért". Így a LICREN `P` jelzője nem beégetett
    # képlet, hanem MÉRHETŐ választás: több jelölt közül a rendszer
    # (vagy a mérés) dönti el, melyik.
    metrika: dict = field(default_factory=dict)
    # FOLYTATÁS "mint X után": a pontfeltétel eltolása (lásd
    # minta.alias_elozmenyek) — a figurapont ennyivel többnek számít
    pont_eltolas: float = 0.0

    @property
    def szkorhelyzet(self) -> str:
        """
        A LICREN @M / @A / @S / @O jelölése:
          M = mindkét vonal beliben
          A = egyik sem
          S = csak MI vagyunk beliben (kedvezőtlen)
          O = csak ŐK vannak beliben (kedvező)
        """
        mi = beliben(self.ules, self.beliallas)
        ok = beliben("E" if vonal(self.ules) == "NS" else "N", self.beliallas)
        if mi and ok:
            return "M"
        if not mi and not ok:
            return "A"
        return "S" if mi else "O"


def rendszer_kontextus(paramtar, **tovabbi) -> "Kontextus":
    """
    Kontextus a rendszer paramétereiből: paramétertár + a logikai
    metrikák (@PONT, @JATEKUTES, @INDULOERO) feloldása + a nevesített
    kritérium-készletek fái.

    E nélkül a `@PONT`-ra hivatkozó szabály ELDÖNTHETETLEN (a metrika
    üres kódra oldódik), és a licitmotor csendben nem ad jelöltet.
    """
    metrika = {}
    keszletek = {}
    if paramtar is not None:
        if hasattr(paramtar, "metrika_terkep"):
            metrika = paramtar.metrika_terkep()
        keszletek = dict(getattr(paramtar, "keszletfak", {}) or {})
    return Kontextus(parametertar=paramtar, metrika=metrika,
                     keszletek=keszletek, **tovabbi)


def _adu(ktx) -> str | None:
    allas = getattr(ktx, "allas", None)
    return allas.adu() if allas is not None and allas.kenyszertar else None


def _partner_igeret(ktx):
    allas = getattr(ktx, "allas", None)
    if allas is None or not allas.kenyszertar:
        return None
    return allas.kenyszertar.get(allas.partner)


def gemesely(kez: Kez, ig) -> bool:
    """
    Van-e gémesély (2026-10-02, Moha) — a partner ígért sávjának bármely
    pontértékével, figurapontban:

      * nemes fittel (a saját lapjaim + a partner ígért minimuma >= 8): 25;
      * minor fittel: 27 (eggyel több ütés kell);
      * szanban: 24, ha a pontok nagyjából egyenlően oszlanak (12-12, legfeljebb
        14-10); nagyobb eltérésnél „plusz” kell: 15-9-től 5-ös szín, 19-5
        (20-4)-től 6-os, 7-es (húzós) szín — a saját kezemben vagy a partner
        ígéretében.
    """
    from ..domain import ERTEKELOK
    sajat = int(round(float(ERTEKELOK["HCP"](kez))))
    lo, hi = int(ig.pont_min), int(min(ig.pont_max, 37))
    hosszu = max(max(kez.hossz(sz) for sz in "CDHS"),
                 max(ig.hossz(sz)[0] for sz in "CDHS"))
    fit_nemes = any(kez.hossz(m) + ig.hossz(m)[0] >= 8 for m in "HS")
    fit_minor = any(kez.hossz(m) + ig.hossz(m)[0] >= 8 for m in "CD")
    for p in range(lo, hi + 1):
        ossz = sajat + p
        if fit_nemes and ossz >= 25:
            return True
        if fit_minor and ossz >= 27:
            return True
        if ossz >= 24:
            elteres = abs(sajat - p)
            if elteres <= 4 or (elteres <= 13 and hosszu >= 5) or hosszu >= 6:
                return True
    return False


def partner_fedo(ktx, kez: Kez | None = None,
                 becsult: bool = False) -> tuple[float, float | None]:
    """
    A partner fedőütése a kényszertárból: (legalább, legfeljebb).

    ALSÓ korlát: a kimondott fedő (és a kulcslicitek összege); a pontjából
    is: ász és király nélkül legfeljebb 12 figurapont lehet (4 dáma, 4
    bubi), minden további 4 pont legalább egy ászt vagy királyt jelent;
    és a TUDOTT RÖVIDSÉGE (pl. splinter): ahol neki szingli van, ott az
    én vesztőimből csak 1 marad, sikénnél 0 — a szerkesztő példája: xxx
    a szingli mellett 2 fedő.
    És a SZÍNRE ígért fedő (pl. a 2/1 után lassan emelő válaszoló első
    színe: 1, de inkább 2): az én vesztőimből ott ennyi fedődik. A
    `becsult` (a biztonságos 5-ös szinthez) a valószínű értéket veszi, a
    szlemjelleg a biztosat — a szerkesztő: „xxx-et ne tekintsen 3
    vesztőnek; a 2, de akár az 1 vesztő sem irracionális”.
    FELSŐ becslés: a kimondott fedő; különben a pontjából (pont/3, nyitott
    sávnál a minimum + 6 pontból) — ez csak becslés.
    """
    ig = _partner_igeret(ktx)
    if ig is None:
        return 0.0, None
    lo = max(ig.fedo_min, math.ceil(max(0.0, ig.pont_min - 12) / 4))
    if kez is not None:
        adu = _adu(ktx)
        for sz in ("S", "H", "D", "C"):
            if sz == adu:
                continue
            rovid = ig.hossz(sz)[1]
            if rovid <= 1:
                lo += max(0.0, vesztok(kez, sz) - rovid)
            elif sz in ig.szin_fedo:
                f = ig.szin_fedo[sz][1 if becsult else 0]
                lo += min(vesztok(kez, sz), f)
    if ig.fedo_max < 99:
        return lo, max(lo, ig.fedo_max)
    if ig.pont_max < 40:
        return lo, max(lo, ig.pont_max / 3)
    if ig.pont_min > 0:
        # nyitott felső határ (pl. 2/1 gémforsz: 12+): a VALÓSZÍNŰ lap a
        # minimum + 6 pont körül van — becslés, a partner "legvalószínűbb keze"
        return lo, max(lo, (ig.pont_min + 6) / 3)
    return lo, None


def szlemjelleg(kez: Kez, ktx) -> str | None:
    """
    "igen" / "talan" / "nem" — a Moha szlem-elve: maradék vesztő = a saját
    vesztőim − a partner fedői. A szlemhez 1-nél KEVESEBB maradhat (a gémnél
    az 1 hiányzó ütés vállalható kockázat, a szlemnél nem).
      igen: a partner legkevesebb fedőjével is < 1 marad
      nem:  a partner legtöbb fedőjével is >= 1 marad
      talan: a kettő között
    """
    if _adu(ktx) is None:
        return None
    sajat = vesztok(kez)
    lo, hi = partner_fedo(ktx, kez)
    if sajat - lo < 1:
        return "igen"
    if hi is not None and sajat - hi >= 1:
        return "nem"
    return "talan"


def ot_biztos(kez: Kez, ktx, min_pont: float = 30, mod: str | None = None) -> bool | None:
    """Biztonságos-e az 5-ös szint: tudottan sok pont (a saját + a partner
    ígért minimuma >= 30), VAGY tudottan kevés vesztő (legfeljebb 2 marad
    a partner legkevesebb fedőjével).

    `mod="vesztok"` (az exclusion, a szerkesztő, 2026-10-21): a VESZTŐK
    összegével is — a partner legtöbb vesztője a pontminimumából (13 pont
    ~ 7, 16 ~ 6, 7 ~ 9 vesztő); ha a kettő összege legfeljebb 13, akkor
    24 − összeg >= 11 ütés: az 5-ös szint nem kockázatos."""
    ig = _partner_igeret(ktx)
    if ig is None:
        return None
    fv = ERTEKELOK.get("HCP")
    if fv is not None and float(fv(kez)) + ig.pont_min >= min_pont:
        return True
    lo, _ = partner_fedo(ktx, kez, becsult=True)
    if vesztok(kez) - lo <= 2:
        return True
    if mod == "vesztok":
        p_vesztok = min(10.0, max(4.0, 34 / 3 - ig.pont_min / 3))
        return vesztok(kez) + p_vesztok <= 13
    return False


def _kotott_szin(sz, ktx) -> str | None:
    """Konkrét szín marad; a "@X" változó a kötéséből; kötetlen: None."""
    if isinstance(sz, str) and sz.startswith("@"):
        from .minta import szin_kotesbol      # a származtatott is (oM, om)
        return szin_kotesbol(sz[1:], ktx.kotesek)
    return sz


# --- Fedőütés -----------------------------------------------------------

def fedoutes(kez: Kez, adu: str) -> float:
    """
    Fedőütés a Moha-kör szerint (2026-09-30; a Standard American, Győr
    2002 meghatározásából kiindulva).

    Biztos:      minden ász és minden király 1; az adu dáma 1; külső
                 színben a szingli 1, a sikén 2.
    Bizonytalan: külső színben a dubló 0.5; a DBx (dáma bubival, ász és
                 király nélkül, 3+ lap) 0.5; a Dxx (dáma ász, király és
                 bubi nélkül, 3+ lap) 0.25.
    """
    ertek = 0.0
    for sz in ("S", "H", "D", "C"):
        lapok = {l.ertek for l in kez.lapok if l.szin == sz}
        n = kez.hossz(sz)
        ertek += ("A" in lapok) + ("K" in lapok)
        if sz == adu:
            ertek += "Q" in lapok
            continue
        ertek += {0: 2.0, 1: 1.0, 2: 0.5}.get(n, 0.0)
        if n >= 3 and "Q" in lapok and not lapok & {"A", "K"}:
            ertek += 0.5 if "J" in lapok else 0.25
    return ertek


def vesztok(kez: Kez, szin: str | None = None) -> float:
    """
    Vesztőütés (LTC) a Moha-kör szerint: színenként az első legfeljebb 3
    lapból hiányzó A, K, D (szinglinél csak az A, dublónál az A és a K
    számít). Eltérés a klasszikustól: a Dxx (dáma ász, király és bubi
    nélkül, 3+ lap) 2.5 vesztő, a DBx marad 2. `szin`: csak az az egy szín.
    """
    ossz = 0.0
    for sz in ((szin,) if szin else ("S", "H", "D", "C")):
        lapok = {l.ertek for l in kez.lapok if l.szin == sz}
        n = min(3, kez.hossz(sz))
        ossz += sum(1 for e in "AKQ"[:n] if e not in lapok)
        if n == 3 and "Q" in lapok and not lapok & {"A", "K", "J"}:
            ossz += 0.5
    return ossz


def ures_figura(kez: Kez) -> int:
    """
    A FELMENTÉS elv „rossz” jele (Moha, 2026-10-05): hány legfeljebb 3 lapos
    színben áll dáma vagy bubi ász és király nélkül (Dxx, Bxx, Dx, D, DBx …
    — a DB együtt egynek számít). Az ilyen figura ritkán ér annyit, amennyit
    a figurapont számol.
    """
    db = 0
    for sz in ("S", "H", "D", "C"):
        lapok = {l.ertek for l in kez.lapok if l.szin == sz}
        if kez.hossz(sz) <= 3 and lapok & {"Q", "J"} and not lapok & {"A", "K"}:
            db += 1
    return db


def dupla_fogas(kez: Kez, sz: str) -> bool:
    """Kétszeres fogás: az A, K, D közül kettő (AD, KD, AK …), vagy egy mellé a
    bubi legalább 3 lappal (KBx, ABx)."""
    lapok = {l.ertek for l in kez.lapok if l.szin == sz}
    fo = len(lapok & {"A", "K", "Q"})
    return fo >= 2 or (fo >= 1 and "J" in lapok and kez.hossz(sz) >= 3)


# --- Numerikus kifejezések -------------------------------------------

def _ertek(csp: dict, kez: Kez, ktx: Kontextus) -> float | None:
    """Egy numerikus részkifejezés értéke, vagy None, ha ismeretlen."""
    t = csp.get("t")

    if t == "SZAM":
        return float(csp["v"])

    if t == "PARAM":
        # a paraméter (rendszer / pár szerint), vagy ha nincs megadva, az
        # `alap`; `eltolas`: hozzáadandó (pl. -1: eggyel kevesebb)
        pt = ktx.parametertar
        v = None
        if pt is not None:
            try:
                v = float(pt.ertek(csp["kod"]))
            except Exception:      # noqa: BLE001
                v = None
        if v is None and "alap" in csp:
            v = float(csp["alap"])
        return None if v is None else v + float(csp.get("eltolas", 0))

    if t == "ISMERETLEN":          # tisztázatlan képletű jelző
        return None

    if t == "HELYZET":             # helyzetfüggő küszöb (motor/helyzet.py)
        if ktx.allas is None:
            return None            # helyzet nélkül nem eldönthető
        from .helyzet import ertek as helyzet_ertek
        return helyzet_ertek(csp["kif"], ktx.allas, ktx.parametertar)

    if t == "ERT":                 # lapértékelő metrika
        kod = csp["kod"]
        if kod.startswith("@"):    # logikai hivatkozás, pl. @PONT
            kod = ktx.metrika.get(kod[1:], "")
        fv = ERTEKELOK.get(kod)
        if fv is None:
            return None
        v = float(fv(kez)) * float(csp.get("szorzo", 1))
        if kod == "HCP" and getattr(ktx, "pont_eltolas", 0):
            v += ktx.pont_eltolas
        return v

    if t == "SZIN":                # egy szín hossza (konkrét vagy kötött)
        sz = csp["szin"]
        if isinstance(sz, str) and sz.startswith("@"):
            from .minta import szin_kotesbol
            sz = szin_kotesbol(sz[1:], ktx.kotesek)
            if sz is None:
                return None        # kötetlen változó: ISMERETLEN
        return float(kez.hossz(sz))

    if t == "SZINFIG":             # figurapont EGY színben (konkrét vagy kötött)
        sz = csp["szin"]
        if isinstance(sz, str) and sz.startswith("@"):
            sz = ktx.kotesek.get(sz[1:])
            if sz is None:
                return None
        sulyok = {"A": 4, "K": 3, "Q": 2, "J": 1}
        return float(sum(sulyok.get(l.ertek, 0) for l in kez.lapok
                         if l.szin == sz))

    if t == "FEDO":                # fedőütés az `adu` szín mellett
        adu = csp["adu"]
        if isinstance(adu, str) and adu.startswith("@"):
            adu = ktx.kotesek.get(adu[1:])
            if adu is None:
                return None        # kötetlen adu: ISMERETLEN
        return fedoutes(kez, adu)

    if t in ("KULCSLAP", "ADU_DAMA"):
        # A megállapodott adu (a kényszertárból) mellett: kulcslap = a 4 ász
        # és az adu király; adu dáma = 1, ha nála van.
        allas = getattr(ktx, "allas", None)
        adu = csp.get("adu")               # a licitből adott adu (kulcs_adu)
        if isinstance(adu, str) and adu.startswith("@"):
            adu = ktx.kotesek.get(adu[1:])
        elif adu is None:
            adu = allas.adu() if allas is not None and allas.kenyszertar else None
        if adu is None:
            return None
        lapok = {(l.szin, l.ertek) for l in kez.lapok}
        if t == "ADU_DAMA":
            return 1.0 if (adu, "Q") in lapok else 0.0
        kizart = csp.get("kizart")         # EXCLUSION: ennek a színnek az ásza nem számít
        if isinstance(kizart, str) and kizart.startswith("@"):
            kizart = ktx.kotesek.get(kizart[1:])
        return float(sum(1 for l in kez.lapok if l.ertek == "A" and l.szin != kizart)
                     + ((adu, "K") in lapok))

    if t == "MARADEK_VESZTO":      # saját vesztők − a partner biztos fedői (rövidség is)
        return vesztok(kez) - partner_fedo(ktx, kez)[0]

    if t == "OSSZESEN":            # saját AP (vagy FP) + a partner ígért maximuma (vagy minimuma)
        ig = _partner_igeret(ktx)
        if ig is None or (ig.pont_max >= 40 and not csp.get("biztos")):
            return None
        partner_resz = ig.pont_min if csp.get("biztos") else ig.pont_max
        if csp.get("mit") == "AP":
            adu = _kotott_szin(csp.get("adu", "@M"), ktx)
            if adu is None:
                kod = "AP_531" if csp.get("biztos") else None   # kötetlen adu: a (feltételezett) fit mellett
                if kod is None:
                    return None
            else:
                kod = "AP_531" if kez.hossz(adu) >= 4 else "AP_321"
        else:
            kod = "HCP"
        fv = ERTEKELOK.get(kod)
        return None if fv is None else float(fv(kez)) + partner_resz

    if t == "FIT_HOSSZ":           # saját hossz + a partner BIZTOSAN ígért minimuma
        sz = _kotott_szin(csp["szin"], ktx)
        ig = _partner_igeret(ktx)
        if sz is None or ig is None:
            return None
        return float(kez.hossz(sz) + ig.hossz(sz)[0])

    if t == "URES_FIGURA":         # üres dáma/bubi (ász és király nélkül) a legfeljebb 3 lapos színekben
        return float(ures_figura(kez)) * float(csp.get("szorzo", 1))

    if t == "KORR_PONT":           # FELMENTÉS: FP + hosszúsági pont (5+ lapos szín) − levonás × üres figura
        fv = ERTEKELOK.get("P_HOSSZ")
        if fv is None:
            return None
        return float(fv(kez)) - float(csp.get("levonas", 0.5)) * ures_figura(kez)

    if t == "VESZTO":              # vesztőütés: az egész kéz, vagy egy szín
        sz = csp.get("szin")
        if isinstance(sz, str) and sz.startswith("@"):
            sz = ktx.kotesek.get(sz[1:])
            if sz is None:
                return None
        return vesztok(kez, sz)

    if t == "HOSSZ":               # L1..L4: rendezett színhosszak
        rang = int(csp["rang"])
        return float(sorted(kez.hosszak, reverse=True)[rang - 1])

    if t == "FIG":                 # f1..f4: figurapont az n-edik rangú színben
        fv = ERTEKELOK.get(f"F{int(csp['rang'])}")
        return float(fv(kez)) if fv else None

    if t == "LAP":                 # vXY: 1, ha nála van a lap
        jel = csp["lap"]
        if jel.startswith("@"):    # "@A:A" — az A változó színének ásza
            valt, ertek = jel[1:].split(":")
            from .minta import szin_kotesbol      # a származtatott is (oM, om)
            sz = szin_kotesbol(valt, ktx.kotesek)
            if sz is None:
                return None
            jel = sz + ertek
        return 1.0 if any(f"{l.szin}{l.ertek}" == jel for l in kez.lapok) else 0.0

    if t == "HA":
        # Feltételes numerikus tag. Ezzel írható le olyan elosztási
        # megfontolás, mint "a rövid treff jobb, mint a rövid káró":
        # nem küszöb, hanem SÚLY, ami az alkalmassági összegbe megy.
        e = kiertekel(csp["felt"], kez, ktx)
        if e is None:
            return None
        ag = csp.get("akkor", 1) if e else csp.get("kulonben", 0)
        return _ertek(ag, kez, ktx) if isinstance(ag, dict) else float(ag)

    if t == "OSSZEG":
        jelek = csp.get("jelek") or [1] * (len(csp["gy"]) - 1)
        ossz = _ertek(csp["gy"][0], kez, ktx)
        if ossz is None:
            return None
        for jel, gyerek in zip(jelek, csp["gy"][1:]):
            e = _ertek(gyerek, kez, ktx)
            if e is None:
                return None
            ossz += jel * e
        return ossz

    raise KifejezesHiba(f"Ismeretlen kifejezés-típus: {t!r}")


# --- Logikai csomópontok (háromértékű) -------------------------------

def kiertekel(csp: dict, kez: Kez, ktx: Kontextus | None = None) -> bool | None:
    """
    A fa kiértékelése. Visszaad: True / False / None (=ISMERETLEN).

    Kleene-logika:
      ÉS   -> False, ha bármelyik False; None, ha van None és nincs False
      VAGY -> True, ha bármelyik True; None, ha van None és nincs True
      LEGALABB(m) -> True, ha az IGAZAK száma >= m
                     False, ha IGAZ + ISMERETLEN < m
                     különben None
    """
    ktx = ktx or Kontextus()
    t = csp.get("t")

    if t in ("ES", "VAGY", "LEGALABB"):
        gyerekek = [kiertekel(g, kez, ktx) for g in csp["gy"]]
        n = len(gyerekek)
        if t == "ES":
            m = n
        elif t == "VAGY":
            m = 1
        else:
            m = int(csp.get("m", math.ceil(n / 2)))
        igaz = sum(1 for g in gyerekek if g is True)
        ismeretlen = sum(1 for g in gyerekek if g is None)
        if igaz >= m:
            return True
        if igaz + ismeretlen < m:
            return False
        return None

    if t == "NEM":
        e = kiertekel(csp["gy"][0], kez, ktx)
        return None if e is None else (not e)

    if t == "KULONBOZO":           # két színváltozó más-más színt jelöl
        a = _kotott_szin(csp["a"], ktx)
        b = _kotott_szin(csp["b"], ktx)
        if a is None or b is None:
            return True            # kötetlen (pl. nincs adu): nincs ütközés
        return a != b

    if t == "IGERET_FELE":         # a lapom az eddig ÍGÉRT sávom alsó/felső felében
        allas = getattr(ktx, "allas", None)
        tar = getattr(allas, "kenyszertar", None) if allas is not None else None
        ig = tar.get(allas.ules) if tar else None
        if ig is None or not ig.nyilatkozott:
            return None
        if csp["mit"] == "AP":
            lo, hi = ig.ap_min, ig.ap_max
            adu = _kotott_szin(csp.get("adu", "@M"), ktx)
            if adu is None:
                return None
            kod = "AP_531" if kez.hossz(adu) >= 4 else "AP_321"
        else:
            lo, hi = ig.pont_min, ig.pont_max
            kod = "HCP"
        if hi >= 40 and (csp["fele"] == "max" or lo <= 0):
            return None            # nincs felső korlát: nincs "teteje"
        fv = ERTEKELOK.get(kod)
        if fv is None:
            return None
        # nyitott sáv (pl. 2/1 gémforsz: 12+): a "minimális" lap a sáv alja
        # + 2 (12-14); fölötte "plusz erő" (a gyors-lassú elvhez).
        # SZÉLES sáv (7+ pont, pl. 1M 11-21): a határ a sáv 35%-ánál (11-14
        # a minimum), nem a közepén — a szerkesztő, 2026-09-30. A `hatar`
        # (0-1) szabályonként felülírja.
        if hi >= 40:
            kozep = lo + 2.5
        else:
            arany = csp.get("hatar")
            if arany is None:
                arany = 0.35 if hi - lo >= 7 else 0.5
            kozep = lo + (hi - lo) * float(arany)
        ertek = float(fv(kez))
        if csp["fele"] == "max":   # a sáv teteje (maximum)
            return ertek >= hi
        return ertek <= kozep if csp["fele"] == "also" else ertek > kozep

    if t == "LICIT_ALATT":         # a most definiált licit a határ alatt van
        from .licital import licit_rang
        licit = ktx.kotesek.get("_licit")
        if csp.get("gem"):         # a határ a megállapodott adu (vagy a megadott szín) géme
            adu = (_kotott_szin(csp["szin"], ktx) if csp.get("szin") else _adu(ktx))
            if licit is None or adu is None:
                return None
            nemes = adu in ("H", "S")
            gem = licit_rang(f"4{adu}" if nemes else f"5{adu}")
            lez = licit_rang(f"3{adu}" if nemes else f"4{adu}")   # a GI szintje
            r = licit_rang(licit)
            otos = licit_rang(f"5{adu}")
            return {"alatt": r < gem, "felett": r > gem, "pont": r == gem,
                    "lezaras_alatt": r < lez, "otos_alatt": r < otos}[csp.get("mod", "alatt")]
        sz = _kotott_szin(csp["szin"], ktx) if csp["szin"] != "NT" else "NT"
        if licit is None or sz is None:
            return None
        return licit_rang(licit) < licit_rang(f"{csp['szint']}{sz}")

    if t == "NEM_ADU":             # a színváltozó nem a megállapodott adu
        sz, adu = _kotott_szin(csp["szin"], ktx), _adu(ktx)
        return None if sz is None or adu is None else sz != adu

    if t == "AZ_ADU":              # a színváltozó épp a megállapodott adu
        sz, adu = _kotott_szin(csp["szin"], ktx), _adu(ktx)
        return None if sz is None or adu is None else sz == adu

    if t == "NEM_RKC":             # a licit nem a kulcslapkérdés (4♠ kőr adunál …)
        licit, adu = ktx.kotesek.get("_licit"), _adu(ktx)
        if licit is None or adu is None:
            return True
        return licit != {"H": "4S", "S": "4NT", "C": "4C", "D": "4D"}[adu]

    if t == "SZLEMJELLEG":         # a Moha szlem-elve (doc/moha-elvek.md)
        e = szlemjelleg(kez, ktx)
        if e is None:
            return None
        cel = csp["ertek"]
        return e != "nem" if cel == "nem_kizart" else e == cel

    if t == "GEMESELY":            # van-e gémesély a partner ígért sávjával (gemesely())
        ig = _partner_igeret(ktx)
        if ig is None or not ig.nyilatkozott:
            return False           # a partner nem mondott semmit: nincs mire építeni
        # 2026-10-04: a nyitott felső határ (pl. a 2/1 „11+”) nem jelenti, hogy
        # nincs gémesély — a minimummal is számolni kell (a gemesely 37-ig vág)
        allas = getattr(ktx, "allas", None)
        v = (getattr(allas, "valoszinu", None) or {}).get(allas.partner) if allas else None
        if v is not None:          # amit a partner NEM licitált: valószínű felső határ
            from .kovetkeztetes import szukitett_tar
            ig = szukitett_tar({"p": ig}, {"p": v})["p"]
        return gemesely(kez, ig)

    if t == "MISFIT":              # 0-1 lap a partner tudott 5+ lapos színében (2026-10-23)
        ig = _partner_igeret(ktx)
        if ig is None:
            return None
        return any(ig.hossz(sz)[0] >= 5 and kez.hossz(sz) <= 1 for sz in ("S", "H", "D", "C"))

    if t == "SPLINTER_FIT":        # feltételezett 8 lapos fit a partner (tudott) nemesében
        allas = getattr(ktx, "allas", None)
        licit = ktx.kotesek.get("_licit")
        if allas is None or not allas.kenyszertar or not licit or len(licit) < 2:
            return None
        b = licit[1:]
        p = allas.kenyszertar[allas.partner]
        return any(m != b and p.hossz(m)[0] >= 4 and kez.hossz(m) + p.hossz(m)[0] >= 8
                   for m in ("H", "S"))

    if t == "FOGAS_MARADEK":       # fogásom van minden még le nem fedett színben
        from .helyzet import SZINEK as _SZ, fogas_kezben
        allas = getattr(ktx, "allas", None)
        if allas is None or not getattr(allas, "kenyszertar", None):
            return None
        fedett = allas.fedett_szinek("mi", bool(csp.get("termeszetes", True)))
        return all(fogas_kezben(kez, sz) for sz in _SZ if sz not in fedett)

    if t == "LEGHOSSZABB_PARTNER_SZIN":   # a partner (4+) színei közül ebben vagyok a leghosszabb
        sz = _kotott_szin(csp["szin"], ktx)
        allas = getattr(ktx, "allas", None)
        if sz is None or allas is None or not getattr(allas, "kenyszertar", None):
            return None
        p = allas.kenyszertar[allas.partner]
        szinei = [x for x in ("S", "H", "D", "C") if p.hossz(x)[0] >= 4]
        if sz not in szinei:
            return False
        return all(kez.hossz(sz) >= kez.hossz(x) for x in szinei)

    if t == "EROS_FOGAS":          # biztos fogás: ász, kétszeres, vagy 3+ lapos (Kxx); a Kx nem
        sz = _kotott_szin(csp["szin"], ktx)
        if sz is None:
            return None
        from .helyzet import fogas_kezben
        lapok = {l.ertek for l in kez.lapok if l.szin == sz}
        return ("A" in lapok or dupla_fogas(kez, sz)
                or (kez.hossz(sz) >= 3 and fogas_kezben(kez, sz)))

    if t == "GEM_ESELYTELEN":      # a gémforsz megszűnése (KENYSZER elv, 2026-10-12)
        # KÖZÖSEN tudott: fogást kértem (HELP), a partner nem mutatott benne
        # fogást (nem szant mondott, és nem ígért ott fogást) — a 3NT nem
        # megy; nemes fit nincs (4-3 sem: mindkettőnknél 3+ és együtt
        # nemes_fit_min+). A SAJÁT döntés: a pontom + a partner ígért
        # minimuma az 5 minorhoz kevés (minor_gem_ero alatt).
        allas = getattr(ktx, "allas", None)
        if allas is None or not getattr(allas, "kenyszertar", None):
            return None
        en = allas.kenyszertar[allas.ules]
        p = allas.kenyszertar[allas.partner]
        hsz = getattr(en, "help_szin", None)
        if not hsz:
            return False
        i_en, utolsom = allas.utolso_licit(allas.ules)
        i_p, valasz = allas.utolso_licit(allas.partner)
        if not utolsom or utolsom[1:] != hsz or not valasz or i_p < i_en:
            return False                       # nem a HELP-re felelt a partner
        if valasz.endswith("NT") or hsz in (getattr(p, "fogas", set()) or set()):
            return False                       # fogást mutatott: a 3NT megy
        fit_min = int(csp.get("nemes_fit_min", 7))
        for m in ("H", "S"):
            sajat, pmin = kez.hossz(m), p.hossz(m)[0]
            if sajat >= 3 and pmin >= 3 and sajat + pmin >= fit_min:
                return False                   # van játszható nemes fit
        fv = ERTEKELOK.get("HCP")
        if fv is None:
            return None
        return float(fv(kez)) + float(p.pont_min) < float(csp.get("minor_gem_ero", 27))

    if t == "HELP_FOGAS":          # van fogásom a partner HELP-színében
        from .helyzet import fogas_kezben
        allas = getattr(ktx, "allas", None)
        if allas is None or not getattr(allas, "kenyszertar", None):
            return None
        hsz = getattr(allas.kenyszertar[allas.partner], "help_szin", None)
        return None if not hsz else fogas_kezben(kez, hsz)

    if t == "GYENGE_FOGAS":        # valamelyik ígért fogásom gyenge (nem ász, nem kétszeres)
        allas = getattr(ktx, "allas", None)
        if allas is None or not getattr(allas, "kenyszertar", None):
            return None
        en = allas.kenyszertar[allas.ules]
        for sz in getattr(en, "fogas", set()) or set():
            lapok = {l.ertek for l in kez.lapok if l.szin == sz}
            if "A" not in lapok and not dupla_fogas(kez, sz):
                return True
        return False

    if t == "KETSEG":              # a partner rövid (0-1) egy színben, amit nem fogok kétszeresen
        allas = getattr(ktx, "allas", None)
        if allas is None or not getattr(allas, "kenyszertar", None):
            return None
        p = allas.kenyszertar[allas.partner]
        termeszetes = allas.termeszetes_szinek("mi")
        for sz in ("S", "H", "D", "C"):
            if p.hossz(sz)[1] <= 1 and sz not in termeszetes and not dupla_fogas(kez, sz):
                return True
        return False

    if t == "NINCS_FIT":           # színtalálkozás nincs: sehol sincs `min`+ lap együtt
        allas = getattr(ktx, "allas", None)
        if allas is None or not getattr(allas, "kenyszertar", None):
            return None
        p = allas.kenyszertar[allas.partner]
        mn = int(csp.get("min", 8))
        szinek = ("S", "H") if csp.get("szinek", "nemes") == "nemes" else ("S", "H", "D", "C")
        # színtalálkozás: a partner ígért a színben (2+), és együtt megvan a `min`
        return not any(p.hossz(sz)[0] >= 2 and kez.hossz(sz) + p.hossz(sz)[0] >= mn
                       for sz in szinek)

    if t == "LEGHOSSZABB":         # ez (az egyik) leghosszabb színe
        sz = _kotott_szin(csp["szin"], ktx)
        if sz is None:
            return None
        return kez.hossz(sz) >= max(kez.hossz(x) for x in ("S", "H", "D", "C"))

    if t == "ONALLO_ADU":          # a partner sikénjével szemben is legfeljebb 1 aduvesztő
        from .adu_esely import ALAP_KUSZOB, onallo_adu
        sz = _kotott_szin(csp["szin"], ktx)
        if sz is None:
            return None
        return onallo_adu(kez, sz, float(csp.get("kuszob", ALAP_KUSZOB)))

    if t == "KONTROLLOK":          # minden külső színben van kontroll (A, K, sikén, szingli)
        adu = _adu(ktx)
        if adu is None:
            return None
        for sz in ("S", "H", "D", "C"):
            if sz == adu:
                continue
            lapok = {l.ertek for l in kez.lapok if l.szin == sz}
            if kez.hossz(sz) > 1 and not lapok & {"A", "K"}:
                return False
        return True

    if t == "OT_BIZTOS":           # az 5-ös szint biztonságos (sok pont / kevés vesztő)
        return ot_biztos(kez, ktx, float(csp.get("pont", 30)), csp.get("mod"))

    if t == "KESZLET":             # nevesített kritérium-készlet hívása
        kod = csp["kod"]
        if kod.startswith("@"):
            kod = ktx.metrika.get(kod[1:], "")
        k = ktx.keszletek.get(kod)
        if k is None:
            return None
        return kiertekel(k, kez, ktx)

    if t == "OSSZE":               # összehasonlítás
        bal = _ertek(csp["bal"], kez, ktx)
        jobb = _ertek(csp["jobb"], kez, ktx)
        if bal is None or jobb is None:
            return None
        op = csp["op"]
        if op == ">":
            return bal > jobb
        if op == "<":
            return bal < jobb
        if op == ">=":
            return bal >= jobb
        if op == "<=":
            return bal <= jobb
        if op == "=":
            return bal == jobb
        raise KifejezesHiba(f"Ismeretlen operátor: {op!r}")

    if t == "INTERV":
        e = _ertek(csp["kif"], kez, ktx)
        if e is None:
            return None
        also = _ertek(csp["min"], kez, ktx) if isinstance(csp["min"], dict) \
            else float(csp["min"])
        felso = _ertek(csp["max"], kez, ktx) if isinstance(csp["max"], dict) \
            else float(csp["max"])
        if also is None or felso is None:
            return None
        return also <= e <= felso

    if t == "ELOSZTAS":
        alak = str(csp["alak"])
        hosszak = (sorted(kez.hosszak, reverse=True) if csp.get("rendezett")
                   else list(kez.hosszak))
        return "".join(str(h) for h in hosszak) == alak

    if t == "SZKOR":
        return ktx.szkorhelyzet == csp["ertek"]

    if t == "IGAZ":
        return True
    if t == "ISMERETLEN":
        return None

    raise KifejezesHiba(f"Ismeretlen csomóponttípus: {t!r}")


# --- Emberi nyelvű leírás --------------------------------------------

_ERT_NEV = {"HCP": "figurapont", "ZAR": "Zar-pont", "LTC": "vesztőütés",
            "KONTROLL": "kontroll", "NANO": "nano-pont",
            "GYORSUTES": "gyorsütés", "EGYENLETES": "egyenletes",
            "LAPMINOSEG": "lapminőség", "AP_321": "asztali pont",
            "AP_531": "asztali pont"}
_SZIN_NEV = {"S": "pikk", "H": "kőr", "D": "káró", "C": "treff"}
_LAP_NEV = {"A": "ásza", "K": "királya", "Q": "dámája", "J": "bubija"}


def _valt_nev(sz) -> str:
    if isinstance(sz, str) and sz.startswith("@"):
        return "{" + sz[1:] + "}"
    return _SZIN_NEV.get(sz, sz)


def leiras(csp: dict) -> str:
    """A fa emberi nyelvű alakja — ez megy az alertbe és a promptba."""
    t = csp.get("t")
    if t == "ES":
        return "(" + " és ".join(leiras(g) for g in csp["gy"]) + ")"
    if t == "VAGY":
        return "(" + " vagy ".join(leiras(g) for g in csp["gy"]) + ")"
    if t == "LEGALABB":
        return (f"(legalább {csp.get('m')} teljesül ezekből: "
                + "; ".join(leiras(g) for g in csp["gy"]) + ")")
    if t == "NEM":
        return "nem " + leiras(csp["gy"][0])
    if t == "KULONBOZO":
        return f"{_valt_nev(csp['a'])} más szín, mint {_valt_nev(csp['b'])}"
    if t == "LICIT_ALATT":
        if csp.get("gem"):
            hol = f" ({_valt_nev(csp['szin'])})" if csp.get("szin") else ""
            return {"alatt": "gém alatt", "felett": "gém fölött", "pont": "gémet mond",
                    "lezaras_alatt": "a leállás (3M / 4m) alatt",
                    "otos_alatt": "az adu 5-ös szintje alatt"}[csp.get("mod", "alatt")] + hol
        return f"a licit {csp['szint']}{_valt_nev(csp['szin'])} alatt"
    if t == "NEM_ADU":
        return f"{_valt_nev(csp['szin'])} nem az adu"
    if t == "AZ_ADU":
        return f"{_valt_nev(csp['szin'])} az adu"
    if t == "NEM_RKC":
        return "nem a kulcslapkérdés licitje"
    if t == "SZLEMJELLEG":
        return {"igen": "szlemjellegű lap (egyértelmű igen)",
                "talan": "a szlem nem kizárt, de nem is biztos",
                "nem": "nem szlemjellegű (a szlem kizárt)",
                "nem_kizart": "a szlem nem kizárt"}[csp["ertek"]]
    if t == "OT_BIZTOS":
        return "az 5-ös szint biztonságos"
    if t == "LEGHOSSZABB":
        return f"{_valt_nev(csp['szin'])} a leghosszabb színe"
    if t == "FOGAS_MARADEK":
        tm = csp.get("termeszetes", True)
        return ("fogás minden még le nem fedett színben"
                + (" (a vonal természetes színe fedettnek számít)" if tm is True else
                   " (a természetes szín fedett-e: {" + str(tm["sablon"]) + "})"
                   if isinstance(tm, dict) else ""))
    if t == "KETSEG":
        return "a partner rövid (0-1 lap) egy színben, amit nem fogok kétszeresen"
    if t == "GYENGE_FOGAS":
        return "valamelyik ígért fogásom gyenge (nem ász, nem kétszeres)"
    if t == "LEGHOSSZABB_PARTNER_SZIN":
        sz = csp.get("szin")
        sz = ("{" + sz[1:] + "}" if isinstance(sz, str) and sz.startswith("@") else _SZIN_NEV.get(sz, sz))
        return f"a partner színei közül a {sz}ban vagyok a leghosszabb"
    if t == "EROS_FOGAS":
        sz = csp.get("szin")
        sz = ("{" + sz[1:] + "}" if isinstance(sz, str) and sz.startswith("@") else _SZIN_NEV.get(sz, sz))
        return f"biztos fogás a {sz} színben (ász, kétszeres, vagy 3+ lapos fogás: Kxx, KBx …)"
    if t == "GEM_ESELYTELEN":
        def _p(x):
            return "{" + str(x["sablon"]) + "}" if isinstance(x, dict) else f"{x}"
        return (f"nincs esélyes gém: a HELP-színben a partner nem mutatott fogást, nemes fit "
                f"({_p(csp.get('nemes_fit_min', 7))}+, 4-3 is) nincs, és a pontom + a partner ígért "
                f"minimuma {_p(csp.get('minor_gem_ero', 27))} alatt van (az 5 minorhoz kevés)")
    if t == "HELP_FOGAS":
        return "van fogásom a partner HELP-színében"
    if t == "NINCS_FIT":
        mn = csp.get("min", 8)
        mn = "{" + str(mn["sablon"]) + "}" if isinstance(mn, dict) and "sablon" in mn else mn
        sz_ = csp.get("szinek", "nemes")
        sz_ = "{" + str(sz_["sablon"]) + "}" if isinstance(sz_, dict) else sz_
        hol = "nemesben" if sz_ == "nemes" else "színben" if sz_ == "barmely" else f"({sz_})"
        return f"nincs színtalálkozás (egyik {hol} sincs {mn}+ lap együtt)"
    if t == "GEMESELY":
        return ("gémesély (nemes fittel 25, minor fittel 27, szanban 24 FP — "
                "egyenetlen pontelosztásnál hosszú színnel)")
    if t == "MISFIT":
        return "misfit (0-1 lap a partner tudottan 5+ lapos színében)"
    if t == "SPLINTER_FIT":
        return "feltételezett 8 lapos fit a partner nemesében"
    if t == "FIT_HOSSZ":
        return f"közös adu ({_valt_nev(csp['szin'])}: a saját lapjaim + a partner ígért minimuma)"
    if t == "MARADEK_VESZTO":
        return "maradék vesztő (a saját vesztőim − a partner biztos fedői)"
    if t == "OSSZESEN":
        return ("asztali pontom" if csp.get("mit") == "AP" else "figurapontom") + \
            " + a partner ígért maximuma"
    if t == "ONALLO_ADU":
        return (f"önállóan játszható adu ({_valt_nev(csp['szin'])}): a partner "
                f"sikénjével szemben is legfeljebb 1 vesztő "
                f"{round(100 * float(csp.get('kuszob', 2 / 3)))}%+ eséllyel")
    if t == "KONTROLLOK":
        return "minden külső színben van kontroll (csak a kulcslapok kérdésesek)"
    if t == "IGERET_FELE":
        mit = "asztali pont" if csp["mit"] == "AP" else "figurapont"
        fele = {"also": "alsó felében (legfeljebb a közepe)",
                "felso": "felső felében", "max": "tetején (maximum)"}[csp["fele"]]
        return f"{mit} az eddig ígért sáv {fele}"
    if t == "OSSZE":
        return f"{_kif_leiras(csp['bal'])} {csp['op']} {_kif_leiras(csp['jobb'])}"
    if t == "INTERV":
        also = (_kif_leiras(csp["min"]) if isinstance(csp["min"], dict)
                else csp["min"])
        felso = (_kif_leiras(csp["max"]) if isinstance(csp["max"], dict)
                 else csp["max"])
        return f"{_kif_leiras(csp['kif'])} {also}-{felso} között"
    if t == "ELOSZTAS":
        return ("elosztás " + str(csp["alak"])
                + (" (hossz szerint)" if csp.get("rendezett") else ""))
    if t == "SZKOR":
        return {"M": "mindkét vonal beliben", "A": "senki nincs beliben",
                "S": "csak mi vagyunk beliben",
                "O": "csak ők vannak beliben"}.get(csp["ertek"], "?")
    if t == "KESZLET":
        return f"[{csp['kod']}]"
    return str(t)


def _kif_leiras(csp: dict) -> str:
    t = csp.get("t")
    if t == "SZAM":
        if isinstance(csp["v"], dict) and "sablon" in csp["v"]:
            return "{" + str(csp["v"]["sablon"]) + "}"     # elv-sablon helyőrzője
        return f"{csp['v']:g}"
    if t == "PARAM":
        x = "{" + csp["kod"] + (f", alapból {csp['alap']:g}" if "alap" in csp else "") + "}"
        e = float(csp.get("eltolas", 0))
        return x + (f" {e:+g}" if e else "")
    if t == "ISMERETLEN":
        return f"<{csp.get('kod','?')} - képlete tisztázatlan>"
    if t == "HELYZET":
        from .helyzet import ertek_leiras
        return ertek_leiras(csp["kif"])
    if t == "ERT":
        if csp["kod"].startswith("@"):
            return "{" + csp["kod"][1:].lower() + "}"
        nev = _ERT_NEV.get(csp["kod"], csp["kod"])
        sz = csp.get("szorzo", 1)
        return f"{nev}*{sz:g}" if sz != 1 else nev
    if t == "SZIN":
        sz = csp["szin"]
        if isinstance(sz, str) and sz.startswith("@"):
            return "{" + sz[1:] + "} hossz"
        return _SZIN_NEV.get(sz, sz) + " hossz"
    if t == "SZINFIG":
        sz = csp["szin"]
        if isinstance(sz, str) and sz.startswith("@"):
            return "figurapont a {" + sz[1:] + "} színben"
        return f"figurapont a {_SZIN_NEV.get(sz, sz)} színben"
    if t == "FEDO":
        adu = csp["adu"]
        adu = ("{" + adu[1:] + "}" if isinstance(adu, str) and adu.startswith("@")
               else _SZIN_NEV.get(adu, adu))
        return f"fedőütés ({adu} adu mellett)"
    if t == "KULCSLAP":
        if csp.get("adu") and not str(csp["adu"]).startswith("@"):
            return f"kulcslap (4 ász + {_SZIN_NEV.get(csp['adu'], csp['adu'])} király)"
        if csp.get("kizart"):
            return f"kulcslap ({_SZIN_NEV.get(csp['kizart'], csp['kizart'])} ász nélkül)"
        return "kulcslap (4 ász + adu király)"
    if t == "ADU_DAMA":
        if csp.get("adu") and not str(csp["adu"]).startswith("@"):
            return f"{_SZIN_NEV.get(csp['adu'], csp['adu'])} dáma"
        return "adu dáma"
    if t == "KORR_PONT":
        lv = csp.get("levonas", 0.5)
        lv = "{" + str(lv["sablon"]) + "}" if isinstance(lv, dict) else f"{float(lv):g}"
        return f"korrigált pont (FP + hosszúsági pont − {lv} × üres dáma/bubi)"
    if t == "URES_FIGURA":
        sz_ = csp.get("szorzo", 1)
        alap = "üres dáma/bubi (ász, király nélkül, legfeljebb 3 lapos színben)"
        if sz_ == 1:
            return alap
        sz_ = "{" + str(sz_["sablon"]) + "}" if isinstance(sz_, dict) else f"{float(sz_):g}"
        return f"{alap} × {sz_} levonás"
    if t == "FIT_HOSSZ":
        sz = csp.get("szin")
        sz = ("{" + sz[1:] + "}" if isinstance(sz, str) and sz.startswith("@")
              else _SZIN_NEV.get(sz, sz))
        return f"közös adu a {sz} színben (a lapom + a partner ígérete)"
    if t == "VESZTO":
        sz = csp.get("szin")
        if not sz:
            return "vesztőütés"
        sz = ("{" + sz[1:] + "}" if sz.startswith("@") else _SZIN_NEV.get(sz, sz))
        return f"vesztőütés a {sz} színben"
    if t == "HOSSZ":
        return f"{csp['rang']}. leghosszabb szín"
    if t == "FIG":
        return f"figurapont a {csp['rang']}. leghosszabb színben"
    if t == "LAP":
        jel = csp["lap"]
        if jel.startswith("@"):
            valt, ertek = jel[1:].split(":")
            return f"nála van a {{{valt}}} szín {_LAP_NEV.get(ertek, ertek)}"
        return f"nála van a(z) {jel}"
    if t == "HA":
        # Feltételes numerikus tag. Ezzel írható le olyan elosztási
        # megfontolás, mint "a rövid treff jobb, mint a rövid káró":
        # nem küszöb, hanem SÚLY, ami az alkalmassági összegbe megy.
        e = kiertekel(csp["felt"], kez, ktx)
        if e is None:
            return None
        ag = csp.get("akkor", 1) if e else csp.get("kulonben", 0)
        return _ertek(ag, kez, ktx) if isinstance(ag, dict) else float(ag)

    if t == "HA":
        return (f"({leiras(csp['felt'])} ? {csp.get('akkor',1)} "
                f": {csp.get('kulonben',0)})")
    if t == "OSSZEG":
        jelek = csp.get("jelek") or [1] * (len(csp["gy"]) - 1)
        s = _kif_leiras(csp["gy"][0])
        for jel, g in zip(jelek, csp["gy"][1:]):
            s += (" + " if jel > 0 else " - ") + _kif_leiras(g)
        return s
    return str(t)


# --- Ismeretlen jelzők felderítése -----------------------------------

def ismeretlen_jelzok(csp: dict) -> set[str]:
    """
    Mely jelzők teszik eldönthetetlenné a fát?
    Ezzel MEGSZÁMOLHATÓ, hány szabály hiúsul meg a hiányzó képletek
    (P, i, j) miatt — vagyis mennyit ér a hiányzó tudás.
    """
    ki: set[str] = set()

    def bejar(x):
        if not isinstance(x, dict):
            return
        if x.get("t") == "ERT":
            kod = x["kod"]
            if kod.startswith("@"):
                ki.add(kod)        # logikai metrika: feloldás nélkül ismeretlen
            elif kod not in ERTEKELOK:
                ki.add(kod)
        if x.get("t") == "KESZLET" and x["kod"].startswith("@"):
            ki.add(x["kod"])
        if x.get("t") == "ISMERETLEN":
            ki.add(x.get("kod", "?"))
        for kulcs in ("gy",):
            for g in x.get(kulcs, []) or []:
                bejar(g)
        for kulcs in ("bal", "jobb", "kif", "min", "max"):
            if isinstance(x.get(kulcs), dict):
                bejar(x[kulcs])

    bejar(csp)
    return ki


def json_be(s: str | dict) -> dict:
    return s if isinstance(s, dict) else json.loads(s)


def json_ki(csp: dict) -> str:
    return json.dumps(csp, ensure_ascii=False, separators=(",", ":"))


# --- Miért NEM teljesült? (magyarázat a tanításhoz) -------------------

def _szam_szoveg(v) -> str:
    return "?" if v is None else (f"{v:g}" if isinstance(v, float) else str(v))


def miert_nem(csp: dict | None, kez: Kez, ktx: Kontextus | None = None,
              _mely: int = 0) -> list[str]:
    """
    Egy NEM teljesült (vagy eldönthetetlen) feltétel emberi okai, a kéz
    tényleges értékeivel: "pikk hossz >= 5 (a kézben: 4)".

    Csak a HIBÁS ágakat sorolja fel: egy ÉS-nél azokat a tagokat, amik
    buknak; egy VAGY-nál azt, hogy egyik ág sem teljesül, ágankénti okkal.
    A kéz értékeit mutatja — ezért ez csak teszt/tanító módban mehet ki,
    ellenfélnek soha.
    """
    if not isinstance(csp, dict) or _mely > 8:
        return []
    ktx = ktx or Kontextus()
    t = csp.get("t")
    e = kiertekel(csp, kez, ktx)
    if e is True:
        return []

    if t == "ES":
        ki: list[str] = []
        for g in csp.get("gy", []):
            ki += miert_nem(g, kez, ktx, _mely + 1)
        return ki
    if t in ("VAGY", "LEGALABB"):
        agak = []
        for g in csp.get("gy", []):
            okok = miert_nem(g, kez, ktx, _mely + 1)
            if okok:
                agak.append(" és ".join(okok))
        fej = "egyik változat sem teljesül" if t == "VAGY" else \
            f"legalább {csp.get('m')} kellene"
        return [f"{fej}: " + " | ".join(f"[{a}]" for a in agak)] if agak \
            else [leiras(csp)]
    if t == "OSSZE":
        bal = _ertek(csp["bal"], kez, ktx)
        jobb = _ertek(csp["jobb"], kez, ktx)
        ertek = _szam_szoveg(bal)
        if csp["jobb"].get("t") not in ("SZAM",):
            ertek += f" vs {_szam_szoveg(jobb)}"
        vege = "nem eldönthető" if e is None else f"a kézben: {ertek}"
        return [f"{leiras(csp)} ({vege})"]
    if t == "INTERV":
        v = _ertek(csp["kif"], kez, ktx)
        return [f"{leiras(csp)} (a kézben: {_szam_szoveg(v)})"]
    return [leiras(csp) + (" (nem eldönthető)" if e is None else "")]
