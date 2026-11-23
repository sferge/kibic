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


def foglalt_fogas(kezek: dict, kint, adu: str | None, k: int) -> set[Lap]:
    """A megtartandó fogáslapok: azok a lapjaink, amelyek nélkül egy színben a fogás már
    nem volna megfelelő (k: a még kiadható ütések). Az adukat nem foglaljuk (a lopásos
    fogást az adukezelés szabályai védik)."""
    ki: set[Lap] = set()
    for sz in "SHDC":
        n = fogas_menet(kezek, kint, sz, adu)
        if not n or not megfelelo(n, k):
            continue
        for u, lapok in kezek.items():
            for l in lapok:
                if l.szin != sz:
                    continue
                nelkule = dict(kezek)
                nelkule[u] = [x for x in lapok if x != l]
                if not megfelelo(fogas_menet(nelkule, kint, sz, adu), k):
                    ki.add(l)
    return ki


def terv_feltetel(allas, terv) -> bool:
    """A kiadás / kiengedés feltétele egy tervre (a jelöltek előszűrése): ha a terv ütést
    ad ki (a kimagasító színeiben biztosan kiadandó ütések, a `kiad` körök), a kiadások
    után is minden színben megfelelő fogásunk marad. A terv nélküli kiadás nem feltétel."""
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
    return all(megfelelo(fogas_menet(kezek, kint, sz, allas.adu), k) for sz in "SHDC")
