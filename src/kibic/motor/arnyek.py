"""
ÁRNYÉK MÓD — új döntéshozó próbája élesben, kockázat nélkül (a terv 0. fázisa,
doc/terv-elvsablonok-2026-10-04.md).

Egy átköltöztetett mechanizmus (pl. a spirál adatként, a hézag-elv egy pontja
elv-sablonként) előbb ÁRNYÉKBAN fut: ugyanabban a helyzetben kiszámolja a
saját döntését, a válaszba és a naplóba írja, egyezik-e a régivel — de a
licit a régi marad. Akkor élesedik, ha az aranykészleten és élesben sem tér
el (vagy minden eltérése szándékos).

Egy árnyék-döntéshozó: `fn(ktx) -> str | None` (a javasolt hívás, vagy None,
ha nem illetékes). A `ktx` szótár: kez, allas, er (a propagálás eredménye),
licitek, engedelyezett, keres, valasz (a régi döntés). A függvény NEM
módosíthat semmit.

Bekapcsolás: `KIBIC_ARNYEK=1` (mind), `KIBIC_ARNYEK=spiral,hezag1` (név
szerint), vagy kérésenként `"shadow": true` / `["nev"]`.

MÁSIK RENDSZER ÁRNYÉKBAN (2026-10-05): a `rendszer:KOD` név ugyanazt a
kérést egy másik rendszerrel is lefuttatja (pl. `rendszer:MOHA_STAND_ELV` —
az elv-sablonos próba-rendszer a MOHA_STAND mellett). Így élesben látszik,
hol licitálna mást.
"""
from __future__ import annotations

import os
from typing import Callable

ARNYEKOK: dict[str, Callable[[dict], str | None]] = {}


def regisztral(nev: str, fn: Callable[[dict], str | None]) -> None:
    ARNYEKOK[nev] = fn


def torol(nev: str) -> None:
    ARNYEKOK.pop(nev, None)


def kivalasztott(keres: dict | None) -> list[str]:
    """Mely árnyékok futnak ennél a kérésnél."""
    kert = (keres or {}).get("shadow")
    if kert is None:
        env = os.environ.get("KIBIC_ARNYEK", "").strip()
        if env in ("", "0", "nem"):
            return []
        kert = True if env in ("1", "igen", "mind") else [x.strip() for x in env.split(",")]
    if kert is True:
        return sorted(ARNYEKOK)
    if not kert:
        return []
    return [n for n in kert if n in ARNYEKOK or str(n).startswith("rendszer:")]


def _masik_rendszer(kod: str, ktx: dict) -> str | None:
    """Ugyanaz a kérés egy másik rendszerrel (árnyék nélkül)."""
    betolto = ktx.get("betolto")
    keres = ktx.get("keres")
    if betolto is None or not isinstance(keres, dict):
        return None
    from ..szolgaltatas.licit import licit_elemzes
    v = licit_elemzes(dict(keres, system=kod, shadow=[]), betolto)
    return v.get("call") or "P"


def futtat(ktx: dict, nevek: list[str]) -> list[dict]:
    """[{name, call, same}] — a hiba is eredmény (nem állíthatja meg a licitet)."""
    regi = (ktx.get("valasz") or {}).get("call")
    ki = []
    for n in nevek:
        fn = ARNYEKOK.get(n)
        if fn is None and str(n).startswith("rendszer:"):
            kod = str(n).split(":", 1)[1]
            fn = (lambda k: lambda ktx: _masik_rendszer(k, ktx))(kod)
        if fn is None:
            continue
        try:
            h = fn(ktx)
        except Exception as e:                   # noqa: BLE001
            ki.append({"name": n, "error": f"{type(e).__name__}: {e}"})
            continue
        if h is None:
            continue
        ki.append({"name": n, "call": h, "same": h == regi})
    return ki
