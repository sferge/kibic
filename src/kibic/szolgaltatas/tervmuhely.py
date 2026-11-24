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
from ..motor.tervkonyvelo import Eredmeny, KTerv, Vegrehajto, ertekel_lepcsos, lejatszik, szabad_helyek, tervjeloltek
from ..motor.tervsema import Allas, technikak_betoltese
from ..motor.tervszamolo import Korlat

PROTOKOLL = "bridzsrobot.workbench/1.0"       # a tervműhely-válasz alakja (Robiéval azonos)
VILAG = int(os.getenv("KIBIC_TERVMUHELY_VILAG", "60"))
ARANY = float(os.getenv("KIBIC_TERVMUHELY_ARANY", "0.45"))
# újratervezéskor a régi terv marad, ha az új legjobb ennél kevesebbel jobb (ugyanazokon a
# világokon): a mintavétel zaja ne ugráltassa a tervet
TURES = float(os.getenv("KIBIC_TERVMUHELY_TURES", "0.05"))
# hibrid döntés: ha a legjobb terv esélye ennyivel elmarad a DD-felső határtól (a mindent
# látó felvevő aránya ugyanazokon a világokon), a kibic általános lejátszója dönt. A
# tanári asztalon alapból KI (1): ott a tervet vizsgáljuk; tartalék csak akkor, ha nincs
# megoldás (a szerkesztő menete, 2026-11-18). Éles játékhoz a mérés dönt majd a küszöbről.
HIBRID = float(os.getenv("KIBIC_TERVMUHELY_HIBRID", "1"))
# a szimulációba ennyi terv megy (az előzetes, keresés nélküli esély szerint a legjobbak)
SZIM_TERV = int(os.getenv("KIBIC_TERVMUHELY_SZIM", "12"))
# TERV_MEGTARTAS (strategiak.yaml): kimutatásnál csak akkor új terv, ha a terv esélye csökkent
SZABALY_MEGTARTAS = os.getenv("KIBIC_K_TERV_MEGTARTAS", "1") != "0"
# FELBE_TERV (2026-11-24, BM A-11): ha az újratervezés egy ütés közepén történt (egy kimutatás
# vagy eltérés miatt, a hátralévő védő lapja előtt), az ütés végén újra tervezünk — a terv
# hiányos tudással készült (Nyugat kimutatott a ♦Q-ra; Kelet még ütheti a ♦Á-val, vagy
# kiengedi: a két helyzet terve más)
SZABALY_FELBE = os.getenv("KIBIC_K_FELBE_TERV", "1") != "0"
# HIVASRA_TETT_LAP (a szerkesztő, 2026-11-22, BM A-12): a védő hívására tett lapunk is a
# terv része — ha a választás a terv szempontjából számít, a tervek szimulációja dönt
SZABALY_HIVASRA = os.getenv("KIBIC_K_HIVASRA_TETT_LAP", "1") != "0"
# HIVASRA_TETT_LAP: a változatokat (a séma döntése, egy-egy lapunk, és a döntés nélküli
# alap) UGYANAZOKON a világokon, ugyanannyin vetjük össze (2026-11-22: eltérő világszámú
# becslések összevetése fantom-nyereséget adott), és legalább ennyi világ nyereség kell
UTES_VILAG = int(os.getenv("KIBIC_TERVMUHELY_UTES_VILAG", "20"))
# ... és a tervezéskor a legjobb ennyi jelölt terv (az előzetes értékelés szerint) fut velük
UTES_TERV = int(os.getenv("KIBIC_TERVMUHELY_UTES_TERV", "6"))
UTES_MIN_VILAG = int(os.getenv("KIBIC_TERVMUHELY_UTES_MIN_VILAG", "2"))
# IGENY_TOBBLET (strategiak.yaml; BM A-12): a jelöltek az igényre ÉS eggyel több forrásra
# is — a felmérés igénye becslés (A-12: igény 1, de a ♣-ból 2 ütés kell a ♦ eldobásához)
SZABALY_IGENY_TOBBLET = os.getenv("KIBIC_K_IGENY_TOBBLET", "1") != "0"
# LICIT_KENYSZER (strategiak.yaml; BM A-13, 2026-11-23): a világok a licit kényszertára
# szerint (amit a védők licitjei ígértek: hossz, pontsáv) — az ellentmondó világ csak
# LICIT_SULY eséllyel. A kényszertárat a szolgáltatás adja (LICIT_FV: a licitmotor és a
# rendszerek kellenek hozzá); ha nincs, a licit nem szűr.
SZABALY_LICIT = os.getenv("KIBIC_K_LICIT_KENYSZER", "1") != "0"
LICIT_SULY = float(os.getenv("KIBIC_LICIT_KENYSZER_SULY", "0.02"))
LICIT_FV = None          # (kérés, felvevő ülés) → {ülés: Igeret}; az api.py állítja be

# ELLENFEL_INDITASA (strategiak.yaml; a szerkesztő, 2026-11-22): az ellenvonal HÍVÁSAI a
# megállapodásuk szerintiek (a konvenciókártyájukon; ha nincs, rá lehet kérdezni) — ezekből
# olvasni kell. (A felvevő hívására adott lapjaikból nem: ott nincs következtetés.) Az
# indító lap: a sorozat teteje, a dubló felső lapja, háromból kicsi… (INDITAS_SULY), és
# színfelvétel ellen ász alól nem indulnak — ez szinte általános (ASZ_ALOL_SULY). Az
# ellentmondó világ csak ekkora eséllyel marad a mintában. A rendszer: az ellenfél
# `game.systems` szerinti rendszerének jelzésrendszere, ha nincs: KIBIC_ELLENFEL_JELZES.
SZABALY_INDITAS = os.getenv("KIBIC_K_ELLENFEL_INDITASA", "1") != "0"
INDITAS_SULY = float(os.getenv("KIBIC_ELLENFEL_INDITAS_SULY", "0.05"))
ASZ_ALOL_SULY = float(os.getenv("KIBIC_ELLENFEL_ASZ_ALOL_SULY", "0.01"))
ELLENFEL_JELZES = os.getenv("KIBIC_ELLENFEL_JELZES", "MOHA_STAND")
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
    # TERV_MEGTARTAS: a terv esélye a legutóbbi ellenőrzéskor (a látott lapokkal), és a
    # már ellenőrzött kimutatások (kéz, szín)
    esely_most: float | None = None
    ellenorzott: list = field(default_factory=list)
    # HIVASRA_TETT_LAP: a terv döntése a védő hívására tett lapjainkról a folyó ütésben —
    # [[index a lejátszásban, kéz, lap vagy KICSI, ok], ...] — és a döntés neve (pl. a
    # hozzátevési séma: „♠ Bath-csel”)
    utes_dontes: list | None = None
    utes_dontes_nev: str | None = None
    utes_megtart: list | None = None          # a séma megtartott lapjai (fogás), szövegként
    felbe: bool = False                       # FELBE_TERV: ütés közben, kimutatás / eltérés miatt készült


