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


# --- 1. A terv -----------------------------------------------------------------------

@dataclass
class KTerv:
    """Egységek sora (az esélyek sora): az első próba, a többi akkor jön, ha az
    előző nem sikerült."""
    lepesek: list[Peldany]

    @property
    def nev(self) -> str:
        return " → ".join(p.rovid for p in self.lepesek) or "csak begyűjtés"


@dataclass
class Egyseg:
    p: Peldany
    i: int = 0
    allapot: str = "var"            # var / siker / kudarc / elmarad / kesz

    def kor(self) -> Kor | None:
        return self.p.korok[self.i] if self.i < len(self.p.korok) else None

    @property
    def el(self) -> bool:
        return self.allapot in ("var", "siker")


def tervjeloltek(allas: Allas, technikak: dict, max_db: int = 40) -> list[KTerv]:
    """Az egy- és kételemű esélysorok a technikák példányaiból. Az első elem
    próba (a kudarca nem kerül ütésbe), és nem fogyaszthatja el a második
    lapjait."""
    P = peldanyok(allas, technikak)
    ki = [KTerv([])] + [KTerv([p]) for p in P]
    for a in P:
        if a.sema.kudarc_koltseg:
            continue
        for b in P:
            if a is b or a.elfogyaszt & (b.hasznal | b.elfogyaszt):
                continue
            ki.append(KTerv([a, b]))
    return ki[:max_db]


# --- 2. A végrehajtó ------------------------------------------------------------------

class Vegrehajto:
    """A felvevő oldal politikája egy világon: a terv egységei körökre bontva."""

    def __init__(self, terv: KTerv, j: tj.Jatek, naplo: list | None = None):
        self.egysegek = [Egyseg(p) for p in terv.lepesek]
        self.j = j
        self.adu = j.adu
        self.folyo: tuple | None = None      # (egység, kör, az ütés kezdő indexe)
        self.szandek: dict[str, tuple] = {}  # a partner kéz teendője a mostani ütésben
        self.szandek_utes = -1
        self.naplo = naplo
        self.cel = None                      # az összes kell ütés (a lejátszó adja)
        self.kitekintes = False              # előrenézés (egyszerű védőkkel): még nem segít, lásd a doksit
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
                elif k.fajta == "lop" and k.hivo:
                    kicsit(k.hivo, k.szin)                 # a lopásra hívott kis lap
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
        """Egy adukör nem viheti el a lopásokra foglalt adukat."""
        if not self.adu:
            return False
        for u in self._mi_kezek():
            n = len(self.j.szin(u, self.adu))
            if n - (1 if n else 0) < self._lopas_igeny(u):
                return False
        return True

    # -- egy körünk eredménye --
    def _frissit(self):
        j = self.j
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
            e.i += 1
            self.folyo = None

    def _siker(self, e: Egyseg):
        self._jegyez(f"{e.p.rovid}: sikerült")
        # az esélyek sora: ha egy sikerült, a többi elmarad (a lapjaik szabadok)
        for x in self.egysegek:
            if x is not e and x.allapot == "var":
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

    def _kovetkezo_kor(self) -> tuple[Egyseg, Kor] | None:
        """Az esélyek sorában az első élő egység soron következő köre. A már lement
        lapok köreit (átmenetként vagy védői hívásra tettük le) átlépi; a `csak_ha:
        siker` körnél dönt: a lap most nyerő-e (megfigyelt tény)."""
        j = self.j
        mieink = j.kezek[j.felvevo] | j.kezek[j.asztal]
        for e in self.egysegek:
            while e.el:
                k = e.kor()
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
        for e in self.egysegek:
            if not e.el:
                continue
            for k in e.p.korok[e.i:]:
                if k.lap is not None and k.lap not in mieink:
                    continue
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

    def _jeloltek(self, H: str) -> list["Jelolt"]:
        out: list[Jelolt] = []
        if self._kint_adu() and self._adukor_mehet():
            out += self._adukor_jeloltek(H, 0)
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
            if kicsi is not None and kicsi.rang < k.lap.rang:
                ki.append(Jelolt(kicsi, ar, cim, {P: ("lap", k.lap)}, (ei, k)))
            return ki + self._atmenet_jeloltek(H, X, e, ar + 0.5)
        if k.fajta == "impassz":
            if k.hivo != H:
                return self._atmenet_jeloltek(H, k.hivo, e, ar + 0.5)
            sajat = j.szin(H, k.szin)
            if not sajat:
                return []
            return [Jelolt(sajat[0], ar, cim, {P: ("impassz", k.lap)}, (ei, k))]
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
        kl.egysegek = [Egyseg(e.p, e.i, e.allapot) for e in self.egysegek]
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
        if not van and len(utes) == 1 and hatra_van_partner and hivott != adu:
            p_nyero = [l for l in j.szin(P, hivott) if self._nyero(l)]
            if p_nyero:
                l = self._dobas(u, fogl)
                return l, f"nem lop: a partnerünk üt ({p_nyero[-1]}); dobás: {l}"
        if van and len(utes) == 1:
            P = j.partner(u)
            p_legjobb = max((l.rang for l in j.szin(P, hivott)), default=0)
            kint_felett = [x for x in j.kint(hivott) if x != nyl and x.rang > p_legjobb]
            p_lop = not j.szin(P, hivott) and adu and hivott != adu and j.szin(P, adu)
            if kint_felett and not p_lop and self._tartalek() <= 0:
                nyerok = [l for l in van if self._nyero(l) and l.rang > nyl.rang]
                if nyerok:
                    return nyerok[0], f"második kéz: üt a nyerővel ({nyerok[0]}) — nincs tartalék"
            l = self._legkisebb(van, fogl)
            return l, "második kéz: kicsi" + _megtart(l, van, fogl)
        if van:
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
                return adu_l[0], f"lop: {adu_l[0]}"
        l = self._dobas(u, fogl)
        return l, f"dobás: {l}" + (" (a foglalt és a nyerő lapokat megtartja)" if fogl & j.kezek[u] else "")

    def _hatra(self, utes) -> list[str]:
        """Akik még tesznek ebbe az ütésbe (a sorrendben)."""
        utolso = utes[-1][0]
        return [kovetkezo_ules(utolso, i) for i in range(1, 4 - len(utes) + 1)]

    def _legkisebb(self, lapok: list[Lap], fogl: set[Lap]) -> Lap:
        szabad = [l for l in lapok if l not in fogl]
        return (szabad or lapok)[0]

    def _dobas(self, u: str, fogl: set[Lap]) -> Lap:
        j = self.j
        hossz = {sz: len(j.szin(u, sz)) for sz in "SHDC"}
        return min(j.kezek[u], key=lambda l: (l in fogl, self._nyero(l), l.szin == self.adu,
                                              -hossz[l.szin], l.rang))


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
