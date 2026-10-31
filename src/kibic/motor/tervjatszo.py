"""
Tervjátszó és jelöltállító (2026-10-25, játék-szál).

A felvevő nem lapot választ, hanem TERVET: a jelöltállító a saját két kéz
lapjaiból értelmes terveket rak össze (színenként kezelések: lehívás, impassz,
kiadás, lopás; kiaduzás; és ezek sorrendje), a tervjátszó pedig minden tervet
végigjátszik a sorsolt világokon. A felvevő minden világban UGYANÚGY játszik
(csak azt használja, amit lát: a két kezét és a lejátszott lapokat — nincs
kukucskálás), a védők DD szerint. A terv esélye = a világok (súlyozott)
hányadában teljesít; a legnagyobb esélyű tervet választjuk.

A típusnevek (impassz, lopás…) itt csak építőkövek; a választás szám.
"""
from __future__ import annotations

import itertools
import time
from dataclasses import dataclass, field

from ..domain import SZINEK, Lap, kovetkezo_ules, vonal
from ..domain.kartya import LAPOK

# az utolsó ennyi ütést (ha a terv már elfogyott) a DD dönti el — gyorsítás
DD_VEGE_UTES = 4

# --- 1. A terv -----------------------------------------------------------------------


@dataclass(frozen=True)
class Lepes:
    fajta: str                 # LEHIV / KIADUZ / IMPASSZ / KIAD / LOP
    szin: str | None = None
    db: int = 0                # LEHIV: ennyi kör (0 = amíg van nyerő); IMPASSZ/KIAD/LOP: körök

    def __str__(self) -> str:
        s = self.fajta + (f" {self.szin}" if self.szin else "")
        return s + (f"×{self.db}" if self.db else "")


@dataclass(frozen=True)
class Terv:
    lepesek: tuple[Lepes, ...]

    def __str__(self) -> str:
        return " → ".join(map(str, self.lepesek)) or "(csak lehívás)"


# --- 2. A játék egy világban ---------------------------------------------------------


def _osszes(sz: str) -> list[Lap]:
    return [Lap(sz, e) for e in LAPOK]


class Jatek:
    """Egy világ lejátszása. A felvevő oldal döntései CSAK a látott lapokból
    (a két kéz + a lejátszott lapok) dolgoznak — `kint()` is ebből számol."""

    def __init__(self, kezek: dict[str, set[Lap]], felvevo: str, adu: str | None,
                 lejatszott: list[tuple[str, Lap]], terv: Terv):
        self.kezek = {u: set(k) for u, k in kezek.items()}
        for u, l in lejatszott:
            self.kezek[u].discard(l)
        self.felvevo = felvevo
        self.asztal = kovetkezo_ules(felvevo, 2)
        self.adu = adu
        self.lapok = list(lejatszott)
        self.terv = terv
        self.kurzor = 0
        self.szamlalo = 0          # a mostani lépés megtett körei
        self.szandek: tuple | None = None   # a mi hívásunkhoz a partner teendője
        self.atmenetek = 0         # a mostani lépéshez kért átmenetek

    # -- amit a felvevő lát --
    def mi(self, u: str) -> bool:
        return vonal(u) == vonal(self.felvevo)

    def partner(self, u: str) -> str:
        return kovetkezo_ules(u, 2)

    def kint(self, sz: str) -> list[Lap]:
        """A védőknél lévő lapok a színben — a felvevő ezt KISZÁMOLJA (nem látja)."""
        lement = {l for _, l in self.lapok}
        sajat = self.kezek[self.felvevo] | self.kezek[self.asztal]
        return [l for l in _osszes(sz) if l not in lement and l not in sajat]

    def nyerok(self, u: str, sz: str) -> list[Lap]:
        k = self.kint(sz)
        top = max((l.rang for l in k), default=0)
        return sorted((l for l in self.kezek[u] if l.szin == sz and l.rang > top),
                      key=lambda l: -l.rang)

    def szin(self, u: str, sz: str) -> list[Lap]:
        return sorted((l for l in self.kezek[u] if l.szin == sz), key=lambda l: l.rang)

    # -- a menet --
    def aktualis(self) -> list[tuple[str, Lap]]:
        n = len(self.lapok) % 4
        return self.lapok[len(self.lapok) - n:] if n else []

    def nyertes(self, utes) -> tuple[str, Lap]:
        best = utes[0]
        for u, l in utes[1:]:
            b = best[1]
            if (l.szin == b.szin and l.rang > b.rang) or (self.adu and l.szin == self.adu and b.szin != self.adu):
                best = (u, l)
        return best

    def soron(self) -> str:
        n = len(self.lapok)
        if n % 4:
            return kovetkezo_ules(self.lapok[-1][0])
        return self.nyertes(self.lapok[-4:])[0]

    def tesz(self, u: str, l: Lap) -> None:
        self.lapok.append((u, l))
        self.kezek[u].discard(l)
        if len(self.lapok) % 4 == 0:
            self.szandek = None

    def felvevo_utesek(self) -> int:
        n = 0
        for i in range(0, len(self.lapok) - len(self.lapok) % 4, 4):
            if self.mi(self.nyertes(self.lapok[i:i + 4])[0]):
                n += 1
        return n


