"""
A tervező az élő játékban (2026-11-01, Felvevő tervjáték): a felvevő oldalán a
`/v1/bridge/play` lapja.

Bekapcsolás: `KIBIC_TERVEZO=1` (minden AI-felvevőre), vagy profilonként
`KIBIC_TERVEZO_PROFILOK=kod1,kod2` (az MB `actor.profile_code`-ja szerint) — így
ugyanannál az asztalnál a tervező és a régi lejátszó összevethető.

Döntési helyzetek (folytatólagos tervezés: minden döntésnél újra, a tárból):
  - mi hívunk (ütés eleje): a tervező legjobb terve, és annak első köre (a kotta
    vagy a színkezelő elemző első lépése); a kör tervezett lapjait megjegyezzük;
  - a mi hívásunk után a 3. kéz: a megjegyzett kör lapja (a fedési szabállyal),
    illetve az elemző 3. kéz-lépése a 2. kéz lapja szerint;
  - védői hívás, a 2. kéz: RELEVANS_UTES — nincs döntés: a legkisebb lap;
    dobás / ütés-döntés: az ütés közbeni tervező;
  - védői hívás, a 4. kéz: a három letett lap ismeretében az ütés közbeni tervező.
Ha valamelyik nem ad lapot (nincs terv, nincs megjegyzett kör, sürgetés az első
eredmény előtt, hiba), None: a régi lejátszó dönt.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from ..domain import SZINEK, Lap, kovetkezo_ules, vonal

RANGOK = "23456789TJQKA"
_KOR_TAR: dict = {}            # (játszma, ütés) → a mi hívásunk körének terve


@dataclass
class TervDontes:
    lap: Lap
    magyarazat: str
    bizonyossag: float
    meta: dict = field(default_factory=dict)


def bekapcsolva(keres: dict) -> bool:
    if os.getenv("KIBIC_TERVEZO", "0").strip().lower() in ("1", "igen", "true"):
        return True
    kod = str(((keres or {}).get("actor") or {}).get("profile_code") or "").strip()
    lista = [x.strip() for x in os.getenv("KIBIC_TERVEZO_PROFILOK", "").split(",") if x.strip()]
    return bool(kod) and kod in lista


def _lap(szin: str, rang: int) -> Lap:
    return Lap.parse(szin + RANGOK[rang - 2])


def _pakli() -> set[Lap]:
    return {_lap(s, r) for s in SZINEK for r in range(2, 15)}


def dontes(ja, kulcs: str, megallito=None, naplo=None) -> TervDontes | None:
    """ja: lejatszas.JatekAllas (a felvevő oldalán). kulcs: a játszma azonosítója."""
    from .tervutes import _nyero
    if ja.vedo:
        return None
    felv, aszt = ja.felvevo, ja.asztal
    if felv not in ja.lathato or aszt not in ja.lathato:
        return None
    adu = ja.adu
    jatszott = list(ja.lejatszott)
    akt = ja.aktualis
    kesz = jatszott[:len(jatszott) - len(akt)]
    X, Y = set(ja.lathato[felv]), set(ja.lathato[aszt])
    kint = _pakli() - X - Y - {l for _, l in jatszott}
    utesszam = len(kesz) // 4
    nyert = sum(1 for i in range(utesszam)
                if vonal(_nyero(kesz[4 * i:4 * i + 4], adu)[0]) == vonal(felv))
    hatra = 13 - utesszam
    cel = 6 + ja.kontraktus.szint - nyert
    korl = _szinhianyok(jatszott, felv, aszt)
    if not akt:
        return _hivas(ja, X, Y, kint, cel, hatra, korl, kulcs, utesszam, megallito, naplo)
    if akt[0][0] in (felv, aszt):
        return _harmadik(ja, akt, kulcs, utesszam)
    return _vedoi_hivas(ja, X, Y, kint, cel, hatra, korl, akt, megallito, naplo)


def _szinhianyok(jatszott, felv, aszt):
    from .tervszamolo import Korlat
    ki = []
    for i in range(0, len(jatszott), 4):
        utes = jatszott[i:i + 4]
        hivott = utes[0][1].szin
        for u, l in utes[1:]:
            if u not in (felv, aszt) and l.szin != hivott:
                ki.append(Korlat(u, hivott, 0, 0, "megfigyelt"))
    return ki


# --- mi hívunk ---------------------------------------------------------------------

def _hivas(ja, X, Y, kint, cel, hatra, korl, kulcs, utesszam, megallito, naplo):
    from .tervsema import Allas, peldanyok, technikak_betoltese
    from .tervezo import Eset, Ertekelo, kezdo_allapot, szinkezeles_peldanyok, tervez
    from .tervszamolo import osztalyok
    from . import tervparhuzam as tp
    felv, aszt = ja.felvevo, ja.asztal
    allas = Allas(felv, ja.adu, {felv: set(X), aszt: set(Y)}, set(kint), cel, hatra, ja.ules)
    stat: dict = {}
    h, ert = tervez(allas, korl, stat=stat, megallito=megallito)
    ert = [e for e in ert if not e.becsult]
    if not ert:
        return None
    v = ert[0]
    # az első kör: a terv útja egy (a legsúlyosabb) osztályon — az első kör még
    # nem függ megfigyeléstől
    relevans = {l for p in v.terv.lepesek for l in p.relevans}
    oszt = osztalyok(allas.kint, {u: hatra for u in allas.vedok}, relevans,
                     [k for k in korl if k.tudas == "megfigyelt"])
    o = max(oszt, key=lambda x: x.suly)
    e = Ertekelo(h, v.terv, kockazat=True)
    e.politika_rogzitett = v.politika
    e.ut = []
    st = e.kiaduzas(kezdo_allapot(allas), "mind" if v.terv.kiaduzas >= 13 else v.terv.kiaduzas)
    e.futtat([Eset(o, 1, h.tartalek, h.hiany)], 0, 0, st)
    lap, kor = None, None
    for lepes in e.ut:
        if lepes[0] in ("adu", "kor"):
            hivo, lapok = lepes[1], lepes[2]
            if hivo != ja.ules:
                return None
            lap, kor = lapok[hivo], {"lapok": dict(lapok)}
            break
        if lepes[0] == "elemzo":
            p, elemzes = lepes[1], lepes[2]
            if elemzes is None:
                return None
            tar = tp.tarbol(elemzes.kulcs)
            if tar is None or len(tar) < 3:
                # régi tárbejegyzés (első lépés nélkül): újraszámolás
                tar = tp.tarba(elemzes.kulcs, tp.kiszamol(elemzes))
            elso = tar[2]
            if elso is None:
                return None
            hivo_xy, c, harmadik = elso
            hivo = felv if hivo_xy == "X" else aszt
            if hivo != ja.ules:
                return None
            if elemzes.fajta == "egy":
                lap = _lap(p.szin, c)
                kor = {"elemzo": True, "szin": p.szin, "harmadik": harmadik}
            else:
                from . import tervtobbszin as tt
                lap = _lap(SZINEK[tt.szine(c)], tt.rangja(c))
                kor = {"elemzo": True, "szin": lap.szin, "harmadik": {}}
            break
    if lap is None or lap not in ja.legalis:
        return None
    kor["elso"] = lap
    _KOR_TAR[(kulcs, utesszam)] = kor
    szoveg = f"Terv: {v.terv.nev} ({v.kockazattal:.0%})."
    return TervDontes(lap, szoveg, 0.5 + 0.45 * v.kockazattal,
                      {"plan": v.terv.nev, "chance": round(v.kockazattal, 3),
                       "plans": stat.get("tervek"), "elapsed_s": round(stat.get("ossz_s", 0), 1),
                       "interrupted": bool(stat.get("megszakitva"))})


def _harmadik(ja, akt, kulcs, utesszam):
    """A mi hívásunk után a 3. kéz: a megjegyzett kör."""
    from .tervutes import _nyero, _ut
    kor = _KOR_TAR.get((kulcs, utesszam))
    if not kor or len(akt) != 2 or akt[0][1] != kor.get("elso"):
        return None
    hivott = akt[0][1].szin
    kez = sorted((l for l in ja.lathato[ja.ules]), key=lambda l: l.rang)
    sajat = [l for l in kez if l.szin == hivott]
    if kor.get("elemzo"):
        l2 = akt[1][1]
        kulcs2 = l2.rang if l2.szin == kor["szin"] else None
        c3 = kor["harmadik"].get(kulcs2)
        if c3 is None:
            return None
        lap = _lap(kor["szin"], c3)
    else:
        lap = kor["lapok"].get(ja.ules)
        if lap is None:
            return None
        nyu, nyl = _nyero(akt, ja.adu)
        if vonal(nyu) != vonal(ja.felvevo) and not _ut(lap, nyl, hivott, ja.adu):
            # fedési szabály: a védő viszi, a tervezett lap nem üti → a legolcsóbb, amely üti
            ut = [l for l in sajat if _ut(l, nyl, hivott, ja.adu)]
            if ut:
                lap = ut[0]
    if lap not in ja.legalis:
        return None
    return TervDontes(lap, "A terv köre folytatódik.", 0.7, {"plan_round": True})


# --- védői hívás ---------------------------------------------------------------------

def _vedoi_hivas(ja, X, Y, kint, cel, hatra, korl, akt, megallito, naplo):
    from .tervpont import NINCS_DONTES, utes_fajta
    from .tervutes import Lepes, UtesAllas, UtesTervezo, _mi_lap
    felv, aszt = ja.felvevo, ja.asztal
    hivo, hivott = akt[0]
    kez = set(ja.lathato[ja.ules])
    # a két kezünk az ütés elején (a már letett lapunkkal együtt)
    kezek = {felv: set(X), aszt: set(Y)}
    for u, l in akt:
        if u in kezek:
            kezek[u].add(l)
    if len(akt) == 1:
        f, miert = utes_fajta(kezek[felv], kezek[aszt], hivott, ja.adu)
        if f == NINCS_DONTES:
            sajat = sorted((l for l in kez if l.szin == hivott.szin), key=lambda l: l.rang)
            if sajat and sajat[0] in ja.legalis:
                return TervDontes(sajat[0], "Nincs döntés: a legkisebb lap.", 0.9,
                                  {"trick_kind": "nincs_dontes"})
            return None
    a = UtesAllas(felv, ja.adu, kezek, set(kint), hivo, hivott, cel, hatra, korl,
                  utes_eddig=list(akt[1:]))
    ut = UtesTervezo(a, naplo=naplo)
    ut.megallito = megallito
    ert = ut.tervez()
    if not ert:
        return None
    v = ert[0]
    lep = v.lepesek.get(ja.ules)
    if lep is None:
        return None
    if lep.fajta == "lap":
        lap = lep.lap
    else:
        lap = _mi_lap(kez, lep, list(akt), ja.adu, kovetkezo_ules(ja.ules, 2), len(akt))
    if lap not in ja.legalis:
        return None
    return TervDontes(lap, f"Ütés közbeni terv: {v.szoveg()} ({v.ertek:.0%}).",
                      0.5 + 0.45 * v.ertek,
                      {"trick_plan": v.szoveg(), "chance": round(v.ertek, 3),
                       "positions_planned": ut.tervezesek})
