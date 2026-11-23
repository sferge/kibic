"""
A tervkönyvelő — első változat (2026-11-18, Felvevő tervjáték).
Tervezet: claude/terv-tervvaz-2026-11-17.md

A terv logikai egységekből áll (a technikasémák példányai, sorrendben: az
esélyek sora); a végrehajtó ezeket KÖRÖKRE bontva illeszti össze, az első
ütéstől. Minden körnél csak azt nézi, melyik kéz hív és melyik visz el:

  * a soron következő egység köre, ha a hívó kéz a mienk; ha nem, átmenet a
    hívó kézbe — az átmenet bármely kör lehet, amely ott ér véget (szabad
    nyerő, adukör, lopás, vagy egy KÉSŐBBI egység köre: a közös lap);
  * a kiaduzás az általános adukezelés szerint: annyi adukör, amennyit a
    lopásokra foglalt aduk megengednek (a lopások előtt is);
  * a hozzátevés is döntés: a foglalt lapokat (az egységek lapjai, az
    impasszhoz a kéz felé hívandó kis lap, a lopásokhoz a kis lapok) csak
    végső esetben adjuk le;
  * a döntési pontok csak megfigyelt tényre ágaznak: az impassz ütött-e, és
    a `csak_ha: siker` kör lapja nyerő-e, amikor sorra kerül.

Az esélyt ebben a változatban sorsolt világokon, DD-védők ellen számoljuk (a
védők a nekünk legrosszabbat játsszák). Az osztályonkénti, keresés nélküli
könyvelés a következő lépés; ez a változat a tervmodell és a végrehajtás
próbája.
"""
from __future__ import annotations

import math

from dataclasses import dataclass, field

from ..domain import Lap, kovetkezo_ules, vonal
from . import tervjatszo as tj
from .tervsema import Allas, Kor, Peldany, peldanyok

SZINJEL = dict(zip("SHDC", "♠♥♦♣"))

import os as _os
# a mérésekhez: a 2026-11-18-i szabályok ki-be kapcsolhatók (1: be)
SZABALY = {n: _os.getenv(f"KIBIC_K_{n}", "1") != "0" for n in
           ("MASODIK", "HARMADIK", "DOBAS", "HOSSZU_LOP", "SZAKASZ", "ELEMZO",
            "HASZNOS_DOBAS", "DOBAS_ELOBB", "KIMERULT", "ELEMZO_LOP", "ELEMZO_ATM", "ATMENET_VEDES", "ADU_IGENY", "DEBLOKK", "ADU_LEALLAS", "ELEMZO_ATM_ADU", "ATMENET_ELOSZTAS", "MAGAS_LOPAS", "HIVAS_ATADAS", "MEGFIGYELT_NYERO", "ATMENET_ADUKOR", "BEDOBAS_TARTALEK", "BIZTONSAGI_KEZELES", "KOMBINACIO", "SZABAD_HELY_UTES", "FOGAS_VEDES", "VESZTORE_DOB", "LOPAS_ELOTT_ADU")}


# --- 1. A terv -----------------------------------------------------------------------

@dataclass
class KTerv:
    """A terv egységei: a biztos egységek (mindig), és utánuk az esélyes egységek
    sorban — amíg a megszerzett hozam el nem éri az igényt (a hiányzó ütések, illetve
    a vesztőtöbblet)."""
    lepesek: list[Peldany]
    igeny: int = 1
    # a sorrend: egységenként "E" (a kiaduzás előtt) vagy "U" (utána); None: a régi,
    # körönkénti döntés
    fazis: tuple | None = None
    adus: bool = True                    # színfelvétel: a nevben a kiaduzás helye is látszik
    elozetes: float | None = None        # az esély keresés nélkül (a forrásokból)

    @property
    def nev(self) -> str:
        if not self.lepesek:
            return "csak begyűjtés"
        if self.fazis is None or not self.adus:
            return " → ".join(p.rovid for p in self.lepesek)
        elotte = [p.rovid for p, f in zip(self.lepesek, self.fazis) if f == "E"]
        utana = [p.rovid for p, f in zip(self.lepesek, self.fazis) if f != "E"]
        return " → ".join(elotte + ["kiaduzás"] + utana)


def alap_fazis(p: Peldany) -> str:
    """Az alapsorrend: a lopás a kiaduzás előtt (a lopó kéz aduja kell hozzá); az
    aduszín kezelése (az elemzővel) maga a kiaduzás, ezért előre; minden más utána."""
    if any(k.fajta == "lop" for k in p.korok):
        return "E"
    if p.sema.fajta == "elemzo" and p.szerepek.get("adu"):
        return "E"
    if p.sema.azon == "BEDOBAS_IMPASSZ" and any(k.szin == p.szin and k.fajta == "impassz" for k in p.korok) \
            and p.szerepek.get("ADUSZIN") == p.szin:
        return "E"                       # az adu-impassz a kiaduzás előtt (BM A-6 #3)
    return "U"


def terv_fazis(lepesek: list[Peldany]) -> tuple:
    """Az alapsorrend egy tervre: az egységek alapszakasza; ha a kiaduzás előtt van
    olyan egység, amely kiadja a hívást (kiengedés, impassz), akkor a vesztőcsere is a
    kiaduzás elé kerül — a dobás a hívás elvesztése előtt (BridgeMasters #1)."""
    f = [alap_fazis(p) for p in lepesek]
    # DOBAS_ELOBB (általános szabály, a szerkesztő 2026-11-19): a vesztőt a magas lapra
    # azelőtt dobjuk, hogy a terv kockázatos körbe menne — kiadás, impassz, vagy lopásos
    # egység (a mellékszín második köre ellopható: a ♦A előtt a ♣K-ra a ♥ vesztő)
    fajtak = ("kiad", "impassz", "lop") if SZABALY["DOBAS_ELOBB"] else ("kiad", "impassz")
    hivast_ad = any(fz == "E" and any(k.fajta in fajtak for k in p.korok)
                    for p, fz in zip(lepesek, f))
    if hivast_ad:
        f = ["E" if p.sema.azon == "VESZTOCSERE" else fz for p, fz in zip(lepesek, f)]
    return tuple(f)


def szakasz_valtozatok(t: KTerv, max_db: int = 8) -> list[KTerv]:
    """A terv sorrendváltozatai: az egységek a kiaduzás előtt vagy után (az alapsorrend
    az első). A lopásos egység mindig előtte marad."""
    from itertools import product
    alap = terv_fazis(t.lepesek)
    ki = [KTerv(t.lepesek, t.igeny, alap, t.adus, t.elozetes)]
    if not t.adus:
        return ki                    # szanzadu: nincs kiaduzás, a fázis nem számít
    szabad = [i for i, p in enumerate(t.lepesek)
              if alap[i] == "U" or p.sema.azon == "VESZTOCSERE"]
    for valaszt in product("UE", repeat=len(szabad)):
        f = list(alap)
        for i, v in zip(szabad, valaszt):
            f[i] = v
        f = tuple(f)
        if f != alap:
            ki.append(KTerv(t.lepesek, t.igeny, f, t.adus, t.elozetes))
        if len(ki) >= max_db:
            break
    return ki


@dataclass
class Egyseg:
    p: Peldany
    i: int = 0
    allapot: str = "var"            # var / siker / kudarc / elmarad / kesz
    fazis: str | None = None        # "E": a kiaduzás előtt, "U": utána, None: nincs megadva

    def kor(self) -> Kor | None:
        return self.p.korok[self.i] if self.i < len(self.p.korok) else None

    @property
    def el(self) -> bool:
        return self.allapot in ("var", "siker")

    @property
    def biztos(self) -> bool:
        """Biztos egység (pl. vesztőcsere, lopás): nincs rejtett feltétele; mindig a
        terv része, és nem az esélyek sorának tagja."""
        return biztos_egyseg(self.p)


def biztos_egyseg(p: Peldany) -> bool:
    return str(p.sema.siker).strip() == "True"


def dobas_valtozatok(p: Peldany, allas: Allas) -> list[Peldany]:
    """A vesztőcsere változatai a dobás színe szerint (a szerkesztő: „én treffet
    dobnék”): a dobó kéz (DK) minden olyan színe, amelyben van nem nyerő lapja (az adu
    és a vesztőcsere színe nélkül). A dobás színe a terv része."""
    import dataclasses
    if p.sema.azon != "VESZTOCSERE":
        return [p]
    dk = p.szerepek.get("DK")
    ki = []
    for c in "SHDC":
        if c in (p.szin, allas.adu) or not dk:
            continue
        lapok = allas.szin(dk, c)
        kint = allas.kint_szin(c)
        if any(not kint or l.rang < kint[0].rang for l in lapok):
            q = dataclasses.replace(p, szerepek=dict(p.szerepek, CELSZIN=c))
            ki.append(q)
    return ki or [p]


def hasznos_dobas(p: Peldany, lepesek: list[Peldany], allas: Allas) -> str | None:
    """LEGHASZNOSABB_DOBAS (általános szabály, a szerkesztő 2026-11-19): a magas lapra a
    dobó kéz abból a színből dob, amelynek a vesztőit a terv más egysége nem kezeli
    (nem lopja, nem fejleszti, nem impasszolja), és amelyben a legtöbb olyan vesztője
    van, amelyet a partner sem lophat el. (MB 4♠: a ♦ a szöktetésé, tehát treffet;
    BridgeMasters #1: a ♦ a lopásé, tehát kőrt.)"""
    dk = p.szerepek.get("DK")
    if not dk:
        return None
    pk = allas.partner(dk) if hasattr(allas, "partner") else (
        allas.asztal if dk == allas.felvevo else allas.felvevo)
    mas = {q.szin for q in lepesek if q is not p}
    adu = allas.adu
    p_adu = len(allas.szin(pk, adu)) if adu else 0
    legjobb, kulcs0 = None, None
    for c in "SHDC":
        if c in (p.szin, adu):
            continue
        d, q = allas.szin(dk, c), allas.szin(pk, c)
        kint = allas.kint_szin(c)
        if not any(not kint or l.rang < kint[0].rang for l in d):
            continue
        # a felső nyerők a két kézben (a kint lévő legnagyobb fölött, sorban)
        sajat = sorted(d + q, key=lambda l: -l.rang)
        nyer = 0
        for l in sajat:
            if kint and l.rang < max(x.rang for x in kint):
                break
            nyer += 1
        vesztok = max(0, len(d) - nyer)
        if adu and len(q) < len(d):
            vesztok -= min(len(d) - len(q), p_adu, vesztok)    # a partner ellophatja
        kulcs = (c not in mas, vesztok, -len(d))
        if kulcs0 is None or kulcs > kulcs0:
            legjobb, kulcs0 = c, kulcs
    return legjobb


ELEMZO_MAX_KINT = int(_os.getenv("KIBIC_K_ELEMZO_KINT", "8"))   # ennél több kint lévő lapnál lassú


def _felmeres(allas: Allas, ures: tuple[int, int] | None):
    from .tervfelmeres import felmeres
    u1, u2 = ures or (13, 13)
    return felmeres({allas.felvevo: set(allas.kezek[allas.felvevo]), allas.asztal: set(allas.kezek[allas.asztal])},
                    allas.felvevo, allas.asztal, set(allas.kint), (u1, u2), allas.adu, allas.cel, allas.hatra)


# a kiaduzáshoz várhatóan szükséges adukörök a kint lévő aduk számából (a leggyakoribb
# elosztás hosszabbik fele: 5 kint → 3-2 → 3 kör)
ADUKOROK = {0: 0, 1: 1, 2: 1, 3: 2, 4: 3, 5: 3, 6: 4, 7: 4, 8: 5, 9: 5}