# --- 3. A felvevő politikája (terv + alapszabályok) ----------------------------------

def _legolcsobb_fole(lapok: list[Lap], fole: Lap, adu: str | None) -> Lap | None:
    jo = [l for l in lapok if (l.szin == fole.szin and l.rang > fole.rang)
          or (adu and l.szin == adu and fole.szin != adu)]
    if not jo:
        return None
    return min(jo, key=lambda l: (l.szin == adu and fole.szin != adu, l.rang))


def _dobas(j: Jatek, u: str) -> Lap:
    """Dobás: az adut és a nyerőket kíméljük; a legreménytelenebb lapot dobjuk (amely
    fölött a legtöbb védőlap van), azon belül a terv még hátralévő színeit kíméljük."""
    hatra = {l.szin for l in j.terv.lepesek[j.kurzor:] if l.szin}

    def ertek(l: Lap):
        nyero = l in j.nyerok(u, l.szin)
        fent = sum(1 for x in j.kint(l.szin) if x.rang > l.rang)
        return (l.szin == j.adu, nyero, l.szin in hatra, -fent, l.rang)
    return min(j.kezek[u], key=ertek)


def kovetes(j: Jatek, u: str) -> Lap:
    """A mi oldalunk nem hív: színt ad / lop / dob."""
    utes = j.aktualis()
    hivott = utes[0][1].szin
    poz = len(utes) + 1                         # 2, 3 vagy 4
    van = j.szin(u, hivott)
    nyu, nyl = j.nyertes(utes)
    partner_nyer = j.mi(nyu)
    if van:
        if poz == 3 and j.szandek is not None:  # a partner hívott, szándékkal
            fajta = j.szandek[0]
            if fajta == "ALACSONY":
                return van[0]
            if fajta == "IMPASSZ":
                f = j.szandek[1]
                masodik = utes[1][1]
                if masodik.szin == hivott and masodik.rang > f.rang:
                    c = _legolcsobb_fole(van, masodik, None)
                    return c or van[0]
                if f in van and (masodik.szin != hivott or masodik.rang < f.rang):
                    return f
            if fajta in ("NYER", "LOP", "IMPASSZ"):
                c = _legolcsobb_fole(van, nyl, j.adu) if not partner_nyer or fajta == "NYER" else None
                if fajta == "NYER" and partner_nyer:
                    # a partner lapja nyer — de a mienk legyen fent (átmenet): ha van nyerőnk, azt
                    ny = j.nyerok(u, hivott)
                    if ny and nyl.rang < ny[-1].rang:
                        return ny[-1]
                    return van[0]
                return c or van[0]
        if partner_nyer:
            # a partner lapja fent van-e (a hátralévő védő nem üti a kintlévő lapjaival)?
            top = max((l.rang for l in j.kint(hivott)), default=0)
            if poz == 4 or (nyl.szin == hivott and nyl.rang > top) or (j.adu and nyl.szin == j.adu):
                return van[0]
        if poz == 2:
            # második kéz kicsit — kivéve: figurára figurát (fedés), és ha a partnerünk
            # (negyedik kéz, látjuk) nem tudja megütni a hívott lapot, és lopni sem tud
            if utes[0][1].rang >= 11:
                c = _legolcsobb_fole(van, nyl, None)
                if c is not None:
                    return c
            p4 = j.partner(u)
            p4_van = j.szin(p4, hivott)
            p4_lop = j.adu and hivott != j.adu and not p4_van and j.szin(p4, j.adu)
            if not p4_lop and not any(l.rang > nyl.rang for l in p4_van):
                c = _legolcsobb_fole(van, nyl, None)
                if c is not None:
                    return c
            return van[0]
        c = _legolcsobb_fole(van, nyl, j.adu)
        return c or van[0]
    # színhiány
    if j.adu and hivott != j.adu:
        adu = j.szin(u, j.adu)
        if adu and poz == 3 and j.szandek and j.szandek[0] == "LOP":
            lopott = [l for _, l in utes if l.szin == j.adu]
            fole = [l for l in adu if all(l.rang > x.rang for x in lopott)]
            return (fole or adu)[0]
        if adu and not partner_nyer:
            c = _legolcsobb_fole(adu, nyl, j.adu)
            if c is not None:
                return c
        if adu and partner_nyer and poz == 2:
            pass                                 # a partner még jön — nem lopunk feleslegesen
    return _dobas(j, u)