_ZAR = threading.Lock()


# --- a terv fájlja ------------------------------------------------------------------------

def _fajlnev(kulcs: tuple) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", "_".join(str(x) for x in kulcs)).strip("-") or "terv"


def _lapok(xs) -> list[str]:
    return [str(l) for l in sorted(xs, key=str)]


def _egysegek_lista(t: KTerv) -> list:
    """Egységenként: technika, szín, szakasz, a dobás színe; az elemzős színkezelésnél a
    cél (k ütés, legfeljebb m vesztés) is — ebből építjük újra a fájlból."""
    return [[p.sema.azon, p.szin, t.fazis[i] if t.fazis else None, p.szerepek.get("CELSZIN"),
             p.szerepek.get("k") if p.sema.fajta == "elemzo" else None,
             p.szerepek.get("m") if p.sema.fajta == "elemzo" else None]
            for i, p in enumerate(t.lepesek)]


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
                     "utes": len(rek.lejatszott) // 4 + 1, "terv": _terv_nev(rek),
                     "esely": round(rek.eredmenyek[0].esely, 3) if rek.eredmenyek else None,
                     "dd_felso": None if rek.dd_felso is None else round(rek.dd_felso, 3)})
    adat = {"kulcs": list(kulcs), "plan_id": rek.plan_id, "revizio": rek.revizio,
            "felvevo": rek.felvevo,
            "kontraktus": {"szint": rek.kontraktus.szint, "szin": rek.kontraktus.szin,
                           "kontra": rek.kontraktus.kontra},
            "kezek": {u: _lapok(x) for u, x in rek.kezek.items()},
            "lejatszott": [[u, str(l)] for u, l in rek.lejatszott],
            "terv": {"nev": rek.terv.nev, "egysegek": _egysegek_lista(rek.terv),
                     "igeny": rek.terv.igeny},
            "jeloltek": [{"nev": r.terv.nev, "egysegek": _egysegek_lista(r.terv),
                          "esely": round(r.esely, 4), "n": r.n, "utesek": r.utesek}
                         for r in rek.eredmenyek],
            "vilag": rek.vilag, "ido_s": round(rek.ido_s, 2), "dd_felso": rek.dd_felso,
            "esely_most": rek.esely_most, "ellenorzott": [list(x) for x in rek.ellenorzott],
            "utes_dontes": rek.utes_dontes, "utes_dontes_nev": rek.utes_dontes_nev,
            "utes_megtart": rek.utes_megtart, "felbe": rek.felbe,
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
    from ..motor.tervkonyvelo import szinkezeles_peldany
    allas0, _ = _allas(h, lejatszott)
    b1, b2 = kovetkezo_ules(h.felvevo, 1), kovetkezo_ules(h.felvevo, 3)
    ures0 = szabad_helyek(lejatszott, b1, b2)
    elemzos: dict = {}

    def elemzo_egyseg(sz, k, m):
        kulcs = (sz, k, m)
        if kulcs not in elemzos:
            elemzos[kulcs] = szinkezeles_peldany(allas0, technikak_betoltese(), sz, k, m, ures0,
                                                 esely_min=-1) \
                or szinkezeles_peldany(allas0, technikak_betoltese(), sz, k, m, ures0,
                                       esely_min=-1, biztonsagi=True)   # a biztonsági kezelés
        return elemzos[kulcs]

    ig = adat["terv"].get("igeny", 1)

    import dataclasses

    def terv(egysegek):
        lep = []
        for x in egysegek:
            if x[0] == "SZINKEZELES" and len(x) > 5:
                p = elemzo_egyseg(x[1], x[4], x[5])
            else:
                p = pld.get((x[0], x[1]))
            if p is None:
                return None
            lep.append(p)
        lep = [dataclasses.replace(p, szerepek=dict(p.szerepek, CELSZIN=x[3]))
               if len(x) > 3 and x[3] else p for p, x in zip(lep, egysegek)]
        fazis = tuple(x[2] for x in egysegek) if egysegek and all(len(x) > 2 and x[2] for x in egysegek) else None
        return KTerv(lep, ig, fazis, h.adu is not None)
    fo = terv(adat["terv"]["egysegek"])
    if fo is None:
        return None
    ered = []
    for x in adat.get("jeloltek", []):
        t = terv(x["egysegek"])
        if t is None:
            continue
        if t.nev == fo.nev and t.fazis == fo.fazis and _egysegek_lista(t) == _egysegek_lista(fo):
            t = fo
        r = Eredmeny(t, teljesult=round(x["esely"] * x["n"]), n=x["n"], utesek=x["utesek"])
        ered.append(r)
    if not ered or ered[0].terv is not fo:
        ered.insert(0, Eredmeny(fo))
    return Rekord(adat["plan_id"], adat["revizio"], fo, ered, lejatszott, kezek, h.felvevo,
                  h.kontraktus, adat.get("vilag", 0), adat.get("ido_s", 0.0),
                  dd_felso=adat.get("dd_felso"), esely_most=adat.get("esely_most"),
                  ellenorzott=[tuple(x) for x in adat.get("ellenorzott", [])],
                  utes_dontes=adat.get("utes_dontes") or ([list(adat["elso_lap"]) + [None]]
                                                          if adat.get("elso_lap") else None),
                  utes_dontes_nev=adat.get("utes_dontes_nev"), utes_megtart=adat.get("utes_megtart"),
                  felbe=bool(adat.get("felbe")))


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
    ellenfel_jelzes: str | None = None     # a védők jelzésrendszere (ELLENFEL_INDITASA)
    kenyszertar: dict | None = None        # a licit kényszertára (LICIT_KENYSZER): ülés → ígéret


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
    tar = None
    if SZABALY_LICIT and LICIT_FV is not None:
        try:
            tar = LICIT_FV(keres, F) or None
        except Exception:                        # noqa: BLE001 — nélküle a licit nem szűr
            tar = None
    return Helyzet(a, F, A, a.kontraktus, a.adu, list(a.lejatszott), kezek, vedok,
                   ellenfel_jelzes_kod(keres, F), tar)


def _jatek(h: Helyzet, lejatszott: list) -> tj.Jatek:
    kezek = {u: set(h.kezek[u]) for u in (h.felvevo, h.asztal)}
    kezek.update({u: set() for u in h.vedok})
    return tj.Jatek(kezek, h.felvevo, h.adu, list(lejatszott), tj.Terv(()))


_JELZ: dict = {}
GYOKER = Path(__file__).resolve().parents[3]


def ellenfel_jelzes_kod(keres: dict | None, felvevo: str) -> str:
    """Az ellenfél (a védők) jelzésrendszerének kódja: a `game.systems` szerinti
    rendszerük `jelzesek:` sora (rendszerek/yaml); ha nem ismert, KIBIC_ELLENFEL_JELZES."""
    try:
        from .profil import vonal_feloldas
        kod = vonal_feloldas(keres, felvevo).get("opponents_system")
    except Exception:                            # noqa: BLE001
        kod = None
    if kod:
        if "rsz" not in _JELZ:
            import yaml
            m = {}
            for f in sorted((GYOKER / "rendszerek" / "yaml").glob("*.yaml")):
                try:
                    d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
                    if isinstance(d, dict) and d.get("jelzesek") and isinstance(d.get("rendszer"), dict):
                        m[d["rendszer"].get("kod")] = d["jelzesek"]
                except Exception:                # noqa: BLE001
                    continue
            _JELZ["rsz"] = m
        if kod in _JELZ["rsz"]:
            return _JELZ["rsz"][kod]
    return ELLENFEL_JELZES


def _ellenfel_jelzesei(kod: str | None = None):
    """Egy jelzésrendszer (YAML), egyszer betöltve; None, ha nem érhető el."""
    kod = kod or ELLENFEL_JELZES
    if kod not in _JELZ:
        try:
            from ..motor import jelzes as jz
            if "osszes" not in _JELZ:
                _JELZ["osszes"] = jz.rendszerek_betolt([GYOKER / "rendszerek" / "jelzesek"])
            _JELZ[kod] = jz.jelzesek(kod, _JELZ["osszes"])
        except Exception:                        # noqa: BLE001 — nélküle egyenletes a minta
            _JELZ[kod] = None
    return _JELZ[kod]


def inditas_osszhang(w: Leosztas, lejatszott: list, adu: str | None, cache: dict | None = None,
                     kod: str | None = None) -> str | None:
    """ELLENFEL_INDITASA: az indító lap a megállapodás szerinti lap-e ebben a világban.
    "OK"; "ASZ_ALOL" (színfelvétel ellen az ász alól indult); "LAP" (a színből más lap
    jönne); None: nincs mit nézni (nincs rendszer, nincs rá sor)."""
    j = _ellenfel_jelzesei(kod)
    if not j or not lejatszott:
        return None
    u0, l0 = lejatszott[0]
    sor = tuple(l.ertek for l in sorted((l for l in w.kezek[u0].lapok if l.szin == l0.szin),
                                        key=lambda l: -l.rang))
    if adu is not None and "A" in sor and l0.szin != adu:
        # ász alól: kisebb lap, amely nem az ásszal kezdődő zárt sorozat tagja (ÁK-ból a K
        # nem ász alóli indulás)
        sorozat = set()
        for r, lr in zip("AKQJT98765432", sor):
            if r != lr:
                break
            sorozat.add(r)
        if l0.ertek not in sorozat:
            return "ASZ_ALOL"
    cache = {} if cache is None else cache
    kulcs = (sor, adu is None)
    if kulcs not in cache:
        try:
            cache[kulcs] = j.indito_lap(list(sor), "SZAN" if adu is None else "SZIN")[0]
        except Exception:                        # noqa: BLE001
            cache[kulcs] = None
    if cache[kulcs] is None:
        return None
    return "OK" if cache[kulcs] == l0.ertek else "LAP"


def _vilagok(lo: Leosztas, h: "Helyzet", kint: set, db: int, vedok: tuple) -> list:
    """A világok: a kint lévő lapok a két védő között, a megfigyelt színhiányokkal —
    és (ELLENFEL_INDITASA) az indító lappal ellentmondó világ csak kis eséllyel."""
    kor = _szinhianyok(h.lejatszott, h.vedok)
    mag = len(h.lejatszott) + 1
    kod = getattr(h, "ellenfel_jelzes", None)
    inditas = SZABALY_INDITAS and h.lejatszott and _ellenfel_jelzesei(kod)
    tar = getattr(h, "kenyszertar", None) if SZABALY_LICIT else None
    tar = {u: tar[u] for u in vedok if tar and tar.get(u) is not None} if tar else None
    if not (inditas or tar):
        return vilagok(lo, h.lejatszott, kint, db, kor, mag=mag, vedok=vedok)
    import random
    rnd = random.Random(mag * 7919)
    suly = {"ASZ_ALOL": ASZ_ALOL_SULY, "LAP": INDITAS_SULY}
    cache: dict = {}
    ki: list = []
    tartalek: list = []                          # a licitnek ellentmondó világok
    for w in vilagok(lo, h.lejatszott, kint, db * 60, kor, mag=mag, vedok=vedok):
        if inditas:
            o = inditas_osszhang(w, h.lejatszott, h.adu, cache, kod)
            if o in suly and rnd.random() >= suly[o]:
                continue
        if tar and not all(lj._megfelel(set(w.kezek[u].lapok), ig) for u, ig in tar.items()):
            # LICIT_KENYSZER: a licitnek ellentmondó világ csak LICIT_SULY eséllyel
            if rnd.random() >= LICIT_SULY:
                if len(tartalek) < db:
                    tartalek.append(w)
                continue
        ki.append(w)
        if len(ki) >= db:
            break
    if len(ki) < db // 2:
        # a licit túl szűk (vagy ellentmondásos): a hiányt az ellentmondó világok pótolják
        ki += tartalek[:db - len(ki)]
    return ki


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
    ut = j.aktualis()
    kovetes = {}
    if ut:
        tett = {u for u, _ in ut}
        kovetes = {u: ut[0][1].szin for u in (h.felvevo, h.asztal) if u not in tett}
    allas = Allas(felvevo=h.felvevo, adu=h.adu,
                  kezek={u: set(j.kezek[u]) for u in (h.felvevo, h.asztal)}, kint=kint,
                  cel=max(0, cel - j.felvevo_utesek()), hatra=13 - len(lejatszott) // 4,
                  soron=j.soron(), kovetes=kovetes, utes=list(ut))
    return allas, kint


def igeny(h: Helyzet, lejatszott: list) -> int:
    """Hány ütést (szanban) / vesztőt (színjátékban) kell a forrásoknak hozniuk: a
    helyzetfelmérés hiánya, illetve vesztőtöbblete."""
    import math
    from ..motor.tervfelmeres import felmeres_jatekbol
    f = felmeres_jatekbol(_jatek(h, lejatszott), 6 + h.kontraktus.szint)
    if f.adu:
        return max(0, math.ceil(f.vesztotobblet - 0.25))
    return f.hiany


def _peldanyok(h: Helyzet, lejatszott: list):
    from ..motor.tervsema import peldanyok
    return peldanyok(_allas(h, lejatszott)[0], technikak_betoltese())


def tervez(h: Helyzet, dd_fv, hatarido_s: float, vilag_db: int | None = None,
           elozo: list | None = None) -> Rekord:
    t0 = time.time()
    from ..motor.tervszinpolitika import urites
    urites()                                     # az elemzők memóriája: tervenként tiszta lap
    vilag_db = vilag_db or VILAG
    cel = 6 + h.kontraktus.szint
    allas, kint = _allas(h, h.lejatszott)
    v1_, v2_ = kovetkezo_ules(h.felvevo, 1), kovetkezo_ules(h.felvevo, 3)
    ures = szabad_helyek(h.lejatszott, v1_, v2_)
    ig = igeny(h, h.lejatszott)
    tervek = tervjeloltek(allas, technikak_betoltese(), max_db=200, igeny=ig, ures=ures, max_szim=SZIM_TERV)
    if SZABALY_IGENY_TOBBLET:
        # IGENY_TOBBLET: a felmérés igénye becslés — eggyel több forrás is jelölt; a szimuláció dönt
        # (csak ha az előzetes esélye nem rosszabb az igény szerinti legjobbnál: a
        # gyengébb, nagyobb célú színkezelés csak drága — 4R01 #1: ♥ 3 ütés, 24%, 4+ GB)
        nevek = {t.nev for t in tervek}
        also = max(((getattr(t, "elozetes", None) or 0.0) for t in tervek), default=0.0) - 1e-9
        tobb = [t for t in tervjeloltek(allas, technikak_betoltese(), max_db=200, igeny=ig + 1, ures=ures,
                                        max_szim=SZIM_TERV)
                if t.nev not in nevek and (getattr(t, "elozetes", None) or 0.0) >= also]
        tervek = sorted(tervek + tobb, key=lambda t: (not getattr(t, "fogas_ok", True),
                                                     -round(getattr(t, "elozetes", None) or 0.0, 3),
                                                     len(t.lepesek)))[:SZIM_TERV]
    k = h.kontraktus
    vl, tar = _vilag_keszlet(h, kint, vilag_db, dd_fv)
    keret = max(1.0, hatarido_s - (time.time() - t0))
    jatek0 = _jatek(h, h.lejatszott)
    mi_jon = jatek0.mi(jatek0.soron())
    dd = {"tel": 0, "n": 0}

    def dd_felso(i, w):
        ossz = [e.felvevo_osszesen for e in tar(i, w, h.lejatszott)]
        dd["n"] += 1
        dd["tel"] += (max(ossz) if mi_jon else min(ossz)) >= cel

    ered = ertekel_lepcsos(tervek, vl, h.felvevo, h.adu, h.lejatszott, tar, cel, keret_s=keret,
                           t0=t0, utana=dd_felso)
    hasznalt = max((r.n for r in ered), default=0)
    dd_tel = dd["tel"]
    if elozo is not None:
        # a régi terv (az egységei szerint) marad, ha nem érezhetően rosszabb
        for i, r in enumerate(ered):
            if [[p.sema.azon, p.szin] for p in r.terv.lepesek] == elozo:
                if i and r.esely >= ered[0].esely - TURES:
                    ered.insert(0, ered.pop(i))
                break
    dontes, dontes_nev, megtart = None, None, None
    if SZABALY_HIVASRA:
        valaszt = utes_dontes(h, vl, tar, cel, max(1.0, hatarido_s - (time.time() - t0)) / 2,
                              jeloltek=[r.terv for r in ered[:UTES_TERV]])
        if valaszt is not None:
            dontes, dontes_nev, ered, megtart = valaszt
            hasznalt = max((r.n for r in ered), default=0)
    return Rekord(uuid.uuid4().hex, 1, ered[0].terv, ered, list(h.lejatszott),
                  {u: set(h.kezek[u]) for u in (h.felvevo, h.asztal)}, h.felvevo, k, hasznalt,
                  time.time() - t0, dd_felso=dd_tel / dd['n'] if dd['n'] else None,
                  utes_dontes=dontes, utes_dontes_nev=dontes_nev, utes_megtart=megtart)


def _vilag_keszlet(h: Helyzet, kint: set, vilag_db: int, dd_fv):
    """A világok (a kint lévő lapok a két védő között, a megfigyelt színhiányokkal és az
    indítási megállapodással) és a DD-tár."""
    v1, v2 = sorted(h.vedok)
    jatszott_v = {u: {l for uu, l in h.lejatszott if uu == u} for u in (v1, v2)}
    kint_l = sorted(kint, key=str)
    n1 = 13 - len(jatszott_v[v1])
    alap = {h.felvevo: Kez(frozenset(h.kezek[h.felvevo])), h.asztal: Kez(frozenset(h.kezek[h.asztal])),
            v1: Kez(frozenset(set(kint_l[:n1]) | jatszott_v[v1])),
            v2: Kez(frozenset(set(kint_l[n1:]) | jatszott_v[v2]))}
    vl = _vilagok(Leosztas(alap), h, kint, vilag_db, (v1, v2))
    return vl, tj.DDTar(dd_fv, h.kontraktus)


def _hatralevo_helyeink(h: Helyzet) -> list[tuple[int, str]]:
    """A folyó ütésben a még nem tett kezeink: (index a lejátszásban, kéz)."""
    n = len(h.lejatszott) % 4
    if not n:
        return []
    kezdo = h.lejatszott[-n][0]
    eleje = len(h.lejatszott) - n
    return [(eleje + i, kovetkezo_ules(kezdo, i)) for i in range(n, 4)
            if kovetkezo_ules(kezdo, i) in (h.felvevo, h.asztal)]


def utes_dontes(h: Helyzet, vl, tar, cel: int, keret_s: float, jeloltek: list,
                tobblet: float = 0.05, csak_lapok: bool = False):
    """HIVASRA_TETT_LAP: a védő hívására tett lapjaink a terv részei (a szerkesztő,
    2026-11-22: „a játékterv a két kézre együtt készül”). A változatok:
      1. a hozzátevési sémák (technikak.yaml, `fajta: hozzatevesi`, pl. Bath-csel): a még
         nem tett KÉT kezünk teendője ebben az ütésben;
      2. a soron lévő kezünk minden (nem egyenértékű) szabályos lapja.
    Mindegyik a jelölt tervekkel, UGYANAZOKON az első `UTES_VILAG` világokon fut, és a
    döntés nélküli alappal vetjük össze (azonos minta: nincs fantom-nyereség). A nyertes
    legalább `tobblet` és `UTES_MIN_VILAG` világ nyereség. A sémák változatai mindig
    lefutnak, a lapoké az időkeretig. Vissza: (döntés [[index, kéz, lap|KICSI, ok]], név,
    eredmények, megtartott lapok) vagy None."""
    from ..motor.tervkonyvelo import KICSI
    from ..motor.tervsema import hozzatetelek
    from ..motor.tervszinpolitika import urites
    if not h.lejatszott or len(h.lejatszott) % 4 == 0 or not jeloltek or not vl:
        return None
    j0 = _jatek(h, h.lejatszott)
    u = j0.soron()
    if not j0.mi(u):
        return None
    i0 = len(h.lejatszott)
    valtozatok: list[tuple[str | None, dict, set]] = []
    allas, _ = _allas(h, h.lejatszott)
    if not csak_lapok:
        helyek = _hatralevo_helyeink(h)
        for hz in hozzatetelek(allas, technikak_betoltese()):
            ok = f"{hz.rovid}: kiengedés (kicsi)" if hz.teendo == "kicsi" else hz.rovid
            valtozatok.append((hz.rovid, {i: (k, KICSI, ok) for i, k in helyek}, set(hz.megtart)))
    lapok = sorted(h.allas_mb.legalis, key=lambda l: (l.szin, l.rang))
    # egyenértékű lapok (egy színben, köztük csak a mi lapjaink vagy lement lapok): egy
    # képviselő (a legkisebb) elég
    lathato = set(h.kezek[h.felvevo]) | set(h.kezek[h.asztal]) | {l for _, l in h.lejatszott}
    kepv: list = []
    for l in lapok:
        if kepv and kepv[-1].szin == l.szin and all(
                any(x.szin == l.szin and x.rang == r for x in lathato) for r in range(kepv[-1].rang + 1, l.rang)):
            continue
        kepv.append(l)
    if len(kepv) >= 2:
        # a sorrend: a legmagasabb és a legkisebb előbb (a két véglet a legkülönbözőbb)
        for l in [kepv[-1], kepv[0]] + kepv[1:-1]:
            valtozatok.append((None, {i0: (u, l, "a terv lapja a hívásra (a tervek szimulációja szerint)")},
                               set()))
    if not valtozatok:
        return None
    vln = vl[:UTES_VILAG]
    n = len(vln)
    t1 = time.time()
    urites()
    alap = ertekel_lepcsos(jeloltek, vln, h.felvevo, h.adu, h.lejatszott, tar, cel, elso=n)
    if not alap:
        return None
    legjobb = None
    for nev, d, megtart in valtozatok:
        # (név: a hozzátevési séma rövid neve; egy-egy lapnál nincs — az nem a terv neve)
        if nev is None and time.time() - t1 > keret_s:
            break
        urites()                                 # az elemzők memóriája változatról változatra tiszta
        er = ertekel_lepcsos(jeloltek, vln, h.felvevo, h.adu, h.lejatszott, tar, cel, elso=n,
                             utes_dontes=d, megtart=megtart)
        if er and (legjobb is None or er[0].teljesult > legjobb[2][0].teljesult):
            legjobb = (nev, d, er, megtart)
    if legjobb is None:
        return None
    nev, d, er, megtart = legjobb
    if er[0].teljesult - alap[0].teljesult < max(UTES_MIN_VILAG, tobblet * n):
        return None
    dontes = [[i, k, l if l == KICSI else str(l), ok] for i, (k, l, ok) in sorted(d.items())]
    return dontes, nev, er, sorted(str(l) for l in megtart) or None


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

def _kenyszer(rek: Rekord) -> dict:
    """A terv döntése a védő hívására tett lapjainkról, a végrehajtó alakjában (a lap
    nélküli bejegyzés: megvizsgálva, a szokásos hozzátevés marad)."""
    from ..motor.tervkonyvelo import KICSI
    ki = {}
    for x in rek.utes_dontes or []:
        i_, u_, l_ = x[0], x[1], x[2]
        if l_ is None:
            continue
        ok = x[3] if len(x) > 3 else None
        ki[int(i_)] = (u_, KICSI if l_ == KICSI else Lap.parse(l_), ok)
    return ki


def _utes_dontes_kell(rek: Rekord, h: Helyzet, v: Vegrehajto) -> bool:
    """A felvevő oldal lapja a terv folyó ütésében, amelyről a terv még nem döntött (a
    terv ebben az ütésben, egy korábbi lapunknál készült)."""
    if not SZABALY_HIVASRA:
        return False
    i = len(h.lejatszott)
    t = len(rek.lejatszott)
    if not i % 4 or not t % 4 or t >= i or t // 4 != i // 4:
        return False
    return not any(int(x[0]) == i for x in rek.utes_dontes or [])


def _lepes_utes_dontes(keres: dict, h: Helyzet, rek: Rekord, dd_zar):
    """A folyó ütés soron lévő lapunk a terv szerint: a mostani terv a mostani
    állásból, a változatok ugyanazokon a világokon (`utes_dontes`)."""
    _, kint = _allas(h, h.lejatszott)
    vl, tar = _vilag_keszlet(h, kint, VILAG, _dd_fv(dd_zar))
    v = utes_dontes(h, vl, tar, 6 + h.kontraktus.szint, max(1.0, _hatarido_s(keres) / 2), [rek.terv])
    return (v[0], v[1], v[3]) if v else None


def _terv_nev(rek: Rekord) -> str:
    """A terv neve; a hozzátevési séma (pl. „♠ Bath-csel”) az elején."""
    return (f"{rek.utes_dontes_nev} → " if rek.utes_dontes_nev else "") + rek.terv.nev


def vegrehajto(rek: Rekord, h: Helyzet) -> tuple[Vegrehajto, tj.Jatek, list[str]]:
    """A terv végrehajtója a tervezés pillanatától a mostani állásig: a lement
    lapokon végigmegy (a saját döntéseit is meghozza, hogy az egységek állapota a
    megfigyelés szerint haladjon). Vissza: a végrehajtó, a játék, és az eltérések
    (a mi oldalunkon nem a javasolt lap ment le)."""
    j = _jatek(h, rek.lejatszott)
    v = Vegrehajto(rek.terv, j, naplo=[])
    v.cel = 6 + rek.kontraktus.szint
    v.kenyszer = _kenyszer(rek)
    v.megtart = {Lap.parse(x) for x in rek.utes_megtart or []}
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


def kimutatasok(rek: Rekord, h: Helyzet, v=None) -> list[tuple[str, str]]:
    """A terv óta megfigyelt új színhiányok (kéz, szín), amelyeket még nem ellenőriztünk.
    Ha a színben már nincs kint lap, a kimutatás semmit sem mond."""
    regi = {(k.kez, k.szin) for k in _szinhianyok(rek.lejatszott, h.vedok)} | set(rek.ellenorzott)
    _, kint = _allas(h, h.lejatszott)
    ures = {sz for sz in "SHDC" if not any(l.szin == sz for l in kint)}
    return [(k.kez, k.szin) for k in _szinhianyok(h.lejatszott, h.vedok)
            if (k.kez, k.szin) not in regi and k.szin not in ures]


def _kimutatas_szoveg(km) -> str:
    return ", ".join(f"{KEZ_NEV[k]} nem adott {SZIN[sz]}-t" for k, sz in km)


def terv_esely_most(rek: Rekord, h: Helyzet, dd_zar=None, vilag_db: int | None = None) -> tuple[float, int]:
    """TERV_MEGTARTAS: a mostani terv esélye a látott lapokkal összeférő elosztásokon —
    a terv a tervezés pillanatától indul, a valóban lement lapokat lejátssza, aztán a
    védők a mindent látó védő szerint játszanak. Vissza: (esély, világok száma)."""
    vilag_db = vilag_db or VILAG
    _, kint = _allas(h, h.lejatszott)
    v1, v2 = sorted(h.vedok)
    jatszott_v = {u: {l for uu, l in h.lejatszott if uu == u} for u in (v1, v2)}
    kint_l = sorted(kint, key=str)
    n1 = 13 - len(jatszott_v[v1])
    lo = Leosztas({h.felvevo: Kez(frozenset(h.kezek[h.felvevo])), h.asztal: Kez(frozenset(h.kezek[h.asztal])),
                   v1: Kez(frozenset(set(kint_l[:n1]) | jatszott_v[v1])),
                   v2: Kez(frozenset(set(kint_l[n1:]) | jatszott_v[v2]))})
    vl = _vilagok(lo, h, kint, vilag_db, (v1, v2))
    tar = tj.DDTar(_dd_fv(dd_zar), h.kontraktus)
    cel = 6 + h.kontraktus.szint
    kenyszer = h.lejatszott[len(rek.lejatszott):]
    ok = 0
    for i, w in enumerate(vl):
        def dd_vedo(j, i=i, w=w):
            return tj._vedo_lap(tar(i, w, j.lapok))
        ok += lejatszik(rek.terv, w, rek.felvevo, h.adu, rek.lejatszott, dd_vedo, cel=cel,
                        kenyszer=kenyszer, utes_dontes=_kenyszer(rek),
                        megtart={Lap.parse(x) for x in rek.utes_megtart or []}) >= cel
    return (ok / len(vl) if vl else 0.0), len(vl)


def terv_borult(elotte: float, most: float, n: int) -> bool:
    """A terv borult, ha az esélye érezhetően csökkent (a szerkesztő, 2026-11-21: „a terv
    esélyének csökkenése azt jelenti, hogy valami alapvetően megváltozott”). Érezhető: a
    nullára esés, vagy legalább 10 pont és a mintavétel kétszeres szórása."""
    if most <= 0 < elotte:
        return True
    szoras = (max(elotte * (1 - elotte), 0.0) / max(n, 1)) ** 0.5
    return elotte - most >= max(0.10, 2 * szoras)


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
        f"<td>{'' if r.terv.elozetes is None else f'{100 * r.terv.elozetes:.0f}%'}</td>"
        f"<td>{100 * r.esely:.0f}%</td><td>{(r.utesek / r.n if r.n else 0):.2f}</td></tr>"
        for r in rek.eredmenyek[:12])
    return (f"<table><tr><th>Terv (sorrendben)</th><th>Esély a forrásokból</th><th>Teljesít a lejátszásban</th>"
            f"<th>Átlag ütés</th></tr>{sorok}</table>"
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
    return ki + (f"</ol><p class=\"halv\">Igény: {terv.igeny} (a hiányzó ütések, illetve a vesztőtöbblet). "
                 "A biztos egységek mindig a terv részei; az esélyesek sorban jönnek, amíg a "
                 "megszerzett hozam el nem éri az igényt — ha egy nem sikerül, a következő. "
                 "Az átmeneteket és az aduköröket a végrehajtó körről körre illeszti be.</p>")


def _uj_terv(keres: dict, h: Helyzet, kulcs: tuple, dd_zar, ok: str,
             elozo: Rekord | None = None) -> Rekord:
    regi_egysegek = [[p.sema.azon, p.szin] for p in elozo.terv.lepesek] if elozo is not None else None
    rek = tervez(h, _dd_fv(dd_zar), _hatarido_s(keres), elozo=regi_egysegek)
    rek.felbe = SZABALY_FELBE and len(h.lejatszott) % 4 != 0 and ok.startswith(("kimutatás", "eltérés"))
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
        f"<td>{s.kiado_biztos}</td><td>{s.tempo}</td>"
        + (f"<td>{s.vesztok:.1f} ({s.vesztok_max})</td>" if f.adu else "") + "</tr>"
        for s in f.szinek)
    fej = ("<tr><th>Szín</th><th>Mi (felvevő–asztal)</th><th>Kint</th><th>Biztos ütés</th>"
           "<th>Biztos kiadás</th><th>Tempóvesztő</th>" + ("<th>Vesztő a fő kézből (legrosszabb)</th>" if f.adu else "") + "</tr>")
    return (f"<table>{fej}{sorok}</table>"
            + "".join(f"<p>{html.escape(x.replace(f.fo_kez or '~', KEZ_NEV.get(f.fo_kez, '')) if f.fo_kez else x)}</p>"
                      for x in f.sorok())
            + "<p class=\"halv\">A vesztők elosztásonként, a felső lapokkal lejátszva (impassz és lopás "
              "nélkül); a biztos kiadás: a kint lévő lapok a legnagyobb lapunk fölött; a tempóvesztő: "
              "a szín végigjátszásakor elveszített további körök — csak ha a védők hívják a színt.</p>")


