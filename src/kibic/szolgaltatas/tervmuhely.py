"""
A kibic tervműhelye: `POST /v1/bridge/plan` és `POST /v1/bridge/step` (2026-11-18).

Az MB tanári asztalához, lépésenkénti vizsgálatra — a BridzsRobot tervműhelyének
szerződése szerint (docs/TERVMUHELY_API.md), hogy az MB ugyanúgy hívhassa:

  * a kérés a `/play` borítéka (látható kezek, lejátszás, legális lapok);
  * `/plan`: a felvevő játékterve (a tervkönyvelő, `motor/tervkonyvelo.py`) — a
    jelölt tervek esélye sorsolt világokon, DD-védők ellen, a választott terv
    egységei és körei; lapot nem ad (`action: null`);
  * `/step`: a terv következő lapja és az indoka (melyik egység melyik köre,
    átmenet, adukör, megfigyelés). Ha az aktív terv hiányzik, vagy a
    lejátszás nem a folytatása, előbb újratervez (mint Robi „combined” módja).

A terv a parti felvevőjéhez tartozik (az asztal lapjai is az övé): kulcsa a
mérkőzés, az asztal, a parti és a felvevő — az MB-nek nem kell azonosítót
tárolnia. A terv fájlban van (`KIBIC_TERVMUHELY_TAR`, partinként egy JSON és egy
olvasható HTML), így a kibic újraindítás után is folytatja.

A lépéskérés menete (a szerkesztő, 2026-11-18):
  1. azonosítás; ha nincs terv (vagy más a leosztás, vagy a lejátszás nem a
     folytatása): új terv, és a fájlba kerül;
  2. ha a parti a terv szerint halad: a terv lapja;
  3. eltérés — egy védő kimutat (új színhiány), a mi oldalunkon nem a javasolt
     lap ment le, vagy a terv egysége elakad (nincs átmenet): újratervezés;
  4. ha a terv minden világban teljesít, és a biztos terítés is megvan: terít
     (`meta.kibic.claim`, mint a /play-nél);
  5. ha nincs megoldás (egyik terv sem teljesít egyik világban sem, vagy a terv
     lapja nem szabályos): a kibic általános lejátszója ad lapot (tartalék).

Csak a felvevő oldalán (felvevő vagy asztal) tervez; védőként `unsupported_position`.
"""
from __future__ import annotations

import html
import json
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..domain import Lap, Leosztas, kovetkezo_ules, vonal
from ..domain.kartya import Kez
from ..motor import lejatszas as lj
from ..motor import tervjatszo as tj
from ..motor.tervellenorzo import vilagok
from ..motor.tervkonyvelo import Eredmeny, KTerv, Vegrehajto, lejatszik, tervjeloltek
from ..motor.tervsema import Allas, technikak_betoltese
from ..motor.tervszamolo import Korlat

PROTOKOLL = "bridzsrobot.workbench/1.0"       # a tervműhely-válasz alakja (Robiéval azonos)
VILAG = int(os.getenv("KIBIC_TERVMUHELY_VILAG", "60"))
ARANY = float(os.getenv("KIBIC_TERVMUHELY_ARANY", "0.45"))
# újratervezéskor a régi terv marad, ha az új legjobb ennél kevesebbel jobb (ugyanazokon a
# világokon): a mintavétel zaja ne ugráltassa a tervet
TURES = float(os.getenv("KIBIC_TERVMUHELY_TURES", "0.05"))
# hibrid döntés (a problémaleírás 7. peremfeltétele): ha a legjobb terv esélye ennyivel
# elmarad a DD-felső határtól (a mindent látó felvevő aránya ugyanazokon a világokon),
# a technikák nem fedik a partit — a kibic általános lejátszója dönt. 1: kikapcsolva.
HIBRID = float(os.getenv("KIBIC_TERVMUHELY_HIBRID", "0.25"))
TAR = Path(os.getenv("KIBIC_TERVMUHELY_TAR", str(Path.home() / ".cache" / "kibic" / "tervmuhely")))
SZIN = dict(zip("SHDC", "♠♥♦♣"))
KEZ_NEV = {"N": "Észak", "E": "Kelet", "S": "Dél", "W": "Nyugat"}


class MuhelyHiba(ValueError):
    def __init__(self, status: str, uzenet: str):
        super().__init__(uzenet)
        self.status = status


@dataclass
class Rekord:
    plan_id: str
    revizio: int
    terv: KTerv
    eredmenyek: list[Eredmeny]
    lejatszott: list[tuple[str, Lap]]         # a tervezés pillanatáig
    kezek: dict[str, set[Lap]]                # a felvevő és az asztal teljes keze
    felvevo: str
    kontraktus: object
    vilag: int
    ido_s: float
    naplo: list[str] = field(default_factory=list)
    dd_felso: float | None = None             # a mindent látó felvevő teljesítése ugyanott