def _atmenet(j: Jatek, kez: str, cel: str) -> tuple[Lap, tuple] | None:
    """Hívás `kez`-ből úgy, hogy `cel` vigye az ütést (a legolcsóbb biztos átmenet)."""
    jelolt = []
    for sz in SZINEK:
        sajat = j.szin(kez, sz)
        if not sajat:
            continue
        ny = j.nyerok(cel, sz)
        if ny and (not j.nyerok(kez, sz) or ny[0].rang > max(l.rang for l in sajat)):
            jelolt.append(((sz == j.adu, len(ny)), sajat[0], ("NYER",)))
        elif j.adu and sz != j.adu and not j.szin(cel, sz) and j.szin(cel, j.adu) and j.kint(sz):
            jelolt.append(((True, 9), sajat[0], ("LOP",)))
    if not jelolt:
        return None
    _, lap, sz_ = min(jelolt, key=lambda x: x[0])
    return lap, sz_


def _lepes_hivas(j: Jatek, kez: str, lp: Lepes):
    """Vissza: ("LAP", lap, szándék) / ("KESZ",) / ("ATMENET", célkéz)."""
    p = j.partner(kez)
    sz = lp.szin
    if lp.fajta == "KIADUZ":
        if not j.adu or not j.kint(j.adu) or j.szamlalo >= (lp.db or 6):
            return ("KESZ",)
        sajat = j.szin(kez, j.adu)
        ny = j.nyerok(kez, j.adu)
        if ny:
            return ("LAP", ny[0], None)
        if j.nyerok(p, j.adu):
            return ("LAP", sajat[0], ("NYER",)) if sajat else ("ATMENET", p)
        if sajat:
            return ("LAP", sajat[0], None)
        return ("ATMENET", p) if j.szin(p, j.adu) else ("KESZ",)
    if lp.fajta == "LEHIV":
        if lp.db and j.szamlalo >= lp.db:
            return ("KESZ",)
        nk, np_ = j.nyerok(kez, sz), j.nyerok(p, sz)
        if not nk and not np_:
            return ("KESZ",)
        lk, lpn = len(j.szin(kez, sz)), len(j.szin(p, sz))
        if nk and (not np_ or lk <= lpn or len(np_) == 0):
            return ("LAP", nk[0] if lk <= lpn else nk[0], ("ALACSONY",))
        if np_:
            sajat = j.szin(kez, sz)
            return ("LAP", sajat[0], ("NYER",)) if sajat else ("ATMENET", p)
        return ("LAP", nk[0], ("ALACSONY",))
    if lp.fajta == "IMPASSZ":
        if j.szamlalo >= max(1, lp.db):
            return ("KESZ",)
        k = j.kint(sz)
        if not k:
            return ("KESZ",)
        # a hiányzó lap: a legnagyobb kint lévő, amely alatt nálunk figura van
        for m in sorted(k, key=lambda l: -l.rang):
            jo = []
            for t in (j.felvevo, j.asztal):
                alatta = [l for l in j.szin(t, sz) if l.rang < m.rang and l.rang >= 9]
                if alatta and j.szin(j.partner(t), sz):
                    jo.append((max(alatta, key=lambda l: l.rang), t))
            if jo:
                f, t = max(jo, key=lambda x: x[0].rang)
                hivo = j.partner(t)
                if kez != hivo:
                    return ("ATMENET", hivo)
                return ("LAP", j.szin(kez, sz)[0], ("IMPASSZ", f))
        return ("KESZ",)
    if lp.fajta == "KIAD":
        if j.szamlalo >= max(1, lp.db) or not j.kint(sz):
            return ("KESZ",)
        sajat = j.szin(kez, sz)
        if not sajat:
            return ("ATMENET", p) if j.szin(p, sz) else ("KESZ",)
        return ("LAP", sajat[0], ("ALACSONY",))
    if lp.fajta == "LOP":
        if j.szamlalo >= max(1, lp.db) or not j.adu:
            return ("KESZ",)
        for r in (j.asztal, j.felvevo):          # a lopó kéz: színhiány + adu
            h = j.partner(r)
            if not j.szin(r, sz) and j.szin(r, j.adu) and j.szin(h, sz):
                if kez != h:
                    return ("ATMENET", h)
                return ("LAP", j.szin(h, sz)[0], ("LOP",))
        return ("KESZ",)
    return ("KESZ",)


