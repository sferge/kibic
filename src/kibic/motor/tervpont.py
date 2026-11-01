"""
A tervezés pillanata (2026-11-01, Felvevő tervjáték): a RELEVANS_UTES szabály.

A tervezés pillanatát nem az dönti el, hogy ki hív, hanem hogy van-e döntésünk
(a szerkesztő szabálya). Egy védői hívásnál:

  1. NINCS DÖNTÉS: mindkét kezünk színt ad, és egyik lapunk sem üti a hívott
     lapot — az ütést mindenképp a védők viszik. Minimális gondolkodás: a
     legkisebb lapok (így a magassá válható lapunk is megmarad).
  2. DOBÁS: az ütést mindenképp a védők viszik, de egyik kezünk színhiányos és
     nem lophat (szanzadu, vagy nincs adója) — mit dobunk: tervezés kell.
  3. ÜTÉS-DÖNTÉS: üthetnénk (nagyobb lapunk van) vagy lophatnánk — ütünk vagy
     kiengedünk, melyik kézben, mivel lopunk: ez már a terv része.

A saját hívásunk mindig tervezést kíván.
"""
from __future__ import annotations

from ..domain import Lap

NINCS_DONTES, DOBAS, UTES_DONTES = 1, 2, 3


def utes_fajta(kez1: set[Lap], kez2: set[Lap], hivott: Lap, adu: str | None) -> tuple[int, str]:
    """kez1, kez2: a két kezünk lapjai az ütés elején. → (fajta, miért)."""
    sz = hivott.szin
    dobas = False
    for kez in (kez1, kez2):
        sajat = [l for l in kez if l.szin == sz]
        if sajat:
            if max(l.rang for l in sajat) > hivott.rang:
                return UTES_DONTES, f"üthetünk ({max(sajat, key=lambda l: l.rang)})"
        elif adu and adu != sz and any(l.szin == adu for l in kez):
            return UTES_DONTES, "lophatunk"
        else:
            dobas = True
    if dobas:
        return DOBAS, "dobnunk kell"
    return NINCS_DONTES, "a legkisebb lapok"


def relevans_vedoi_hivas(kez1: set[Lap], kez2: set[Lap], hivott: Lap, kint=None,
                         menetek=None, adu: str | None = None) -> tuple[bool, str]:
    """Visszafelé kompatibilis alak: releváns-e (2. vagy 3. fajta)."""
    f, miert = utes_fajta(kez1, kez2, hivott, adu)
    return f != NINCS_DONTES, miert
