"""FOGAS_VEDES — a megfelelő fogás (a szerkesztő, 2026-11-22/23).

„Plusz ütés szerzése érdekében úgy engedhetünk ki (adhatunk ki) lapot, hogy legyen megfelelő
fogásunk minden színben.” A fogás: amivel biztosan megszerezzük az ütést a színben.

- **n-edik menet fogás:** a védők — akárhogy ülnek, akárhonnan hívnak — legfeljebb n−1
  ütést visznek a színben, mielőtt mi ütünk. Az Á első menet; ha az Á kint van, a KD
  második menet (az egyiket viszi az Á, utána első menet fogásunk marad). A K egyedül (az Á
  kint) nem fogás: a védők a K előtt / mögött ülve megkerülhetik. Színfelvételben az adu is
  fogás egy idegen színben: színhiánnyal első menet, szinglivel második menet.
- **Megfelelő:** ha még k ütést adhatunk ki (a kiadási keret mínusz a terv tervezett
  kiadásai), a legfeljebb (k+1)-edik menet fogás elég. Ha csak egy ütést engedhetünk ki,
  első menet fogás kell; ha kettőt, elég a második menet fogás.
- A keret a TERVEZETT ütésekből jön (általában a felvétel teljesítése; MP / BAM esetén a
  terv a túlteljesítésre is készülhet).

A szabály két oldala: a kiadás / kiengedés FELTÉTELE (a jelöltek: tervmuhely), és a fogás
MEGTARTÁSA (a végrehajtó: a fogás lapja nem átmenet, nem dobás, amíg a hátralévő tervezett
ütések — a fogás ütésével együtt — nincsenek meg biztos ütésként).

**A kiadási ALKALMAK (a szerkesztő, 2026-11-23, MB 49):** nem elég azt nézni, hány ütést
adhatunk még ki — az is számít, HÁNYSZOR kerülnek a védők ütésbe. Minden ütésbe kerüléskor a
fenyegető színt hívhatják, és egy fogásunkat kiütik. Ha m alkalommal kerülnek ütésbe (a terv
m ütést ad ki), a színben m fogás kell, és a védők ütései a színben az m-edik fogásunkig
(a menetsor) férjenek bele a keretbe. „Az 1x 2 db kiadó szín esetét a 2x 1 db kiadó esetétől
meg kell különböztetni”:
- egy alkalom (egyszer kerülnek ütésbe, és utána a fenyegető színt hívják): egy fogás kell,
  és ha a keretbe a kiadó ütésen felül még egy belefér, elég a második menet fogás;
- két alkalom (pl. két kiadó treff): két fogás kell (az első alkalommal kiütik az egyiket, a
  másodikkal a másikat) — egy pikkfogással a második alkalommal lehívják a színt.
A terv kiadó színeiben a védők ütései a tervezett kiadások (azokat nem számoljuk kétszer).
"""
from __future__ import annotations

from ..domain import Lap


def fogas_menet(kezek: dict, kint, sz: str, adu: str | None) -> int | None:
    """A legkisebb n, amellyel a színben n-edik menet fogásunk van; 0, ha a védőknél nincs
    lap a színben (nincs mit megfogni); None, ha nincs fogásunk.

    A figurás fogás: a legnagyobb lapunk (b) fölött h kint lap van, és a b-vel kezdődő
    sorozatunk (b-től lefelé a lapjaink, amelyek közt nincs kint lap; a két kezünkben
    együtt) g lapos. Ha g > h, a védők minden nagyobb lapja csak egy sorozatlapunkat viszi,
    a (h+1)-edik menetben a miénk az ütés. A lopásos fogás (színfelvételben, idegen
    színben): a kéz L lapot tart a színből, és van adója — az (L+1)-edik menetben lop."""
    ki = [l for l in kint if l.szin == sz]
    if not ki:
        return 0
    mi = sorted((l for lapok in kezek.values() for l in lapok if l.szin == sz), key=lambda l: -l.rang)
    legjobb = None
    if mi:
        b = mi[0]
        h = sum(1 for l in ki if l.rang > b.rang)
        g = sum(1 for l in mi if not any(l.rang < x.rang < b.rang for x in ki))
        if g > h:
            legjobb = h + 1
    if adu and sz != adu:
        for lapok in kezek.values():
            if any(l.szin == adu for l in lapok):
                n = sum(1 for l in lapok if l.szin == sz) + 1
                legjobb = n if legjobb is None else min(legjobb, n)
    return legjobb


