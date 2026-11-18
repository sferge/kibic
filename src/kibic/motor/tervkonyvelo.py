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

from dataclasses import dataclass, field

from ..domain import Lap, kovetkezo_ules, vonal
from . import tervjatszo as tj
from .tervsema import Allas, Kor, Peldany, peldanyok

SZINJEL = dict(zip("SHDC", "♠♥♦♣"))

import os as _os
# a mérésekhez: a 2026-11-18-i szabályok ki-be kapcsolhatók (1: be)
SZABALY = {n: _os.getenv(f"KIBIC_K_{n}", "1") != "0" for n in
           ("MASODIK", "HARMADIK", "DOBAS", "HOSSZU_LOP", "SZAKASZ", "ELEMZO")}


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
    return "U"


def szakasz_valtozatok(t: KTerv, max_db: int = 8) -> list[KTerv]:
    """A terv sorrendváltozatai: az egységek a kiaduzás előtt vagy után (az alapsorrend
    az első). A lopásos egység mindig előtte marad."""
    from itertools import product
    alap = tuple(alap_fazis(p) for p in t.lepesek)
    ki = [KTerv(t.lepesek, t.igeny, alap, t.adus, t.elozetes)]
    szabad = [i for i, p in enumerate(t.lepesek) if alap[i] == "U"]
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


ELEMZO_MAX_KINT = int(_os.getenv("KIBIC_K_ELEMZO_KINT", "8"))   # ennél több kint lévő lapnál lassú


def szinkezeles_peldany(allas: Allas, technikak: dict, sz: str, k: int, m: int,
                        ures: tuple[int, int] | None = None, esely_min: float = 0.01) -> Peldany | None:
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
    try:
        pol = SzinPolitika(X, Y, kint, ures1, ures2, k, m, adu)
    except Exception:                            # noqa: BLE001
        return None
    if pol.p <= esely_min:
        return None
    biztos = allas.biztos_utesek(sz)
    lapok = set(allas.szin(F, sz)) | set(allas.szin(A, sz))
    # hozam: a mellékszínben a biztosakon felüli ütések; az aduban a vesztők
    # csökkenése a szokásos (kb. kettő) aduvesztőhöz képest
    hozam = max(1, k - biztos) if not adu else max(0, 2 - m)
    if hozam <= 0:
        return None
    sz_ = {"k": k, "m": m, "biztos": biztos, "esely": pol.p, "aduval": False, "adu": adu}
    return Peldany(sema, sz, sz_, [Kor("elemzo", sz)], set(lapok), set(lapok),
                   {l for l in allas.kint_szin(sz)}, hozam)


def szinkezeles_peldanyok(allas: Allas, technikak: dict, igeny: int,
                          ures: tuple[int, int] | None = None) -> list[Peldany]:
    """Az egyszínű elemző kezelései forrásként: színenként a cél k ütés (a biztosakon
    felül legfeljebb az igényig) legfeljebb m vesztéssel (a megengedett kiadásból, ami
    a többi szín biztos kiadása után marad). Az aduszínben a vesztés 0–2 (a kiaduzás
    kezelése: „legfeljebb egy aduvesztő”)."""
    if "SZINKEZELES" not in technikak or not SZABALY.get("ELEMZO", True):
        return []
    F, A = allas.felvevo, allas.asztal
    megengedett = max(0, allas.hatra - allas.cel)
    ki = []
    for sz in "SHDC":
        X, Y = allas.szin(F, sz), allas.szin(A, sz)
        kint = allas.kint_szin(sz)
        if not (X or Y) or not kint or len(kint) > ELEMZO_MAX_KINT:
            continue
        hossz = max(len(X), len(Y))
        biztos = allas.biztos_utesek(sz)
        if sz == allas.adu:
            celok = [(hossz - v, v) for v in range(0, 3) if hossz - v > biztos]
        else:
            celok = [(k, min(megengedett, hossz)) for k in range(biztos + 1, min(hossz, biztos + max(1, igeny)) + 1)]
        for k, m in celok:
            p = szinkezeles_peldany(allas, technikak, sz, k, m, ures)
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
    if a.szerepek.get("CELSZIN") and a.szerepek["CELSZIN"] == b.szin:
        return True                      # amiből dobunk, azt nem kezeljük másképp
    if b.szerepek.get("CELSZIN") and b.szerepek["CELSZIN"] == a.szin:
        return True
    return bool((a.hasznal | a.elfogyaszt) & (b.hasznal | b.elfogyaszt)) or a.szin == b.szin


def max_hozam(lepesek: list[Peldany]) -> int:
    return sum(p.hozam for p in lepesek)