def elemzo_lopasok(adu: str | None, sz: str, adu_x: int, adu_y: int, kint_adu: int,
                   hossz_x: int = 0, hossz_y: int = 0, kint_sz: int = 0) -> tuple[int, int]:
    """Színjátékban a mellékszín elemzője lophat is (lopásos kimagasítás): kezenként az
    aduk, amelyek a kiaduzás után megmaradnak (a rövid adus kéz is követ a körökben).
    BM A-2 #3 (6♥): AK5432 / 76, a kézben ♥AKQJT — a ♣ két kis lapját a kéz lopja."""
    if not adu or sz == adu or not SZABALY["ELEMZO_LOP"]:
        return 0, 0
    if kint_sz > 6 or hossz_x == hossz_y:
        return 0, 0                      # a keresés túl nagy lenne / nincs rövid kéz
    d = ADUKOROK.get(kint_adu, (kint_adu + 1) // 2 + 1)
    # csak a színben rövidebb kéz lop (a hosszú kéz a saját színét nem lopja), legfeljebb
    # kétszer — a keresési tér így kezelhető marad
    lx = min(2, max(0, adu_x - d)) if hossz_x < hossz_y else 0
    ly = min(2, max(0, adu_y - d)) if hossz_y < hossz_x else 0
    return lx, ly


def elemzo_atmenetek(kezek: dict, F: str, A: str, kint: list, adu: str | None, sz: str) -> tuple[int, int] | tuple[None, None]:
    """Az átmenetek a színen kívül, kezenként (a mellékszín elemzőjének korlátja): a
    többi színben a kéz nyerői, amelyekhez a partnernek kisebb lapja van. Durva
    becslés (a lopásos átmenetet nem számolja). BM A-2 #3: ♠A2 / ♠KQ — az asztalra egy
    átmenet van, ezért a ♣-ot egy kiengedéssel kell kezdeni, nem két lopással."""
    if not SZABALY["ELEMZO_ATM"]:
        return None, None
    return atmenet_szam(kezek, F, A, kint, sz)


def atmenet_szam(kezek: dict, F: str, A: str, kint: list, sz: str) -> tuple[int, int]:
    """Az átmenetek száma a `sz` színen kívül, kezenként (lásd elemzo_atmenetek)."""
    def be(H, P):
        n = 0
        for s in "SHDC":
            if s == sz:
                continue
            ks = [x for x in kint if x.szin == s]
            felul = max((x.rang for x in ks), default=0)
            ny = [l for l in kezek[H] if l.szin == s and l.rang > felul]
            if not ny:
                continue
            also = [l for l in kezek[P] if l.szin == s and l.rang < max(x.rang for x in ny)]
            n += min(len(ny), len(also))
        return n
    return be(F, A), be(A, F)


def szinkezeles_peldany(allas: Allas, technikak: dict, sz: str, k: int, m: int,
                        ures: tuple[int, int] | None = None, esely_min: float = 0.01,
                        fm=None, biztonsagi: bool = False) -> Peldany | None:
    """Egy elemzős színkezelési egység (a szín, a cél: k ütés, legfeljebb m vesztés)."""
    from .tervszinpolitika import SzinPolitika
    sema = technikak.get("SZINKEZELES")
    if sema is None:
        return None
    F, A = allas.felvevo, allas.asztal
    ures1, ures2 = ures or (13, 13)
    X = frozenset(l.rang for l in allas.szin(F, sz))
    Y = frozenset(l.rang for l in allas.szin(A, sz))
    kint = frozenset(l.rang for l in allas.kint_szin(sz))
    if not (X or Y) or not kint:
        return None
    adu = sz == allas.adu
    lx, ly = elemzo_lopasok(allas.adu, sz, len(allas.szin(F, allas.adu)) if allas.adu else 0,
                            len(allas.szin(A, allas.adu)) if allas.adu else 0,
                            len(allas.kint_szin(allas.adu)) if allas.adu else 0,
                            len(X), len(Y), len(kint))
    ax, ay = (None, None) if (adu and not SZABALY["ELEMZO_ATM_ADU"]) else elemzo_atmenetek(
        {F: allas.szin_mind(F) if hasattr(allas, "szin_mind") else set(allas.kezek[F]),
         A: set(allas.kezek[A])}, F, A, list(allas.kint), allas.adu, sz)
    try:
        # a szín első hívása is átmenetbe kerül (a terv más egységei után nem tudjuk,
        # melyik kézben leszünk): „-”
        pol = SzinPolitika(X, Y, kint, ures1, ures2, k, m, adu, lx, ly, ax, ay,
                           None if ax is None else "-")
    except Exception:                            # noqa: BLE001
        return None
    if pol.p <= esely_min:
        return None
    fm = fm or _felmeres(allas, ures)
    sf = next(x for x in fm.szinek if x.szin == sz)
    biztos = sf.biztos
    lapok = set(allas.szin(F, sz)) | set(allas.szin(A, sz))
    # hozam: a mellékszínben a biztosakon felüli ütések; az aduban a várható vesztők
    # (a helyzetfelmérés) csökkenése
    # az aduban: a legrosszabb (legalább 5%-os) elosztás vesztőiből ennyitől véd meg —
    # a szerkesztő (2026-11-20, BM A-2 #5): „a kőrben simán kiadhatunk 3-at is”; a
    # várható 2,3 vesztő a 2-es keret mellett nem „0 hozam”
    if not adu:
        hozam = k - biztos
    else:
        hozam = int(max(0.0, sf.vesztok - m) + 0.5)
        if hozam <= 0 and m <= sf.kiado and sf.vesztok_max > m:
            # a legszigorúbb aduszín-cél (csak a biztos vesztők): ha a legrosszabb
            # elosztás több vesztőt ad, ez véd meg tőle — jelölt marad (a többi m-nél nem:
            # azok kiszorították a jobb terveket, 4A01 #1)
            hozam = 1
        if hozam <= 0 and biztonsagi and sf.vesztok_max > m:
            # BIZTONSAGI_KEZELES (a szerkesztő, 2026-11-21, BM A-6 #4): a szín biztonsági
            # kezelése — a kötelező ütésszám a teljes vesztéskerettel, a legnagyobb
            # biztonságra (nem a legtöbb ütésre): a legrosszabb elosztás vesztőitől véd
            hozam = 1
    if hozam <= 0:
        # (többlet nélküli aduszín-egységgel próbálva — BM A-2 #4 — nem segített, és a
        # jelöltszűrésből kiszorította a jobb terveket: a kiaduzás marad)
        return None
    sz_ = {"k": k, "m": m, "biztos": biztos, "esely": pol.p, "aduval": False, "adu": adu}
    return Peldany(sema, sz, sz_, [Kor("elemzo", sz)], set(lapok), set(lapok),
                   {l for l in allas.kint_szin(sz)}, hozam)


def szabad_helyek(lejatszott, v1: str, v2: str) -> tuple[int, int]:
    """A két védő ismeretlen lapjainak száma (szabad helyek). A folyó, még be nem
    fejezett ütésre a hátralévő védő is tesz egy lapot (a hívott színből, ha követ):
    azt is lement lapnak számoljuk, különben a szabad helyek az ütés közepén
    aszimmetrikusak lennének (BM A-11: az indulás után Nyugat 12, Kelet 13 — pedig
    Kelet is tesz egy pikket; a szerkesztő, 2026-11-21)."""
    L = list(lejatszott)
    ures = [13 - sum(1 for u, _ in L if u == v) for v in (v1, v2)]
    if SZABALY["SZABAD_HELY_UTES"] and len(L) % 4:
        folyo = {u for u, _ in L[len(L) - len(L) % 4:]}
        ures = [x - (1 if v not in folyo else 0) for x, v in zip(ures, (v1, v2))]
    return ures[0], ures[1]


def _egyetlen_feladat(allas: Allas, technikak: dict, sz: str, fm) -> bool:
    """BIZTONSAGI_KEZELES feltétele (a szerkesztő, 2026-11-21): a szín biztonsági
    kezelése csak akkor érvényes, ha ez a teljesítés egyetlen feltétele — a többi
    színben nincs feladat. Egy színben nincs feladat, ha nincs várható vesztője, vagy a
    vesztőit biztos egység tünteti el (lopás abban a színben, dobás abból a színből: BM
    A-6 #4, a kézi ♦ vesztő a magas kőrre esik). Különben kombinációs játék kell: egy
    szín sem rögzíthető a maximuma alatt."""
    from .tervsema import peldanyok as _pld
    biztosak = [q for p in _pld(allas, technikak) for q in dobas_valtozatok(p, allas) if biztos_egyseg(q)]
    tobbi = [x for x in fm.szinek if x.szin != sz and x.vesztok > 0.05]
    if not tobbi:
        return True
    # a biztos egységek ütközésmentes készletei (mint a tervjelölteknél): elég, ha egy
    # készlet minden más szín vesztőit eltünteti
    for p0 in biztosak or [None]:
        x = [p0] if p0 is not None else []
        for q in biztosak:
            if q is not p0 and not any(_utkozik(q, r) for r in x):
                x.append(q)
        fedett: dict[str, int] = {}
        for q in x:
            cel = q.szerepek.get("CELSZIN") if q.sema.azon == "VESZTOCSERE" else q.szin
            if cel:
                fedett[cel] = fedett.get(cel, 0) + q.hozam
        if all(t.vesztok - fedett.get(t.szin, 0) <= 0.05 for t in tobbi):
            return True
    return False


def szinkezeles_peldanyok(allas: Allas, technikak: dict, igeny: int,
                          ures: tuple[int, int] | None = None) -> list[Peldany]:
    """Az egyszínű elemző kezelései forrásként: színenként a cél k ütés (a biztosakon
    felül legfeljebb az igényig) legfeljebb m vesztéssel (a megengedett kiadásból, ami
    a többi szín biztos kiadása után marad). Az aduszínben a vesztés 0–2 (a kiaduzás
    kezelése: „legfeljebb egy aduvesztő”)."""
    if "SZINKEZELES" not in technikak or not SZABALY.get("ELEMZO", True):
        return []
    F, A = allas.felvevo, allas.asztal
    fm = _felmeres(allas, ures)
    ki = []
    for sz in "SHDC":
        X, Y = allas.szin(F, sz), allas.szin(A, sz)
        kint = allas.kint_szin(sz)
        if not (X or Y) or not kint or len(kint) > ELEMZO_MAX_KINT:
            continue
        sf = next(x for x in fm.szinek if x.szin == sz)
        hossz = max(len(X), len(Y))
        # a vesztéskeret: a megengedett kiadás, mínusz a többi szín biztosan kiadó ütései
        keret = max(0, fm.megengedett - (fm.kiado - sf.kiado))
        if sz == allas.adu:
            celok = [(hossz - v, v) for v in range(sf.kiado, min(keret, sf.kiado + 2) + 1) if hossz - v > 0]
            if SZABALY["BIZTONSAGI_KEZELES"] and keret > sf.kiado and hossz - keret > 0 \
                    and keret <= sf.kiado + 2 and _egyetlen_feladat(allas, technikak, sz, fm):
                p = szinkezeles_peldany(allas, technikak, sz, hossz - keret, keret, ures, fm=fm, biztonsagi=True)
                # csak ha érdemben biztonságosabb a szigorúbb céloknál (különben csak
                # kiszorítaná a többi tervet az előszűrésből — 4A01 #1, 4Q01 #2)
                p_szig = [szinkezeles_peldany(allas, technikak, sz, hossz - v, v, ures, fm=fm, esely_min=-1)
                          for v in range(sf.kiado, keret) if hossz - v > 0]
                e_szig = max((float(q.szerepek.get("esely", 0)) for q in p_szig if q is not None), default=0.0)
                if p is not None and float(p.szerepek.get("esely", 0)) >= e_szig + 0.10:
                    ki.append(p)
                celok = [c for c in celok if c != (hossz - keret, keret)]
        else:
            # a keret két határa: a többi szín biztos kiadása után maradó (óvatos), és a
            # teljes megengedett kiadás — a „biztosan kiadó” vesztő nem mindig kiadó: a
            # többi szín vesztőit eldobhatjuk erre a színre (BridgeMasters #2, 6NT: a ♣
            # kiengedése a ♥ és a ♦ vesztők helyett; ezt a szimuláció dönti el)
            # csak ha a szín hosszkülönbsége elég dobást ad a többi szín biztos vesztőire
            tobbi = fm.kiado - sf.kiado
            dobhato = abs(len(X) - len(Y)) >= tobbi > 0
            celok = [(k, keret) for k in range(sf.biztos + 1, min(hossz, sf.biztos + max(1, igeny)) + 1)]
            if dobhato and fm.megengedett > keret:
                # a bővebb keret csak akkor jelölt, ha érdemben jobb (különben csak
                # kiszorítaná a többit az előszűrésből)
                for k, _ in list(celok):
                    p0 = szinkezeles_peldany(allas, technikak, sz, k, keret, ures, fm=fm)
                    p1 = szinkezeles_peldany(allas, technikak, sz, k, fm.megengedett, ures, fm=fm)
                    e0 = float(p0.szerepek.get("esely", 0)) if p0 else 0.0
                    if p1 is not None and float(p1.szerepek.get("esely", 0)) >= e0 + 0.10:
                        ki.append(p1)
        for k, m in celok:
            p = szinkezeles_peldany(allas, technikak, sz, k, m, ures, fm=fm)
            if p is not None:
                ki.append(p)
    return ki


def egyseg_esely(p: Peldany, allas: Allas, ures: tuple[int, int] | None) -> float:
    """Egy egység esélye keresés nélkül: a biztosé 1, az elemzősé az elemzőé, a többié a
    `siker` feltétel az elosztásosztályokon (tervforras)."""
    if biztos_egyseg(p):
        return 1.0
    if p.sema.fajta == "elemzo":
        return float(p.szerepek.get("esely", 0.0))
    from .tervforras import esely
    from ..domain import kovetkezo_ules as _ku
    u1, u2 = ures or (13, 13)
    try:
        return esely(p, allas.kint, {_ku(allas.felvevo, 1): u1, _ku(allas.felvevo, 3): u2})
    except Exception:                            # noqa: BLE001
        return 0.0


def elozetes_esely(t: "KTerv", eselyek: dict) -> float:
    """A terv esélye keresés nélkül (a szerkesztő 5–6. lépése): annak a valószínűsége,
    hogy a sikeres egységek hozama eléri az igényt — az egységeket függetlennek véve."""
    eloszlas = {0: 1.0}
    for p in t.lepesek:
        q = eselyek.get(id(p), 0.0)
        uj: dict = {}
        for h, w in eloszlas.items():
            uj[h + p.hozam] = uj.get(h + p.hozam, 0.0) + w * q
            uj[h] = uj.get(h, 0.0) + w * (1 - q)
        eloszlas = uj
    return sum(w for h, w in eloszlas.items() if h >= t.igeny)


def _utkozik(a: Peldany, b: Peldany) -> bool:
    # a bedobás kényszerszíneit a védő hívja meg: más egység nem kezelheti őket
    # (BEDOBAS_TARTALEK: ha az adu a kiadó szín, egy kényszerszín-egység a bedobás
    # tartaléka — a végrehajtó visszatartja, amíg a bedobás körei tartanak, és csak a
    # kudarca után indul; más kiadó színnél a borulás nem ismerhető fel: ütközés)
    for x, y in ((a, b), (b, a)):
        if x.sema.azon in ("BEDOBAS", "BEDOBAS_IMPASSZ") and y.szin in (x.szerepek.get("K") or []) \
                and not (SZABALY["BEDOBAS_TARTALEK"] and x.szerepek.get("ADUKIAD") and not biztos_egyseg(y)):
            return True
    return _utkozik_alap(a, b)


def _utkozik_alap(a: Peldany, b: Peldany) -> bool:
    if a.szerepek.get("CELSZIN") and a.szerepek["CELSZIN"] == b.szin:
        return True                      # amiből dobunk, azt nem kezeljük másképp
    if b.szerepek.get("CELSZIN") and b.szerepek["CELSZIN"] == a.szin:
        return True
    return bool((a.hasznal | a.elfogyaszt) & (b.hasznal | b.elfogyaszt)) or a.szin == b.szin


def max_hozam(lepesek: list[Peldany]) -> int:
    return sum(p.hozam for p in lepesek)


def _tartalom(p: Peldany) -> tuple:
    return (p.sema.azon, p.szin, p.hozam,
            tuple((k.fajta, k.lap, k.hivo, getattr(k, "lopo", None)) for k in p.korok),
            tuple(sorted((x, str(v)) for x, v in p.szerepek.items() if not str(x).startswith("_"))))


def tervjeloltek(allas: Allas, technikak: dict, max_db: int = 60, igeny: int = 1,
                 ures: tuple[int, int] | None = None, max_szim: int | None = None) -> list[KTerv]:
    """A jelölt tervek: a biztos egységek (vesztőcsere, lopás — nincs rejtett
    feltételük) egy ütközésmentes készlete, és utánuk egy- vagy kételemű esélysor a
    többi technikából (az első próba: a kudarca nem kerül ütésbe, és nem fogyaszthatja
    el a második lapjait)."""
    P = [q for p in peldanyok(allas, technikak) for q in dobas_valtozatok(p, allas)]
    P += szinkezeles_peldanyok(allas, technikak, igeny, ures)
    # a biztos egységek sorrendje: előbb azok, amelyek nem adják ki a hívást (pl. a
    # vesztőcsere: a dobás a hívás elvesztése előtt — BridgeMasters #1), aztán a többi
    elobb = SZABALY["DOBAS_ELOBB"] and allas.adu is not None
    biztosak = sorted((p for p in P if biztos_egyseg(p)),
                      key=lambda p: (not (elobb and p.sema.azon == "VESZTOCSERE"),
                                     any(k.fajta in ("kiad", "impassz") for k in p.korok), -p.hozam))
    esely = [p for p in P if not biztos_egyseg(p)]
    adu_igeny = 0
    if allas.adu and SZABALY["ADU_IGENY"]:
        fm = _felmeres(allas, ures)
        sfa = next((x for x in fm.szinek if x.szin == allas.adu), None)
        if sfa is not None:
            keret_adu = max(0, fm.megengedett - (fm.kiado - sfa.kiado))
            # (a legrosszabb elosztással kötelezővé téve rontott: 4A01 #1, 4Q01 #2 — az
            # aduszín-egység ott jelölt, de a szimuláció dönt)
            adu_igeny = max(0, math.ceil(sfa.vesztok - keret_adu - 0.25))
            if adu_igeny and not any(p.szin == allas.adu for p in P):
                adu_igeny = 0            # nincs aduszín-egység (pl. túl sok kint lap)
    keszletek: list[list[Peldany]] = []
    rend = {id(p): i for i, p in enumerate(biztosak)}
    # a biztos egységek ütközésmentes készletei: mindegyik egységből indulva mohón
    # (így a változatok — pl. a két ♦-lopás vagy a dobás színei — mind sorra kerülnek)
    teljesek = []
    for p0 in biztosak:
        x = [p0]
        for p in biztosak:
            if p is not p0 and not any(_utkozik(p, q) for q in x):
                x.append(p)
        x.sort(key=lambda p: rend[id(p)])
        if x not in teljesek:
            teljesek.append(x)
    for x in teljesek + [[p] for p in biztosak] + [[]]:
        if x not in keszletek:
            keszletek.append(x)
    egy_keszletre = max(8, max_db // max(1, len(keszletek)))
    ki: list[KTerv] = []
    latott = set()

    # KOMBINACIO (a szerkesztő, 2026-11-21, BM A-11): pontos kombináció — ha egy szín
    # magában megoldja a partit (a kezelése ugyanazzal a vesztéskerettel fedi az igényt),
    # a kombinációban nem rögzíthető a maximuma alatt („a káró 2 ütésért nem pontos; a
    # káró 3 ütésért úgy, hogy a 2 ütés nincs kockáztatva”)
    megoldo = {(p.szin, int(p.szerepek.get("m", 0))): int(p.szerepek.get("k", 0))
               for p in P if p.sema.fajta == "elemzo" and p.hozam >= igeny
               and not p.szerepek.get("adu") and float(p.szerepek.get("esely", 0)) >= 0.5} \
        if SZABALY["KOMBINACIO"] else {}

    def hozzaad(lepesek):
        # a terv csak akkor jelölt, ha minden egysége sikere esetén fedi az igényt
        if max_hozam(lepesek) < igeny:
            return
        if megoldo and sum(1 for p in lepesek if p.sema.fajta == "elemzo") >= 2:
            for p in lepesek:
                if p.sema.fajta != "elemzo" or p.szerepek.get("adu"):
                    continue
                kk = megoldo.get((p.szin, int(p.szerepek.get("m", 0))))
                if kk is not None and kk > int(p.szerepek.get("k", 0)):
                    return
        if adu_igeny > 0:
            # ADU_IGENY: az aduszín vesztőtöbbletét csak az aduszín kezelése fedheti; a
            # lopás és a dobás csak a mellékszínek vesztőire számít
            adu_h = sum(p.hozam for p in lepesek if p.szin == allas.adu)
            mellek = sum(p.hozam for p in lepesek if p.szin != allas.adu)
            if adu_h < adu_igeny or min(mellek, max(0, igeny - adu_igeny)) + adu_h < igeny:
                return
        # BEDOBAS: a lopással eliminálandó színeket egy lopó egységnek kell
        # eltüntetnie (pl. asztalfordítás) — enélkül a bedobás nem működik
        for p in lepesek:
            for sz in (p.szerepek.get("LOPVA") or []) if p.sema.azon in ("BEDOBAS", "BEDOBAS_IMPASSZ") else []:
                if not any(q is not p and any(k.fajta == "lop" and k.szin == sz for k in q.korok)
                           for q in lepesek):
                    return
        if SZABALY["HASZNOS_DOBAS"] and any(
                p.sema.azon == "VESZTOCSERE" and p.szerepek.get("CELSZIN")
                and p.szerepek["CELSZIN"] != hasznos_dobas(p, lepesek, allas) for p in lepesek):
            return
        if allas.adu is None:
            # szanzaduban a biztos lehívások (vesztőcsere) a végére: előbb a szín
            # kifejlesztése, amíg az átmenetek megvannak; dobni úgysem lehet ellopni
            lepesek = ([p for p in lepesek if not biztos_egyseg(p)]
                       + [p for p in lepesek if biztos_egyseg(p)])
        # tartalom szerinti kulcs: ugyanaz az egység más szerepkötésből (pl. a két
        # kéz azonos hosszánál) ne legyen külön jelölt — az előszűrésben kiszorítaná a többit
        kulcs = tuple(_tartalom(p) for p in lepesek)
        if kulcs not in latott:
            latott.add(kulcs)
            ki.append(KTerv(list(lepesek), igeny,
                        terv_fazis(lepesek) if SZABALY["SZAKASZ"] else None,
                        allas.adu is not None))

    if igeny <= 0:
        hozzaad([])
    for alap in keszletek:
        eleje = len(ki)
        hozzaad(alap)
        szabad = [p for p in esely if not any(_utkozik(p, q) for q in alap)]
        for p in szabad:
            hozzaad(alap + [p])
        for a in szabad:
            if a.sema.kudarc_koltseg:
                continue
            for b in szabad:
                if len(ki) - eleje >= egy_keszletre:
                    break
                if a is b or a.elfogyaszt & (b.hasznal | b.elfogyaszt):
                    continue
                hozzaad(alap + [a, b])
    if ki and max_szim:
        # előszűrés a források esélyéből: csak a legjobbak mennek a szimulációba
        eselyek = {id(p): egyseg_esely(p, allas, ures) for p in P}
        for t in ki:
            t.elozetes = elozetes_esely(t, eselyek)
        # egyenlő előzetes esélynél (pl. csupa biztos egység: 100%) az egyszerűbb terv
        # előbb — a szimuláció dönt, de csak a legjobb `max_szim` jut el oda
        # FOGAS_VEDES (a szerkesztő, 2026-11-23): a kiadás / kiengedés feltétele a megfelelő
        # fogás minden színben — a feltételt teljesítő tervek előbb jutnak a szimulációba
        # (kizárva nincs egyik sem: ha nincs jobb, a szimuláció dönt)
        if SZABALY["FOGAS_VEDES"]:
            from .tervfogas import terv_feltetel
            for t in ki:
                t.fogas_ok = terv_feltetel(allas, t)
        ki.sort(key=lambda t: (not getattr(t, "fogas_ok", True), -round(t.elozetes, 3), len(t.lepesek)))
        ki = ki[:max_szim]
    if not ki:
        # egyik terv sem fedi az igényt: a legtöbbet hozók (a tartalék dönt majd)
        osszes = sorted(P, key=lambda p: -p.hozam)
        valasztott: list[Peldany] = []
        for p in osszes:
            if not any(_utkozik(p, q) for q in valasztott):
                valasztott.append(p)
        ki.append(KTerv(valasztott, igeny, tuple(alap_fazis(p) for p in valasztott), allas.adu is not None))
    return ki[:max_db]


# --- 2. A végrehajtó ------------------------------------------------------------------

# MEGFIGYELT_NYERO régi része: a negyedik kéz „nem ütött fölé” következtetése (kikapcsolva)
NEGYEDIK_KOVETKEZTETES = _os.getenv("KIBIC_K_NEGYEDIK_KOVETKEZTETES", "0") != "0"


# a hozzátevési séma teendője a kényszerben (Vegrehajto.kenyszer): a színből a legkisebb lap
KICSI = "KICSI"


class Vegrehajto:
    """A felvevő oldal politikája egy világon: a terv egységei körökre bontva."""

    def __init__(self, terv: KTerv, j: tj.Jatek, naplo: list | None = None):
        self.egysegek = [Egyseg(p, fazis=(terv.fazis[i] if terv.fazis else None))
                         for i, p in enumerate(terv.lepesek)]
        self.szakaszos = terv.fazis is not None
        self.j = j
        self.adu = j.adu
        self.folyo: tuple | None = None      # (egység, kör, az ütés kezdő indexe)
        self.szandek: dict[str, tuple] = {}  # a partner kéz teendője a mostani ütésben
        self.szandek_utes = -1
        self.naplo = naplo
        self.cel = None                      # az összes kell ütés (a lejátszó adja)
        self.igeny = terv.igeny
        # a megszerzett hozam: a biztos egységeké előre beszámít
        self.megszerzett = sum(e.p.hozam for e in self.egysegek if e.biztos)
        self.kitekintes = False              # előrenézés (egyszerű védőkkel): még nem segít, lásd a doksit
        self.politikak: dict[int, object] = {}   # az elemzős egységek politikája (egység sorszáma)
        self.kezdo = len(j.lapok)
        self.feldolgozott = len(j.lapok) - len(j.lapok) % 4
        self.kitekintes_db = 5
        self.kitekintes_vilag = 4

    # -- látott tények --
    def _mi_kezek(self) -> tuple[str, str]:
        return (self.j.felvevo, self.j.asztal)

    def _kint_felett(self, l: Lap) -> bool:
        return any(x.rang > l.rang for x in self.j.kint(l.szin))

    def _nyero(self, l: Lap) -> bool:
        return not self._kint_felett(l)

    def _megfigyelt_nyero(self, l: Lap, utes) -> bool:
        """A folyó ütésben `l` biztosan üt-e a látott lapok szerint (MEGFIGYELT_NYERO, a
        szerkesztő 2026-11-21, BM A-2 #5): ha a színt élő elemzős egység kezeli, a
        tartásai közül csak azok maradnak, amelyek a lement lapokkal összeférnek (egy
        sikerült impassz után a király nem lehet a mögötte ülő védőnél). Ha a még tevő
        védőknek egyik ilyen tartásban sincs `l`-nél nagyobb lapja, `l` biztos ütés."""
        if self._nyero(l):
            return True
        if not SZABALY["MEGFIGYELT_NYERO"]:
            return False
        j = self.j
        sz = l.szin
        pol = next((p for ei, p in self.politikak.items()
                    if self.egysegek[ei].p.szin == sz and self.egysegek[ei].el), None)
        if pol is None or (self.adu and sz != self.adu and any(
                x.szin == self.adu for _, x in utes)):
            return False
        try:
            _, idx, l1, l2, *_ = pol.node
            tart = [(pol.el.tart[i][0] - l1[n], pol.el.tart[i][1] - l2[n]) for n, i in enumerate(idx)]
        except Exception:                        # noqa: BLE001
            return False
        if not tart:
            return False
        v1, v2 = kovetkezo_ules(j.felvevo, 1), kovetkezo_ules(j.felvevo, 3)
        tett = {u for u, _ in utes}
        latott = {v: {x.rang for u, x in utes if u == v and x.szin == sz} for v in (v1, v2)}
        hatra = [v for v in (v1, v2) if v not in tett]
        if not hatra:
            return True
        # a korábbi ütések a színben: ha a negyedik kéz védője nem ütött fölé, pedig
        # tudott volna, az ilyen tartás kiesett — EZ MÁR NEM ÉL (a szerkesztő,
        # 2026-11-22): a felvevő hívására tett lapjukból nem olvasunk semmit (nincs
        # ütéskényszer); a lement lap csak annyit mond, hogy nála volt.
        L = j.lapok if NEGYEDIK_KOVETKEZTETES else []
        kesz = len(L) - len(L) % 4
        negyedik = []                            # (védő, a nyerő rangja, később tett lapjai)
        for i in range(0, kesz, 4):
            ut = L[i:i + 4]
            if ut[0][1].szin != sz:
                continue
            gy, gl = j.nyertes(ut)
            d, dl = ut[3]
            if j.mi(gy) and gl.szin == sz and d in (v1, v2) and dl.szin == sz and dl.rang < gl.rang:
                kesobb = {x.rang for u, x in L[i + 4:] if u == d and x.szin == sz}
                negyedik.append((d, gl.rang, kesobb))
        for a, b in tart:
            kez = {v1: a, v2: b}
            if any(not latott[v] <= kez[v] for v in (v1, v2)):
                continue                         # a látott lappal össze nem férő tartás
            if any(any(r > w for r in (kez[d] | k)) for d, w, k in negyedik):
                continue                         # a negyedik kéz nem engedett volna
            if any(r > l.rang for v in hatra for r in kez[v]):
                return False
        return True

    def _bedobasra_var(self, e: "Egyseg") -> bool:
        """BEDOBAS_TARTALEK: a kényszerszín egysége vár, amíg a bedobás körei tartanak;
        a sikeres bedobás után elmarad (a kényszerszínt a védő nyitja), csak a kudarca
        után indul."""
        if not SZABALY["BEDOBAS_TARTALEK"]:
            return False
        if e.allapot == "var" and any(
                b is not e and b.allapot in ("siker", "kesz") and b.p.sema.azon in ("BEDOBAS", "BEDOBAS_IMPASSZ")
                and e.p.szin in (b.p.szerepek.get("K") or []) for b in self.egysegek):
            e.allapot = "elmarad"
            return True
        return any(b is not e and b.allapot == "var" and b.p.sema.azon in ("BEDOBAS", "BEDOBAS_IMPASSZ")
                   and e.p.szin in (b.p.szerepek.get("K") or []) for b in self.egysegek)

    def _bedobas_folosleges(self, e: "Egyseg", k: Kor) -> bool:
        if not SZABALY["BEDOBAS_TARTALEK"] or e.p.sema.azon != "BEDOBAS":
            return False
        j = self.j
        mi = max((l.rang for u in self._mi_kezek() for l in j.szin(u, k.szin)), default=0)
        return mi > 0 and not any(l.rang > mi for l in j.kint(k.szin))

    def _bedobas_borult(self, e: "Egyseg") -> bool:
        """Az aduszín a kiadó szín, a felső adukat már lehívtuk, de a mieink fölött
        vagy mellett egynél több adu maradt kint (pl. 4-1-es aduelosztás): a nyerő védő
        adut hívhat vissza (vagy egy eliminált színt kis aduval lop) — a bedobás nem
        kényszerít, a tartaléka (a kényszerszín egysége) indul."""
        if not SZABALY["BEDOBAS_TARTALEK"] or e.p.sema.azon != "BEDOBAS" or e.p.szin != self.adu:
            return False
        j = self.j
        mieink = j.kezek[j.felvevo] | j.kezek[j.asztal]
        if any(l in mieink for l in (e.p.szerepek.get("NY") or [])):
            return False
        return len(j.kint(e.p.szin)) > 1

    def _kint_adu(self) -> int:
        return len(self.j.kint(self.adu)) if self.adu else 0

    def _tartalek(self) -> int:
        """Ennyi ütést veszthetünk még (a kiadási keret)."""
        if self.cel is None:
            return 0
        j = self.j
        kesz = len(j.lapok) // 4
        mi = j.felvevo_utesek()
        return (13 - self.cel) - (kesz - mi)

    def _fogas_foglalt(self) -> set[Lap]:
        """FOGAS_VEDES (a szerkesztő, 2026-11-23): a megfelelő fogás lapjai nem átmenetek
        és nem dobhatók, amíg a hátralévő tervezett ütések — a fogás ütésével együtt —
        nincsenek meg biztos ütésként, és amíg a terv még ütést ad ki (a kiadás feltétele a
        megfelelő fogás). A tervezett ütés a terv célja (`cel`)."""
        from .tervfogas import biztos_utesek, foglalt_fogas, tervezett_vesztes
        j = self.j
        if self.cel is None:
            return set()
        kulcs = len(j.lapok)
        tar = getattr(self, "_fogas_tar", None)
        if tar is not None and tar[0] == kulcs:
            return tar[1]
        kezek = {u: list(j.kezek[u]) for u in (j.felvevo, j.asztal)}
        kint = [l for sz in "SHDC" for l in j.kint(sz)]
        kell = self.cel - j.felvevo_utesek()
        szinek = {e.p.szin for e in self._aktiv() if not biztos_egyseg(e.p) and e.p.szin}
        tervezett = tervezett_vesztes(kezek, kint, szinek)
        ki: set[Lap] = set()
        # a fogás szabad, ha a tervezett ütések (a fogáséval együtt) biztosan megvannak, és a
        # terv már nem ad ki ütést (a kiadás feltétele a megfelelő fogás)
        if kell > 0 and (tervezett > 0 or biztos_utesek(kezek, kint, self.adu) < kell):
            ki = foglalt_fogas(kezek, kint, self.adu, self._tartalek() - tervezett)
        self._fogas_tar = (kulcs, ki)
        return ki

    def _jegyez(self, s: str):
        if self.naplo is not None:
            self.naplo.append(f"{len(self.j.lapok) // 4 + 1}. ütés: {s}")

    # -- foglalások --
    def _aktiv(self) -> list[Egyseg]:
        return [e for e in self.egysegek if e.el]

    def _foglalt(self) -> set[Lap]:
        """A még élő egységek lapjai, és a köreikhez szükséges kis lapok."""
        f: set[Lap] = set()
        mieink = self.j.kezek[self.j.felvevo] | self.j.kezek[self.j.asztal]
        # a hozzátevési séma megtartott lapjai (Bath-csel: a szín fogásai — nem átmenet,
        # nem dobás, a védők színe ellen kellenek)
        f |= getattr(self, "megtart", set()) & mieink
        if SZABALY["FOGAS_VEDES"]:
            f |= self._fogas_foglalt()
        aktiv = self._aktiv()
        for e in aktiv:
            f |= (e.p.hasznal | e.p.elfogyaszt) & mieink

        def kicsit(kez, sz):
            kicsi = [l for l in self.j.szin(kez, sz) if l not in f]
            if kicsi:
                f.add(kicsi[0])

        for e in aktiv:
            for k in e.p.korok[e.i:]:
                if k.fajta == "impassz" and k.hivo:
                    kicsit(k.hivo, k.szin)                 # a kéz felé hívott kis lap
                elif k.fajta in ("lop", "kiad") and k.hivo:
                    kicsit(k.hivo, k.szin)                 # a lopásra / a kiadásra hívott kis lap
                elif k.fajta == "lehiv" and k.lap is not None and k.lap in mieink:
                    # kísérő lap: a másik kéz is tesz egy lapot, ne a kulcslapját
                    X = j_keze(self.j, k.lap)
                    Y = self.j.partner(X)
                    if self.j.szin(Y, k.szin) and not any(
                            kk.lap in self.j.kezek[Y] for kk in e.p.korok if kk is not k and kk.lap is not None
                            and kk.szin == k.szin and kk.fajta == "lehiv" and False):
                        kicsit(Y, k.szin)
        return f

    def _lopas_igeny(self, kez: str) -> int:
        return sum(1 for e in self._aktiv() for k in e.p.korok[e.i:]
                   if k.fajta == "lop" and k.lopo == kez)

    def _adukor_mehet(self) -> bool:
        """Egy adukör nem viheti el a lopásokra foglalt adukat; az aduszín elemzős
        kezelése alatt (az a kiaduzás) nincs általános adukör."""
        if not self.adu:
            return False
        if any(e.el and e.p.sema.fajta == "elemzo" and e.p.szin == self.adu for e in self.egysegek):
            return False
        for u in self._mi_kezek():
            n = len(self.j.szin(u, self.adu))
            if n - (1 if n else 0) < self._lopas_igeny(u):
                return False
        return True

    # -- egy körünk eredménye --
    def _szerep(self, u: str) -> str:
        j = self.j
        if u == j.felvevo:
            return "X"
        if u == j.asztal:
            return "Y"
        return "V1" if u == kovetkezo_ules(j.felvevo, 1) else "V2"

    def _politika_lep(self):
        """A lement teljes ütések az elemzős egységek politikájának (a szín ütései)."""
        from .tervszinkezeles import LOP
        j = self.j
        while self.feldolgozott + 4 <= len(j.lapok):
            utes = j.lapok[self.feldolgozott:self.feldolgozott + 4]
            self.feldolgozott += 4
            hivott = utes[0][1].szin
            for ei, pol in list(self.politikak.items()):
                sz = self.egysegek[ei].p.szin
                if hivott != sz:
                    continue
                lepes = []
                for u, l in utes:
                    if l.szin == sz:
                        c = l.rang
                    elif self.adu and l.szin == self.adu and sz != self.adu:
                        c = LOP
                    else:
                        c = None
                    lepes.append((self._szerep(u), c))
                try:
                    pol.lep(tuple(lepes))
                except Exception:                # noqa: BLE001 — a politika elveszett: újraépül
                    del self.politikak[ei]

    def _atm_nyers(self, sz: str):
        j = self.j
        if sz == self.adu and not SZABALY["ELEMZO_ATM_ADU"]:
            return None, None
        return elemzo_atmenetek(
            {j.felvevo: set(j.kezek[j.felvevo]), j.asztal: set(j.kezek[j.asztal])},
            j.felvevo, j.asztal, [l for s_ in "SHDC" for l in j.kint(s_)], self.adu, sz)

    def _atmenet_elosztas(self, ei: int, ax: int, ay: int) -> tuple[int, int]:
        """ATMENET_ELOSZTAS (általános szabály, a szerkesztő 2026-11-20, BM A-2 #5): ha két
        színkezelés ugyanazokra az átmenetekre számít, a terv osztja el őket úgy, hogy a
        két kezelés együttes esélye a legnagyobb legyen. „Az 1. problémát (a ♠K
        elfogása, két impassz) csak egy módon lehet megoldani, ahhoz két híd kell az
        asztalra; a 2. probléma (a kőr) megoldásához nem marad asztalra menet, tehát csak
        az eltalálás marad.” Visszaadja az `ei` egységnek jutó átmeneteket."""
        if not SZABALY["ATMENET_ELOSZTAS"]:
            return ax, ay
        masok = []
        for ej, e in enumerate(self.egysegek):
            if ej == ei or not e.el or e.p.sema.fajta != "elemzo" or not self.j.kint(e.p.szin):
                continue
            pj = self._politika(ej, osztas=False)
            if pj is not None and pj.el.korlatos:
                masok.append(pj)
        if len(masok) != 1:
            return ax, ay
        pi, pj = self.politikak.get(ei), masok[0]
        if pi is None or not pi.el.korlatos:
            return ax, ay
        hol_i = pi.node[0][6]
        legjobb, val = None, (ax, ay)
        for a in range(0, ax + 1):
            for b in range(0, ay + 1):
                p = pi.esely_atmenettel(a, b, hol_i) * pj.esely_atmenettel(ax - a, ay - b, "-")
                kulcs = (round(p, 6), a + b)          # egyenlő esélynél a több
                if legjobb is None or kulcs > legjobb:
                    legjobb, val = kulcs, (a, b)
        return val

    def _hivas_atadasa(self, ei: int) -> int | None:
        """ATMENET_ELOSZTAS, a mostani hívással (a szerkesztő 2026-11-21, BM A-2 #5): a kéz,
        amelyben most a hívás van, maga is egy átmenet. Ha két elemzős kezelés verseng az
        átmenetekért, és a másik kezelés ebből a kézből jobban tud indulni (az együttes
        esély nagyobb), most a másik kezelés köre jön. „Ha az asztalon kell ütnünk, onnan
        pikk impasszal jövünk kézbe az aduzás befejezéséhez.” Visszaadja a másik egység
        indexét, vagy None-t."""
        if not (SZABALY["ATMENET_ELOSZTAS"] and SZABALY["HIVAS_ATADAS"]):
            return None
        j = self.j
        if j.aktualis():
            return None
        soron = j.soron()
        if soron not in (j.felvevo, j.asztal):
            return None
        hol = "X" if soron == j.felvevo else "Y"
        pi = self._politika(ei)
        if pi is None or not pi.el.korlatos:
            return None
        ax, ay = self._atm_nyers(self.egysegek[ei].p.szin)
        if ax is None:
            return None
        masik = None
        for ej, e in enumerate(self.egysegek):
            if ej == ei or not e.el or e.p.sema.fajta != "elemzo" or not j.kint(e.p.szin):
                continue
            k = e.kor()
            if k is None or k.fajta != "elemzo":
                continue
            pj = self._politika(ej, osztas=False)
            if pj is not None and pj.el.korlatos:
                if masik is not None:
                    return None
                masik = (ej, pj)
        if masik is None:
            return None
        ej, pj = masik
        akc = pj.dontes()
        if akc is None or akc[0] != hol:
            return None                       # a másik kezelés sem innen indulna

        def legjobb(hol_i, hol_j):
            return max(pi.esely_atmenettel(a, b, hol_i) * pj.esely_atmenettel(ax - a, ay - b, hol_j)
                       for a in range(ax + 1) for b in range(ay + 1))
        # a másik kezelés köre után a hívás ott lesz, ahol a színben a nagyobb lapunk
        # van (egy impassz a villa kezében végződik, ha sikerül)
        szj = self.egysegek[ej].p.szin
        H, P = (j.felvevo, j.asztal) if hol == "X" else (j.asztal, j.felvevo)
        hlap = [l.rang for l in j.szin(H, szj)]
        plap = [l.rang for l in j.szin(P, szj)]
        utana = ("Y" if hol == "X" else "X") if plap and (not hlap or max(plap) > max(hlap)) else hol
        marad = legjobb(hol, "-")
        atad = legjobb(utana, hol)
        if atad > marad + 0.02:
            self._jegyez(f"a hívás a {self.egysegek[ej].p.rovid} kezelésé "
                         f"(együtt {atad:.0%}, nem {marad:.0%})")
            return ej
        return None

    def _politika(self, ei: int, osztas: bool = True):
        """Az elemzős egység politikája (lustán; ha a lapjaink nem egyeznek, újraépül a
        mostani állásból, a cél még hiányzó részével)."""
        from .tervszinpolitika import SzinPolitika
        j = self.j
        e = self.egysegek[ei]
        sz = e.p.szin
        X = frozenset(l.rang for l in j.szin(j.felvevo, sz))
        Y = frozenset(l.rang for l in j.szin(j.asztal, sz))
        pol = self.politikak.get(ei)
        if pol is not None and SZABALY["KOMBINACIO"] and self.cel is not None \
                and pol.m > max(0, self._tartalek()):
            pol = None                           # a közös keret szűkült: újraépül (KOMBINACIO)
        if pol is not None and pol.lapjaink() == (X, Y):
            ax, ay = self._atm_nyers(sz)
            if ax is not None and not j.aktualis():
                soron = j.soron()
                pol.frissit(ax, ay, "X" if soron == j.felvevo else ("Y" if soron == j.asztal else "-"))
                if osztas:
                    ax2, ay2 = self._atmenet_elosztas(ei, ax, ay)
                    if (ax2, ay2) != (ax, ay):
                        pol.frissit(ax2, ay2, pol.node[0][6])
            return pol
        # a cél: a terv óta a színben szerzett / vesztett ütések levonásával
        nyert = vesztett = 0
        L = j.lapok
        for i in range(self.kezdo - self.kezdo % 4, len(L) - len(L) % 4, 4):
            ut = L[i:i + 4]
            if len(ut) == 4 and sz == self.adu and ut[0][1].szin != sz:
                # az aduszín kezelésében a lopásunk is aduütés (egy adunk elfogyott rá)
                gy, gl = j.nyertes(ut)
                if j.mi(gy) and gl.szin == sz:
                    nyert += 1
                continue
            if len(ut) < 4 or ut[0][1].szin != sz:
                continue
            gy, gl = j.nyertes(ut)
            if j.mi(gy):
                nyert += gl.szin == sz
            else:
                vesztett += 1
        ut = j.aktualis()
        if ut and sz == self.adu and ut[0][1].szin != sz and any(j.mi(u_) and l_.szin == sz for u_, l_ in ut):
            nyert += 1        # a folyó ütésben lopunk: aduütés (a lopó adu kikerült a kezünkből)
        k = e.p.szerepek["k"] - nyert
        m = e.p.szerepek["m"] - vesztett
        if SZABALY["KOMBINACIO"] and self.cel is not None:
            # KOMBINACIO: a vesztéskeret közös — a kezelés legfeljebb annyit veszíthet,
            # amennyi a teljes keretből még megmaradt (BM A-11: a ♦A kiadása után a ♣ már
            # vesztés nélkül, a látott lapok szerinti legbiztosabb módon)
            m = min(m, max(0, self._tartalek()))
        kint = frozenset(l.rang for l in j.kint(sz))
        v1, v2 = kovetkezo_ules(j.felvevo, 1), kovetkezo_ules(j.felvevo, 3)
        ures = list(szabad_helyek(L, v1, v2))
        lx, ly = elemzo_lopasok(self.adu, sz, len(j.szin(j.felvevo, self.adu)) if self.adu else 0,
                                len(j.szin(j.asztal, self.adu)) if self.adu else 0,
                                len(j.kint(self.adu)) if self.adu else 0,
                                len(X), len(Y), len(kint))
        ax, ay = self._atm_nyers(sz)
        hivas = None
        if ax is not None:
            soron = j.soron() if not j.aktualis() else None
            hivas = "X" if soron == j.felvevo else ("Y" if soron == j.asztal else "-")
        try:
            pol = SzinPolitika(X, Y, kint, ures[0], ures[1], k, m, sz == self.adu, lx, ly, ax, ay, hivas)
        except Exception:                        # noqa: BLE001
            return None
        self.politikak[ei] = pol
        if osztas and ax is not None:
            ax2, ay2 = self._atmenet_elosztas(ei, ax, ay)
            if (ax2, ay2) != (ax, ay):
                pol.frissit(ax2, ay2, pol.node[0][6])
        return pol

    def _frissit(self):
        j = self.j
        self._politika_lep()
        if self.folyo and len(j.lapok) >= self.folyo[2] + 4:
            e, k, kezd = self.folyo
            nyu, _ = j.nyertes(j.lapok[kezd:kezd + 4])
            if k.fajta == "impassz":
                if j.mi(nyu):
                    self._siker(e)
                    e.allapot = "siker"
                else:
                    e.allapot = "kudarc"
                    self._jegyez(f"{e.p.rovid}: nem sikerült")
            if k.fajta != "elemzo":                # az elemzős egység körei a politikában
                e.i += 1
            self.folyo = None

    def _siker(self, e: Egyseg):
        self._jegyez(f"{e.p.rovid}: sikerült")
        # az esélyek sora: ha egy sikerült, a többi elmarad (a lapjaik szabadok)
        if e.biztos:
            return
        self.megszerzett += e.p.hozam
        if self.megszerzett < self.igeny:
            return                               # még hiányzik: a többi esély is kell
        for x in self.egysegek:
            if x is not e and x.allapot == "var" and not x.biztos:
                x.allapot = "elmarad"

    # -- döntés --
    def lap(self, u: str) -> Lap:
        self._frissit()
        j = self.j
        kv = getattr(self, "kenyszer", None)
        if kv and len(j.lapok) in kv and kv[len(j.lapok)][0] == u:
            # HIVASRA_TETT_LAP: a terv lapja a védő hívására (a tervezéskor kiválasztva) —
            # egy lap, vagy a hozzátevési séma teendője (KICSI: a színből a legkisebb)
            d = kv[len(j.lapok)]
            l = d[1]
            ok = d[2] if len(d) > 2 and d[2] else "a terv lapja a hívásra (a tervek szimulációja szerint)"
            if l == KICSI:
                utes = j.aktualis()
                van = j.szin(u, utes[0][1].szin) if utes else []
                l = min(van, key=lambda x: x.rang) if van else None
            if l is not None and l in j.kezek[u]:
                self._jegyez(f"{l}: {ok}")
                return l
        utes_i = len(j.lapok) // 4
        if self.szandek_utes != utes_i:
            self.szandek, self.szandek_utes = {}, utes_i
        if not j.aktualis():
            return self._hivas(u)
        return self._kovetes(u)

    def _elotte_aktiv(self) -> bool:
        """Van-e még élő, kiaduzás előtti egység (a szakaszos tervben)."""
        return self.szakaszos and any(e.el and e.fazis == "E" and e.kor() is not None
                                      for e in self.egysegek)

    def _egyseg_sor(self, csak: str | None = None) -> list:
        """Az egységek sora; ha az első élő elemzős egység a mostani hívást egy másik
        elemzős egységnek adja át (HIVAS_ATADAS), az kerül előre."""
        sor = list(self.egysegek)
        for ei, e in enumerate(sor):
            if (csak is not None and e.fazis != csak) or not e.el:
                continue
            k = e.kor()
            if k is None or k.fajta != "elemzo":
                return sor
            ej = self._hivas_atadasa(ei)
            if ej is not None and (csak is None or self.egysegek[ej].fazis == csak):
                sor.remove(self.egysegek[ej])
                sor.insert(ei, self.egysegek[ej])
            return sor
        return sor

    def _kovetkezo_kor(self, csak: str | None = None) -> tuple[Egyseg, Kor] | None:
        """Az esélyek sorában az első élő egység soron következő köre. A már lement
        lapok köreit (átmenetként vagy védői hívásra tettük le) átlépi; a `csak_ha:
        siker` körnél dönt: a lap most nyerő-e (megfigyelt tény)."""
        j = self.j
        mieink = j.kezek[j.felvevo] | j.kezek[j.asztal]
        sor = self._egyseg_sor(csak)
        for e in sor:
            if csak is not None and e.fazis != csak:
                continue
            if self._bedobasra_var(e):
                continue
            while e.el:
                k = e.kor()
                if k is not None and k.fajta == "elemzo":
                    ei = self.egysegek.index(e)
                    pol = self._politika(ei)
                    akc = pol.dontes() if pol is not None else None
                    if SZABALY["KIMERULT"] and akc is None and pol is not None and pol.k > 0 and pol.m >= 0 \
                            and not j.kint(e.p.szin) and max(len(j.szin(j.felvevo, e.p.szin)),
                                                             len(j.szin(j.asztal, e.p.szin))) >= pol.k:
                        # a színben már nincs kint lap: a hátralévő ütések biztosak (a
                        # döntési fa itt véget ér), a begyűjtés viszi őket. Az egység
                        # lezárul, de a hozamát nem könyveljük: a terv többi egysége
                        # (pl. egy szöktetés) így tovább él — ez mérve jobb
                        e.allapot = "kudarc"
                        self._jegyez(f"{e.p.rovid}: a színben nincs több kint lap — a maradék begyűjtés")
                        break
                    if akc is None:
                        if pol is not None and pol.k <= 0:
                            if e.allapot == "var":
                                self._siker(e)
                            e.allapot = "kesz"
                        else:
                            e.allapot = "kudarc"
                            self._jegyez(f"{e.p.rovid}: nem sikerült (a látott lapokkal már nem érhető el)")
                        break
                    hivo = j.felvevo if akc[0] == "X" else j.asztal
                    lap = next((l for l in j.szin(hivo, k.szin) if l.rang == akc[1]), None)
                    if lap is None:
                        e.allapot = "kudarc"
                        break
                    return e, Kor("elemzo", k.szin, lap=lap, hivo=hivo)
                if k is None:
                    if e.allapot == "var":
                        self._siker(e)
                    e.allapot = "kesz"
                    break
                if k.fajta == "lehiv" and k.lap is not None and k.lap not in mieink:
                    e.i += 1
                    continue
                if k.fajta == "kiad" and self._bedobas_folosleges(e, k):
                    # a kiadandó vesztő eltűnt (pl. a hiányzó adudáma leesett): nincs mit
                    # kiadni — a bedobás célja teljesült, a tartaléka elmarad
                    self._jegyez(f"{e.p.rovid}: nincs kiadandó vesztő — a terv teljesült")
                    if e.allapot == "var":
                        self._siker(e)
                    e.allapot = "kesz"
                    break
                if self._bedobas_borult(e):
                    e.allapot = "kudarc"
                    self._jegyez(f"{e.p.rovid}: nem sikerült (a kiadás után a védőnek marad kijátszója)")
                    break
                if k.fajta == "impassz" and k.lap is not None and k.lap not in mieink:
                    # a villa lapja egy védői hívásra már lement: a megfigyelés dönt
                    e.i += 1
                    if self._utott(k.lap):
                        if e.allapot == "var":
                            self._siker(e)
                        e.allapot = "siker"
                    else:
                        e.allapot = "kudarc"
                        self._jegyez(f"{e.p.rovid}: nem sikerült ({k.lap} nem ütött)")
                    continue
                if k.csak_ha_siker and k.lap is not None:
                    if not self._nyero(k.lap):
                        e.allapot = "kudarc"
                        self._jegyez(f"{e.p.rovid}: nem sikerült ({k.lap} nem nyerő)")
                        break
                    if e.allapot == "var":
                        self._siker(e)
                        e.allapot = "siker"
                return e, k
        return None

    def _kovetkezo_hivo(self) -> str | None:
        """Melyik kezünkből indul a terv következő köre (mellékhatás nélkül)."""
        j = self.j
        mieink = j.kezek[j.felvevo] | j.kezek[j.asztal]
        elotte = self._elotte_aktiv()
        for e in self.egysegek:
            if not e.el or (elotte and e.fazis != "E") or self._bedobasra_var(e):
                continue
            for k in e.p.korok[e.i:]:
                if k.lap is not None and k.lap not in mieink:
                    continue
                if k.fajta == "elemzo":
                    pol = self.politikak.get(self.egysegek.index(e))
                    akc = pol.dontes() if pol is not None else None
                    if akc is None:
                        return None
                    return j.felvevo if akc[0] == "X" else j.asztal
                if k.fajta == "kiad":
                    for kez in (j.felvevo, j.asztal):
                        if any(not self._nyero(l) for l in j.szin(kez, k.szin)):
                            return None          # bármelyik kézből mehet
                    return k.hivo
                if k.fajta in ("impassz", "lop"):
                    return k.hivo
                if k.fajta == "lehiv" and k.lap is not None:
                    return j_keze(j, k.lap)
                return None
        return None

    def _utott(self, lap: Lap) -> bool:
        """A lement `lap` vitte-e az ütését."""
        L = self.j.lapok
        for i, (_, l) in enumerate(L):
            if l == lap:
                kezd = i - i % 4
                if kezd + 4 > len(L):
                    return False
                return self.j.nyertes(L[kezd:kezd + 4])[1] == lap
        return False

    def _adu_nyero(self) -> Lap | None:
        if not self.adu:
            return None
        for u in self._mi_kezek():
            for l in reversed(self.j.szin(u, self.adu)):
                if self._nyero(l):
                    return l
        return None

    # -- hívás: a jelölt körök, és a lánc előrenézése --
    def _hivas(self, H: str) -> Lap:
        jel = self._jeloltek(H)
        if self.kitekintes and len(jel) > 1:
            v = self._kitekint(jel)
        else:
            v = jel[0]
        self._alkalmaz(v)
        return v.lap

    def _alkalmaz(self, v: "Jelolt"):
        self.szandek.update(v.szandek)
        if v.folyo is not None:
            ei, k = v.folyo
            self.folyo = (self.egysegek[ei], k, len(self.j.lapok))
        self._jegyez(v.leiras)

    def _bedobas_frissites(self):
        """A borult bedobás már a jelöltek előtt kudarc: a kiaduzás és a tartalék
        egység ugyanebben a lépésben a helyzethez igazodik."""
        for e in self.egysegek:
            if e.allapot == "var" and self._bedobas_borult(e):
                e.allapot = "kudarc"
                self._jegyez(f"{e.p.rovid}: nem sikerült (a kiadás után a védőnek marad kijátszója)")

    def _jeloltek(self, H: str) -> list["Jelolt"]:
        self._bedobas_frissites()
        if self.szakaszos:
            return self._jeloltek_szakaszos(H)
        out: list[Jelolt] = []
        kk = self._kovetkezo_kor()
        if self._kint_adu() and self._adukor_mehet():
            adu = self._adukor_jeloltek(H, 0)
            # a nyerők begyűjtése előtt aduzni kell (különben ellopják): ilyenkor a felső
            # adu kiütése is az egység köre elé kerül
            begyujt = kk is None or kk[1].begyujtes or kk[1].csak_ha_siker
            if begyujt:
                for v in adu:
                    v.ar = min(v.ar, -0.5)
            out += adu
        while kk is not None:
            e, k = kk
            ej = self._egyseg_jeloltek(H, e, k, 1)
            if ej:
                out += ej
                break
            e.allapot = "kudarc"
            self._jegyez(f"{e.p.rovid}: nem játszható (nincs átmenet)")
            kk = self._kovetkezo_kor()
        if kk is None:
            out += self._begyujtes_jeloltek(H, 1)
        if not out:
            out.append(self._feladas(H))
        out.sort(key=lambda v: v.ar)
        egyedi, latott = [], set()
        for v in out:
            if v.lap not in latott:
                latott.add(v.lap)
                egyedi.append(v)
        return egyedi

    def _jeloltek_szakaszos(self, H: str) -> list["Jelolt"]:
        """A szakaszos terv: előbb a kiaduzás előtti egységek (aduzás nélkül), aztán a
        kiaduzás (felső aduval vagy a felső adu kiütésével), aztán a többi egység és a
        begyűjtés."""
        out: list[Jelolt] = []
        kk = None
        if self._elotte_aktiv():
            kk = self._kovetkezo_kor("E")
            while kk is not None:
                e, k = kk
                ej = self._egyseg_jeloltek(H, e, k, 1)
                if ej:
                    out += ej
                    break
                e.allapot = "kudarc"
                self._jegyez(f"{e.p.rovid}: nem játszható (nincs átmenet)")
                kk = self._kovetkezo_kor("E")
        if not out:
            if self._kint_adu() and self._adukor_mehet():
                adu = self._adukor_jeloltek(H, 0)
                for v in adu:
                    v.ar = -1.0
                out += adu
            kk = self._kovetkezo_kor()
            while kk is not None:
                e, k = kk
                ej = self._egyseg_jeloltek(H, e, k, 1)
                if ej:
                    out += ej
                    break
                e.allapot = "kudarc"
                self._jegyez(f"{e.p.rovid}: nem játszható (nincs átmenet)")
                kk = self._kovetkezo_kor()
            if kk is None:
                out += self._begyujtes_jeloltek(H, 1)
        if not out:
            out.append(self._feladas(H))
        out.sort(key=lambda v: v.ar)
        egyedi, latott = [], set()
        for v in out:
            if v.lap not in latott:
                latott.add(v.lap)
                egyedi.append(v)
        return egyedi

    def _adu_leallas(self) -> bool:
        """ADU_LEALLAS (általános szabály, a szerkesztő 2026-11-20, BM A-2 #4): nem
        hívunk több adut, ha a védők maradék adui mind nagyobbak a mieinknél (minden
        adukör csak kiadás, és két adunkba kerül), és beleférnek a kiadási keretbe a
        többi vesztővel együtt. Ilyenkor a magas lapjainkat hívjuk, és hagyjuk, hogy
        ellopják, amelyiket akarják: a védő minden aduja legfeljebb egy ütés, a mi
        aduink pedig a lopatás ellen kellenek. ♠A5432 / ♠876, kint KQJT9: az ász után
        megállunk."""
        if not self.adu or not SZABALY["ADU_LEALLAS"]:
            return False
        j, adu = self.j, self.adu
        kint = j.kint(adu)
        if not kint:
            return False
        mi = [l for u in self._mi_kezek() for l in j.szin(u, adu)]
        if not mi or max(l.rang for l in mi) > min(l.rang for l in kint):
            return False                       # van még aduütésünk: azt le lehet hívni
        fo = max(self._mi_kezek(), key=lambda u: len(j.szin(u, adu)))
        P = j.partner(fo)
        egyeb = 0
        for sz in "SHDC":
            if sz == adu:
                continue
            km = max((l.rang for l in j.kint(sz)), default=0)
            felso = sum(1 for l in j.szin(fo, sz) + j.szin(P, sz) if l.rang > km)
            egyeb += max(0, len(j.szin(fo, sz)) - felso)
        if len(kint) + egyeb > self._tartalek():
            return False
        # A szerkesztő ellenpéldája (2026-11-20): ha az egyik kézben sok nyerő van egy
        # mellékszínben, és oda csak ebben a színben van átmenet, a védő akkor lop be,
        # amikor az utolsó átmenetet használjuk — a többi nyerő beragad, és a másik kéz
        # vesztői nem dobhatók rá. Ezért a lopás csak akkor ér egy ütést (és nem többet),
        # ha a lopás után a védő bármit hív, visszaszerezzük a hívást abban a kézben,
        # amelyben a hosszú nyerők vannak:
        for H in self._mi_kezek():
            Pk = j.partner(H)
            hosszu = False
            for sz in "SHDC":
                if sz == adu:
                    continue
                km = max((l.rang for l in j.kint(sz)), default=0)
                ny = [l for l in j.szin(H, sz) if l.rang > km]
                if len(ny) > len(j.szin(Pk, sz)):
                    hosszu = True
            if not hosszu:
                continue
            for sz in "SHDC":
                if sz == adu or not j.kint(sz):
                    continue
                km = max(l.rang for l in j.kint(sz))
                if any(l.rang > km for l in j.szin(H, sz)):
                    continue                      # a kézben nyerő van: visszaüt
                if not j.szin(H, sz) and j.szin(H, adu):
                    continue                      # üres, és van adója: lop
                return False
        # ha a terv még dobást vár a hosszú adus kézből (a vesztőit a másik kéz nyerőire),
        # a védő lopása a dobást is elviszi: aduzunk tovább
        if any(e.el and e.p.sema.azon == "VESZTOCSERE" and e.p.szerepek.get("DK") == fo
               for e in self.egysegek):
            return False
        return True

    def _adukor_jeloltek(self, H: str, ar: float) -> list["Jelolt"]:
        j, adu = self.j, self.adu
        P = j.partner(H)
        ki = []
        if self._adu_leallas():
            return ki
        sajat, par = j.szin(H, adu), j.szin(P, adu)
        if sajat and self._nyero(sajat[-1]):
            ki.append(Jelolt(sajat[-1], ar, f"adukör ({sajat[-1]})"))
        if sajat and par and self._nyero(par[-1]) and sajat[0].rang < par[-1].rang:
            ki.append(Jelolt(sajat[0], ar + 0.1, f"adukör a másik kézbe ({par[-1]})", {P: ("lap", par[-1])}))
        if not ki and any(e.el and e.p.sema.azon in ("BEDOBAS", "BEDOBAS_IMPASSZ") and e.p.szin == adu
                          for e in self.egysegek):
            # a kint lévő felső adu a bedobásé (BM A-6 #3): a kiaduzás itt megáll, a kiadás
            # az elimináció után jön
            return ki
        if not ki and sajat and not any(self._nyero(l) for l in sajat + par):
            # nincs felső adunk: a kint lévő felső adu kiütése (egy ütés kiadás)
            if par and par[-1].rang > sajat[-1].rang:
                ki.append(Jelolt(sajat[0], ar + 1.2, f"adukör: a felső adu kiütése ({par[-1]} a másik kézből)",
                                 {P: ("lap", par[-1])}))
            else:
                ki.append(Jelolt(sajat[-1], ar + 1.2, f"adukör: a felső adu kiütése ({sajat[-1]})"))
        return ki

    def _egyseg_jeloltek(self, H: str, e: Egyseg, k: Kor, ar: float) -> list["Jelolt"]:
        j = self.j
        P = j.partner(H)
        ei = self.egysegek.index(e)
        fogl = self._foglalt()
        cim = f"{e.p.rovid}: {k.fajta}" + (f" {k.lap}" if k.lap else "")
        if k.fajta == "lehiv":
            X = j_keze(j, k.lap)
            if X == H:
                return [Jelolt(k.lap, ar, cim, folyo=(ei, k))]
            ki = []
            kicsi = self._kicsi(H, k.szin, fogl)
            # a hívó kéz kis lapja nem lehet az egység saját kulcslapja (pl. a villa lapja)
            if kicsi is not None and kicsi.rang < k.lap.rang \
                    and kicsi not in (e.p.hasznal | e.p.elfogyaszt):
                ki.append(Jelolt(kicsi, ar, cim, {P: ("lap", k.lap)}, (ei, k)))
            return ki + self._atmenet_jeloltek(H, X, e, ar + 0.5)
        if k.fajta == "impassz":
            if k.hivo != H:
                return self._atmenet_jeloltek(H, k.hivo, e, ar + 0.5)
            sajat = j.szin(H, k.szin)
            if not sajat:
                return []
            return [Jelolt(sajat[0], ar, cim, {P: ("impassz", k.lap)}, (ei, k))]
        if k.fajta == "elemzo":
            if k.hivo != H:
                return self._atmenet_jeloltek(H, k.hivo, e, ar + 0.5)
            pol = self._politika(ei)
            akc = pol.dontes() if pol is not None else None
            if akc is None:
                return []
            return [Jelolt(k.lap, ar, f"{e.p.rovid}: hívás {k.lap}", {P: ("elemzo", ei, akc)}, (ei, k))]
        if k.fajta == "kiad":
            # a kiengedés bármelyik kezünkből indulhat, amelyikben van szabad kis lap a
            # színből (a partner a legkisebbjét adja) — így nem kell átmenet (BridgeMasters #1)
            sajat = j.szin(H, k.szin)
            szabad = [l for l in sajat if l not in fogl and not self._nyero(l)]
            P = j.partner(H)
            if not szabad and any(not self._nyero(l) for l in j.szin(P, k.szin)):
                # a kiengedés körében a partner is kicsit tesz: a foglalt kis lap is
                # vezethet (a kísérőnek szánt lap helyett a partner kis lapja megy rá)
                szabad = [l for l in sajat if not self._nyero(l)]
            if szabad:
                return [Jelolt(szabad[0], ar, f"{e.p.rovid}: kiengedés ({szabad[0]})", folyo=(ei, k))]
            cel_kez = k.hivo
            if cel_kez is None:
                # bármelyik kezünkből mehet: abba, amelyikben van nem nyerő lap
                cel_kez = P if any(not self._nyero(l) for l in j.szin(P, k.szin)) else H
            if cel_kez != H:
                return self._atmenet_jeloltek(H, cel_kez, e, ar + 0.5)
            if not sajat:
                return []
            szabad = [l for l in sajat if l not in fogl] or sajat
            return [Jelolt(szabad[0], ar, f"{e.p.rovid}: kiengedés ({szabad[0]})", folyo=(ei, k))]
        if k.fajta == "lop":
            if k.hivo != H:
                return self._atmenet_jeloltek(H, k.hivo, e, ar + 0.5)
            sajat = [l for l in j.szin(H, k.szin) if l not in (e.p.hasznal | e.p.elfogyaszt)] \
                or j.szin(H, k.szin)
            if not sajat or j.szin(P, k.szin) or not j.szin(P, self.adu):
                return []
            adukor = self._lopas_elotti_adukor(H, P, e)
            if adukor is not None:
                return [Jelolt(adukor, ar, f"{e.p.rovid}: adukör a lopás előtt ({adukor})")]
            return [Jelolt(sajat[0], ar, cim, {P: ("lop",)}, (ei, k))]
        return []

    def _lopas_elotti_adukor(self, H: str, L: str, e: Egyseg) -> Lap | None:
        """LOPAS_ELOTT_ADU (BM A-13, a szerkesztő: „két aduzás után az asztal lopja”): a
        rövid kezes lopás előtt annyi adukört hívunk a hívó kéz felső aduival, amennyi
        után a lopó kéznek a hátralévő lopásaihoz elég adója marad — így a védők közül,
        akinek kevés adója volt, már nem tud felülopni. Csak ha a hívó kéz adója minden
        kint lévő adunál nagyobb (az adukör nem ad ki ütést)."""
        if not SZABALY["LOPAS_ELOTT_ADU"] or not self.adu:
            return None
        if e.p.sema.azon != "VESZTORE_VESZTO":
            # egyelőre csak a vesztőre vesztő lopásánál: általánosan (minden rövid kezes
            # lopás előtt) a 40 partin rontott (4N01 #2: 93% → 63%, 4P01 #1, 4D01 #1)
            return None
        j = self.j
        # a kint lévő aduk: amit nem mi tartunk, és még nem ment le (nem a védők kezéből)
        lement = {l for _, l in j.lapok}
        kint = [Lap(self.adu, r) for r in "AKQJT98765432"
                if Lap(self.adu, r) not in lement and Lap(self.adu, r) not in j.kezek[H]
                and Lap(self.adu, r) not in j.kezek[L]]
        if not kint:
            return None
        kell = sum(1 for k in e.p.korok[e.i:] if k.fajta == "lop" and k.lopo == L)
        if len(j.szin(L, self.adu)) <= kell:
            return None
        legf = max(l.rang for l in kint)
        felso = sorted((l for l in j.szin(H, self.adu) if l.rang > legf), key=lambda l: l.rang)
        return felso[0] if felso else None

    def _kicsi(self, H: str, sz: str, fogl: set[Lap]) -> Lap | None:
        lapok = self.j.szin(H, sz)
        if not lapok:
            return None
        szabad = [l for l in lapok if l not in fogl]
        return (szabad or lapok)[0]

    def _atmenet_jeloltek(self, H: str, R: str, kero: Egyseg | None, ar0: float) -> list["Jelolt"]:
        """Átmenetek H-ból R-be: a körök, amelyek R-ben érnek véget, áruk szerint."""
        j, adu = self.j, self.adu
        fogl = self._foglalt()
        kint_adu = self._kint_adu()
        kesobbi = {}                             # egy másik egység lehívó köre: a közös lap
        for e in self._aktiv():
            if e is kero:
                continue
            k = e.kor()
            if k is not None and k.fajta == "lehiv" and k.lap is not None and j_keze(j, k.lap) == R:
                kesobbi[k.lap] = e
        ki = []
        adu_atmenet = None
        for sz in "SHDC":
            hl = j.szin(H, sz)
            if not hl:
                continue
            hivo_ar = 0 if any(l not in fogl for l in hl) else 3
            rl = j.szin(R, sz)
            nyerok = [l for l in rl if self._nyero(l)]
            if nyerok and any(l.rang < nyerok[0].rang for l in hl):
                w = nyerok[0]
                hivo = [l for l in hl if l.rang < w.rang and l not in fogl] or [l for l in hl if l.rang < w.rang]
                if sz == adu:
                    ar = 1 if self._adukor_mehet() else 5
                    if len(hl) <= self._lopas_igeny(H):
                        ar = 6               # a lopásokra foglalt adu nem átmenet

                elif w in kesobbi:
                    ar = 2.5
                elif w in fogl:
                    ar = 4
                else:
                    ar = 2
                if self._nyero(hivo[0]):
                    # átvétel: a hívó kéz nyerője a partner nagyobb nyerője alá megy — két
                    # nyerő egy ütésre, és a visszaút is elfogy (BM A-2 #3: a ♠K a ♠A alá,
                    # a ♦ kis lap a ♦A-hoz helyett)
                    ar += 3
                leiras = f"átmenet {w}" + (f" — egyben {kesobbi[w].p.rovid} köre (közös lap)" if w in kesobbi else "")
                ki.append(Jelolt(hivo[0], ar0 + (ar + hivo_ar) / 10, leiras, {R: ("lap", w)}))
                if sz == adu:
                    adu_atmenet = (hivo[0], w)
            elif not rl and sz != adu and adu and j.szin(R, adu) \
                    and len(j.szin(R, adu)) > self._lopas_igeny(R):
                hivo = [l for l in hl if l not in fogl] or hl
                kint_a = j.kint(adu)
                felul = max((x.rang for x in kint_a), default=0)
                # magas aduval lopva a negyedik kéz sem lophat felül
                ar = 0 if kint_adu == 0 else (1 if all(l.rang > felul for l in j.szin(R, adu)) else 3)
                ki.append(Jelolt(hivo[0], ar0 + (ar + hivo_ar) / 10, f"átmenet lopással ({SZINJEL[sz]})",
                                 {R: ("lop",)}))
        if adu_atmenet is not None and SZABALY["ATMENET_ADUKOR"] and kint_adu \
                and not any(x.lap.szin != adu for x in ki):
            # ATMENET_ADUKOR (a szerkesztő, BM A-6 #2, 12:45): ha az aduval való átmenet
            # az utolsó lehetőség a partnerhez, előbb annyi magas adut hívunk a kézből,
            # amennyi a terv végrehajtását nem veszélyezteti: a kézben maradjon meg a
            # lopásaira szánt adu, és — ha a terv bedobással (dob-lop) zárul — még egy.
            hl = j.szin(H, adu)
            tartalek = self._lopas_igeny(H) + (1 if any(
                e.el and e.p.sema.azon in ("BEDOBAS", "BEDOBAS_IMPASSZ") for e in self.egysegek) else 0)
            ny_h = [l for l in hl if self._nyero(l) and l != adu_atmenet[0]]
            if ny_h and len(hl) - 1 - 1 >= tartalek:
                elso = min((x.ar for x in ki if x.lap.szin == adu), default=ar0)
                ki.append(Jelolt(ny_h[-1], elso - 0.005,
                                 f"az utolsó átmenet (adu) előtt egy magas adu a kézből ({ny_h[-1]})"))
        return ki

    def _begyujtes_jeloltek(self, H: str, ar: float) -> list["Jelolt"]:
        j = self.j
        P = j.partner(H)
        ki = []
        if self._kint_adu():
            ki += self._adukor_jeloltek(H, ar - 0.5)
        for sz in "SHDC":
            if sz == self.adu and self._kint_adu():
                continue
            ny = [l for l in j.szin(H, sz) if self._nyero(l)]
            if not ny:
                continue
            rovid = len(j.szin(H, sz)) <= len(j.szin(P, sz))
            l = ny[-1] if rovid else ny[0]
            pl = j.szin(P, sz)
            # ha a partner csak nagyobb lapot tehet rá, átveszi a hívást: két nyerő egy
            # ütésre, és a hívó kéz többi nyerője ott ragadhat (BM A-2 #3: az asztal ♠K-ja a
            # kéz ♠A-ja alá, a két hosszú treff az asztalon maradt) — a végére
            atvesz = bool(pl) and all(x.rang > l.rang for x in pl)
            ki.append(Jelolt(l, ar + (0.2 if sz == self.adu else 0) + (0 if rovid else 0.1)
                             + (0.8 if atvesz else 0), f"begyűjtés {l}"))
        if any(self._nyero(l) for l in j.kezek[P]):
            ki += self._atmenet_jeloltek(H, P, None, ar + 1)
        return ki

    def _feladas(self, H: str) -> "Jelolt":
        j = self.j
        fogl = self._foglalt()
        szabad = [l for l in j.kezek[H] if l not in fogl] or list(j.kezek[H])
        hossz = {sz: len(j.szin(H, sz)) for sz in "SHDC"}
        l = min(szabad, key=lambda l: (l.szin == self.adu, -hossz[l.szin], l.rang))
        return Jelolt(l, 9, f"kiadás {l}")

    def _kitekint(self, jel: list["Jelolt"]) -> "Jelolt":
        """A jelölt körök közül az, amelyikkel a terv további körei a legjobban
        mennek végig: néhány sorsolt elosztáson, egyszerű védőkkel (a lánc
        végrehajthatósága a kérdés, nem a védekezés)."""
        import random
        j = self.j
        jel = jel[:self.kitekintes_db]
        vedok = [u for u in "NESW" if not j.mi(u)]
        kint = [l for sz in "SHDC" for l in j.kint(sz)]
        rnd = random.Random(len(j.lapok) * 7919 + sum(l.rang for _, l in j.lapok))
        vilagok = []
        for _ in range(self.kitekintes_vilag):
            rnd.shuffle(kint)
            n0 = len(j.kezek[vedok[0]])
            vilagok.append({vedok[0]: set(kint[:n0]), vedok[1]: set(kint[n0:])})
        legjobb, legjobb_pont = jel[0], None
        for v in jel:
            pont = 0.0
            for vk in vilagok:
                kezek = {u: set(j.kezek[u]) for u in (j.felvevo, j.asztal)}
                kezek.update({u: set(x) for u, x in vk.items()})
                j2 = tj.Jatek(kezek, j.felvevo, j.adu, [], tj.Terv(()))
                j2.lapok = list(j.lapok)
                kl = self._klon(j2)
                kl._alkalmaz(v)
                j2.tesz(j.soron(), v.lap)
                while len(j2.lapok) < 52:
                    u = j2.soron()
                    lap = kl.lap(u) if j2.mi(u) else _egyszeru_vedo(j2, u)
                    utes = j2.aktualis()
                    if lap not in j2.kezek[u] or (utes and lap.szin != utes[0][1].szin
                                                  and any(x.szin == utes[0][1].szin for x in j2.kezek[u])):
                        van = [x for x in j2.kezek[u] if utes and x.szin == utes[0][1].szin]
                        lap = min(van or j2.kezek[u], key=lambda x: x.rang)
                    j2.tesz(u, lap)
                n = j2.felvevo_utesek()
                pont += (100 if self.cel is not None and n >= self.cel else 0) + n
            if legjobb_pont is None or pont > legjobb_pont + 1e-9:
                legjobb, legjobb_pont = v, pont
        return legjobb

    def _klon(self, j2: tj.Jatek) -> "Vegrehajto":
        kl = Vegrehajto.__new__(Vegrehajto)
        kl.egysegek = [Egyseg(e.p, e.i, e.allapot, e.fazis) for e in self.egysegek]
        kl.szakaszos = self.szakaszos
        import copy as _copy
        kl.politikak = {i: _copy.copy(p) for i, p in self.politikak.items()}
        kl.kezdo = self.kezdo
        kl.feldolgozott = self.feldolgozott
        kl.j = j2
        kl.adu = self.adu
        kl.folyo = None
        if self.folyo is not None:
            e, k, kezd = self.folyo
            kl.folyo = (kl.egysegek[self.egysegek.index(e)], k, kezd)
        kl.szandek = dict(self.szandek)
        kl.szandek_utes = self.szandek_utes
        kl.naplo = None
        kl.cel = self.cel
        kl.igeny = self.igeny
        kl.megszerzett = self.megszerzett
        kl.kitekintes = False
        kl.kitekintes_db = self.kitekintes_db
        kl.kitekintes_vilag = self.kitekintes_vilag
        return kl

    # -- hozzátevés --
    def _kovetes(self, u: str) -> Lap:
        lap, ok = self._kovetes_ok(u)
        if SZABALY["ATMENET_VEDES"]:
            lap, ok = self._atmenet_vedes(u, lap, ok)
        self._jegyez(ok)
        return lap

    def _deblokk(self, u: str, sz: str, van: list[Lap], utes: list) -> Lap | None:
        """DEBLOKK (általános szabály, BM A-2 #4): ha a színben minden kör a miénk (a
        két kéz felső lapjai elég kört visznek), a rövidebb kéz a nagy lapját adja, hogy
        a hosszú kéz lapjai ne ragadjanak be. ♣A2 / ♣KQJT: a védő treffhívására az
        asztal az ászt teszi, a kéz a tízest — később az asztal kettese átmenet a KQJ-hez."""
        j = self.j
        P = j.partner(u)
        p_lapok = j.szin(P, sz)
        p_tett = next((l for x, l in utes if x == P), None)
        p_hossz = len(p_lapok) + (1 if p_tett is not None and p_tett.szin == sz else 0)
        if len(van) >= p_hossz or not p_lapok:
            return None                                  # nem mi vagyunk a rövid kéz
        kint = j.kint(sz)
        kmax = max((l.rang for l in kint), default=0)
        mind = list(van) + list(p_lapok) + ([p_tett] if p_tett is not None and p_tett.szin == sz else [])
        felso = sum(1 for l in mind if l.rang > kmax)
        if felso < p_hossz:
            return None                                  # a szín nem zárt
        legnagyobb = max(van, key=lambda l: l.rang)
        if legnagyobb.rang <= kmax:
            return None
        nyu, nyl = j.nyertes(utes + [(u, legnagyobb)])
        if not j.mi(nyu):
            return None
        return legnagyobb

    def _atmenet_vedes(self, u: str, lap: Lap, ok: str) -> tuple[Lap, str]:
        """ATMENET_VEDES (általános szabály, a szerkesztő 2026-11-20): a terv által
        igényelt átmenetek védése. Ha az ütés így is, úgy is a miénk, azt a lapot tesszük
        (és abban a kézben ütünk), amely után a terv hátralévő része a legjobban
        végrehajtható:
        - az elemzős egységeknél a kezelések együttes esélye a megmaradó átmenetekkel (ha
          két kezelés ugyanazokra az átmenetekre számít, a legjobb elosztással);
        - a többi egységnél a soron következő kör hívó keze legyen elérhető.
        BM A-2 #3: a ♠B visszahívásra az asztal ♠D-jét a kéz ♠A-val üti át (negyedik kéz).
        BM A-2 #5: a védő treffhívására a kéz második kézen az ♣A-val üt — az asztal ♣KD-je
        a két pikkimpassz átmenete marad („kézben ütünk és folytatjuk az aduzást”)."""
        j = self.j
        utes = j.aktualis()
        if not utes:
            return lap, ok
        P = j.partner(u)
        hivott = utes[0][1].szin
        van = j.szin(u, hivott)
        if lap not in van:
            return lap, ok
        F, A = j.felvevo, j.asztal
        # a lehetőségek: (a kezünkből tett lap, a partner lapja vagy None, ki üt)
        opciok = []
        if any(x == P for x, _ in utes) and len(utes) == 3:
            for l in van:
                nyu, _ = j.nyertes(utes + [(u, l)])
                if j.mi(nyu):
                    opciok.append((l, None, nyu))
        elif len(utes) == 1 and not j.mi(utes[0][0]) and self._hatra(utes)[-1] == P:
            # második kéz, a partner negyedik: ütünk a biztos nyerőnkkel, vagy kicsit
            # teszünk, és a partner üt a legolcsóbb biztos nyerőjével
            for l in van:
                if self._nyero(l) and _ut(l, utes[0][1], self.adu):
                    opciok.append((l, None, u))
            p_ny = [x for x in j.szin(P, hivott) if self._nyero(x)]
            kicsik = [l for l in van if not self._nyero(l)]
            if p_ny and kicsik:
                opciok.append((kicsik[0], p_ny[0], P))
        if len(opciok) < 2 or not any(o[0] == lap for o in opciok):
            return lap, ok
        kint = [l for s_ in "SHDC" for l in j.kint(s_)]
        elemzosok = []
        korok = []
        for ei, e in enumerate(self.egysegek):
            if not e.el or e.p.szin == hivott:
                continue
            if e.p.sema.fajta == "elemzo":
                if j.kint(e.p.szin):
                    pol = self._politika(ei, osztas=False)
                    if pol is not None and pol.el.korlatos:
                        elemzosok.append((e.p.szin, pol))
            else:
                k = e.kor()
                if k is not None and getattr(k, "hivo", None) in (F, A):
                    korok.append((k.hivo, k.szin))
        if not elemzosok and not korok:
            return lap, ok

        def pont(o):
            l, pl, gy = o
            kezek = {F: set(j.kezek[F]), A: set(j.kezek[A])}
            kezek[u].discard(l)
            if pl is not None:
                kezek[P].discard(pl)
            hivas = "X" if gy == F else "Y"
            if len(elemzosok) == 2:
                (sz1, p1), (sz2, p2) = elemzosok
                ax, ay = atmenet_szam(kezek, F, A, kint, sz1)
                p = max(p1.esely_atmenettel(a, b, hivas) * p2.esely_atmenettel(ax - a, ay - b, "-")
                        for a in range(ax + 1) for b in range(ay + 1))
            else:
                p = 0.0
                for sz, pol in elemzosok:
                    ax, ay = atmenet_szam(kezek, F, A, kint, sz)
                    p += pol.esely_atmenettel(ax, ay, hivas)
            elerheto = 0
            for R, sz in korok:
                ax, ay = atmenet_szam(kezek, F, A, kint, sz)
                elerheto += gy == R or (ax if R == F else ay) > 0
            return (round(p, 6), elerheto)
        alap_o = next(o for o in opciok if o[0] == lap)
        alap = pont(alap_o)
        legjobb = max(((pont(o), o) for o in opciok if o is not alap_o), key=lambda x: (x[0], -x[1][0].rang))
        if legjobb[0] > alap:
            l, pl, gy = legjobb[1]
            if pl is not None:
                self.szandek[P] = ("lap", pl)
            return l, f"{l} — a terv átmenetét védi ({ok})"
        return lap, ok

    def _kovetes_ok(self, u: str) -> tuple[Lap, str]:
        """A hozzátevés és az oka (a tanári asztal ezt mutatja)."""
        j, adu = self.j, self.adu
        utes = j.aktualis()
        hivott = utes[0][1].szin
        nyu, nyl = j.nyertes(utes)
        van = j.szin(u, hivott)
        fogl = self._foglalt()
        sz = self.szandek.pop(u, None)
        if (self.folyo is not None and self.folyo[1].fajta == "kiad" and van
                and j.mi(utes[0][0]) and self.folyo[2] == len(j.lapok) - len(utes)):
            # kiengedés: a terv szerint ezt az ütést átadjuk — a partner is kicsit tesz
            kicsik = [l for l in van if not self._nyero(l)] or van
            l = self._legkisebb(kicsik, fogl)
            return l, f"kiengedés: kicsi ({l})"
        if (SZABALY["VESZTORE_DOB"] and self.folyo is not None and self.folyo[1].fajta == "kiad"
                and self.folyo[1].dob and not van and j.mi(utes[0][0])
                and self.folyo[2] == len(j.lapok) - len(utes)):
            # vesztőre vesztő (BM A-13): a kiadott vesztőre nem lopunk, hanem a terv
            # színéből dobunk (később abban a színben lopunk)
            dob = sorted(j.szin(u, self.folyo[1].dob), key=lambda l: l.rang)
            if dob:
                return dob[0], f"vesztőre vesztő: {dob[0]}"
        if sz is not None and sz[0] == "elemzo" and len(utes) == 2:
            from .tervszinkezeles import LOP
            ei, akc = sz[1], sz[2]
            pol = self.politikak.get(ei)
            l2 = utes[1][1]
            r2 = l2.rang if l2.szin == hivott else None
            c3 = pol.harmadik(akc, r2) if pol is not None else None
            if c3 == LOP and not van and adu:
                adu_l = [l for l in j.szin(u, adu) if _ut(l, nyl, adu)]
                if adu_l:
                    return adu_l[0], f"a színkezelés szerint lop: {adu_l[0]}"
            if isinstance(c3, int) and c3 != LOP:
                lap = next((l for l in van if l.rang == c3), None)
                if lap is not None:
                    return lap, f"a színkezelés szerint: {lap}"
            sz = None
        if sz is not None:
            if sz[0] == "lap" and sz[1] in j.kezek[u] and (sz[1].szin == hivott or not van):
                if j.mi(nyu) or _ut(sz[1], nyl, adu):
                    return sz[1], f"a kör lapja: {sz[1]}"
                fole = [l for l in van if _ut(l, nyl, adu)]
                return (fole[0], f"fölé: {fole[0]}") if fole else (sz[1], f"a kör lapja: {sz[1]}")
            if sz[0] == "impassz" and van and sz[1] in j.kezek[u]:
                if j.mi(nyu):
                    return van[0], "a partnerünk üt: kicsi"
                if _ut(sz[1], nyl, adu):
                    return sz[1], f"impassz: {sz[1]}"
                fole = [l for l in van if _ut(l, nyl, adu)]
                return (fole[0], f"a védő fedett: fölé {fole[0]}") if fole else (van[0], "kicsi")
            if sz[0] == "lop" and not van:
                adu_l = [l for l in j.szin(u, adu) if _ut(l, nyl, adu)] if adu else []
                if adu_l:
                    l = self._lopo_lap(adu_l, utes)
                    return l, f"lopás: {l}"
        partner_nyer = j.mi(nyu)
        R = self._kovetkezo_hivo()
        P = j.partner(u)
        if SZABALY["DEBLOKK"] and van and hivott != adu:
            l = self._deblokk(u, hivott, van, utes)
            if l is not None:
                return l, f"deblokk: a rövid kéz a nagy lapját adja ({l})"
        hatra_van_partner = len(utes) <= 2 and any(x == P for x in self._hatra(utes))
        if van and not partner_nyer and R == u:
            # a terv innen folytatódik: ha biztosan üthetünk, itt üssünk — negyedik kézen a
            # legolcsóbb ütő lap is biztos (ingyen impassz: a ♠B a ♠6-ra, nem az ász)
            if len(utes) == 3:
                biztos = [l for l in sorted(van, key=lambda x: x.rang) if _ut(l, nyl, adu)]
            else:
                biztos = [l for l in sorted(van, key=lambda x: x.rang)
                          if _ut(l, nyl, adu) and self._megfigyelt_nyero(l, utes)]
            if biztos:
                return biztos[0], f"üt a nyerővel ({biztos[0]}): a terv innen folytatódik"
        if van and len(utes) == 1 and R == P and hatra_van_partner:
            p_nyero = [l for l in j.szin(P, hivott) if self._nyero(l) and _ut(l, nyl, adu)]
            if p_nyero:
                l = self._legkisebb(van, fogl)
                return l, "második kéz: kicsi — a partnerünk üt, a terv onnan folytatódik"
        kint_szin = [x for x in j.kint(hivott) if x != nyl]
        # a mögöttünk ülő védő lophat-e: ha a színből alig van kint, és van kint adu
        vedo_lophat = bool(adu) and hivott != adu and self._kint_adu() and len(kint_szin) < 2
        if not van and len(utes) == 1 and hatra_van_partner and hivott != adu and not vedo_lophat:
            p_nyero = [l for l in j.szin(P, hivott) if self._nyero(l)]
            if p_nyero:
                l = self._dobas(u, fogl)
                return l, f"nem lop: a partnerünk üt ({p_nyero[-1]}); dobás: {l}"
        if van and len(utes) == 1:
            P = j.partner(u)
            p_legjobb = max((l.rang for l in j.szin(P, hivott)), default=0)
            kint_felett = [x for x in j.kint(hivott) if x != nyl and x.rang > p_legjobb]
            p_lop = not j.szin(P, hivott) and adu and hivott != adu and j.szin(P, adu)
            if kint_felett and not p_lop:
                # a partner nem tud biztosan ütni: ha van biztos nyerőnk, nem adjuk a
                # harmadik kéznek az ütést („második kéz kicsi” csak ott jó, ahol a
                # partner fedez, vagy nincs nyerőnk)
                nyerok = [l for l in van if self._nyero(l) and l.rang > nyl.rang]
                megf = [l for l in van if l.rang > nyl.rang and self._megfigyelt_nyero(l, utes)]
                if megf and (not nyerok or megf[0].rang < nyerok[0].rang):
                    return megf[0], (f"második kéz: üt a legolcsóbb biztos lappal ({megf[0]}) — a "
                                     "látott lapok szerint a mögöttünk ülő nem tudja megütni")
                if nyerok and (self._tartalek() <= 0 or (SZABALY["MASODIK"] and (
                        not any(l in fogl for l in nyerok) or len(nyerok) >= 2))):
                    return nyerok[0], (f"második kéz: üt a nyerővel ({nyerok[0]}) — a partner "
                                       "nem tudja biztosan megütni")
            l = self._legkisebb(van, fogl)
            return l, "második kéz: kicsi" + _megtart(l, van, fogl)
        if van:
            if SZABALY["HARMADIK"] and partner_nyer and len(utes) == 2 and nyl.szin == hivott \
                    and not self._nyero(nyl) \
                    and [x for x in j.kint(hivott) if x.rang > nyl.rang]:
                # harmadik kéz: a partner lapja áll, de a negyedik (védő) megütheti
                biztos = [l for l in van if self._nyero(l)]
                if biztos:
                    return biztos[0], f"harmadik kéz: a nyerővel ({biztos[0]}) — a partner lapját megüthetik"
                fole = [l for l in van if l.rang > nyl.rang]
                if fole and not all(l in fogl for l in fole):
                    l = [x for x in fole if x not in fogl][-1]
                    return l, f"harmadik kéz: magasan ({l})"
            if partner_nyer:
                l = self._legkisebb(van, fogl)
                return l, "a partnerünk üt: kicsi" + _megtart(l, van, fogl)
            fole = [l for l in van if _ut(l, nyl, adu)]
            if fole:
                return fole[0], f"üt a legolcsóbbal: {fole[0]}"
            l = self._legkisebb(van, fogl)
            return l, "nem tud ütni: kicsi" + _megtart(l, van, fogl)
        if not partner_nyer and adu and hivott != adu:
            adu_l = [l for l in j.szin(u, adu) if _ut(l, nyl, adu)]
            if adu_l:
                vesztoje = self._dobhato_veszto(u, fogl)
                if SZABALY["HOSSZU_LOP"] and vesztoje is not None and self._fo_kez() == u \
                        and self._kint_adu():
                    # a hosszú adus kézben a lopás nem hoz plusz ütést (az adu úgyis ütne),
                    # csak a kontrollt rontja: vesztőt dobunk (vesztő a vesztőre)
                    return vesztoje, f"nem lop a hosszú adus kézben: vesztő a vesztőre ({vesztoje})"
                l = self._lopo_lap(adu_l, utes)
                return l, f"lop: {l}"
        l = self._dobas(u, fogl)
        return l, f"dobás: {l}" + (" (a foglalt és a nyerő lapokat megtartja)" if fogl & j.kezek[u] else "")

    def _fo_kez(self) -> str | None:
        """A hosszabb adus kezünk (a fő kéz)."""
        if not self.adu:
            return None
        j = self.j
        a1, a2 = len(j.szin(j.felvevo, self.adu)), len(j.szin(j.asztal, self.adu))
        return j.felvevo if a1 >= a2 else j.asztal

    def _lopo_lap(self, adu_l: list[Lap], utes: list) -> Lap:
        """A lopó adu: ha utánunk még védő jön (felüllophat), annyira magasan lopunk, hogy
        csak a „természetes” aduütései (a mi legnagyobb adunk fölötti lapjai) üthessék
        felül — azok úgyis ütnek (BM A-2 #5: ♥QJ98-ból a ♥8-cal lopva Nyugat a ♥10-zel
        felüllopott; a ♥J-vel csak az ász üthetett volna, az pedig amúgy is ütés)."""
        adu_l = sorted(adu_l, key=lambda l: l.rang)
        if len(utes) >= 3 or not SZABALY["MAGAS_LOPAS"]:
            return adu_l[0]
        j = self.j
        hivott = utes[0][1].szin
        hatra = [x for x in self._hatra(utes) if not j.mi(x)]
        # felüllopás csak akkor fenyeget, ha a hátralévő védő már kimutatott a színből,
        # vagy alig van kint a színből (BM A-2 #5: Nyugatnak volt kárója, nem kell a ♥B)
        kimutatott = any(not any(l.szin == hivott for l in j.kezek[x]) and
                         any(uu == x and ll.szin != hivott and ut0[1].szin == hivott
                             for uu, ll, ut0 in self._lejatszott_kovetesek()) for x in hatra)
        if not kimutatott and len(j.kint(hivott)) >= 2:
            return adu_l[0]
        # asztalfordításnál a hosszú adus kéz nagy adui a kiaduzáshoz kellenek: csak a
        # tényleges kimutatás (biztos felüllopás-veszély) ér meg egy nagy adut (BM A-6 #2)
        if not kimutatott and self.folyo is not None and \
                self.folyo[0].p.sema.azon == "ASZTALFORDITAS":
            return adu_l[0]
        mi_max = max(l.rang for u in self._mi_kezek() for l in j.szin(u, self.adu))
        kint = [l.rang for l in j.kint(self.adu) if l.rang < mi_max]
        if not kint:
            return adu_l[0]
        hatar = max(kint)
        jo = [l for l in adu_l if l.rang > hatar]
        return jo[0] if jo else adu_l[0]

    def _lejatszott_kovetesek(self):
        """(ki, mit tett, az ütés első lapja) a lement lapokra — a kimutatások ebből."""
        L = self.j.lapok
        ki = []
        for i in range(0, len(L), 4):
            ut = L[i:i + 4]
            for u_, l_ in ut[1:]:
                ki.append((u_, l_, ut[0]))
        return ki

    def _dobhato_veszto(self, u: str, fogl: set[Lap]) -> Lap | None:
        """Egy vesztő, amelyet dobhatunk: nem foglalt, nem nyerő, nem adu, és olyan
        színből, amelyben a partnernek sincs nyerője, ami fedné."""
        j = self.j

        def veszto_szin(sz):
            # valódi vesztő csak ott van, ahol a kéz lapjai többen vannak, mint a két
            # kezünk nyerői (♣A32 / ♣KQ4: a kis treffek nem vesztők — azok az asztal
            # átmenetei; BM A-2 #5)
            ny = sum(1 for k_ in (j.felvevo, j.asztal) for l in j.szin(k_, sz) if self._nyero(l))
            return len(j.szin(u, sz)) > ny
        jelolt = [l for l in j.kezek[u] if l not in fogl and not self._nyero(l) and l.szin != self.adu
                  and veszto_szin(l.szin)]
        if not jelolt:
            return None
        return self._dobas(u, fogl) if self._dobas(u, fogl) in jelolt else jelolt[0]

    def _hatra(self, utes) -> list[str]:
        """Akik még tesznek ebbe az ütésbe (a sorrendben)."""
        utolso = utes[-1][0]
        return [kovetkezo_ules(utolso, i) for i in range(1, 4 - len(utes) + 1)]

    def _legkisebb(self, lapok: list[Lap], fogl: set[Lap]) -> Lap:
        szabad = [l for l in lapok if l not in fogl]
        return (szabad or lapok)[0]

    def _dobas(self, u: str, fogl: set[Lap]) -> Lap:
        """Dobás: nem foglalt lap, nem nyerő, nem adu; abból a színből, amelyre nincs
        élő egység (annak a vesztőit a terv máshogy kezeli), a hosszabból, kicsit."""
        j = self.j
        hossz = {sz: len(j.szin(u, sz)) for sz in "SHDC"}
        # a vesztők színenként ebben a kézben: a kéz lapjai, mínusz a két kezünk nyerői
        vesztok = {}
        for sz in "SHDC":
            ny = sum(1 for k_ in (j.felvevo, j.asztal) for l in j.szin(k_, sz) if self._nyero(l))
            vesztok[sz] = max(0, hossz[sz] - ny)
        if not SZABALY["DOBAS"]:
            vesztok = {sz: 0 for sz in "SHDC"}
        cel = next((e.p.szerepek.get("CELSZIN") for e in self.egysegek
                    if e.el and e.kor() is not None and e.p.szerepek.get("CELSZIN")
                    and e.p.szerepek.get("DK") == u), None)
        if not cel:
            # BEDOBAS: ha a bedobó színben ez a kéz a hosszabb, abból dobunk — így a
            # kiadások után a szín mindkét kezünkből elfogy, és a védőnek nem marad
            # biztonságos kijátszása (BM A-6 #2: ♦432 / ♦65 — a ♣-ra a ♦ megy)
            P_ = j.partner(u)
            cel = next((e.p.szin for e in self.egysegek
                        if e.el and e.p.sema.azon == "BEDOBAS"
                        and len(j.szin(u, e.p.szin)) > len(j.szin(P_, e.p.szin))), None)
        if cel:
            # a terv dobásszíne (a vesztőcsere része): onnan dobunk, ha lehet
            return min(j.kezek[u], key=lambda l: (self._nyero(l), l in fogl, l.szin != cel,
                                                  l.szin == self.adu, l.rang))
        # nyerőt csak akkor dobunk, ha nincs más; utána a foglalt lapokat kíméljük
        return min(j.kezek[u], key=lambda l: (self._nyero(l), l in fogl, l.szin == self.adu,
                                              -vesztok[l.szin], -hossz[l.szin], l.rang))


@dataclass
class Jelolt:
    """Egy lehetséges körünk: a hívott lap, az ára (az alapsorrend), a partner
    teendője, és ha egy egység köre, akkor melyiké."""
    lap: Lap
    ar: float
    leiras: str
    szandek: dict = field(default_factory=dict)
    folyo: tuple | None = None


def _egyszeru_vedo(j: tj.Jatek, u: str) -> Lap:
    """Egyszerű védő az előrenézéshez: színre ad, a partnerét nem üti felül, ha tud,
    üt a legolcsóbbal; hívásnál a leghosszabb színéből a legkisebbet."""
    utes = j.aktualis()
    lapok = j.kezek[u]
    if not utes:
        hossz = {sz: len(j.szin(u, sz)) for sz in "SHDC"}
        return min(lapok, key=lambda l: (-hossz[l.szin], l.rang))
    hivott = utes[0][1].szin
    nyu, nyl = j.nyertes(utes)
    van = j.szin(u, hivott)
    partner_nyer = not j.mi(nyu)
    if van:
        if partner_nyer:
            return van[0]
        fole = [l for l in van if _ut(l, nyl, j.adu)]
        return fole[0] if fole else van[0]
    if not partner_nyer and j.adu:
        adu_l = [l for l in j.szin(u, j.adu) if _ut(l, nyl, j.adu)]
        if adu_l:
            return adu_l[0]
    hossz = {sz: len(j.szin(u, sz)) for sz in "SHDC"}
    return min(lapok, key=lambda l: (l.szin == j.adu, -hossz[l.szin], l.rang))


def _megtart(l: Lap, van: list[Lap], fogl: set[Lap]) -> str:
    if l in fogl:
        return " (minden lapja foglalt; a legkisebbet adja)"
    if any(x in fogl for x in van):
        return " (a foglalt lapokat megtartja)"
    return ""


def j_keze(j: tj.Jatek, l: Lap) -> str | None:
    for u in (j.felvevo, j.asztal):
        if l in j.kezek[u]:
            return u
    return None


def _ut(l: Lap, nyl: Lap, adu: str | None) -> bool:
    if l.szin == nyl.szin:
        return l.rang > nyl.rang
    return bool(adu) and l.szin == adu and nyl.szin != adu


# --- 3. Lejátszás és értékelés ------------------------------------------------------

@dataclass
class Eredmeny:
    terv: KTerv
    teljesult: int = 0
    n: int = 0
    utesek: int = 0
    naplok: list = field(default_factory=list)

    @property
    def esely(self) -> float:
        return self.teljesult / self.n if self.n else 0.0


def lejatszik(terv: KTerv, vilag, felvevo: str, adu: str | None, lejatszott: list,
              dd_vedo, naplo: list | None = None, cel: int | None = None,
              jatek_ki: list | None = None, kenyszer: list | None = None,
              utes_dontes: dict | None = None, megtart: set | None = None) -> int:
    """Egy világ végigjátszása: mi a terv szerint, a védők a `dd_vedo` szerint.
    `kenyszer`: a terv óta valóban lement lapok — ezek mennek le előbb (a végrehajtó a
    saját lapjait közben meghozza, hogy az egységei a megfigyelés szerint haladjanak).
    `utes_dontes`: a terv döntése a védő hívására tett lapjainkról
    ({index: (kéz, lap vagy KICSI, ok)}, HIVASRA_TETT_LAP)."""
    j = tj.Jatek({u: set(vilag.kezek[u].lapok) for u in "NESW"}, felvevo, adu, lejatszott, tj.Terv(()))
    v = Vegrehajto(terv, j, naplo)
    v.cel = cel
    if utes_dontes:
        v.kenyszer = dict(utes_dontes)
    if megtart:
        v.megtart = set(megtart)
    for u, l in kenyszer or []:
        if j.mi(u):
            if v.lap(u) != l:
                if v.folyo is not None and v.folyo[2] == len(j.lapok):
                    v.folyo = None
                v.szandek = {}
        j.tesz(u, l)
    while len(j.lapok) < 52:
        u = j.soron()
        lap = v.lap(u) if j.mi(u) else dd_vedo(j)
        utes = j.aktualis()
        if lap not in j.kezek[u]:
            lap = min(j.kezek[u], key=lambda l: l.rang)
        if utes:
            van = [l for l in j.kezek[u] if l.szin == utes[0][1].szin]
            if van and lap.szin != utes[0][1].szin:
                if naplo is not None:
                    naplo.append(f"!! szabálytalan lap: {u} {lap}")
                lap = van[0]
        j.tesz(u, lap)
    if jatek_ki is not None:
        jatek_ki.append(j)
    return j.felvevo_utesek()


def ertekel(tervek: list[KTerv], vilagok: list, felvevo: str, kontraktus, lejatszott: list,
            dd_tar: "tj.DDTar") -> list[Eredmeny]:
    adu = None if kontraktus.szin == "NT" else kontraktus.szin
    cel = 6 + kontraktus.szint
    ki = []
    for t in tervek:
        r = Eredmeny(t)
        for i, lo in enumerate(vilagok):
            def dd_vedo(j, i=i, lo=lo):
                return tj._vedo_lap(dd_tar(i, lo, j.lapok))
            n = lejatszik(t, lo, felvevo, adu, lejatszott, dd_vedo, cel=cel)
            r.n += 1
            r.utesek += n
            r.teljesult += n >= cel
        ki.append(r)
    return ki


def ertekel_lepcsos(tervek: list[KTerv], vilagok: list, felvevo: str, adu: str | None,
                    lejatszott: list, dd_tar, cel: int, keret_s: float | None = None,
                    elso: int = 20, legjobb: int = 3, vege: int = 4, t0: float | None = None,
                    utana=None, utes_dontes: dict | None = None,
                    megtart: set | None = None) -> list[Eredmeny]:
    """Lépcsős értékelés (a sorrendtervező):
      1. minden jelölt az első `elso` világon;
      2. a `legjobb` tervek sorrendváltozatai (az egységek a kiaduzás előtt / után)
         ugyanezeken a világokon;
      3. a `vege` legjobb a többi világon is, amíg az időkeret engedi.
    A DD-tár a világ sorszámával gyorsítótáraz, ezért a lépcsők közös elejei egyszer
    számolódnak. `utana(i, w)`: világonként egyszer hívódik (pl. a DD-felső határhoz)."""
    import time
    t0 = t0 or time.time()
    ered: dict[int, Eredmeny] = {}
    sorrend: list[KTerv] = []

    def regisztral(t):
        if id(t) not in ered:
            ered[id(t)] = Eredmeny(t)
            sorrend.append(t)

    def futtat(ts, idx):
        for i in idx:
            w = vilagok[i]
            if utana is not None:
                utana(i, w)

            def dd_vedo(j, i=i, w=w):
                return tj._vedo_lap(dd_tar(i, w, j.lapok))
            for t in ts:
                r = ered[id(t)]
                n = lejatszik(t, w, felvevo, adu, lejatszott, dd_vedo, cel=cel, utes_dontes=utes_dontes,
                              megtart=megtart)
                r.n += 1
                r.utesek += n
                r.teljesult += n >= cel

    def kulcs(r):
        return (-r.esely, -(r.utesek / r.n if r.n else 0), len(r.terv.lepesek))

    for t in tervek:
        regisztral(t)
    n1 = min(elso, len(vilagok))
    futtat(tervek, range(n1))
    rang = sorted(ered.values(), key=kulcs)
    uj = []
    for r in (rang[:legjobb] if SZABALY["SZAKASZ"] else []):
        for v in szakasz_valtozatok(r.terv)[1:]:
            if all(v.fazis != x.fazis or v.lepesek != x.lepesek for x in sorrend):
                regisztral(v)
                uj.append(v)
    futtat_uj = [t for t in uj]
    if futtat_uj:
        # az utana-hívás csak egyszer világonként: itt már nem kell
        mentett, utana = utana, None
        futtat(futtat_uj, range(n1))
        utana = mentett
    rang = sorted(ered.values(), key=kulcs)
    elol = [r.terv for r in rang[:vege]]
    for i in range(n1, len(vilagok)):
        if keret_s is not None and time.time() - t0 > keret_s:
            break
        futtat(elol, [i])
    vegso = sorted((ered[id(t)] for t in elol), key=kulcs)
    elol_id = {id(t) for t in elol}
    tobbi = [r for r in rang if id(r.terv) not in elol_id]
    return vegso + tobbi