def megfelelo(n: int | None, k: int) -> bool:
    """Az n-edik menet fogás megfelelő-e, ha még k ütést adhatunk ki."""
    return n is not None and n - 1 <= max(0, k)


def menetsor(kezek: dict, kint, sz: str, adu: str | None) -> str:
    """A szín menetei, ha a védők hívják a színt (a legrosszabb esetben): „M” = mi ütünk
    (fogás), „V” = a védők ütnek. Menetenként a `fogas_menet` dönt: első menet fogásnál mi
    ütünk (a legkisebb lapunkkal, amely minden kint lapnál nagyobb, vagy lopással), a másik
    kezünk a legkisebb lapját teszi; különben a védők a legnagyobb lapjukkal ütnek, és a
    legjobb lapunkat viszik (a sorozatunk egy lapját — a fogás_menet feltevése), a másik
    kezünk a legkisebbet teszi. A kint lapok helyét nem ismerjük: a menetsor addig tart,
    amíg a védőknek van lapjuk a színben (mintha egy kézben volnának — óvatos becslés)."""
    kezek = {u: list(l) for u, l in kezek.items()}
    ki = sorted((l for l in kint if l.szin == sz), key=lambda l: l.rang)
    sor = ""

    def legkisebb(u):
        sajat = [l for l in kezek[u] if l.szin == sz]
        if sajat:
            kezek[u].remove(min(sajat, key=lambda l: l.rang))

    while ki and len(sor) < 13:
        n = fogas_menet(kezek, ki, sz, adu)
        felso = ki[-1].rang
        if n == 1:
            nyero = [(l.rang, u, l) for u, lapok in kezek.items() for l in lapok
                     if l.szin == sz and l.rang > felso]
            if nyero:
                _, u, l = min(nyero, key=lambda x: x[0])
                kezek[u].remove(l)
            else:   # lopás: a színhiányos kéz adut tesz
                u = next(u for u, lapok in kezek.items()
                         if not any(l.szin == sz for l in lapok) and any(l.szin == adu for l in lapok))
                kezek[u].remove(min((l for l in kezek[u] if l.szin == adu), key=lambda l: l.rang))
            for v in kezek:
                if v != u:
                    legkisebb(v)
            ki.pop(0)
            sor += "M"
        else:
            ki.pop()
            mi = [(l.rang, u, l) for u, lapok in kezek.items() for l in lapok if l.szin == sz]
            if mi:
                _, u, l = max(mi, key=lambda x: x[0])
                kezek[u].remove(l)
                for v in kezek:
                    if v != u:
                        legkisebb(v)
            sor += "V"
    return sor


def vedo_utesek(sor: str, alkalom: int) -> int:
    """A védők ütései a színben, ha `alkalom`-szor kerülnek ütésbe: minden alkalommal hívják
    a színt (lehívják, ami az övék, és kiütik a következő fogásunkat) — a „V” menetek az
    `alkalom`-adik „M” előtt; ha ennyi fogásunk nincs, a szín minden „V” menete."""
    if alkalom <= 0:
        return 0
    v = m = 0
    for c in sor:
        if c == "M":
            m += 1
            if m == alkalom:
                return v
        else:
            v += 1
    return v


def fogasok_megfelelok(kezek: dict, kint, adu: str | None, k: int, alkalom: int = 1,
                       kiado=()) -> bool:
    """A kiadási alkalmak szabálya: minden (nem kiadó) színben a védők ütései az
    `alkalom`-adik fogásunkig legfeljebb k (a tervezett kiadásokon felül még kiadható
    ütések). Egy alkalomnál ez a régi feltétel (n-edik menet fogás, n − 1 ≤ k)."""
    return all(vedo_utesek(menetsor(kezek, kint, sz, adu), alkalom) <= max(0, k)
               for sz in "SHDC" if sz not in kiado)


