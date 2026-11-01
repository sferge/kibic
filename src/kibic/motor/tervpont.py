"""
A tervezés pillanata (2026-11-01, Felvevő tervjáték): a RELEVANS_UTES szabály.

Nem kell tervezni, amíg nincs valódi döntés. Egy védői hívás nem releváns (a
legkisebb lapokat tesszük), ha
  - mindkét kezünkben van a hívott színből (nincs lopás- vagy dobásdöntés),
  - egyik lapunk sem nagyobb a hívottnál (nem kell eldönteni, ütünk-e, hol),
  - és egyik lapunk sem válhat magassá a szín `menetek` menete után: a kint
    lévő, nála nagyobb lapok (a hívotton kívül) több mint `menetek`.
A saját hívásunk mindig releváns. (A szerkesztő szabálya.)
"""
from __future__ import annotations

from ..domain import Lap


def menetek_szama() -> int:
    from .tervsema import strategiak_betoltese
    _, szab = strategiak_betoltese()
    r = next((s for s in szab if s.get("szabaly") == "RELEVANS_UTES"), {})
    return int(r.get("menetek", 2))


def relevans_vedoi_hivas(kez1: set[Lap], kez2: set[Lap], hivott: Lap, kint: set[Lap],
                         menetek: int | None = None) -> tuple[bool, str]:
    """kez1, kez2: a két kezünk lapjai az ütés elején; kint: a védők még le nem
    játszott lapjai (a hívottal együtt vagy nélküle). → (releváns-e, miért)."""
    if menetek is None:
        menetek = menetek_szama()
    sz = hivott.szin
    for kez in (kez1, kez2):
        if not any(l.szin == sz for l in kez):
            return True, "színhiány: lopás vagy dobás"
    mi = sorted((l for l in kez1 | kez2 if l.szin == sz), key=lambda l: -l.rang)
    if mi[0].rang > hivott.rang:
        return True, f"nagyobb lapunk van ({mi[0]})"
    felette = sum(1 for l in kint if l.szin == sz and l != hivott and l.rang > mi[0].rang)
    if felette <= menetek:
        return True, f"a {mi[0]} magassá válhat ({felette} nagyobb kint)"
    return False, "a legkisebb lapok"