_ZAR = threading.Lock()


# --- a terv fájlja ------------------------------------------------------------------------

def _fajlnev(kulcs: tuple) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", "_".join(str(x) for x in kulcs)).strip("-") or "terv"


def _lapok(xs) -> list[str]:
    return [str(l) for l in sorted(xs, key=str)]


def ment(kulcs: tuple, rek: Rekord, ok: str, html_nezet: str | None = None) -> None:
    """A terv a fájlba (atomi írással); a korábbi tervek okai a `tortenet`-ben maradnak."""
    TAR.mkdir(parents=True, exist_ok=True)
    ut = TAR / (_fajlnev(kulcs) + ".json")
    tortenet = []
    try:
        tortenet = json.loads(ut.read_text(encoding="utf-8")).get("tortenet", [])
    except (OSError, ValueError):
        pass
    tortenet.append({"revizio": rek.revizio, "ok": ok, "ido": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "utes": len(rek.lejatszott) // 4 + 1, "terv": rek.terv.nev,
                     "esely": round(rek.eredmenyek[0].esely, 3) if rek.eredmenyek else None,
                     "dd_felso": None if rek.dd_felso is None else round(rek.dd_felso, 3)})
    adat = {"kulcs": list(kulcs), "plan_id": rek.plan_id, "revizio": rek.revizio,
            "felvevo": rek.felvevo,
            "kontraktus": {"szint": rek.kontraktus.szint, "szin": rek.kontraktus.szin,
                           "kontra": rek.kontraktus.kontra},
            "kezek": {u: _lapok(x) for u, x in rek.kezek.items()},
            "lejatszott": [[u, str(l)] for u, l in rek.lejatszott],
            "terv": {"nev": rek.terv.nev, "egysegek": [[p.sema.azon, p.szin] for p in rek.terv.lepesek]},
            "jeloltek": [{"nev": r.terv.nev, "egysegek": [[p.sema.azon, p.szin] for p in r.terv.lepesek],
                          "esely": round(r.esely, 4), "n": r.n, "utesek": r.utesek}
                         for r in rek.eredmenyek],
            "vilag": rek.vilag, "ido_s": round(rek.ido_s, 2), "dd_felso": rek.dd_felso,
            "tortenet": tortenet}
    tmp = ut.with_suffix(".tmp")
    tmp.write_text(json.dumps(adat, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ut)
    if html_nezet:
        (TAR / (_fajlnev(kulcs) + ".html")).write_text(html_nezet, encoding="utf-8")


def betolt(kulcs: tuple, h: "Helyzet") -> Rekord | None:
    """A fájlból a terv; a technikák példányait a tervezés pillanatának lapjain
    újra előállítja (a sémák adatok: a fájlban csak a nevük van)."""
    ut = TAR / (_fajlnev(kulcs) + ".json")
    try:
        adat = json.loads(ut.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        kezek = {u: {Lap.parse(x) for x in xs} for u, xs in adat["kezek"].items()}
        lejatszott = [(u, Lap.parse(x)) for u, x in adat["lejatszott"]]
    except (KeyError, ValueError):
        return None
    if adat.get("felvevo") != h.felvevo or kezek != {u: h.kezek[u] for u in (h.felvevo, h.asztal)}:
        return None
    pld = {(p.sema.azon, p.szin): p for p in _peldanyok(h, lejatszott)}

    def terv(egysegek):
        try:
            return KTerv([pld[(a, sz)] for a, sz in egysegek])
        except KeyError:
            return None
    fo = terv(adat["terv"]["egysegek"])
    if fo is None:
        return None
    ered = []
    for x in adat.get("jeloltek", []):
        t = terv(x["egysegek"])
        if t is None:
            continue
        if t.nev == fo.nev:
            t = fo
        r = Eredmeny(t, teljesult=round(x["esely"] * x["n"]), n=x["n"], utesek=x["utesek"])
        ered.append(r)
    if not ered or ered[0].terv is not fo:
        ered.insert(0, Eredmeny(fo))
    return Rekord(adat["plan_id"], adat["revizio"], fo, ered, lejatszott, kezek, h.felvevo,
                  h.kontraktus, adat.get("vilag", 0), adat.get("ido_s", 0.0),
                  dd_felso=adat.get("dd_felso"))


def _lap(l: Lap) -> str:
    return f"{SZIN[l.szin]}{'10' if l.ertek == 'T' else l.ertek}"


_LAPMINTA = re.compile(r"\b([SHDC])([2-9TJQKA])\b")


def _szep(s: str) -> str:
    """A naplóban a lapok (HJ, DT) jelekkel: ♥J, ♦10."""
    return _LAPMINTA.sub(lambda m: SZIN[m.group(1)] + ("10" if m.group(2) == "T" else m.group(2)), s)


def _kulcs(keres: dict, felvevo: str) -> tuple:
    g = keres.get("game") or {}
    return (str(g.get("match_id")), g.get("table_index"), g.get("board_number"), felvevo)


# --- a kérésből: a látott helyzet -------------------------------------------------------

@dataclass
class Helyzet:
    allas_mb: object                       # lj.JatekAllas
    felvevo: str
    asztal: str
    kontraktus: object
    adu: str | None
    lejatszott: list[tuple[str, Lap]]
    kezek: dict[str, set[Lap]]             # a felvevő és az asztal TELJES keze (13 lap)
    vedok: tuple[str, str]


def helyzet(keres: dict) -> Helyzet:
    try:
        a = lj.allas_keresbol(keres)
    except lj.LejatszasHiba as e:
        raise MuhelyHiba("invalid_request", str(e)) from e
    F = a.felvevo
    A = a.asztal
    if vonal(a.ules) != vonal(F):
        raise MuhelyHiba("unsupported_position",
                         "A kibic tervműhelye a felvevő oldalán tervez; védőként nincs terve.")
    if F not in a.lathato or A not in a.lathato:
        raise MuhelyHiba("no_plan", "A terv az indulás után készül, amikor az asztal már látszik.")
    kezek = {}
    for u in (F, A):
        kezek[u] = set(a.lathato[u]) | {l for uu, l in a.lejatszott if uu == u}
        if len(kezek[u]) != 13:
            raise MuhelyHiba("invalid_request", f"{KEZ_NEV[u]} keze nem 13 lap ({len(kezek[u])})")
    vedok = (kovetkezo_ules(F, 1), kovetkezo_ules(F, 3))
    return Helyzet(a, F, A, a.kontraktus, a.adu, list(a.lejatszott), kezek, vedok)


def _jatek(h: Helyzet, lejatszott: list) -> tj.Jatek:
    kezek = {u: set(h.kezek[u]) for u in (h.felvevo, h.asztal)}
    kezek.update({u: set() for u in h.vedok})
    return tj.Jatek(kezek, h.felvevo, h.adu, list(lejatszott), tj.Terv(()))


def _szinhianyok(lejatszott: list, vedok) -> list[Korlat]:
    ki = set()
    for i in range(0, len(lejatszott), 4):
        utes = lejatszott[i:i + 4]
        hivott = utes[0][1].szin
        for u, l in utes[1:]:
            if u in vedok and l.szin != hivott:
                ki.add((u, hivott))
    return [Korlat(u, sz, 0, 0, "megfigyelt") for u, sz in sorted(ki)]


# --- tervezés -------------------------------------------------------------------------

def _allas(h: Helyzet, lejatszott: list) -> tuple[Allas, set[Lap]]:
    j = _jatek(h, lejatszott)
    cel = 6 + h.kontraktus.szint
    lement = {l for _, l in lejatszott}
    mieink = h.kezek[h.felvevo] | h.kezek[h.asztal]
    kint = {Lap.parse(s + r) for s in "SHDC" for r in "23456789TJQKA"} - mieink - lement
    allas = Allas(felvevo=h.felvevo, adu=h.adu,
                  kezek={u: set(j.kezek[u]) for u in (h.felvevo, h.asztal)}, kint=kint,
                  cel=max(0, cel - j.felvevo_utesek()), hatra=13 - len(lejatszott) // 4,
                  soron=j.soron())
    return allas, kint


def _peldanyok(h: Helyzet, lejatszott: list):
    from ..motor.tervsema import peldanyok
    return peldanyok(_allas(h, lejatszott)[0], technikak_betoltese())


def tervez(h: Helyzet, dd_fv, hatarido_s: float, vilag_db: int | None = None,
           elozo: list | None = None) -> Rekord:
    t0 = time.time()
    vilag_db = vilag_db or VILAG
    cel = 6 + h.kontraktus.szint
    allas, kint = _allas(h, h.lejatszott)
    tervek = tervjeloltek(allas, technikak_betoltese())
    # a világok: a kint lévő lapok a két védő között, a megfigyelt színhiányokkal
    v1, v2 = sorted(h.vedok)
    jatszott_v = {u: {l for uu, l in h.lejatszott if uu == u} for u in (v1, v2)}
    kint_l = sorted(kint, key=str)
    n1 = 13 - len(jatszott_v[v1])
    alap = {h.felvevo: Kez(frozenset(h.kezek[h.felvevo])), h.asztal: Kez(frozenset(h.kezek[h.asztal])),
            v1: Kez(frozenset(set(kint_l[:n1]) | jatszott_v[v1])),
            v2: Kez(frozenset(set(kint_l[n1:]) | jatszott_v[v2]))}
    lo = Leosztas(alap)
    k = h.kontraktus
    vl = vilagok(lo, h.lejatszott, kint, vilag_db, _szinhianyok(h.lejatszott, h.vedok),
                 mag=len(h.lejatszott) + 1, vedok=(v1, v2))
    ered = [Eredmeny(t) for t in tervek]
    tar = tj.DDTar(dd_fv, k)
    keret = max(1.0, hatarido_s - (time.time() - t0))
    hasznalt = 0
    dd_tel = 0
    jatek0 = _jatek(h, h.lejatszott)
    mi_jon = jatek0.mi(jatek0.soron())
    for i, w in enumerate(vl):
        if i >= 8 and time.time() - t0 > keret:
            break                                # a határidő: az eddigi világok döntenek
        hasznalt += 1
        dd = tar(i, w, h.lejatszott)
        ossz = [e.felvevo_osszesen for e in dd]
        dd_tel += (max(ossz) if mi_jon else min(ossz)) >= cel
        for r in ered:
            def dd_vedo(jj, i=i, w=w):
                return tj._vedo_lap(tar(i, w, jj.lapok))
            n = lejatszik(r.terv, w, h.felvevo, h.adu, h.lejatszott, dd_vedo, cel=cel)
            r.n += 1
            r.utesek += n
            r.teljesult += n >= cel
    ered.sort(key=lambda r: (-r.esely, -(r.utesek / r.n if r.n else 0), len(r.terv.lepesek)))
    if elozo is not None:
        # a régi terv (az egységei szerint) marad, ha nem érezhetően rosszabb
        for i, r in enumerate(ered):
            if [[p.sema.azon, p.szin] for p in r.terv.lepesek] == elozo:
                if i and r.esely >= ered[0].esely - TURES:
                    ered.insert(0, ered.pop(i))
                break
    return Rekord(uuid.uuid4().hex, 1, ered[0].terv, ered, list(h.lejatszott),
                  {u: set(h.kezek[u]) for u in (h.felvevo, h.asztal)}, h.felvevo, k, hasznalt,
                  time.time() - t0, dd_felso=dd_tel / hasznalt if hasznalt else None)


def _dd_fv(dd_zar):
    from ..solver import dds

    def fv(lo, jatszott, k):
        if dd_zar is None or dds.parhuzamos():
            return dds.lap_elemzes(lo, jatszott, k)
        with dd_zar:
            return dds.lap_elemzes(lo, jatszott, k)
    return fv


def _hatarido_s(keres: dict) -> float:
    return int(keres.get("deadline_ms") or 60000) / 1000 * ARANY


# --- a végrehajtó a mostani állásig ----------------------------------------------------

def vegrehajto(rek: Rekord, h: Helyzet) -> tuple[Vegrehajto, tj.Jatek, list[str]]:
    """A terv végrehajtója a tervezés pillanatától a mostani állásig: a lement
    lapokon végigmegy (a saját döntéseit is meghozza, hogy az egységek állapota a
    megfigyelés szerint haladjon). Vissza: a végrehajtó, a játék, és az eltérések
    (a mi oldalunkon nem a javasolt lap ment le)."""
    j = _jatek(h, rek.lejatszott)
    v = Vegrehajto(rek.terv, j, naplo=[])
    v.cel = 6 + rek.kontraktus.szint
    elteresek = []
    for u, l in h.lejatszott[len(rek.lejatszott):]:
        if j.mi(u):
            javasolt = v.lap(u)
            if javasolt != l:
                elteresek.append(f"{len(j.lapok) // 4 + 1}. ütés: a javaslat {_lap(javasolt)} volt, "
                                 f"{_lap(l)} ment le")
                v.naplo.append(elteresek[-1])
                if v.folyo is not None and v.folyo[2] == len(j.lapok):
                    v.folyo = None
                v.szandek = {}
        j.tesz(u, l)
    return v, j, elteresek


def kimutatasok(rek: Rekord, h: Helyzet) -> list[str]:
    """A terv óta megfigyelt új színhiányok (egy védő nem adott színt)."""
    regi = {(k.kez, k.szin) for k in _szinhianyok(rek.lejatszott, h.vedok)}
    return [f"{KEZ_NEV[k.kez]} nem adott {SZIN[k.szin]}-t"
            for k in _szinhianyok(h.lejatszott, h.vedok) if (k.kez, k.szin) not in regi]


# --- a válaszok -------------------------------------------------------------------------

def _alap_valasz(keres: dict, muvelet: str, status: str, summary: str) -> dict:
    return {"protocol": PROTOKOLL, "request_id": keres.get("request_id"), "operation": muvelet,
            "status": status, "summary": summary, "plan_id": None, "plan_revision": None,
            "action": None, "execution": "proposal_only",
            "limitations": KORLATOK, "meta": {"pipeline": "kibic_tervmuhely", "source": "model"}}


KORLATOK = [
    "Első változat (2026-11-18): a terv egy- vagy kételemű esélysor a technikasémákból "
    "(ejtés, impassz, lopásos kimagasítás, lopás a rövid kézben).",
    "Az esély sorsolt világokon, mindent látó (DD) védők ellen; a licitből nem következtet.",
    "Beszorítást, végjátékot, kiengedést még nem tervez; az átmeneteket körről körre "
    "választja (még nincs előrenézés).",
]


def _html(cim: str, reszek: list[tuple[str, str]]) -> dict:
    stilus = ("body{font:16px/1.5 system-ui;margin:1.5rem auto;padding:0 1rem;max-width:900px;"
              "background:#f6f5f0;color:#1d2b26}h1{font-size:1.4rem}h2{font-size:1.1rem;margin:0 0 .5rem}"
              "section{background:#fff;border:1px solid #d5d9d0;border-radius:10px;padding:.8rem 1rem;"
              "margin:.8rem 0}table{border-collapse:collapse}td,th{padding:.2rem .6rem;text-align:left;"
              "border-bottom:1px solid #eee}.lap{font-size:1.8rem;font-weight:700}.halv{color:#667}")
    test = "".join(f"<section><h2>{html.escape(c)}</h2>{t}</section>" for c, t in reszek)
    doc = (f"<!doctype html><html lang=\"hu\"><meta charset=\"utf-8\"><title>{html.escape(cim)}</title>"
           f"<style>{stilus}</style><body><h1>{html.escape(cim)}</h1>{test}</body></html>")
    return {"title": cim, "format": "html", "html": doc}


def _helyzet_html(h: Helyzet, rek: Rekord) -> str:
    j = _jatek(h, rek.lejatszott)
    cel = 6 + rek.kontraktus.szint
    kesz = len(rek.lejatszott) // 4
    k = rek.kontraktus
    sor = (f"<p>{k.szint}{'NT' if k.szin == 'NT' else SZIN[k.szin]} {KEZ_NEV[rek.felvevo]}ról. "
           f"Kell: {cel} ütés; eddig {kesz} ütés ment le, ebből {j.felvevo_utesek()} a miénk.</p>")
    kezek = "".join(
        f"<p><b>{KEZ_NEV[u]}</b>: " + " ".join(
            SZIN[sz] + "".join(('10' if l.ertek == 'T' else l.ertek)
                               for l in sorted(j.kezek[u], key=lambda x: -x.rang) if l.szin == sz)
            for sz in "SHDC") + "</p>" for u in (rek.felvevo, kovetkezo_ules(rek.felvevo, 2)))
    return sor + kezek


def _hibrid(rek: Rekord) -> bool:
    if rek.dd_felso is None or not rek.eredmenyek or HIBRID >= 1:
        return False
    return rek.eredmenyek[0].esely < rek.dd_felso - HIBRID


def _terv_html(rek: Rekord) -> str:
    sorok = "".join(
        f"<tr><td>{'➜ ' if r.terv is rek.terv else ''}{html.escape(_szep(r.terv.nev))}</td>"
        f"<td>{100 * r.esely:.0f}%</td><td>{(r.utesek / r.n if r.n else 0):.2f}</td></tr>"
        for r in rek.eredmenyek[:12])
    return (f"<table><tr><th>Terv (esélysor)</th><th>Teljesít</th><th>Átlag ütés</th></tr>{sorok}</table>"
            f"<p class=\"halv\">{rek.vilag} sorsolt világ, DD-védők ellen; {rek.ido_s:.1f} s. "
            + (f"A mindent látó (DD) felvevő ugyanezeken a világokon {100 * rek.dd_felso:.0f}%-ot teljesít."
               if rek.dd_felso is not None else "") + "</p>"
            + (f"<p><b>A terv messze elmarad a DD-felső határtól</b> (több mint {100 * HIBRID:.0f} pont): "
               "a technikák nem fedik ezt a partit; a lépéskérésre a kibic általános lejátszója ad lapot.</p>"
               if _hibrid(rek) else ""))


def _egysegek_html(terv: KTerv, v: Vegrehajto | None = None) -> str:
    if not terv.lepesek:
        return "<p>Nincs technika: a nyerők begyűjtése (adukör, ha kell).</p>"
    allapot = {"var": "vár", "siker": "sikerült", "kudarc": "nem sikerült", "elmarad": "elmarad",
               "kesz": "kész"}
    ki = "<ol>"
    for i, p in enumerate(terv.lepesek):
        e = v.egysegek[i] if v is not None else None
        korok = []
        for n, k in enumerate(p.korok):
            t = {"lehiv": "lehívás", "impassz": "impassz", "lop": "lopás"}.get(k.fajta, k.fajta)
            if k.lap is not None:
                t += f" {_lap(k.lap)}"
            if k.hivo:
                t += f" ({KEZ_NEV[k.hivo]} hív)"
            if k.csak_ha_siker:
                t += ", ha sikerült"
            if e is not None and n < e.i:
                t = f"<s>{t}</s>"
            korok.append(t)
        siker = html.escape(str(p.sema.siker))
        all_ = f" — <b>{allapot.get(e.allapot, e.allapot)}</b>" if e is not None else ""
        ki += (f"<li><b>{html.escape(p.rovid)}</b>{all_}<br>"
               f"<span class=\"halv\">{html.escape(p.sema.nev)}</span><br>"
               f"körök: {'; '.join(korok)}<br><span class=\"halv\">feltétel (rejtett): {siker}"
               f"{'; kudarca egy ütés' if p.sema.kudarc_koltseg else ''}</span></li>")
    return ki + "</ol><p class=\"halv\">Ha egy egység sikerült, a többi elmarad; ha nem, a következő jön. " \
                "Az átmeneteket és az aduköröket a végrehajtó körről körre illeszti be.</p>"


def _uj_terv(keres: dict, h: Helyzet, kulcs: tuple, dd_zar, ok: str,
             elozo: Rekord | None = None) -> Rekord:
    regi_egysegek = [[p.sema.azon, p.szin] for p in elozo.terv.lepesek] if elozo is not None else None
    rek = tervez(h, _dd_fv(dd_zar), _hatarido_s(keres), elozo=regi_egysegek)
    with _ZAR:
        regi = betolt(kulcs, h)
        if regi is not None:
            rek.revizio = regi.revizio + 1
            rek.plan_id = regi.plan_id
        ment(kulcs, rek, ok, _terv_nezet(h, rek)["html"])
    return rek


def _felmeres_html(h: Helyzet, rek: Rekord) -> str:
    from ..motor.tervfelmeres import felmeres_jatekbol
    f = felmeres_jatekbol(_jatek(h, rek.lejatszott), 6 + rek.kontraktus.szint)
    sorok = "".join(
        f"<tr><td>{SZIN[s.szin]}</td><td>{s.mi[0]}–{s.mi[1]}</td><td>{s.kint}</td><td>{s.biztos}</td>"
        f"<td>{s.kiado}</td>" + (f"<td>{s.vesztok:.1f} ({s.vesztok_max})</td>" if f.adu else "") + "</tr>"
        for s in f.szinek)
    fej = ("<tr><th>Szín</th><th>Mi (felvevő–asztal)</th><th>Kint</th><th>Biztos ütés</th>"
           "<th>Biztosan kiadó</th>" + ("<th>Vesztő a fő kézből (legrosszabb)</th>" if f.adu else "") + "</tr>")
    return (f"<table>{fej}{sorok}</table>"
            + "".join(f"<p>{html.escape(x.replace(f.fo_kez or '~', KEZ_NEV.get(f.fo_kez, '')) if f.fo_kez else x)}</p>"
                      for x in f.sorok())
            + "<p class=\"halv\">A vesztők elosztásonként, a felső lapokkal lejátszva (impassz és lopás "
              "nélkül); a biztosan kiadó: a kint lévő lapok a legnagyobb lapunk fölött.</p>")


def _felmeres_adat(h: Helyzet, rek: Rekord) -> dict:
    from ..motor.tervfelmeres import felmeres_jatekbol
    f = felmeres_jatekbol(_jatek(h, rek.lejatszott), 6 + rek.kontraktus.szint)
    return {"needed": f.cel, "remaining": f.hatra, "sure_tricks": f.biztos, "missing": f.hiany,
            "allowed_losers": f.megengedett, "sure_losers": f.kiado, "balance": f.egyenleg,
            "expected_losers": round(f.vesztok, 2) if f.adu else None,
            "suits": {s.szin: {"sure_tricks": s.biztos, "sure_losers": s.kiado,
                               "expected_losers": round(s.vesztok, 2)} for s in f.szinek}}


def _terv_nezet(h: Helyzet, rek: Rekord) -> dict:
    return _html("kibic — játékterv", [
        ("A helyzet", _helyzet_html(h, rek)),
        ("A helyzetfelmérés", _felmeres_html(h, rek)),
        ("A jelölt tervek", _terv_html(rek)),
        ("A választott terv egységei", _egysegek_html(rek.terv)),
        ("Korlátok", "<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in KORLATOK) + "</ul>")])


def plan_valasz(keres: dict, dd_zar=None) -> dict:
    try:
        h = helyzet(keres)
    except MuhelyHiba as e:
        return _alap_valasz(keres, "plan", e.status, str(e))
    kulcs = _kulcs(keres, h.felvevo)
    rek = _uj_terv(keres, h, kulcs, dd_zar, "tervkérés (/plan)")
    legjobb = rek.eredmenyek[0]
    v = _alap_valasz(keres, "plan", "planned" if legjobb.esely > 0 else "no_plan",
                     _szep(f"Terv: {rek.terv.nev} — {100 * legjobb.esely:.0f}% ({rek.vilag} világ"
                           + (f"; a mindent látó felvevő {100 * rek.dd_felso:.0f}%" if rek.dd_felso is not None else "")
                           + "). "
                           + ("A terv messze elmarad ettől: a lépéskérésre a kibic általános lejátszója ad lapot."
                              if _hibrid(rek) else "Lapot a lépéskérés ad.")) if legjobb.esely > 0 else
                     "Egyik terv sem teljesít egyik sorsolt világban sem; a lépéskérésre a kibic "
                     "általános lejátszója ad lapot.")
    v.update(plan_id=rek.plan_id, plan_revision=rek.revizio, analysis_result="new_plan",
             plan=_terv_adat(rek), assessment=dict(_jeloltek_adat(rek), situation=_felmeres_adat(h, rek)),
             presentation=_terv_nezet(h, rek))
    v["meta"]["elapsed_ms"] = int(rek.ido_s * 1000)
    return v


def _terv_adat(rek: Rekord) -> dict:
    return {"name": _szep(rek.terv.nev), "units": [p.nev for p in rek.terv.lepesek],
            "probability": round(rek.eredmenyek[0].esely, 3) if rek.eredmenyek else None,
            "dd_upper_bound": None if rek.dd_felso is None else round(rek.dd_felso, 3),
            "hybrid_fallback": _hibrid(rek), "worlds": rek.vilag}


def _jeloltek_adat(rek: Rekord) -> dict:
    return {"candidates": [{"name": _szep(r.terv.nev), "probability": round(r.esely, 3),
                            "mean_tricks": round(r.utesek / r.n, 2) if r.n else None}
                           for r in rek.eredmenyek]}


def step_valasz(keres: dict, dd_zar=None, tartalek_fv=None) -> dict:
    """A lépéskérés (a modul leírásának 1–5. pontja). `tartalek_fv(keres)`: a kibic
    általános lejátszója (a /play döntése), ha a tervnek nincs lapja."""
    t0 = time.time()
    try:
        h = helyzet(keres)
    except MuhelyHiba as e:
        return _alap_valasz(keres, "step", e.status, str(e))
    kulcs = _kulcs(keres, h.felvevo)
    rek = betolt(kulcs, h)
    ok = None
    if rek is None:
        ok = "nincs terv ehhez a partihoz"
    elif h.lejatszott[:len(rek.lejatszott)] != rek.lejatszott:
        ok = "a lejátszás nem a terv folytatása"
    else:
        v, j, elteresek = vegrehajto(rek, h)
        km = kimutatasok(rek, h)
        tartalekban = _hibrid(rek) or not rek.eredmenyek or rek.eredmenyek[0].esely <= 0
        if km:
            ok = "kimutatás: " + ", ".join(km)
        elif elteresek and not tartalekban:
            # ha a tartalék játszik, a terv lapjától való eltérés várható: nem ok újratervezésre
            ok = "eltérés a tervtől: " + elteresek[-1]
    if ok is not None:
        folytat = rek is not None and h.lejatszott[:len(rek.lejatszott)] == rek.lejatszott
        rek = _uj_terv(keres, h, kulcs, dd_zar, ok, rek if folytat else None)
        v, j, _ = vegrehajto(rek, h)
    u = j.soron()
    if not j.mi(u):
        return _alap_valasz(keres, "step", "stale_state", "Most nem a felvevő oldala következik.")
    elotte = len(v.naplo)
    lap = v.lap(u)
    if ok is None and any("nem játszható" in x for x in v.naplo[elotte:]):
        ok = "a terv egysége elakadt: " + _szep(next(x for x in v.naplo[elotte:] if "nem játszható" in x))
        rek = _uj_terv(keres, h, kulcs, dd_zar, ok)
        v, j, _ = vegrehajto(rek, h)
        elotte = len(v.naplo)
        lap = v.lap(u)
    indok = v.naplo[elotte:]
    legalis = h.allas_mb.legalis
    esely = rek.eredmenyek[0].esely if rek.eredmenyek else 0.0
    if esely <= 0 or lap not in legalis or _hibrid(rek):
        if esely <= 0:
            miert = "egyik terv sem teljesít egyik sorsolt világban sem"
        elif lap not in legalis:
            miert = f"a terv lapja ({_lap(lap)}) itt nem szabályos"
        else:
            miert = (f"a terv ({100 * esely:.0f}%) messze elmarad a mindent látó felvevőtől "
                     f"({100 * rek.dd_felso:.0f}%): a technikák nem fedik ezt a partit")
        ki = _tartalek(keres, tartalek_fv, miert)
    else:
        szoveg = _szep("; ".join(s.split(": ", 1)[1] if ": " in s else s for s in indok)) or "a terv szerint"
        ki = _alap_valasz(keres, "step", "action_available",
                          f"{_lap(lap)} — {szoveg}" + (f" (új terv: {_szep(ok)})" if ok else ""))
        ki["action"] = {"type": "play", "card": legalis[lap]}
        if esely >= 1.0 and not j.aktualis():
            claim = _terites(h)
            if claim is not None:
                ki.setdefault("meta", {}).setdefault("kibic", {})["claim"] = claim
                ki["summary"] += f" — terítés: {claim['statement']}"
    ki.update(plan_id=rek.plan_id, plan_revision=rek.revizio,
              analysis_result="existing_plan" if ok is None else "new_plan",
              replan_reason=ok, plan=_terv_adat(rek),
              observation={"log": [_szep(x) for x in v.naplo[-30:]]},
              presentation=_html("kibic — lépés", [
                  ("A javasolt lap", (f"<p class=\"lap\">{_lap(lap)}</p>" if ki.get("action") and
                                      ki["meta"].get("source") != "fallback" else "")
                   + "".join(f"<p>{html.escape(_szep(s))}</p>" for s in indok)
                   + (f"<p><b>Új terv:</b> {html.escape(_szep(ok))}</p>" if ok else "")),
                  ("A terv", f"<p><b>{html.escape(_szep(rek.terv.nev))}</b> — {100 * esely:.0f}%</p>"
                   + _egysegek_html(rek.terv, v)),
                  ("A napló", "<ol>" + "".join(f"<li>{html.escape(_szep(s))}</li>" for s in v.naplo) + "</ol>"),
                  ("A jelölt tervek", _terv_html(rek))]))
    ki["meta"]["elapsed_ms"] = int((time.time() - t0) * 1000)
    return ki


def _tartalek(keres: dict, tartalek_fv, miert: str) -> dict:
    """A kibic általános lejátszója ad lapot (a /play döntése)."""
    ki = _alap_valasz(keres, "step", "action_available", "")
    if tartalek_fv is None:
        ki.update(status="unsupported_continuation", summary=f"A tervnek nincs lapja: {miert}.")
        return ki
    v = tartalek_fv(keres)
    akcio = (v or {}).get("action") or {}
    ki["action"] = {"type": "play", "card": akcio.get("card")}
    ki["summary"] = f"{miert} — a kibic általános lejátszója dönt: {(v or {}).get('explanation') or ''}".strip()
    ki["meta"].update(source="fallback", fallback_reason=miert)
    claim = (((v or {}).get("meta") or {}).get("kibic") or {}).get("claim")
    if claim:
        ki["meta"]["kibic"] = {"claim": claim}
    return ki


def _terites(h: Helyzet) -> dict | None:
    """Terítés, ha a biztos terv (motor/terites.py) a felvételt teljesíti."""
    from ..motor.terites import szoveg, terites
    try:
        t = terites(h.allas_mb)
    except Exception:                           # noqa: BLE001
        return None
    if t is None or t.osszes < 6 + h.kontraktus.szint:
        return None
    return {"tricks": t.utesek, "remaining": t.hatralevo, "total_tricks": t.osszes,
            "statement": szoveg(t)}