def _alap_hivas(j: Jatek, kez: str) -> tuple[Lap, tuple | None]:
    """A terv után: kiaduzás (ha van felső adunk), nyerők lehívása, átmenet, kicsi."""
    p = j.partner(kez)
    if j.adu and j.kint(j.adu) and j.nyerok(kez, j.adu):
        return j.nyerok(kez, j.adu)[0], ("ALACSONY",)
    for sz in sorted(SZINEK, key=lambda s: s == j.adu):
        ny = j.nyerok(kez, sz)
        if ny:
            return ny[0], ("ALACSONY",)
    a = _atmenet(j, kez, p)
    if a and any(j.nyerok(p, sz) for sz in SZINEK):
        return a
    # nincs nyerő: a leghosszabb színünk legkisebbje (nem adu)
    szinek = [s for s in SZINEK if j.szin(kez, s)]
    sz = max(szinek, key=lambda s: (s != j.adu, len(j.szin(kez, s)) + len(j.szin(p, s))))
    return j.szin(kez, sz)[0], None


def hivas(j: Jatek, kez: str) -> Lap:
    probak = 0
    while j.kurzor < len(j.terv.lepesek) and probak < 20:
        probak += 1
        lp = j.terv.lepesek[j.kurzor]
        r = _lepes_hivas(j, kez, lp)
        if r[0] == "KESZ":
            j.kurzor += 1
            j.szamlalo = j.atmenetek = 0
            continue
        if r[0] == "ATMENET":
            a = _atmenet(j, kez, r[1]) if j.atmenetek < 2 else None
            if a is None:                      # nincs átmenet: a lépést kihagyjuk
                j.kurzor += 1
                j.szamlalo = j.atmenetek = 0
                continue
            j.atmenetek += 1
            j.szandek = a[1]
            return a[0]
        j.szamlalo += 1
        j.szandek = r[2]
        return r[1]
    lap, sz = _alap_hivas(j, kez)
    j.szandek = sz
    return lap


def szabalyos(j: Jatek, u: str, lap: Lap) -> Lap:
    utes = j.aktualis()
    van = [l for l in j.kezek[u] if utes and l.szin == utes[0][1].szin]
    if lap in j.kezek[u] and (not van or lap.szin == utes[0][1].szin):
        return lap
    return min(van or j.kezek[u], key=lambda l: l.rang)


