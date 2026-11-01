"""
A felvevő tervezője (2026-10-31, Felvevő tervjáték) — a sémákból.

    helyzetelemzés → stratégiák → technikák példányai a lapokon → kombinációk a
    stratégia szabályai szerint → értékelés (pontos valószínűség, kockázattal)
    → választás → a következő technika

Az adatok: `rendszerek/tervek/sema/*.yaml` (technikák, stratégiák, általános
szabályok). Ez a modul a sémák általános értelmezője: a technika köreit
(kotta) lejátssza minden elosztás-osztályon, és közben alkalmazza az általános
szabályokat (ELLOPÁS, KIADUZÁS, ÁTMENET). A döntés a terv ágain (folytatás vagy
váltás a következő technikára) a megfigyelésen múlik: ugyanazon megfigyelés
mellett ugyanaz a döntés (információs halmaz), és a tervező a jobbikat
választja.

Egyszerűsítések (dokumentálva, hogy a mérés tudja, mit mér):
  - a védők lapjai közül csak a hossz és a releváns figurák helye számít;
  - a védő akkor lop, ha színhiányos és van adója (az addig lehúzott adukörök
    után); felüllopni a mi kezünk csak akkor tudja, ha minden kint lévő adunál
    nagyobb adója van;
  - a kiaduzás egy kőre a kiaduzó kéz legnagyobb aduja; a kiaduzás után a
    védőknél maradt adu: max(0, hossz − körök);
  - egy elvesztett ütés után (ha a tartalék engedi) ugyanonnan folytatjuk.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace

from ..domain import SZINEK, Lap, kovetkezo_ules
from .tervsema import (Allas, Kor, Peldany, kifejezes, peldanyok, strategiak_betoltese,
                       technikak_betoltese)
from .tervszamolo import Korlat, Osztaly, osztalyok, rejtett_fogalmak


SZK_TAR: dict = {}            # az egyszínű elemző futásai (a lapok és a cél szerint)


def _lemez_tar(kulcs, ertek=None):
    """A többszínű elemző futásai lemezen is (KIBIC_SZK_TAR=könyvtár), mert egy futás
    percekig tart."""
    import os
    import pickle
    import hashlib
    kvt = os.environ.get("KIBIC_SZK_TAR")
    if not kvt:
        return None
    os.makedirs(kvt, exist_ok=True)
    def kanon(x):
        if isinstance(x, (frozenset, set)):
            return ("halmaz", tuple(sorted(kanon(e) for e in x)))
        if isinstance(x, tuple):
            return tuple(kanon(e) for e in x)
        return x
    ut = os.path.join(kvt, hashlib.sha1(repr(kanon(kulcs)).encode()).hexdigest() + ".pkl")
    if ertek is None:
        if os.path.exists(ut):
            with open(ut, "rb") as f:
                return pickle.load(f)
        return None
    with open(ut, "wb") as f:
        pickle.dump(ertek, f)
    return ertek


# --- 1. Helyzetelemzés ---------------------------------------------------------------

@dataclass
class Helyzet:
    allas: Allas
    biztos: dict[str, int]
    hiany: int
    tartalek: int

    def szoveg(self) -> str:
        b = ", ".join(f"{'♠♥♦♣'['SHDC'.index(s)]} {n}" for s, n in self.biztos.items() if n)
        return (f"cél {self.allas.cel} a hátralévő {self.allas.hatra}-ból; biztos {sum(self.biztos.values())} "
                f"({b}); hiány {self.hiany}; tartalék {self.tartalek}")


def helyzetelemzes(allas: Allas) -> Helyzet:
    biztos = {sz: allas.biztos_utesek(sz) for sz in SZINEK}
    return Helyzet(allas, biztos, max(0, allas.cel - sum(biztos.values())),
                   allas.hatra - allas.cel)


# --- 2. Terv és jelöltek -----------------------------------------------------------------

@dataclass
class Terv:
    strategia: str
    lepesek: list[Peldany]
    kiaduzas: int                      # ennyi adukör a technikák előtt

    @property
    def nev(self) -> str:
        return " → ".join(p.rovid for p in self.lepesek)


def jeloltek(helyzet: Helyzet, pld: list[Peldany], strategiak: dict) -> list[tuple[str, list[Peldany]]]:
    """A stratégiák technikasorai (a kombinálás szabályai szerint)."""
    ki = []
    for nev, s in strategiak.items():
        kor = {"hiany": helyzet.hiany, "tartalek": helyzet.tartalek}
        if not all(kifejezes(f, kor) for f in s.get("alkalmazhato", [])):
            continue
        tk = s.get("technikak", {})
        for n in range(int(tk.get("min", 1)), int(tk.get("max", 1)) + 1):
            for sor in itertools.permutations(pld, n):
                if len({(p.sema.azon.split("_FELSO")[0], p.szin) for p in sor}) < n:
                    continue
                if not _kombinalhato(sor, s, helyzet):
                    continue
                ki.append((nev, list(sor)))
    return ki


def _kombinalhato(sor, s: dict, helyzet: Helyzet) -> bool:
    szabalyok = s.get("kombinalas", [])
    if "elozok_probak" in szabalyok:
        kif = (s.get("minosites") or {}).get("proba", "kudarc_koltseg <= tartalek")
        for p in sor[:-1]:
            if not kifejezes(kif, {"kudarc_koltseg": p.sema.kudarc_koltseg,
                                   "tartalek": helyzet.tartalek}):
                return False
    if "nincs_elfogyasztas" in szabalyok:
        for i, p in enumerate(sor):
            for q in sor[i + 1:]:
                if p.elfogyaszt & q.hasznal:
                    return False
    return True


# --- 3. Az értékelő: a kotta lejátszása az osztályokon -----------------------------------

@dataclass(frozen=True)
class Allapot:
    """A determinisztikus rész (a mi lapjaink, a körök, ki van hívásban)."""
    kezek: tuple                 # ((kéz, frozenset lapok), …)
    korok: tuple                 # ((szín, körök száma), …)
    soron: str
    kiaduzva: bool = False       # a kiaduzás végig megy (amíg a védőknél adu van)

    def kez(self, k: str) -> frozenset:
        return dict(self.kezek)[k]

    def kor(self, sz: str) -> int:
        return dict(self.korok).get(sz, 0)


@dataclass
class Eset:
    o: Osztaly
    w: float
    tartalek: int
    hiany: int
    megfigyelt: tuple = ()        # az elemzős technikák látott kimenetei (a döntésekhez)


class Ertekelo:
    def __init__(self, helyzet: Helyzet, terv: Terv, kockazat: bool = True,
                 naplo: list | None = None, gyujto: bool = False, becsles: bool = False):
        self.h = helyzet
        # gyujto: a hiányzó elemzést nem számolja, hanem jelzi (HianyzoElemzes) — a
        # tervező a hiányzókat egyszerre, párhuzamosan számolja
        self.gyujto = gyujto
        # becsles: az egyszínű elemzés korlátlan átmenettel, mindegy, ki hív (olcsó,
        # általában optimista) — a drága tervek rangsorához
        self.becsles = becsles
        self.a = helyzet.allas
        self.terv = terv
        self.kockazat = kockazat
        self.naplo = naplo
        self._siker: dict = {}
        kint_adu = self.a.kint_szin(self.a.adu) if self.a.adu else []
        self.kint_adu_max = kint_adu[0].rang if kint_adu else 0
        self.kint_adu_db = len(kint_adu)
        self.vedok = self.a.vedok
        self._szk_cache: dict = {}
        self.politika: dict = {}              # (technika, kör, állapot, megfigyelés) → tovabb / valt
        self.politika_rogzitett: dict | None = None
        self.ut: list | None = None           # egyetlen eset útja (a végrehajtás-ellenőrzéshez)

    # -- a rejtett feltétel (csak itt, a számolásban) --
    def siker(self, p: Peldany, o: Osztaly) -> bool:
        kulcs = (id(p), o.azon)
        if kulcs not in self._siker:
            env = dict(rejtett_fogalmak(o))
            env.update(p.siker_kornyezet())
            self._siker[kulcs] = bool(kifejezes(p.sema.siker, env))
        return self._siker[kulcs]

    def adu_maradek(self, o: Osztaly, k: str, st: Allapot) -> int:
        if not self.a.adu:
            return 0
        t = o.kezhossz(k, self.a.adu)
        if st.kiaduzva:
            # végig kiaduzva: csak akkor marad adu, ha több van nála, mint a biztos aduütésünk
            return max(0, t - self.h.biztos.get(self.a.adu, 0))
        return max(0, t - st.kor(self.a.adu))

    # -- a lapjaink --
    def _foglalt(self, ti: int, ri: int) -> set[Lap]:
        f = set()
        for j, p in enumerate(self.terv.lepesek):
            if j > ti:
                f |= p.hasznal
            elif j == ti:
                for k in p.korok[ri:]:
                    if k.lap is not None:
                        f.add(k.lap)
        return f

    def _kicsi(self, st: Allapot, k: str, sz: str, foglalt: set[Lap]) -> Lap | None:
        lapok = sorted((l for l in st.kez(k) if l.szin == sz), key=lambda l: l.rang)
        szabad = [l for l in lapok if l not in foglalt]
        return (szabad or lapok or [None])[0]

    def _dobas(self, st: Allapot, k: str, foglalt: set[Lap]) -> Lap:
        lapok = list(st.kez(k))
        if not lapok:          # a modell állapotában elfogyott a kéz: a kör nem játszható
            return None
        szabad = [l for l in lapok if l not in foglalt and l.szin != self.a.adu]
        jelolt = szabad or [l for l in lapok if l not in foglalt] or lapok
        hossz = {sz: sum(1 for l in jelolt if l.szin == sz) for sz in SZINEK}
        return min(jelolt, key=lambda l: (l.szin == self.a.adu, -hossz[l.szin], l.rang))

    def _tesz(self, st: Allapot, lapok: dict[str, Lap], szin: str, nyero: str) -> Allapot:
        kezek = tuple((k, frozenset(v - {lapok[k]}) if k in lapok else v) for k, v in st.kezek)
        korok = dict(st.korok)
        korok[szin] = korok.get(szin, 0) + 1
        return Allapot(kezek, tuple(sorted(korok.items())), nyero, st.kiaduzva)

    def _kovet(self, st: Allapot, k: str, sz: str, foglalt: set[Lap], lop: bool = False) -> Lap:
        van = [l for l in st.kez(k) if l.szin == sz]
        if van:
            return self._kicsi(st, k, sz, foglalt)
        if lop and self.a.adu:
            adu = sorted((l for l in st.kez(k) if l.szin == self.a.adu), key=lambda l: l.rang)
            if adu:
                fole = [l for l in adu if l.rang > self.kint_adu_max]
                return (fole or adu)[0]
        return self._dobas(st, k, foglalt)

    # -- egy kör a védők szemszögéből: ellopják-e? --
    def _ellopjak(self, e: Eset, st: Allapot, sz: str, hivo: str, lapok: dict[str, Lap],
                  lopo: str | None) -> bool:
        """ELLOPÁS: a kört ellopja-e egy védő (és nem tudjuk felüllopni)?"""
        if not self.kockazat or not self.a.adu or sz == self.a.adu:
            return False
        r = st.kor(sz) + 1
        sorrend = [kovetkezo_ules(hivo, i) for i in range(4)]
        for i, x in enumerate(sorrend):
            if x not in self.vedok:
                continue
            if e.o.kezhossz(x, sz) >= r or self.adu_maradek(e.o, x, st) <= 0:
                continue
            if lopo is not None:
                l = lapok.get(lopo)
                if l is not None and l.szin == self.a.adu and l.rang > self.kint_adu_max:
                    continue                    # a lopásunk elég magas: sem előtte, sem utána nem üt
                return True
            utana = sorrend[i + 1:]
            ment = any(m not in self.vedok and lapok.get(m) is not None
                       and lapok[m].szin == self.a.adu and lapok[m].rang > self.kint_adu_max
                       for m in utana)
            if not ment:
                return True
        return False

    # -- a kiaduzás és az átmenet --
    def kiaduzas(self, st: Allapot, korok: int | str) -> Allapot:
        """Adukörök a technikák előtt: a hosszabb adus kéz a legnagyobb aduját hívja,
        a partnere a legkisebbet teszi (vagy dob). „mind”: amíg a védőknél adu van —
        a lapjaink fogyását a legvalószínűbb körszámmal (a kint lévő aduk fele,
        felfelé kerekítve) vesszük; a védőknél maradó adu ilyenkor 0 (ha a biztos
        aduütésünk elég)."""
        if not self.a.adu:
            return st
        mind = korok == "mind"
        n = -(-self.kint_adu_db // 2) if mind else min(int(korok), self.kint_adu_db)
        adu = self.a.adu
        for _ in range(n):
            T = max(dict(st.kezek), key=lambda k: sum(1 for l in st.kez(k) if l.szin == adu))
            P = kovetkezo_ules(T, 2)
            t_adu = sorted((l for l in st.kez(T) if l.szin == adu), key=lambda l: l.rang)
            p_adu = sorted((l for l in st.kez(P) if l.szin == adu), key=lambda l: l.rang)
            if not t_adu:
                break
            hivo = st.soron
            if mind and hivo == T and p_adu and p_adu[-1].rang > self.kint_adu_max \
                    and t_adu[0].rang < self.kint_adu_max:
                # deblokkolás: a rövid kéz nagy aduja előbb (kicsit alá)
                lapok, nyero = {T: t_adu[0], P: p_adu[-1]}, P
            elif hivo == P and p_adu:
                lapok, nyero = {P: p_adu[0], T: t_adu[-1]}, T     # vissza a hosszú kézbe
            elif hivo == T:
                lapok, nyero = {T: t_adu[-1], P: self._kovet(st, P, adu, self._foglalt(-1, 0))}, T
            else:
                break
            if self.ut is not None:
                self.ut.append(("adu", hivo, dict(lapok)))
            st = self._tesz(st, lapok, adu, nyero)
        if mind:
            if self.ut is not None:
                self.ut.append(("adu_vegig", hivo if n else None))
            st = replace(st, kiaduzva=True)
        return st

    def _atmenet(self, st: Allapot, cel: str, foglalt: set[Lap]) -> tuple | None:
        """Átmenet a `cel` kézbe: (szín, a hívó lapja, a cél lapja) vagy None."""
        jelolt = []
        for sz in SZINEK:
            kint = self.a.kint_szin(sz)
            kint_max = kint[0].rang if kint else 0
            hivo_lapok = sorted((l for l in st.kez(st.soron) if l.szin == sz), key=lambda l: l.rang)
            if not hivo_lapok:
                continue
            for c in sorted((l for l in st.kez(cel) if l.szin == sz), key=lambda l: l.rang):
                if c in foglalt or c.rang < kint_max or c.rang < hivo_lapok[0].rang:
                    continue
                jelolt.append(((sz == self.a.adu, c.rang), sz, hivo_lapok[0], c))
                break
        if not jelolt:
            return None
        _, sz, h, c = min(jelolt, key=lambda x: x[0])
        return sz, h, c

    def _alairas(self, e: Eset, st: Allapot) -> tuple:
        """A megfigyelés: színenként a védők látott hossza (min(hossz, körök)),
        a releváns figurák közül a már leesettek helye, és a tartalék."""
        ki = []
        for sz, r in st.korok:
            if r <= 0:
                continue
            ki.append((sz,) + tuple(min(e.o.kezhossz(v, sz), r) for v in self.vedok))
        les = tuple(sorted((str(l), k) for l, k in e.o.birtokos.items()
                           if e.o.kezhossz(k, l.szin) <= st.kor(l.szin)))
        return tuple(ki), les, e.tartalek, e.megfigyelt

    # -- a rekurzió --
    def futtat(self, esetek: list[Eset], ti: int, ri: int, st: Allapot) -> float:
        if not esetek:
            return 0.0
        lepesek = self.terv.lepesek
        if ti >= len(lepesek):
            if self.ut is not None:
                self.ut.append(("kudarc",))
            return 0.0
        p = lepesek[ti]
        if p.sema.fajta == "elemzo":
            return self._elemzos(esetek, ti, st)
        if ri >= len(p.korok):
            ok, tovabb = 0.0, []
            for e in esetek:
                if self.siker(p, e.o):
                    h = e.hiany - p.sema.hozam
                    if h <= 0 and not self._lezaras(e, st):
                        if self.ut is not None:
                            self.ut.append(("kudarc",))
                        continue                  # a maradék begyűjtése közben ellopnak
                    if h <= 0:
                        ok += e.w
                        if self.ut is not None:
                            self.ut.append(("siker", p.rovid))
                        continue
                    tovabb.append(replace(e, hiany=h))
                else:
                    tovabb.append(e)
            return ok + self.futtat(tovabb, ti + 1, 0, st)
        kor = p.korok[ri]
        extra = 0.0
        if kor.csak_ha_siker:
            nem = [e for e in esetek if not self.siker(p, e.o)]
            esetek = [e for e in esetek if self.siker(p, e.o)]
            extra = self.futtat(nem, ti + 1, 0, st)
            if not esetek:
                return extra
        if all(k.begyujtes for k in p.korok[ri:]):
            h = self._halaszt(st, ti, ri)
            if h is not None:                 # BEGYUJTES: a kiaduzás utánra
                st_h, kapacitas = h
                # csak ott, ahol a kiaduzó kéz aduja elég a védőknél maradt adukhoz
                jo = [e for e in esetek if max(self.adu_maradek(e.o, x, st) for x in self.vedok) <= kapacitas]
                rossz = [e for e in esetek if e not in jo]
                if self.naplo is not None:
                    self.naplo.append(f"begyűjtés halasztva ({p.rovid})")
                if self.ut is not None and jo:
                    self.ut.append(("halaszt",))
                ertek = self.futtat(jo, ti, len(p.korok), st_h)
                if not rossz:
                    return extra + ertek
                extra += ertek
                esetek = rossz
        van_kovetkezo = ti + 1 < len(lepesek)
        elo = self._elokeszit(esetek, ti, ri, st)
        if elo is None:                       # a kör nem játszható (nincs átmenet)
            return extra + (self.futtat(esetek, ti + 1, 0, st) if van_kovetkezo else 0.0)
        esetek, st, hivo, nyero = elo
        if (ri > 0 or kor.csak_ha_siker) and van_kovetkezo:
            # E5: megfigyelésenként folytatás vagy váltás a következő technikára
            csoport: dict = {}
            for e in esetek:
                csoport.setdefault(self._alairas(e, st), []).append(e)
            ossz = 0.0
            for alairas, cs in csoport.items():
                kulcs = (ti, ri, st, alairas)
                if self.politika_rogzitett is not None:
                    d = self.politika_rogzitett.get(kulcs, "tovabb")
                    ossz += (self.kor(cs, ti, ri, st, hivo, nyero) if d == "tovabb"
                             else self.futtat(cs, ti + 1, 0, st))
                    continue
                tovabb = self.kor(cs, ti, ri, st, hivo, nyero)
                valt = self.futtat(cs, ti + 1, 0, st)
                self.politika[kulcs] = "valt" if valt > tovabb else "tovabb"
                ossz += max(tovabb, valt)
            return extra + ossz
        return extra + self.kor(esetek, ti, ri, st, hivo, nyero)

    # -- az elemzős technika (SZINKEZELES): az egyszínű elemző kezelése --
    def _elemzes(self, e, regi_kulcs=None):
        """Az elemzés a tárból; ha nincs: gyűjtő módban jelzi, különben kiszámolja."""
        from . import tervparhuzam as tp
        ertek = tp.tarbol(e.kulcs)
        if ertek is None and regi_kulcs is not None:
            ertek = _lemez_tar(regi_kulcs)          # a 2026-10-31-i tár kulcsa
            if ertek is not None:
                tp.tarba(e.kulcs, ertek)
        if ertek is None:
            if self.gyujto:
                raise tp.HianyzoElemzes(e)
            ertek = tp.tarba(e.kulcs, tp.kiszamol(e))
        return ertek

    def _szk_futas(self, p: Peldany, st: Allapot):
        """Az elemző a mostani lapjainkkal, átmenetekkel és hívással (a tárból)."""
        if p.szerepek.get("aduval"):
            return self._szk_futas_aduval(p, st)
        from .tervszinkezeles import Feladat
        from .tervparhuzam import Elemzes
        sz = p.szin
        X, Y = self.a.felvevo, self.a.asztal
        rang = lambda ls: frozenset(l.rang for l in ls)
        xr = rang(l for l in st.kez(X) if l.szin == sz)
        yr = rang(l for l in st.kez(Y) if l.szin == sz)
        kint = rang(l for l in self.a.kint if l.szin == sz)
        if self.becsles:
            bx = by = hivas = None
        else:
            foglalt = self._foglalt(self.terv.lepesek.index(p), 0) - p.hasznal
            bx = self._atmenetek(st, X, sz, foglalt)
            by = self._atmenetek(st, Y, sz, foglalt)
            hivas = "X" if st.soron == X else "Y"
        f = Feladat(xr, yr, kint, self.a.hatra, self.a.hatra,
                    p.szerepek.get("lop_x", 0), p.szerepek.get("lop_y", 0), bx, by,
                    hivas, sz == self.a.adu)
        return self._elemzes(Elemzes("egy", f, p.szerepek["k"], p.szerepek["m"]))

    def _szk_futas_aduval(self, p: Peldany, st: Allapot):
        """Az adu és a mellékszín együtt (többszínű elemző): az adu körei átmenetek,
        a lopások és a védők lopásai a játék részei."""
        from . import tervtobbszin as tt
        from .tervparhuzam import Elemzes
        sz, adu = p.szin, self.a.adu
        szinek = tuple(sorted({"SHDC".index(adu), "SHDC".index(sz)}))
        X, Y = self.a.felvevo, self.a.asztal
        kodok = lambda ls: frozenset(tt.kod("SHDC".index(l.szin), l.rang) for l in ls)
        xk = kodok(l for l in st.kez(X) if l.szin in (sz, adu))
        yk = kodok(l for l in st.kez(Y) if l.szin in (sz, adu))
        kint = kodok(l for l in self.a.kint if l.szin in (sz, adu))
        foglalt = self._foglalt(self.terv.lepesek.index(p), 0) - p.hasznal
        bx = self._atmenetek(st, X, (sz, adu), foglalt)
        by = self._atmenetek(st, Y, (sz, adu), foglalt)
        hivas = "X" if st.soron == X else "Y"
        f = tt.Feladat(xk, yk, kint, szinek, "SHDC".index(adu), self.a.hatra, self.a.hatra,
                       bx, by, hivas)
        regi = ("aduval", sz, xk, yk, kint, p.szerepek["k"], p.szerepek["m"], bx, by, hivas)
        return self._elemzes(Elemzes("tobb", f, p.szerepek["k"], p.szerepek["m"]), regi)

    def _atmenetek(self, st: Allapot, kez: str, sz, foglalt: set) -> int:
        """Átmenetek a kézbe más színben: a nyerő lapjai (a kint lévő legnagyobbnál
        nagyobb), amelyek alá a partner hívni tud; a terv más lapjai nem."""
        p = kovetkezo_ules(kez, 2)
        db = 0
        kihagy = set(sz) if isinstance(sz, tuple) else {sz}
        for l in st.kez(kez):
            if l.szin in kihagy or l in foglalt:
                continue
            kint = self.a.kint_szin(l.szin)
            if kint and l.rang < kint[0].rang:
                continue
            if any(x.szin == l.szin and x.rang < l.rang for x in st.kez(p)):
                db += 1
        return db

    def _szk_eloszlas(self, p: Peldany, o: Osztaly, tart, kim) -> dict:
        """Az osztályra: (hozam, költség, lopás, átm. X, átm. Y) → arány. Az
        osztályon belül a szín tartásai egyformán valószínűek (rögzített hossz)."""
        kulcs = (id(kim), o.azon)
        if kulcs in self._szk_cache:
            return self._szk_cache[kulcs]
        sz = p.szin
        v1 = self.vedok[0]
        db: dict = {}
        n = 0
        if p.szerepek.get("aduval"):
            from . import tervtobbszin as tt
            adu = self.a.adu
            ia, isz = "SHDC".index(adu), "SHDC".index(sz)
            h_adu, h_sz = o.kezhossz(v1, adu), o.kezhossz(v1, sz)
            biztos = self.h.biztos.get(sz, 0) + self.h.biztos.get(adu, 0)
            for i, (t1, t2, w) in enumerate(tart):
                if sum(1 for c in t1 if tt.szine(c) == ia) != h_adu or \
                        sum(1 for c in t1 if tt.szine(c) == isz) != h_sz:
                    continue
                km = kim[i]
                kul = (max(0, km.utes - biztos), km.vesztes, 0, km.atm_x, km.atm_y)
                # az összevont tartás súlya (a szabad helyek része az osztályon belül állandó)
                ww = w
                db[kul] = db.get(kul, 0) + ww
                n += ww
            ki = {k: v / n for k, v in db.items()} if n else {}
            self._szk_cache[kulcs] = ki
            return ki
        hossz = o.kezhossz(v1, sz)
        rel = {l.rang: o.birtokos[l] for l in o.birtokos if l.szin == sz}
        biztos = self.h.biztos.get(sz, 0)
        for i, (t1, t2, _) in enumerate(tart):
            if len(t1) != hossz:
                continue
            if any((r in t1) != (k == v1) for r, k in rel.items()):
                continue
            km = kim[i]
            kul = (max(0, km.utes - biztos), km.vesztes, km.lopas, km.atm_x, km.atm_y)
            db[kul] = db.get(kul, 0) + 1
            n += 1
        ki = {k: v / n for k, v in db.items()} if n else {}
        self._szk_cache[kulcs] = ki
        return ki

    def _elemzos(self, esetek: list[Eset], ti: int, st: Allapot) -> float:
        p = self.terv.lepesek[ti]
        tart, kim = self._szk_futas(p, st)
        sz = p.szin
        # az állapot utána: a szín lapjaink elfogynak; a lopások és az átmenetek
        # (a legrosszabb tartás szerint) a legkisebb adut / a legolcsóbb nyerőt viszik
        kezek = {k: set(v) for k, v in st.kezek}
        max_lop = max((getattr(k, "lopas", 0) for k in kim.values()), default=0)
        max_ax = max((k.atm_x for k in kim.values()), default=0)
        max_ay = max((k.atm_y for k in kim.values()), default=0)
        aduval = bool(p.szerepek.get("aduval"))
        kivett = {sz, self.a.adu} if aduval else {sz}
        for k in kezek:
            kezek[k] = {l for l in kezek[k] if l.szin not in kivett}
        if max_lop and self.a.adu and not aduval:
            lopo = self.a.felvevo if p.szerepek.get("lop_x") else self.a.asztal
            adu = sorted((l for l in kezek[lopo] if l.szin == self.a.adu), key=lambda l: l.rang)
            kezek[lopo] -= set(adu[:max_lop])
        foglalt = self._foglalt(ti, 0) - p.hasznal
        for kez, db in ((self.a.felvevo, max_ax), (self.a.asztal, max_ay)):
            jelolt = sorted((l for l in kezek[kez] if l.szin not in kivett and l not in foglalt),
                            key=lambda l: (l.szin == self.a.adu, l.rang))
            nyerok = [l for l in jelolt if not self.a.kint_szin(l.szin)
                      or l.rang > self.a.kint_szin(l.szin)[0].rang]
            kezek[kez] -= set(nyerok[:db])
        korok = dict(st.korok)
        korok[sz] = korok.get(sz, 0) + max((k.utes + k.vesztes + getattr(k, "lopas", 0) for k in kim.values()), default=0)
        st2 = Allapot(tuple(sorted((k, frozenset(v)) for k, v in kezek.items())),
                      tuple(sorted(korok.items())), self.a.felvevo,
                      st.kiaduzva or sz == self.a.adu or aduval)
        ok, tovabb = 0.0, []
        for e in esetek:
            for (hozam, koltseg, lop, ax, ay), arany in self._szk_eloszlas(p, e.o, tart, kim).items():
                # ELLOPÁS a mellékszín köreire, amíg a védőknél adu van (durva közelítés:
                # ha egy védő a kör előtt színhiányos és van adója, a hozam elvész)
                if self.kockazat and self.a.adu and sz != self.a.adu and not st.kiaduzva and not aduval:
                    korszam = hozam + self.h.biztos.get(sz, 0) + koltseg + lop
                    if any(e.o.kezhossz(x, sz) < korszam and self.adu_maradek(e.o, x, st) > 0
                           for x in self.vedok):
                        hozam, koltseg = 0, koltseg + 1
                if koltseg > e.tartalek:
                    if self.ut is not None:
                        self.ut.append(("kudarc",))
                    continue
                uj = Eset(e.o, e.w * arany, e.tartalek - koltseg, e.hiany - hozam,
                          e.megfigyelt + ((ti, hozam, koltseg),))
                if uj.hiany <= 0:
                    if self._lezaras(uj, st2):
                        ok += uj.w
                        if self.ut is not None:
                            self.ut.append(("siker", p.rovid))
                    continue
                tovabb.append(uj)
        if self.naplo is not None:
            self.naplo.append(f"színkezelés {p.rovid}")
        return ok + self.futtat(tovabb, ti + 1, 0, st2)

    def _lezaras(self, e: Eset, st: Allapot) -> bool:
        """A cél megvan; a maradék (biztos ütések) begyűjthető-e úgy, hogy a védők
        maradék aduját előbb lehúzzuk? A kiaduzó kézbe vissza kell jutni: ha hívásban
        van, vagy lopással jut be, rendben; ha csak egy nyerő színnel, arra az
        ELLOPÁS vonatkozik. Végül a kiaduzó kéz nagy adói elegendők-e."""
        adu = self.a.adu
        if not adu or st.kiaduzva or not self.kockazat:
            return True
        marad = max(self.adu_maradek(e.o, x, st) for x in self.vedok)
        if marad <= 0:
            return True
        T = max(dict(st.kezek), key=lambda k: sum(1 for l in st.kez(k) if l.szin == adu))
        magas = sum(1 for l in st.kez(T) if l.szin == adu and l.rang > self.kint_adu_max)
        if st.soron == T:
            return magas >= marad
        if any(sz != adu and any(l.szin == sz for l in st.kez(st.soron))
               and not any(l.szin == sz for l in st.kez(T)) for sz in SZINEK):
            return magas - 1 >= marad              # lopással jut be (magasan)
        for sz in SZINEK:
            if sz == adu or not any(l.szin == sz for l in st.kez(st.soron)):
                continue
            kint = self.a.kint_szin(sz)
            if not any(l.szin == sz and (not kint or l.rang > kint[0].rang) for l in st.kez(T)):
                continue
            r = st.kor(sz) + 1
            if all(e.o.kezhossz(x, sz) >= r or self.adu_maradek(e.o, x, st) <= 0 for x in self.vedok):
                return magas >= marad
        return False

    def _halaszt(self, st: Allapot, ti: int, ri: int) -> tuple[Allapot, int] | None:
        """BEGYUJTES: a technika hátralévő (begyűjtő) köreit a kiaduzás utánra
        halaszthatjuk-e? Vissza: az állapot a kiaduzás után (a begyűjtés ezután
        kockázat nélkül) és a kiaduzó kéz adóinak száma (ennyi kört bír), vagy None
        (most kell játszani, a kockázatával)."""
        p = self.terv.lepesek[ti]
        adu = self.a.adu
        foglalt = self._foglalt(ti, ri)
        kapacitas = 99
        if adu and not st.kiaduzva:
            T = max(dict(st.kezek), key=lambda k: sum(1 for l in st.kez(k) if l.szin == adu))
            if not any(l.szin == adu for l in st.kez(T)):
                return None
            if st.soron != T:
                # átmenet a kiaduzó kézbe lopással: a hívó kéz színéből T színhiányos
                lopas = next((sz for sz in SZINEK if sz != adu
                              and any(l.szin == sz for l in st.kez(st.soron))
                              and not any(l.szin == sz for l in st.kez(T))), None)
                if lopas is None:
                    return None
                adui = sorted((l for l in st.kez(T) if l.szin == adu), key=lambda l: l.rang)
                magas = [l for l in adui if l.rang > self.kint_adu_max]
                lapok = {st.soron: self._kicsi(st, st.soron, lopas, foglalt),
                         T: (magas or adui)[0]}          # magasan lop, hogy ne lophassák felül
                st = self._tesz(st, lapok, lopas, T)
            # ennyi adukört bír: a kiaduzó kéz minden kint lévőnél nagyobb adói
            kapacitas = sum(1 for l in st.kez(T) if l.szin == adu and l.rang > self.kint_adu_max)
            # a hátralévő adukörök (a lapjaink fogyása: a legvalószínűbb körszámig)
            for _ in range(max(0, -(-self.kint_adu_db // 2) - st.kor(adu))):
                sajat = sorted((l for l in st.kez(T) if l.szin == adu), key=lambda l: -l.rang)
                if not sajat:
                    return None
                pt = kovetkezo_ules(T, 2)
                st = self._tesz(st, {T: sajat[0], pt: self._kovet(st, pt, adu, foglalt)}, adu, T)
            st = replace(st, kiaduzva=True)
        # a begyűjtő lapok keze elérhető-e?
        for k in p.korok[ri:]:
            if k.lap is None:
                continue
            X = self.a.keze(k.lap)
            if X == st.soron or any(l.szin == k.lap.szin for l in st.kez(st.soron)):
                continue
            if self._atmenet(st, X, foglalt - {k.lap}) is None:
                return None
        return st, kapacitas

    def _elokeszit(self, esetek: list[Eset], ti: int, ri: int, st: Allapot):
        """Ki hívja a kört, ki üt; ha a hívó kéz nincs hívásban: átmenet (ELLOPÁS-sal).
        Vissza: (esetek, állapot, hívó, nyerő) vagy None."""
        p = self.terv.lepesek[ti]
        k: Kor = p.korok[ri]
        sz = k.szin
        foglalt = self._foglalt(ti, ri)
        if k.fajta == "lehiv":
            gazda = self.a.keze(k.lap) if k.lap is not None else None
            if gazda is None or k.lap not in st.kez(gazda):
                return None
            if st.soron == gazda or any(l.szin == sz for l in st.kez(st.soron)):
                hivo = st.soron
            else:
                hivo = gazda
            nyero = gazda
        elif k.fajta == "impassz":
            hivo, nyero = k.hivo, self.a.keze(k.lap)
        elif k.fajta == "lop":
            hivo, nyero = k.hivo, k.lopo
        else:
            return None
        if st.soron != hivo:
            atm = self._atmenet(st, hivo, foglalt)
            if atm is None:
                return None
            asz, hl, cl = atm
            lapok = {st.soron: hl, hivo: cl}
            tovabb = []
            for e in esetek:
                if self._ellopjak(e, st, asz, st.soron, lapok, None):
                    if e.tartalek <= 0:
                        continue
                    e = replace(e, tartalek=e.tartalek - 1)
                tovabb.append(e)
            if self.ut is not None:
                self.ut.append(("kor", st.soron, dict(lapok)))
            st = self._tesz(st, lapok, asz, hivo)
            esetek = tovabb
            if self.naplo is not None:
                self.naplo.append(f"átmenet: {hl}→{cl}")
        return esetek, st, hivo, nyero

    def kor(self, esetek: list[Eset], ti: int, ri: int, st: Allapot, hivo: str, nyero: str) -> float:
        p = self.terv.lepesek[ti]
        k: Kor = p.korok[ri]
        sz = k.szin
        foglalt = self._foglalt(ti, ri)
        # a kör lapjai
        partner = kovetkezo_ules(hivo, 2)
        if k.fajta == "lehiv":
            if hivo == nyero:
                lapok = {hivo: k.lap, partner: self._kovet(st, partner, sz, foglalt - {k.lap})}
            else:
                lapok = {hivo: self._kicsi(st, hivo, sz, foglalt), nyero: k.lap}
        elif k.fajta == "impassz":
            if hivo == nyero:                     # átengedés: a sorozat lapját hívjuk
                lapok = {hivo: k.lap, partner: self._kovet(st, partner, sz, foglalt)}
            else:                                 # villa felé: kicsi, a villa alsó lapja
                lapok = {hivo: self._kicsi(st, hivo, sz, foglalt), nyero: k.lap}
        else:                                     # lop
            lapok = {hivo: self._kicsi(st, hivo, sz, foglalt),
                     k.lopo: self._kovet(st, k.lopo, sz, foglalt, lop=True)}
        if any(v is None for v in lapok.values()):
            return 0.0
        tovabb = []
        for e in esetek:
            vesztett = 0
            if self._ellopjak(e, st, sz, hivo, lapok, k.lopo if k.fajta == "lop" else None):
                vesztett = 1
            elif k.fajta == "impassz" and not self.siker(p, e.o):
                vesztett = p.sema.kudarc_koltseg
            if vesztett:
                if e.tartalek < vesztett:
                    continue
                e = replace(e, tartalek=e.tartalek - vesztett)
            tovabb.append(e)
        if self.ut is not None:
            self.ut.append(("kor", hivo, dict(lapok)))
            if not tovabb:
                self.ut.append(("kudarc",))
        st2 = self._tesz(st, lapok, sz, nyero)
        if self.naplo is not None:
            self.naplo.append(f"{k.fajta} {sz}: " + " ".join(f"{u}:{l}" for u, l in lapok.items()))
        return self.futtat(tovabb, ti, ri + 1, st2)


def szinkezeles_peldanyok(allas: Allas, helyzet: Helyzet, sema) -> list[Peldany]:
    """A SZINKEZELES (elemzős) technika példányai: színenként a célok (k ütés,
    legfeljebb m vesztés, lopással), amelyeknek van esélye; az azonos kimenetet
    adó célok közül csak az első."""
    from .tervszinkezeles import Feladat
    from . import tervparhuzam as tp
    ki = []
    X, Y = allas.felvevo, allas.asztal
    feladatok = []            # (szín, lop_x, lop_y, elemzés)
    for sz in SZINEK:
        xs = [l for l in allas.kezek[X] if l.szin == sz]
        ys = [l for l in allas.kezek[Y] if l.szin == sz]
        if not xs and not ys:
            continue
        b = helyzet.biztos.get(sz, 0)
        kmax = min(max(len(xs), len(ys)), b + helyzet.hiany)
        if kmax <= b:
            continue
        valt = [(0, 0)]
        if allas.adu and sz != allas.adu:
            for kez, sajat, masik, hely in ((X, xs, ys, 0), (Y, ys, xs, 1)):
                adu = sum(1 for l in allas.kezek[kez] if l.szin == allas.adu)
                if len(sajat) < len(masik) and adu:
                    r = min(adu, len(masik) - len(sajat))
                    valt.append((r, 0) if hely == 0 else (0, r))
        kint = frozenset(l.rang for l in allas.kint if l.szin == sz)
        celok = tuple((k, m) for k in range(b + 1, kmax + 1) for m in range(0, helyzet.tartalek + 1))
        for lx, ly in valt:
            f = Feladat(frozenset(l.rang for l in xs), frozenset(l.rang for l in ys), kint,
                        allas.hatra, allas.hatra, lx, ly, adu=(sz == allas.adu))
            feladatok.append((sz, lx, ly, tp.Elemzes("celok", f, celok=celok)))
    tp.szamol_mind([e for *_, e in feladatok])          # párhuzamosan, a tárba
    latott: dict = {}
    for sz, lx, ly, e in feladatok:
        eredm = tp.tarbol(e.kulcs)
        lapok = {l for kk in (X, Y) for l in allas.kezek[kk] if l.szin == sz}
        for k, m in e.celok:
            p, elo = eredm[(k, m)]
            if p <= 0 or elo in latott.setdefault(sz, set()):
                continue
            latott[sz].add(elo)
            ki.append(Peldany(sema, sz, {"k": k, "m": m, "lop_x": lx, "lop_y": ly},
                              [], lapok, lapok, set()))
    # az adu és egy mellékszín együtt (többszínű elemző): ahol a séma felismerése
    # engedi (a rövidebb kezünk lophat a színben) — itt számít az adu körei mint
    # átmenetek és a lopások ideje
    aduval = (sema.celok or {}).get("aduval")
    if allas.adu and aduval is not None:
        from .tervsema import fogalmak
        fog = fogalmak(allas)
        ba = helyzet.biztos.get(allas.adu, 0)
        for sz in SZINEK:
            if not all(kifejezes(f, dict(fog, SZ=sz)) for f in aduval.get("felismeres", [])):
                continue
            xs = [l for l in allas.kezek[X] if l.szin == sz]
            ys = [l for l in allas.kezek[Y] if l.szin == sz]
            if not (xs or ys):
                continue
            k = ba + helyzet.biztos.get(sz, 0) + helyzet.hiany
            lapok = set(xs) | set(ys) | {l for kk in (X, Y) for l in allas.kezek[kk] if l.szin == allas.adu}
            ki.append(Peldany(sema, sz, {"k": k, "m": helyzet.tartalek, "aduval": True},
                              [], lapok, lapok, set()))
    return ki


# --- 4. A tervező ---------------------------------------------------------------------------

@dataclass
class TervErtek:
    terv: Terv                 # a kockázattal legjobb kiaduzással
    elvi: float                # csak a sikerfeltétel (a legjobb kiaduzással)
    kockazattal: float         # az általános szabályokkal (ELLOPÁS, ÁTMENET, BEGYŰJTÉS)
    elvi_kiaduzas: int = 0
    politika: dict = field(default_factory=dict)   # a megfigyelésen múló döntések
    becsult: bool = False      # csak becslés (a drága lépés pontos elemzése nélkül)


def kezdo_allapot(allas: Allas) -> Allapot:
    return Allapot(tuple(sorted((k, frozenset(v)) for k, v in allas.kezek.items())), (), allas.soron)


def _draga(p: Peldany) -> bool:
    """Drága lépés: a többszínű elemzés (percekig tarthat)."""
    return p.sema.fajta == "elemzo" and bool(p.szerepek.get("aduval"))


def _terv_ertek(helyzet: Helyzet, strat: str, sor: list[Peldany], oszt, W, valasztek,
                gyujto: bool = True, becsles: bool = False) -> TervErtek:
    """Egy technikasor értéke: minden kiaduzás-változat; a terv „szándék szerinti”
    változatai azok, amelyekben az elvi esélye a legnagyobb (pl. a lopásos
    kimagasításhoz meg kell őrizni az átmenetet) — ezek közül a kockázattal
    legjobb a terv értéke."""
    allas = helyzet.allas
    kezdo = kezdo_allapot(allas)
    valtozatok = []
    adu_szk = any(p.sema.fajta == "elemzo" and (p.szin == allas.adu or p.szerepek.get("aduval"))
                  for p in sor)
    for kd in ([0] if adu_szk else valasztek):     # az adu kezelése maga a technika
        n = "mind" if kd == "mind" else int(kd)
        terv = Terv(strat, list(sor), 13 if n == "mind" else n)
        ertekek, pol = [], {}
        for kock in (False, True):
            ert = Ertekelo(helyzet, terv, kockazat=kock, gyujto=gyujto, becsles=becsles)
            st = ert.kiaduzas(kezdo, n)
            esetek = [Eset(o, o.suly, helyzet.tartalek, helyzet.hiany) for o in oszt]
            ertekek.append(ert.futtat(esetek, 0, 0, st) / W)
            pol = ert.politika
        valtozatok.append((terv, *ertekek, pol))
    elvi = max(v[1] for v in valtozatok)
    terv, _, k_, pol = max((v for v in valtozatok if v[1] >= elvi - 1e-9), key=lambda v: v[2])
    return TervErtek(terv, elvi, k_, terv.kiaduzas, pol)


def _helyettesitok(p: Peldany, pld: list[Peldany], adu: str) -> list[list[Peldany]]:
    """A drága lépés (adu + szín együtt) becsléséhez: a két szín külön, az egyszínű
    elemző példányaival (`becsles: kulon_szinek`), mindkét sorrendben."""
    egy = [q for q in pld if q.sema.fajta == "elemzo" and not q.szerepek.get("aduval")]
    t = [q for q in egy if q.szin == adu]
    s = [q for q in egy if q.szin == p.szin]
    ki = [[x] for x in t + s]
    ki += [[a, b] for a in t for b in s] + [[b, a] for a in t for b in s]
    return ki


def tervez(allas: Allas, korlatok: list[Korlat] = (), kiaduzas_valasztek=None,
           feltevesbol: bool = False, teljes: bool = False,
           stat: dict | None = None, draga_pontos: bool = True) -> tuple[Helyzet, list[TervErtek]]:
    """A tervek értékelése három lépcsőben (TERVEZES szabály): felismerés (a sémák
    `felismeres` feltételei), az olcsó tervek pontosan, a drága (többszínű
    elemzést kívánó) tervek becsléssel, és pontosan csak a legjobb jelöltek.
    `teljes`: minden drága tervet pontosan (a lépcsők ellenőrzéséhez);
    `draga_pontos=False`: a drága tervek csak becsléssel (az ütés közbeni
    jelöltek gyors összevetéséhez)."""
    import time
    from . import tervparhuzam as tp
    t0 = time.time()
    stat = stat if stat is not None else {}
    tp.MEMORIA.clear()                 # a fő folyamat csak az aktuális tervezés elemzéseit tartja
    szamolt0 = tp.STATISZTIKA["szamolt"]
    helyzet = helyzetelemzes(allas)
    technikak = technikak_betoltese()
    strategiak, szabalyok = strategiak_betoltese()
    szabaly = lambda nev: next((s for s in szabalyok if s.get("szabaly") == nev), {})
    if kiaduzas_valasztek is None:
        kiaduzas_valasztek = szabaly("KIADUZAS").get("valasztek", ["mind", 0])
    tz = szabaly("TERVEZES")
    pld = peldanyok(allas, technikak)
    if "SZINKEZELES" in technikak:
        pld += szinkezeles_peldanyok(allas, helyzet, technikak["SZINKEZELES"])
    relevans = {l for p in pld for l in p.relevans}
    # a védők kint lévő lapjainak száma: a hátralévő ütések (ütés elején)
    ures = {v: allas.hatra for v in allas.vedok}
    assert len(allas.kint) == 2 * allas.hatra, "a tervező ütés elején dolgozik"
    # SZABAD_HELYEK: a hosszakból következő súlyozás (pl. az impassz esélye) csak
    # ismert (megfigyelt vagy bizonyított) hosszkülönbségből; a feltételezett hossz
    # (a licitből) a szabály engedélyével
    engedett = set(szabaly("SZABAD_HELYEK").get("tudas", ["megfigyelt", "bizonyitott"]))
    if feltevesbol:
        engedett.add("feltetelezett")
    korlatok = [k for k in korlatok if k.tudas in engedett]
    oszt = osztalyok(allas.kint, ures, relevans, list(korlatok))
    W = sum(o.suly for o in oszt)
    jel = jeloltek(helyzet, pld, strategiak)
    olcso = [(st, sor) for st, sor in jel if not any(_draga(p) for p in sor)]
    draga = [(st, sor) for st, sor in jel if any(_draga(p) for p in sor)]
    stat["felismeres_s"] = time.time() - t0

    # 1. az olcsó tervek pontosan (a hiányzó egyszínű elemzések párhuzamosan)
    t1 = time.time()
    ki = tp.ertekel_mind(olcso, lambda x: _terv_ertek(helyzet, *x, oszt, W, kiaduzas_valasztek))
    stat["olcso_s"] = time.time() - t1

    # 2. a drága tervek becslése: a drága lépés helyett a két szín külön
    t2 = time.time()
    memo: dict = {}

    def becsles(x):
        strat, sor = x
        valtozat = [[]]
        for p in sor:
            alt = _helyettesitok(p, pld, allas.adu) if _draga(p) else [[p]]
            valtozat = [v + a for v in valtozat for a in alt] if alt else valtozat
        legjobb = 0.0
        for v in valtozat:
            kulcs = tuple(id(p) for p in v)
            if kulcs not in memo:
                memo[kulcs] = _terv_ertek(helyzet, strat, v, oszt, W, kiaduzas_valasztek,
                                          becsles=True).kockazattal if v else 0.0
            legjobb = max(legjobb, memo[kulcs])
        return legjobb

    becsult = tp.ertekel_mind(draga, becsles)
    stat["becsles_s"] = time.time() - t2

    # 3. pontos számítás a legjobb drága jelöltekre
    t3 = time.time()
    legjobb = max((e.kockazattal for e in ki), default=0.0)
    sorrend = sorted(range(len(draga)), key=lambda i: -becsult[i])
    if teljes:
        valasztott = sorrend
    elif not draga_pontos:
        valasztott = []
    else:
        valasztott = [i for i in sorrend if becsult[i] >= legjobb - float(tz.get("sav", 0.05))]
        valasztott = valasztott[:int(tz.get("pontos", 3))]
    pontos = dict(zip(valasztott, tp.ertekel_mind(
        [draga[i] for i in valasztott],
        lambda x: _terv_ertek(helyzet, *x, oszt, W, kiaduzas_valasztek))))
    legjobb = max([legjobb] + [e.kockazattal for e in pontos.values()])
    if draga_pontos and legjobb < float(tz.get("kiterjesztes_alatt", 0.5)):
        maradek = [i for i in sorrend if i not in pontos]
        pontos.update(zip(maradek, tp.ertekel_mind(
            [draga[i] for i in maradek],
            lambda x: _terv_ertek(helyzet, *x, oszt, W, kiaduzas_valasztek))))
        stat["kiterjesztes"] = True
    stat["pontos_s"] = time.time() - t3
    for i, (strat, sor) in enumerate(draga):
        if i in pontos:
            ki.append(pontos[i])
        else:
            ki.append(TervErtek(Terv(strat, list(sor), 0), becsult[i], becsult[i], becsult=True))
    ki.sort(key=lambda x: (x.becsult, -x.kockazattal, -x.elvi))
    stat.update(tervek=len(jel), olcso=len(olcso), draga=len(draga),
                draga_pontos=len(pontos), elemzes_szamolt=tp.STATISZTIKA["szamolt"] - szamolt0,
                ossz_s=time.time() - t0)
    return helyzet, ki
