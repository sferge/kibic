"""
További lapértékelő metrikák.

Az `ertekelo` regiszter bővítése. A modul importálásakor az itteni
függvények bekerülnek a domain.ERTEKELOK szótárba, tehát a
kritérium-motor azonnal használni tudja őket.

FONTOS ELVI MEGJEGYZÉS (a projekt egyik tanulsága):
A lapértékelés NEM univerzális. Egy metrika (asztali pont, elosztási pont,
vesztőütés) rendszer- ÉS helyzetfüggő: az adott rendszer adott pontján
érvényes, nem általánosan. Ezért a metrikák itt csak SZÁMOLÓ FÜGGVÉNYEK;
azt, hogy egy adott döntésnél melyiket kell használni, a
licitrendszer-bejegyzés (kriterium_keszlet) mondja meg.
Kivétel a ZAR-pont, ami szándékosan aggregálja a figurapontot, az
elosztást és a hosszúságot egyetlen számmá.

FORRÁSOK — melyik rendszer melyik metrikát használja:
  HCP        4-3-2-1        mindenütt
  KONTROLL   A=2, K=1       Sylstandard 2♣ válaszok, szlemkutatás
  NANO       A=3, K=2, D=1  Sylstandard 2♣ válaszok
  AP_321     HCP + sikén3/szingli2/dubló1
  AP_531     HCP + sikén5/szingli3/dubló1   Standard American (Győr, 2002)
  GYORSUTES  AK=2, AQ=1.5, A=1, KQ=1, Kx=0.5
  F1..F4     figurapont az n-edik RANGÚ színben   (LICREN: f1..f4)
  EGYENLETES legalább 2 lap minden színben        (LICREN: b)

A Heavy Club NEM használ elosztási pontot: 4-3-2-1 figurapont, az
elosztást relével kérdezi ki egzaktan.
"""
from __future__ import annotations

from .kartya import ERTEKELOK, HCP_TABLA, Kez, SZINEK, ert_hcp

NANO_TABLA = {"A": 3, "K": 2, "Q": 1}


def ert_nano(kez: Kez) -> float:
    """Nano-pont (Sylstandard): A=3, K=2, D=1."""
    return float(sum(NANO_TABLA.get(l.ertek, 0) for l in kez.lapok))


def _ap(kez: Kez, siken: int, szingli: int, dublo: int) -> float:
    pont = 0
    for h in kez.hosszak:
        if h == 0:
            pont += siken
        elif h == 1:
            pont += szingli
        elif h == 2:
            pont += dublo
    return ert_hcp(kez) + pont


def ert_ap_321(kez: Kez) -> float:
    """Asztali pont, 3-2-1 iskola: sikén 3, szingli 2, dubló 1."""
    return _ap(kez, 3, 2, 1)


def ert_ap_531(kez: Kez) -> float:
    """Asztali pont, 5-3-1 iskola (Standard American, Győr 2002)."""
    return _ap(kez, 5, 3, 1)


def ert_gyorsutes(kez: Kez) -> float:
    """Gyorsütés: AK=2, AQ=1.5, A=1, KQ=1, Kx=0.5."""
    ossz = 0.0
    for szin in SZINEK:
        lapok = {l.ertek for l in kez.lapok if l.szin == szin}
        db = len(lapok)
        if "A" in lapok and "K" in lapok:
            ossz += 2.0
        elif "A" in lapok and "Q" in lapok:
            ossz += 1.5
        elif "A" in lapok:
            ossz += 1.0
        elif "K" in lapok and "Q" in lapok:
            ossz += 1.0
        elif "K" in lapok and db >= 2:
            ossz += 0.5
    return ossz


def ert_egyenletes(kez: Kez) -> float:
    """LICREN `b`: legalább két lap MINDEN színben. 1 vagy 0."""
    return 1.0 if min(kez.hosszak) >= 2 else 0.0


def _figurapont_rangban(kez: Kez, rang: int) -> float:
    """A `rang`-adik leghosszabb színben lévő figurapontok (LICREN f1..f4)."""
    rendezett = sorted(SZINEK, key=lambda sz: (-kez.hossz(sz), SZINEK.index(sz)))
    szin = rendezett[rang - 1]
    return float(sum(HCP_TABLA.get(l.ertek, 0)
                     for l in kez.lapok if l.szin == szin))


def ert_f1(kez: Kez) -> float: return _figurapont_rangban(kez, 1)
def ert_f2(kez: Kez) -> float: return _figurapont_rangban(kez, 2)
def ert_f3(kez: Kez) -> float: return _figurapont_rangban(kez, 3)
def ert_f4(kez: Kez) -> float: return _figurapont_rangban(kez, 4)


UJ_ERTEKELOK = {
    "NANO":       ert_nano,
    "AP_321":     ert_ap_321,
    "AP_531":     ert_ap_531,
    "GYORSUTES":  ert_gyorsutes,
    "EGYENLETES": ert_egyenletes,
    "F1": ert_f1, "F2": ert_f2, "F3": ert_f3, "F4": ert_f4,
}
ERTEKELOK.update(UJ_ERTEKELOK)