def felvevo_lap(j: Jatek, u: str) -> Lap:
    return szabalyos(j, u, hivas(j, u) if not j.aktualis() else kovetes(j, u))


# --- 4. Lejátszás a világokon --------------------------------------------------------

def vedo_dd(dd_fv, leosztas, kontraktus):
    """A védő DD szerint (egyenlőségnél a legkisebb lappal)."""
    def fv(j: Jatek, u: str) -> Lap:
        ered = dd_fv(leosztas, [str(l) for _, l in j.lapok], kontraktus)
        legj = max(e.utesek for e in ered)
        return min((Lap.parse(e.lap) for e in ered if e.utesek == legj), key=lambda l: (l.rang, l.szin))
    return fv


def lejatszik(kezek, felvevo, adu, lejatszott, terv: Terv, vedo_fv) -> int:
    """Egy világ végigjátszása a tervvel; vissza: a felvevő ÖSSZES ütése."""
    j = Jatek(kezek, felvevo, adu, lejatszott, terv)
    while len(j.lapok) < 52:
        u = j.soron()
        if j.mi(u):
            lap = felvevo_lap(j, u)
        else:
            lap = vedo_fv(j, u)
        if lap not in j.kezek[u]:              # biztonsági háló: szabályos lap
            utes = j.aktualis()
            van = [l for l in j.kezek[u] if utes and l.szin == utes[0][1].szin]
            lap = min(van or j.kezek[u], key=lambda l: l.rang)
        utes = j.aktualis()
        if utes:
            van = [l for l in j.kezek[u] if l.szin == utes[0][1].szin]
            if van and lap.szin != utes[0][1].szin:
                lap = min(van, key=lambda l: l.rang)
        j.tesz(u, lap)
    return j.felvevo_utesek()


@dataclass
class TervErtek:
    terv: Terv
    esely: float          # a teljesítés (súlyozott) aránya
    atlag: float          # átlagos ütésszám
    n: int


class DDTar:
    """DD-eredmények világonként és lapsoronként (a tervek közös eleje egyszer számol)."""

    def __init__(self, dd_fv, kontraktus):
        self.dd_fv = dd_fv
        self.k = kontraktus
        self.tar: dict = {}
        self.hivas = 0

    def __call__(self, i: int, lo, lapok: list[tuple[str, Lap]]):
        kulcs = (i, tuple(str(l) for _, l in lapok))
        r = self.tar.get(kulcs)
        if r is None:
            self.hivas += 1
            r = self.dd_fv(lo, list(kulcs[1]), self.k)
            self.tar[kulcs] = r
        return r


def _vedo_lap(ered) -> Lap:
    legj = max(e.utesek for e in ered)
    return min((Lap.parse(e.lap) for e in ered if e.utesek == legj), key=lambda l: (l.rang, l.szin))


def _szandekos(j: Jatek, u: str) -> bool:
    """A követő lapot a terv szándéka dönti el (a partner hívott, szándékkal)?"""
    return len(j.aktualis()) == 2 and j.szandek is not None and j.szandek[0] in (
        "ALACSONY", "IMPASSZ", "NYER", "LOP")


def dd_szavazas(eredmenyek: list, sulyok: list[float], cel: int) -> Lap:
    """Közös lap több világra (amelyeket a felvevő nem tud megkülönböztetni): a
    teljesítés súlyozott aránya, utána az átlagos ütésszám szerint; egyenlőségnél
    a legkisebb lap."""
    pont: dict[str, list[float]] = {}
    for ered, w in zip(eredmenyek, sulyok):
        for e in ered:
            x = pont.setdefault(e.lap, [0.0, 0.0])
            x[0] += w * (e.felvevo_osszesen >= cel)
            x[1] += w * e.felvevo_osszesen
    best = max(pont.values(), key=lambda v: (v[0], v[1]))
    jo = [Lap.parse(l) for l, v in pont.items() if v == best]
    return min(jo, key=lambda l: (l.rang, l.szin))