def biztos_utesek(kezek: dict, kint, adu: str | None) -> int:
    """A biztos ütéseink (felső lapokból): színenként a kint lévő legnagyobbnál nagyobb
    lapjaink, legfeljebb a hosszabb kéz hossza (kint lap nélkül a hosszabb kéz hossza).
    Színfelvételben, ha a védőknél adu van, a mellékszínek felső lapjai nem biztosak
    (ellophatják) — csak az aduszíné."""
    kint = list(kint)
    kint_adu = adu is not None and any(l.szin == adu for l in kint)
    n = 0
    for sz in "SHDC":
        if kint_adu and sz != adu:
            continue
        ki = [l for l in kint if l.szin == sz]
        hosszabb = max((sum(1 for l in lapok if l.szin == sz) for lapok in kezek.values()), default=0)
        if not ki:
            n += hosszabb
            continue
        felso = max(l.rang for l in ki)
        n += min(hosszabb, sum(1 for lapok in kezek.values() for l in lapok
                               if l.szin == sz and l.rang > felso))
    return n


def tervezett_vesztes(kezek: dict, kint, szinek) -> int:
    """A terv kimagasító színeiben biztosan kiadandó ütések: színenként a legnagyobb
    lapunknál nagyobb kint lapok (pl. ♦KDB10 mellett a ♦Á)."""
    n = 0
    for sz in szinek:
        mi = [l.rang for lapok in kezek.values() for l in lapok if l.szin == sz]
        if mi:
            n += sum(1 for l in kint if l.szin == sz and l.rang > max(mi))
    return n


def foglalt_fogas(kezek: dict, kint, adu: str | None, k: int, alkalom: int = 1,
                  kiado=()) -> set[Lap]:
    """A megtartandó fogáslapok: azok a lapjaink, amelyek nélkül egy színben a fogás már
    nem volna megfelelő (k: a tervezett kiadásokon felül még kiadható ütések; `alkalom`:
    ahányszor a védők még ütésbe kerülnek; a `kiado` színek a terv kiadó színei, ott nem
    foglalunk). Az adukat nem foglaljuk (a lopásos fogást az adukezelés szabályai védik).
    Színenként a legnagyobb alkalomszám (≤ `alkalom`) számít, amelyre a fogásunk még
    megfelelő: ha a két fogás két alkalomra is elég, mindkettőt megtartjuk; ha csak egyre,
    legalább azt az egyet."""
    ki: set[Lap] = set()
    k = max(0, k)
    for sz in "SHDC":
        if sz in kiado or not any(l.szin == sz for l in kint):
            continue
        sor = menetsor(kezek, kint, sz, adu)
        alk = next((a for a in range(max(1, alkalom), 0, -1) if vedo_utesek(sor, a) <= k), 0)
        if not alk:
            continue
        for u, lapok in kezek.items():
            for l in lapok:
                if l.szin != sz:
                    continue
                nelkule = dict(kezek)
                nelkule[u] = [x for x in lapok if x != l]
                if vedo_utesek(menetsor(nelkule, kint, sz, adu), alk) > k:
                    ki.add(l)
    return ki


def terv_feltetel(allas, terv) -> bool:
    """A kiadás / kiengedés feltétele egy tervre (a jelöltek előszűrése): ha a terv ütést
    ad ki (a kimagasító színeiben biztosan kiadandó ütések, a `kiad` körök), a kiadások
    után is minden színben megfelelő fogásunk marad — a kiadási alkalmak száma szerint
    (minden kiadott ütés egy alkalom: a védők ütésbe kerülnek, és a fenyegető színt hívják).
    A terv nélküli kiadás nem feltétel."""
    from .tervkonyvelo import biztos_egyseg
    kezek = {u: list(l) for u, l in allas.kezek.items()}
    kint = list(allas.kint)
    kiad: dict[str, int] = {}
    for p in terv.lepesek:
        for k in p.korok:
            if k.fajta == "kiad" and k.szin:
                kiad[k.szin] = kiad.get(k.szin, 0) + 1
    for sz in {p.szin for p in terv.lepesek if not biztos_egyseg(p) and p.szin}:
        kiad[sz] = max(kiad.get(sz, 0), tervezett_vesztes(kezek, kint, [sz]))
    n = sum(kiad.values())
    if not n:
        return True
    k = (allas.hatra - allas.cel) - n
    kiado = {sz for sz, db in kiad.items() if db}
    # a folyó ütés: ha védő hívta, az maga is egy alkalom a hívott színben (MB 49: a ♠D
    # indulás a ♠K-t viszi — a két kiadás után egy pikkfogás marad); a hívott lap is az övék
    utes = list(getattr(allas, "utes", None) or [])
    if utes and utes[0][0] not in allas.kezek:
        hsz = utes[0][1].szin
        tett = [l for u, l in utes if u not in allas.kezek and l.szin == hsz]
        if hsz not in kiado and vedo_utesek(menetsor(kezek, kint + tett, hsz, allas.adu), n + 1) > max(0, k):
            return False
        kiado = kiado | {hsz}
    return fogasok_megfelelok(kezek, kint, allas.adu, k, alkalom=n, kiado=kiado)