def _forrasok(h: Helyzet, rek: Rekord):
    from ..motor.tervforras import Forras, forrasok
    from ..motor.tervkonyvelo import szinkezeles_peldanyok
    allas, kint = _allas(h, rek.lejatszott)
    v1, v2 = h.vedok
    ures = dict(zip((v1, v2), szabad_helyek(rek.lejatszott, v1, v2)))
    ki = forrasok(allas, technikak_betoltese(), ures, _szinhianyok(rek.lejatszott, h.vedok))
    b1, b2 = kovetkezo_ules(h.felvevo, 1), kovetkezo_ules(h.felvevo, 3)
    for p in szinkezeles_peldanyok(allas, technikak_betoltese(), rek.terv.igeny,
                                   (ures.get(b1, 13), ures.get(b2, 13))):
        ki.append(Forras(p, p.hozam, p.szerepek["esely"], p.szerepek["m"], False))
    ki.sort(key=lambda f: (-f.hozam * f.esely, f.kudarc, f.nev))
    return ki


def _forras_html(h: Helyzet, rek: Rekord) -> str:
    fk = _forrasok(h, rek)
    if not fk:
        return "<p>Nincs alkalmazható technika.</p>"
    sorok = "".join(
        f"<tr><td>{html.escape(f.nev)}</td><td>{f.hozam}</td>"
        f"<td>{'biztos' if f.biztos else f'{100 * f.esely:.0f}%'}</td><td>{f.kudarc}</td>"
        f"<td class=\"halv\">{html.escape(f.p.sema.nev)}</td></tr>" for f in fk)
    return ("<table><tr><th>Forrás</th><th>Hozam</th><th>Esély</th><th>Kudarc költsége</th>"
            f"<th>Technika</th></tr>{sorok}</table>"
            "<p class=\"halv\">Az esély a kint lévő lapok elosztásain, a szabad helyek szerint "
            "súlyozva (keresés nélkül). „Biztos”: nincs rejtett feltétele; a kockázata a "
            "végrehajtásé (ellopás, időzítés).</p>")