def ertekel(tervek: list[Terv], vilagok, sulyok, felvevo, kontraktus, lejatszott,
            dd_fv=None, hatarido: float | None = None, dd_tar: DDTar | None = None,
            dd_vege: bool = True) -> list[TervErtek]:
    """Minden terv: az összes világ EGYÜTT halad (lépésenként). A felvevő hívásait a
    terv adja; a követő lapjait, ahol a terv nem rendelkezik, a még meg nem
    különböztethető világok közös DD-szavazása (ugyanazt a lapot teszi mindben)."""
    if dd_tar is None:
        if dd_fv is None:
            from ..solver.dds import lap_elemzes as dd_fv
        dd_tar = DDTar(dd_fv, kontraktus)
    adu = None if kontraktus.szin == "NT" else kontraktus.szin
    cel = 6 + kontraktus.szint
    ki = []
    for t in tervek:
        if hatarido and time.time() > hatarido and ki:
            break
        jatekok = [Jatek({u: set(lo.kezek[u].lapok) for u in "NESW"}, felvevo, adu, lejatszott, t)
                   for lo in vilagok]
        vegso: dict[int, int] = {}            # világ -> a felvevő végső ütésszáma (ha már eldőlt)
        while len(vegso) < len(jatekok):
            csoport: dict[tuple, list[int]] = {}
            for i, j in enumerate(jatekok):
                if i not in vegso:
                    csoport.setdefault(tuple(j.lapok), []).append(i)
            for idx in csoport.values():
                j0 = jatekok[idx[0]]
                if len(j0.lapok) >= 52:
                    for i in idx:
                        vegso[i] = jatekok[i].felvevo_utesek()
                    continue
                u = j0.soron()
                # a terv elfogyott, és ütés elején vagyunk: a maradékot a DD dönti el
                # (itt már csak lehívás van hátra — a kukucskálás itt kevés kárt tesz)
                if dd_vege and not j0.aktualis() and j0.kurzor >= len(t.lepesek) \
                        and len(j0.lapok) >= 52 - 4 * DD_VEGE_UTES:
                    for i in idx:
                        ered = dd_tar(i, vilagok[i], jatekok[i].lapok)
                        vegso[i] = (max if j0.mi(u) else min)(e.felvevo_osszesen for e in ered)
                    continue
                if not j0.mi(u):
                    for i in idx:
                        jatekok[i].tesz(u, _vedo_lap(dd_tar(i, vilagok[i], jatekok[i].lapok)))
                    continue
                if not j0.aktualis() or _szandekos(j0, u):
                    lapok = [felvevo_lap(jatekok[i], u) for i in idx]
                else:
                    ered = [dd_tar(i, vilagok[i], jatekok[i].lapok) for i in idx]
                    lap = dd_szavazas(ered, [sulyok[i] for i in idx], cel)
                    lapok = [szabalyos(jatekok[i], u, lap) for i in idx]
                for i, lap in zip(idx, lapok):
                    jatekok[i].tesz(u, lap)
        W = sum(sulyok)
        ut = [vegso[i] for i in range(len(jatekok))]
        ok = sum(w for w, x in zip(sulyok, ut) if x >= cel)
        ki.append(TervErtek(t, ok / W if W else 0.0,
                            sum(w * x for w, x in zip(sulyok, ut)) / W if W else 0.0, len(jatekok)))
    return sorted(ki, key=lambda x: (-x.esely, -x.atlag))


def kovetesi_valasztas(legalis: list[Lap], utes: list[tuple[str, Lap]], adu: str | None) -> list[Lap]:
    """A követő lap valódi választásai: a legkisebb lap, amely NEM viszi az ütést
    (kihagyás, kiengedés), és a legolcsóbb, amely viszi (fedés, megütés). Ha csak
    az egyik fajta van, nincs ilyen választás (üres lista)."""
    if not utes:
        return []
    hivott = utes[0][1].szin
    nyl = utes[0][1]
    for _, l in utes[1:]:
        if (l.szin == nyl.szin and l.rang > nyl.rang) or (adu and l.szin == adu and nyl.szin != adu):
            nyl = l
    viszi = [l for l in legalis if (l.szin == nyl.szin and l.rang > nyl.rang)
             or (adu and l.szin == adu and nyl.szin != adu)]
    nem = [l for l in legalis if l not in viszi]
    if not viszi or not nem:
        return []
    kicsi = min(nem, key=lambda l: (l.szin == adu, l.szin != hivott, l.rang))
    olcso = min(viszi, key=lambda l: (l.szin == adu and hivott != adu, l.rang))
    return [kicsi, olcso]