# --- VESZELYES_KEZ (a szerkesztő, 2026-11-24, BM A-11) -----------------------------------
# Egy védő veszélyes, ha ütésbe kerülve olyan hívása van, ami az ellenvonalnak plusz ütést
# hoz: a kereten túl lehív, vagy átimpasszolja a figuránkat (a partnere 2-t vagy többet üt).
# A mérték: ha D hív egy színt, hány ütést visznek a védők, mielőtt mi ütünk (a védők a
# legjobb lapjaikkal, mi a legjobbakkal; D partnere is folytathatja). Helyfüggő: a ♥Kx a
# hívó bal kezén (a hívás „átmegy” rajta) más, mint a jobb kezén.

from functools import lru_cache as _lru


def _kepv(lapok, ellen) -> list:
    ki, elozo = [], None
    for r in sorted(lapok):
        if elozo is not None and not any(elozo < e < r for e in ellen):
            elozo = r
            continue
        ki.append(r)
        elozo = r
    return ki


@_lru(maxsize=200_000)
def _vh(D: frozenset, L: frozenset, P: frozenset, R: frozenset, lop_l: bool, lop_r: bool) -> int:
    """D hív (ülésrend: D, L, P, R; L és R a mi kezeink): a védők ütései a színben, mielőtt
    mi ütünk. A színhiányos kezünk lophat (`lop_*`)."""
    if not D:
        return 0
    mi, ok = L | R, D | P
    legjobb = 0
    for d in _kepv(D, mi):
        rossz = None
        for l in (_kepv(L, ok) if L else ([None, 100] if lop_l else [None])):
            if l == 100:
                rossz = 0
                break
            jo = 0
            for p in (_kepv(P, mi) if P else [None]):
                legr = None
                for r in (_kepv(R, ok) if R else ([None, 100] if lop_r else [None])):
                    lapok = [("D", d), ("L", l), ("P", p), ("R", r)]
                    gy = max((x for x in lapok if x[1] is not None), key=lambda x: x[1])[0]
                    if gy in ("L", "R"):
                        v = 0
                    else:
                        D2, L2, P2, R2 = (D - {d}, L - {l}, P - {p}, R - {r})
                        v = 1 + (_vh(D2, L2, P2, R2, lop_l, lop_r) if gy == "D"
                                 else _vh(P2, R2, D2, L2, lop_r, lop_l))
                    legr = v if legr is None else min(legr, v)
                    if legr == 0:
                        break
                jo = max(jo, legr)
            rossz = jo if rossz is None else min(rossz, jo)
            if rossz == 0:
                break
        legjobb = max(legjobb, rossz or 0)
    return legjobb


VH_MAX_KINT = 11        # e fölött nem soroljuk fel az elosztásokat


def vedo_hivas(bal: frozenset, jobb: frozenset, kint: frozenset, d_hiany: bool, p_hiany: bool,
               lop_bal: bool = False, lop_jobb: bool = False) -> tuple[int, int]:
    """(legkevesebb, legtöbb) védőütés a színben, ha D hívja (mielőtt mi ütünk), a kint lévő
    lapok minden lehetséges elosztásán. `bal`/`jobb`: a mi lapjaink D bal / jobb kezén;
    `d_hiany`/`p_hiany`: D / a partnere már kimutatott a színből."""
    if d_hiany or not kint:
        return 0, 0
    if p_hiany:
        v = _vh(kint, bal, frozenset(), jobb, lop_bal, lop_jobb)
        return v, v
    if len(kint) > VH_MAX_KINT:
        return 0, _vh(kint, bal, frozenset(), jobb, lop_bal, lop_jobb)
    lapok = sorted(kint)
    lo, hi = 0, 0                    # D-nek nincs a színből (amíg nem tudjuk, hogy van): nem hívhatja
    from itertools import combinations
    for n in range(1, len(lapok) + 1):
        for d in combinations(lapok, n):
            D = frozenset(d)
            v = _vh(D, bal, kint - D, jobb, lop_bal, lop_jobb)
            hi = max(hi, v)
    return lo, hi