def _felmeres_adat(h: Helyzet, rek: Rekord) -> dict:
    from ..motor.tervfelmeres import felmeres_jatekbol
    f = felmeres_jatekbol(_jatek(h, rek.lejatszott), 6 + rek.kontraktus.szint)
    return {"needed": f.cel, "remaining": f.hatra, "sure_tricks": f.biztos, "missing": f.hiany,
            "allowed_losers": f.megengedett, "sure_losers": f.kiado, "balance": f.egyenleg,
            "certain_losers": f.kiado_biztos, "tempo_losers": f.tempo, "certain_balance": f.egyenleg_biztos,
            "expected_losers": round(f.vesztok, 2) if f.adu else None,
            "suits": {s.szin: {"sure_tricks": s.biztos, "sure_losers": s.kiado,
                               "certain_losers": s.kiado_biztos, "tempo_losers": s.tempo,
                               "condition": s.feltetel or None,
                               "expected_losers": round(s.vesztok, 2)} for s in f.szinek}}


def _terv_nezet(h: Helyzet, rek: Rekord) -> dict:
    return _html("kibic — játékterv", [
        ("A helyzet", _helyzet_html(h, rek)),
        ("A helyzetfelmérés", _felmeres_html(h, rek)),
        ("A források (a hiányzó ütések és a vesztők)", _forras_html(h, rek)),
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
                     _szep(f"Terv: {_terv_nev(rek)} — {100 * legjobb.esely:.0f}% ({rek.vilag} világ"
                           + (f"; a mindent látó felvevő {100 * rek.dd_felso:.0f}%" if rek.dd_felso is not None else "")
                           + "). "
                           + ("A terv messze elmarad ettől: a lépéskérésre a kibic általános lejátszója ad lapot."
                              if _hibrid(rek) else "Lapot a lépéskérés ad.")) if legjobb.esely > 0 else
                     "Egyik terv sem teljesít egyik sorsolt világban sem; a lépéskérésre a kibic "
                     "általános lejátszója ad lapot.")
    v.update(plan_id=rek.plan_id, plan_revision=rek.revizio, analysis_result="new_plan",
             plan=_terv_adat(rek), assessment=dict(
                 _jeloltek_adat(rek), situation=_felmeres_adat(h, rek),
                 sources=[{"name": _szep(f.nev), "yield": f.hozam, "probability": round(f.esely, 3),
                           "failure_cost": f.kudarc, "sure": f.biztos} for f in _forrasok(h, rek)]),
             presentation=_terv_nezet(h, rek))
    v["meta"]["elapsed_ms"] = int(rek.ido_s * 1000)
    return v


def _terv_adat(rek: Rekord) -> dict:
    return {"name": _szep(_terv_nev(rek)), "units": ([rek.utes_dontes_nev] if rek.utes_dontes_nev else []) + [p.nev for p in rek.terv.lepesek],
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
        if e.status in ("unsupported_position", "no_plan") and tartalek_fv is not None:
            # ellenvonalon (vagy az indulásnál) nincs terv: a /play döntése megy, nem hiba
            return _tartalek(keres, tartalek_fv, str(e).rstrip("."))
        return _alap_valasz(keres, "step", e.status, str(e))
    kulcs = _kulcs(keres, h.felvevo)
    rek = betolt(kulcs, h)
    ok = None
    jegyzet = None
    if rek is None:
        ok = "nincs terv ehhez a partihoz"
    elif h.lejatszott[:len(rek.lejatszott)] != rek.lejatszott:
        ok = "a lejátszás nem a terv folytatása"
    else:
        v, j, elteresek = vegrehajto(rek, h)
        km = kimutatasok(rek, h, v)
        tartalekban = _hibrid(rek) or not rek.eredmenyek or rek.eredmenyek[0].esely <= 0
        if km and not elteresek and not tartalekban and SZABALY_MEGTARTAS:
            # TERV_MEGTARTAS: a kimutatás nem ok újratervezésre, csak ha a terv esélye
            # érezhetően csökkent (a terv „borult")
            elotte = rek.esely_most if rek.esely_most is not None else rek.eredmenyek[0].esely
            most, n = terv_esely_most(rek, h, dd_zar)
            szoveg = _kimutatas_szoveg(km)
            if terv_borult(elotte, most, n):
                ok = f"kimutatás: {szoveg} — a terv esélye {elotte:.0%} → {most:.0%}"
            else:
                rek.esely_most = most
                rek.ellenorzott = list(rek.ellenorzott) + list(km)
                with _ZAR:
                    ment(kulcs, rek, f"kimutatás: {szoveg} — a terv marad ({elotte:.0%} → {most:.0%})")
                jegyzet = f"kimutatás ({szoveg}): a terv marad, esélye {most:.0%}"
        elif km:
            ok = "kimutatás: " + _kimutatas_szoveg(km)
        elif elteresek and not tartalekban:
            # ha a tartalék játszik, a terv lapjától való eltérés várható: nem ok újratervezésre
            ok = "eltérés a tervtől: " + elteresek[-1]
        elif rek.felbe and not tartalekban and len(h.lejatszott) >= (len(rek.lejatszott) // 4 + 1) * 4:
            ok = "a terv az előző ütés közben készült (a hátralévő védőlapok előtt)"
    if ok is not None:
        folytat = rek is not None and h.lejatszott[:len(rek.lejatszott)] == rek.lejatszott
        rek = _uj_terv(keres, h, kulcs, dd_zar, ok, rek if folytat else None)
        v, j, _ = vegrehajto(rek, h)
    u = j.soron()
    if not j.mi(u):
        return _alap_valasz(keres, "step", "stale_state", "Most nem a felvevő oldala következik.")
    if ok is None and _utes_dontes_kell(rek, h, v):
        # HIVASRA_TETT_LAP: a terv a folyó ütésben készült (pl. az asztal lapjánál); a
        # felvevő lapja is a terv döntése — most, hogy a védő lapja is látszik
        uj = _lepes_utes_dontes(keres, h, rek, dd_zar)
        rek.utes_dontes = list(rek.utes_dontes or []) + (uj[0] if uj else [[len(h.lejatszott), u, None, None]])
        if uj and uj[1]:
            rek.utes_dontes_nev = uj[1]
        if uj and uj[2]:
            rek.utes_megtart = sorted(set(rek.utes_megtart or []) | set(uj[2]))
        with _ZAR:
            ment(kulcs, rek, "a védő hívására tett lap: " + ("a terv döntése" if uj else "nincs jobb a szokásosnál"))
        v.kenyszer = _kenyszer(rek)
        v.megtart = {Lap.parse(x) for x in rek.utes_megtart or []}
    elotte = len(v.naplo)
    lap = v.lap(u)
    if ok is None and any("nem játszható" in x for x in v.naplo[elotte:]):
        ok = "a terv egysége elakadt: " + _szep(next(x for x in v.naplo[elotte:] if "nem játszható" in x))
        rek = _uj_terv(keres, h, kulcs, dd_zar, ok)
        v, j, _ = vegrehajto(rek, h)
        elotte = len(v.naplo)
        lap = v.lap(u)
    indok = v.naplo[elotte:]
    if jegyzet and ok is None:
        indok.append(jegyzet)
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
                  ("A terv", f"<p><b>{html.escape(_szep(_terv_nev(rek)))}</b> — {100 * esely:.0f}%</p>"
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
