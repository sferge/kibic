"""
A források (2026-11-18, Felvevő tervjáték) — a tervkészítés 2. lépése a szerkesztő
leírása szerint: a hiányzó ütések (és a vesztőtöbblet) megszerzésének lehetőségei,
az esélyükkel.

Egy forrás egy technika példánya a látott lapokon (`tervsema.peldanyok`):
  * hozam — ennyi ütést hoz, vagy ennyi vesztőt tüntet el, ha sikerül;
  * esély — a rejtett feltétel (`siker`) valószínűsége a kint lévő lapok
    elosztásain (osztályokban: a hosszak és a releváns figurák helye; a szabad
    helyek szerint súlyozva — `tervszamolo.osztalyok`), keresés nélkül;
  * kudarc költsége — ennyi ütést ad ki, ha nem sikerül;
  * biztos — nincs rejtett feltétele (vesztőcsere, lopás): a kockázata a
    végrehajtásé (ellopás, időzítés), nem a lapok helyéé.
"""
from __future__ import annotations

from dataclasses import dataclass

from .tervsema import Allas, Peldany, kifejezes, peldanyok
from .tervszamolo import Korlat, osztalyok, rejtett_fogalmak


@dataclass
class Forras:
    p: Peldany
    hozam: int
    esely: float
    kudarc: int
    biztos: bool

    @property
    def nev(self) -> str:
        return self.p.rovid


def esely(p: Peldany, kint, ures: dict[str, int], korlatok: list[Korlat] = ()) -> float:
    """A technika `siker` feltételének valószínűsége (osztályokon)."""
    siker = str(p.sema.siker).strip()
    if siker == "True":
        return 1.0
    oszt = osztalyok(kint, ures, p.relevans, list(korlatok))
    W = sum(o.suly for o in oszt)
    if not W:
        return 0.0
    jo = 0
    for o in oszt:
        kor = dict(rejtett_fogalmak(o), **p.siker_kornyezet())
        try:
            if kifejezes(siker, kor):
                jo += o.suly
        except Exception:                    # noqa: BLE001 — értelmezhetetlen: nem számít
            pass
    return jo / W


def forrasok(allas: Allas, technikak: dict, ures: dict[str, int],
             korlatok: list[Korlat] = ()) -> list[Forras]:
    ki = []
    for p in peldanyok(allas, technikak):
        e = esely(p, allas.kint, ures, korlatok)
        ki.append(Forras(p, p.hozam, e, p.sema.kudarc_koltseg, str(p.sema.siker).strip() == "True"))
    ki.sort(key=lambda f: (-f.hozam * f.esely, f.kudarc, f.nev))
    return ki