# --- DEBLOKK_DOBAS (a szerkesztő, 2026-11-24, 3NT ♣ÁK87 / ♣D65432) ------------------------
# „Ha a rövidebb kéz valamelyik színe BLOKKOLÓ LAPOT tartalmaz, ami a szín lehívását
# megakadályozza, mivel a hosszú kéz lapjai beragadnak, akkor a blokkoló lapot el kell
# dobni.” A ♣8 és a ♣7 a kéz kis treffjei fölött van: 3–0-s elosztásnál a hosszú kéz két
# lapja beragad (ha a 4. treff a ♣2 volna, csak a sorrend számítana). A mérés: a hosszú
# kéznek nincs beütése, a rövid kéz hív; a szín minden lapja ütés-e — és nő-e ez az esély,
# ha a rövid kézből egy lapot elveszünk.

@_lru(maxsize=500_000)
def _vegig(L: frozenset, R: frozenset, A: frozenset, B: frozenset, rovid_hiv: bool) -> int:
    """Mindent látva: hány ütést viszünk a színben megszakítás nélkül. A hívó a `L` kéz
    (ülésrend: L, A, R, B — A és B a védők); `rovid_hiv`: L a rövid kéz-e. Ha egy védő üt,
    vagy a hívó kéz kifogy, a sor véget ér (a hosszú kézbe nincs beütés)."""
    if not L:
        return 0
    legjobb = 0
    for l in sorted(L):
        rossz = None
        for a in (sorted(A) if A else [None]):
            jo = 0
            for r in (sorted(R) if R else [None]):
                legr = None
                for b in (sorted(B) if B else [None]):
                    lapok = [(0, l), (1, a), (2, r), (3, b)]
                    gy = max((x for x in lapok if x[1] is not None), key=lambda x: x[1])[0]
                    L2, A2, R2, B2 = L - {l}, A - {a}, R - {r}, B - {b}
                    if gy == 0:
                        v = 1 + _vegig(L2, R2, A2, B2, rovid_hiv)
                    elif gy == 2:
                        v = 1 + _vegig(R2, L2, B2, A2, not rovid_hiv)
                    else:
                        v = 0
                    legr = v if legr is None else min(legr, v)
                jo = max(jo, legr)
            rossz = jo if rossz is None else min(rossz, jo)
        legjobb = max(legjobb, rossz)
    return legjobb


def _lehivas_esely(X: frozenset, Y: frozenset, kint: frozenset, ures1: int, ures2: int,
                   rovid: str, k: int) -> float:
    """A rövid kéz hív (onnan indulunk), a hosszú kézbe nincs beütés: mekkora eséllyel
    visszük a szín k ütését megszakítás nélkül (elosztásonként, mindent látva)."""
    from .tervfelmeres import _elosztasok
    ossz = jo = 0
    for w, a, b in _elosztasok(sorted(kint, reverse=True), ures1, ures2):
        V1, V2 = frozenset(a), frozenset(b)
        if rovid == "X":      # a felvevő hív: utána V1, az asztal, V2
            t = _vegig(X, Y, V1, V2, True)
        else:                 # az asztal hív: utána V2, a felvevő, V1
            t = _vegig(Y, X, V2, V1, True)
        ossz += w
        jo += w if t >= k else 0
    return jo / ossz if ossz else 0.0