def tervjeloltek(allas: Allas, technikak: dict, max_db: int = 60, igeny: int = 1,
                 ures: tuple[int, int] | None = None, max_szim: int | None = None) -> list[KTerv]:
    """A jelölt tervek: a biztos egységek (vesztőcsere, lopás — nincs rejtett
    feltételük) egy ütközésmentes készlete, és utánuk egy- vagy kételemű esélysor a
    többi technikából (az első próba: a kudarca nem kerül ütésbe, és nem fogyaszthatja
    el a második lapjait)."""
    P = [q for p in peldanyok(allas, technikak) for q in dobas_valtozatok(p, allas)]
    P += szinkezeles_peldanyok(allas, technikak, igeny, ures)
    biztosak = sorted((p for p in P if biztos_egyseg(p)), key=lambda p: -p.hozam)
    esely = [p for p in P if not biztos_egyseg(p)]
    keszletek: list[list[Peldany]] = []
    teljes: list[Peldany] = []
    for p in biztosak:
        if not any(_utkozik(p, q) for q in teljes):
            teljes.append(p)
    # előbb a teljes biztos készlet (a vesztőcsere minden dobásszínével), aztán
    # egyenként, végül nélkülük
    teljesek = [teljes] if teljes else []
    for p in biztosak:
        for i, q in enumerate(teljes):
            if q.sema.azon == p.sema.azon and q.szin == p.szin and q is not p:
                teljesek.append(teljes[:i] + [p] + teljes[i + 1:])
    for x in teljesek + [[p] for p in biztosak] + [[]]:
        if x not in keszletek:
            keszletek.append(x)
    egy_keszletre = max(8, max_db // max(1, len(keszletek)))
    ki: list[KTerv] = []
    latott = set()

    def hozzaad(lepesek):
        # a terv csak akkor jelölt, ha minden egysége sikere esetén fedi az igényt
        if max_hozam(lepesek) < igeny:
            return
        kulcs = tuple(id(p) for p in lepesek)
        if kulcs not in latott:
            latott.add(kulcs)
            ki.append(KTerv(list(lepesek), igeny,
                        tuple(alap_fazis(p) for p in lepesek) if SZABALY["SZAKASZ"] else None,
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
        ki.sort(key=lambda t: -t.elozetes)
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

    def _politika(self, ei: int):
        """Az elemzős egység politikája (lustán; ha a lapjaink nem egyeznek, újraépül a
        mostani állásból, a cél még hiányzó részével)."""
        from .tervszinpolitika import SzinPolitika
        j = self.j
        e = self.egysegek[ei]
        sz = e.p.szin
        X = frozenset(l.rang for l in j.szin(j.felvevo, sz))
        Y = frozenset(l.rang for l in j.szin(j.asztal, sz))
        pol = self.politikak.get(ei)
        if pol is not None and pol.lapjaink() == (X, Y):
            return pol
        # a cél: a terv óta a színben szerzett / vesztett ütések levonásával
        nyert = vesztett = 0
        L = j.lapok
        for i in range(self.kezdo - self.kezdo % 4, len(L) - len(L) % 4, 4):
            ut = L[i:i + 4]
            if len(ut) < 4 or ut[0][1].szin != sz:
                continue
            gy, gl = j.nyertes(ut)
            if j.mi(gy):
                nyert += gl.szin == sz
            else:
                vesztett += 1
        k = e.p.szerepek["k"] - nyert
        m = e.p.szerepek["m"] - vesztett
        kint = frozenset(l.rang for l in j.kint(sz))
        v1, v2 = kovetkezo_ules(j.felvevo, 1), kovetkezo_ules(j.felvevo, 3)
        ures = [13 - sum(1 for u, _ in L if u == v) for v in (v1, v2)]
        try:
            pol = SzinPolitika(X, Y, kint, ures[0], ures[1], k, m, sz == self.adu)
        except Exception:                        # noqa: BLE001
            return None
        self.politikak[ei] = pol
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

    def _kovetkezo_kor(self, csak: str | None = None) -> tuple[Egyseg, Kor] | None:
        """Az esélyek sorában az első élő egység soron következő köre. A már lement
        lapok köreit (átmenetként vagy védői hívásra tettük le) átlépi; a `csak_ha:
        siker` körnél dönt: a lap most nyerő-e (megfigyelt tény)."""
        j = self.j
        mieink = j.kezek[j.felvevo] | j.kezek[j.asztal]
        for e in self.egysegek:
            if csak is not None and e.fazis != csak:
                continue
            while e.el:
                k = e.kor()
                if k is not None and k.fajta == "elemzo":
                    ei = self.egysegek.index(e)
                    pol = self._politika(ei)
                    akc = pol.dontes() if pol is not None else None
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
            if not e.el or (elotte and e.fazis != "E"):
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
                if k.fajta in ("impassz", "lop", "kiad"):
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

    def _jeloltek(self, H: str) -> list["Jelolt"]:
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

    def _adukor_jeloltek(self, H: str, ar: float) -> list["Jelolt"]:
        j, adu = self.j, self.adu
        P = j.partner(H)
        ki = []
        sajat, par = j.szin(H, adu), j.szin(P, adu)
        if sajat and self._nyero(sajat[-1]):
            ki.append(Jelolt(sajat[-1], ar, f"adukör ({sajat[-1]})"))
        if sajat and par and self._nyero(par[-1]) and sajat[0].rang < par[-1].rang:
            ki.append(Jelolt(sajat[0], ar + 0.1, f"adukör a másik kézbe ({par[-1]})", {P: ("lap", par[-1])}))
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
            if k.hivo != H:
                return self._atmenet_jeloltek(H, k.hivo, e, ar + 0.5)
            sajat = j.szin(H, k.szin)
            if not sajat:
                return []
            szabad = [l for l in sajat if l not in fogl] or sajat
            return [Jelolt(szabad[0], ar, f"{e.p.rovid}: kiadás ({szabad[0]})", folyo=(ei, k))]
        if k.fajta == "lop":
            if k.hivo != H:
                return self._atmenet_jeloltek(H, k.hivo, e, ar + 0.5)
            sajat = [l for l in j.szin(H, k.szin) if l not in (e.p.hasznal | e.p.elfogyaszt)] \
                or j.szin(H, k.szin)
            if not sajat or j.szin(P, k.szin) or not j.szin(P, self.adu):
                return []
            return [Jelolt(sajat[0], ar, cim, {P: ("lop",)}, (ei, k))]
        return []

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
                elif w in kesobbi:
                    ar = 2.5
                elif w in fogl:
                    ar = 4
                else:
                    ar = 2
                leiras = f"átmenet {w}" + (f" — egyben {kesobbi[w].p.rovid} köre (közös lap)" if w in kesobbi else "")
                ki.append(Jelolt(hivo[0], ar0 + (ar + hivo_ar) / 10, leiras, {R: ("lap", w)}))
            elif not rl and sz != adu and adu and j.szin(R, adu) \
                    and len(j.szin(R, adu)) > self._lopas_igeny(R):
                hivo = [l for l in hl if l not in fogl] or hl
                ar = 0 if kint_adu == 0 else 3
                ki.append(Jelolt(hivo[0], ar0 + (ar + hivo_ar) / 10, f"átmenet lopással ({SZINJEL[sz]})",
                                 {R: ("lop",)}))
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
            ki.append(Jelolt(l, ar + (0.2 if sz == self.adu else 0) + (0 if rovid else 0.1),
                             f"begyűjtés {l}"))
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
        self._jegyez(ok)
        return lap

    def _kovetes_ok(self, u: str) -> tuple[Lap, str]:
        """A hozzátevés és az oka (a tanári asztal ezt mutatja)."""
        j, adu = self.j, self.adu
        utes = j.aktualis()
        hivott = utes[0][1].szin
        nyu, nyl = j.nyertes(utes)
        van = j.szin(u, hivott)
        fogl = self._foglalt()
        sz = self.szandek.pop(u, None)
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
                    return adu_l[0], f"lopás: {adu_l[0]}"
        partner_nyer = j.mi(nyu)
        R = self._kovetkezo_hivo()
        P = j.partner(u)
        hatra_van_partner = len(utes) <= 2 and any(x == P for x in self._hatra(utes))
        if van and not partner_nyer and R == u:
            # a terv innen folytatódik: ha biztosan üthetünk, itt üssünk
            biztos = [l for l in van if self._nyero(l) and _ut(l, nyl, adu)]
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
                return adu_l[0], f"lop: {adu_l[0]}"
        l = self._dobas(u, fogl)
        return l, f"dobás: {l}" + (" (a foglalt és a nyerő lapokat megtartja)" if fogl & j.kezek[u] else "")

    def _fo_kez(self) -> str | None:
        """A hosszabb adus kezünk (a fő kéz)."""
        if not self.adu:
            return None
        j = self.j
        a1, a2 = len(j.szin(j.felvevo, self.adu)), len(j.szin(j.asztal, self.adu))
        return j.felvevo if a1 >= a2 else j.asztal

    def _dobhato_veszto(self, u: str, fogl: set[Lap]) -> Lap | None:
        """Egy vesztő, amelyet dobhatunk: nem foglalt, nem nyerő, nem adu, és olyan
        színből, amelyben a partnernek sincs nyerője, ami fedné."""
        j = self.j
        jelolt = [l for l in j.kezek[u] if l not in fogl and not self._nyero(l) and l.szin != self.adu]
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
              jatek_ki: list | None = None) -> int:
    """Egy világ végigjátszása: mi a terv szerint, a védők a `dd_vedo` szerint."""
    j = tj.Jatek({u: set(vilag.kezek[u].lapok) for u in "NESW"}, felvevo, adu, lejatszott, tj.Terv(()))
    v = Vegrehajto(terv, j, naplo)
    v.cel = cel
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
                    utana=None) -> list[Eredmeny]:
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
                n = lejatszik(t, w, felvevo, adu, lejatszott, dd_vedo, cel=cel)
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