def kovetes_tervvel(lapok: list[Lap], tervek: list[Terv], vilagok, sulyok, felvevo, kontraktus,
                    lejatszott, u: str, dd_fv=None) -> tuple[Lap, list[tuple[str, float, float, str]]]:
    """A követő lap a tervek szerint (nem DD-szavazással): minden jelölt lapot
    letesz a világokon, és a folytatást a tervekkel értékeli (a felvevő ott sem
    kukucskál). A lap értéke a legjobb terv esélye (egyenlőségnél az átlagos
    ütésszám). Vissza: a választott lap és a napló (lap, esély, átlag, terv)."""
    if dd_fv is None:
        from ..solver.dds import lap_elemzes as dd_fv
    naplo = []
    for c in lapok:
        tar = DDTar(dd_fv, kontraktus)
        ert = ertekel(tervek, vilagok, sulyok, felvevo, kontraktus, list(lejatszott) + [(u, c)],
                      dd_tar=tar)
        naplo.append((str(c), ert[0].esely, ert[0].atlag, str(ert[0].terv)))
    i = max(range(len(lapok)), key=lambda i: (naplo[i][1], naplo[i][2]))
    return lapok[i], naplo


def ertekel_lepcsos(tervek: list[Terv], vilagok, sulyok, felvevo, kontraktus, lejatszott,
                    dd_fv=None, elso: int = 4, marad: int = 8) -> list[TervErtek]:
    """Lépcsős értékelés: minden terv az első `elso` világon, a legjobb `marad`
    (legalább a jelöltek ötöde) az összesen. A DD-tár közös (a világok indexe azonos)."""
    if dd_fv is None:
        from ..solver.dds import lap_elemzes as dd_fv
    tar = DDTar(dd_fv, kontraktus)
    if len(vilagok) <= elso or len(tervek) <= marad:
        return ertekel(tervek, vilagok, sulyok, felvevo, kontraktus, lejatszott, dd_tar=tar)
    elo = ertekel(tervek, vilagok[:elso], sulyok[:elso], felvevo, kontraktus, lejatszott, dd_tar=tar)
    n = max(marad, len(tervek) // 5)
    return ertekel([e.terv for e in elo[:n]], vilagok, sulyok, felvevo, kontraktus, lejatszott,
                   dd_tar=tar)


# --- 5. Jelöltállító -----------------------------------------------------------------

def _szinkezelesek(d: set[Lap], y: set[Lap], sz: str, adu: str | None, kint: list[Lap]) -> list[tuple]:
    """Egy szín értelmes kezelései (lépés-sorozatok) a két kéz lapjaiból."""
    dd = sorted((l for l in d if l.szin == sz), key=lambda l: -l.rang)
    yy = sorted((l for l in y if l.szin == sz), key=lambda l: -l.rang)
    mi = sorted(dd + yy, key=lambda l: -l.rang)
    if not mi:
        return [()]
    top = max((l.rang for l in kint), default=0)
    felso = sum(1 for l in mi if l.rang > top)
    ki: list[tuple] = []
    if felso:
        ki.append((Lepes("LEHIV", sz),))
    # impassz: van kint figura, amely alatt nálunk figura (T+) van, a másik kézben kísérő
    kint_fig = [l for l in kint if l.rang >= 11]
    imp = False
    for m in kint_fig:
        for t, masik in ((dd, yy), (yy, dd)):
            if any(9 <= l.rang < m.rang for l in t) and masik:
                imp = True
    if imp:
        ki.append((Lepes("IMPASSZ", sz, 1), Lepes("LEHIV", sz)))
        if len(kint_fig) >= 2:
            ki.append((Lepes("IMPASSZ", sz, 2), Lepes("LEHIV", sz)))
        if felso:
            ki.append((Lepes("LEHIV", sz, 1), Lepes("IMPASSZ", sz, 1), Lepes("LEHIV", sz)))
    # kimagasítás kiadással: hosszú szín (7+ együtt), van kint nagyobb lap
    if len(mi) >= 7 and kint and felso < max(len(dd), len(yy)):
        ki.append((Lepes("KIAD", sz, 1), Lepes("LEHIV", sz)))
        if felso:
            ki.append((Lepes("LEHIV", sz), Lepes("KIAD", sz, 1), Lepes("LEHIV", sz)))
    # lopás a rövid kézben
    if adu and sz != adu:
        ad = sum(1 for l in d if l.szin == adu)
        ay = sum(1 for l in y if l.szin == adu)
        for rovid, hosszu, ar in ((yy, dd, ay), (dd, yy, ad)):
            if ar and len(rovid) < len(hosszu) and len(rovid) <= 2:
                db = min(ar, len(hosszu) - len(rovid))
                ki.append(tuple([Lepes("LEHIV", sz)] if rovid else []) + (Lepes("LOP", sz, db),))
    return ki or [()]


def jeloltek(d: set[Lap], y: set[Lap], adu: str | None, kint_fv, max_db: int = 80,
             max_elter: int = 2, adu_kezeles: bool = False) -> list[Terv]:
    """Tervjelöltek. Színenként az alapkezelés a lehívás; a terv legfeljebb
    `max_elter` színben tér el tőle (impassz, kiadás, lopás…), ezek elöl állnak
    (minden sorrendben), a lehívások a végén. Színfelvételnél a kiaduzás helye:
    elöl / a lopások után / sehol."""
    kez: dict[str, list[tuple]] = {sz: _szinkezelesek(d, y, sz, adu, kint_fv(sz))
                                   for sz in SZINEK if sz != adu}
    alap = {sz: (k[0] if k and k[0] and k[0][0].fajta == "LEHIV" and len(k[0]) == 1 else ())
            for sz, k in kez.items()}
    elter = [(sz, t) for sz, k in kez.items() for t in k if t and t != alap[sz]]
    if adu and adu_kezeles:
        # az aduszín kezelése (impassz, kiadás) a kiaduzás helyén: a kezelés után
        # a maradék kiaduzás (LEHIV helyett KIADUZ)
        for t in _szinkezelesek(d, y, adu, adu, kint_fv(adu)):
            if t and not (len(t) == 1 and t[0].fajta == "LEHIV") and all(l.fajta != "LOP" for l in t):
                elter.append((adu, tuple(Lepes("KIADUZ", None, l.db) if l.fajta == "LEHIV" else l
                                         for l in t)))
    tervek: list[Terv] = []
    lat = set()

    def hozzaad(lepesek: list[Lepes]):
        valtozatok = [lepesek]
        if adu and any(l.szin == adu for l in lepesek):
            valtozatok = [lepesek]               # az adu kezelése már a tervben van
        elif adu:
            lopas = [i for i, l in enumerate(lepesek) if l.fajta == "LOP"]
            valtozatok = [[Lepes("KIADUZ")] + lepesek]
            if lopas:
                k = lopas[-1] + 1
                valtozatok.append(lepesek[:k] + [Lepes("KIADUZ")] + lepesek[k:])
            valtozatok.append(lepesek)
        for v in valtozatok:
            if tuple(v) not in lat:
                lat.add(tuple(v))
                tervek.append(Terv(tuple(v)))

    def vege(kihagy: set[str]) -> list[Lepes]:
        return [l for sz in SZINEK if sz in alap and sz not in kihagy for l in alap[sz]]

    hozzaad(vege(set()))
    for n in range(1, max_elter + 1):
        for kombo in itertools.permutations(elter, n):
            szinek = [sz for sz, _ in kombo]
            if len(set(szinek)) < n:
                continue
            lepesek = [l for _, t in kombo for l in t]
            hozzaad(lepesek + vege(set(szinek)))
    return tervek[:max_db]