@_lru(maxsize=4096)
def blokkolo_lap(X: frozenset, Y: frozenset, kint: frozenset, ures1: int, ures2: int,
                 rovid: str, kuszob: float = 0.05) -> int | None:
    """A rövid kéz (`rovid`: "X" a felvevő, "Y" az asztal) blokkoló lapja (rang), vagy None.
    (A színkezelés-elemző itt nem használható: a kint lévő lapok alatti saját lapjainkat
    egyformának veszi, a blokk pedig épp ezeken múlik.)"""
    R, H = (X, Y) if rovid == "X" else (Y, X)
    if not R or len(H) <= len(R) or not kint or len(kint) > 7 or len(H) + len(R) > 11:
        return None
    k = len(H)
    p0 = _lehivas_esely(X, Y, kint, ures1, ures2, rovid, k)
    legjobb, lap = p0, None
    for r in sorted(R):
        R2 = R - {r}
        p = (_lehivas_esely(R2, Y, kint, ures1, ures2, rovid, k) if rovid == "X"
             else _lehivas_esely(X, R2, kint, ures1, ures2, rovid, k))
        if p > legjobb + 1e-9:
            legjobb, lap = p, r
    if lap is None or legjobb < 0.5 or legjobb - p0 < kuszob:
        return None
    return lap


# --- LEHIVAS_SORREND (2026-11-24, a fenti partin) ----------------------------------------
# A szín begyűjtésekor (mindkét kezünkben van a színből) az a lap — hívásnál és a partner
# hívására is —, amelyikkel a legnagyobb eséllyel visszük a szín minden ütését megszakítás
# nélkül (♣ÁK87 / ♣D65432, 2–1: Á, K, 8, és a 7-est a D üti át).

def _utes_vege_dd(kezek: dict, rend: list[str], tett: list, mi: str) -> int:
    """A folyó ütés hátralévő lapjai mindent látva (mi: maximum, a védők: minimum), utána
    `_vegig`. `rend`: a négy ülés sorrendje a hívótól; `tett`: a már tett lapok (rang/None)."""
    n = len(tett)
    if n == 4:
        legjobb = max((i for i in range(4) if tett[i] is not None), key=lambda i: tett[i])
        gy = rend[legjobb]
        if gy not in ("X", "Y"):
            return 0
        X, Y, V1, V2 = kezek["X"], kezek["Y"], kezek["V1"], kezek["V2"]
        return 1 + (_vegig(X, Y, V1, V2, False) if gy == "X" else _vegig(Y, X, V2, V1, False))
    u = rend[n]
    lapok = sorted(kezek[u]) if kezek[u] else [None]
    ert = []
    for l in lapok:
        k2 = dict(kezek)
        if l is not None:
            k2[u] = kezek[u] - {l}
        ert.append(_utes_vege_dd(k2, rend, tett + [l], mi))
    return max(ert) if u in ("X", "Y") else min(ert)


def lehivas_lap(X: frozenset, Y: frozenset, kint: frozenset, ures1: int, ures2: int,
                hivo: str, tett: tuple, k: int) -> tuple[int | None, float, dict]:
    """A soron lévő kezünk lapja (rang) a szín teljes lehívásához. `hivo`: "X"/"Y" (az ütés
    hívója); `tett`: a folyó ütés eddigi lapjai a hívótól (rang/None); X, Y: a mostani
    lapjaink (a már tett nélkül); `kint`: a védők még nem tett lapjai. Visszaad: (lap,
    esély, {lap: esély})."""
    from .tervfelmeres import _elosztasok
    rend = ["X", "V1", "Y", "V2"] if hivo == "X" else ["Y", "V2", "X", "V1"]
    u = rend[len(tett)]
    if u not in ("X", "Y"):
        return None, 0.0, {}
    sajat = X if u == "X" else Y
    if not sajat or len(kint) > 7:
        return None, 0.0, {}
    ert: dict = {}
    eloszl = list(_elosztasok(sorted(kint, reverse=True), ures1, ures2))
    W = sum(w for w, _, _ in eloszl) or 1
    for c in sorted(sajat):
        jo = 0
        for w, a, b in eloszl:
            kez = {"X": X, "Y": Y, "V1": frozenset(a), "V2": frozenset(b)}
            kez[u] = sajat - {c}
            if _utes_vege_dd(kez, rend, list(tett) + [c], u) >= k:
                jo += w
        ert[c] = jo / W
    legjobb = max(ert.values())
    c = max((r for r in ert if ert[r] >= legjobb - 1e-9), key=lambda r: r)
    return c, legjobb, ert
