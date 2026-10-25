"""
A felvevő tervtára — a FOGALMAK (függvények) és a TERVSOROK kiértékelése
(2026-10-25, tervezet: claude/terv-tervtar-2026-10-25.md).

A fogalmak a felvevő szemszögéből, az indulás után számolódnak (a saját keze és
az asztal, a felvétel, az indulás). Kétféle:

  * globális (pl. `hiany`, `vesztok`, `lopas_rovid`, `fenyegetes`);
  * színenkénti (`szin.egyutt`, `szin.impasszolhato`, ...) — a `szinenkent: igen`
    sor akkor illik, ha VAN olyan szín, amelyre minden színenkénti feltétel igaz.

A tervsorok (rendszerek/tervek/*.yaml) a fogalmakra hivatkozó feltételek:

    - tipus: KIMAGASITAS            # absztrakt sor: szűrő + közös rész
      szuro: {hiany: "1+"}
      szinenkent: igen
      cimkek: ["Finessing", ...]    # a Pavlicek-címkék, amelyeket ez a típus fed (méréshez)
    - valtozat: IMPASSZ
      alap: KIMAGASITAS
      ha: {szin.impasszolhato: igen}
      kivon: [...]                   # örökölt feltétel elhagyása
      felulir: {...}                 # örökölt feltétel más értékkel

Feltétel-értékek: igen/nem; szám; "a-b"; "n+"; "n-"; lista (bármelyik).
A fogalmak egyszerű, tankönyvi közelítések — a mérés (cli/tervfelismeres.py)
mondja meg, hol kell finomítani őket.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from ..domain import SZINEK, Lap, kovetkezo_ules

FIGURAK = (14, 13, 12, 11)          # Á K D B
RANG_NEV = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}


# --- 1. A helyzet és a fogalmak ------------------------------------------------------

@dataclass
class Helyzet:
    """A felvevő szemszöge az indulás után."""
    felvevo: str
    szint: int
    szin: str                         # S/H/D/C/NT
    kez: set[Lap]                     # a felvevő 13 lapja
    asztal: set[Lap]                  # az asztal 13 lapja
    indulas: Lap | None = None

    @property
    def adu(self) -> str | None:
        return None if self.szin == "NT" else self.szin

    @property
    def cel(self) -> int:
        return 6 + self.szint


def _rangok(lapok, sz) -> list[int]:
    return sorted((l.rang for l in lapok if l.szin == sz), reverse=True)


def _szin_jellemzok(h: Helyzet, sz: str) -> dict:
    d, y = _rangok(h.kez, sz), _rangok(h.asztal, sz)
    mi = sorted(d + y, reverse=True)
    vedo = [r for r in range(14, 1, -1) if r not in mi]
    hmax, hmin = max(len(d), len(y)), min(len(d), len(y))
    # felső ütések: a felülről folyamatos sor, a hosszabb kéz hosszáig
    felso = 0
    for r in range(14, 1, -1):
        if r in mi:
            felso += 1
        else:
            break
    felso = min(felso, hmax)
    # kimagasítás: a hosszú kéz lapjai ütnek, ha a védők lapjai elfogynak;
    # kiadandó: a védők annyi lapja, amennyi a mi hmax-adik legnagyobb lapunk fölött van
    kiadando = 0
    if hmax and mi:
        kuszob = mi[min(hmax, len(mi)) - 1]
        kiadando = sum(1 for r in vedo if r > kuszob)
    kint = len(vedo)
    rovid_vedo = math.ceil(kint / 2) if kint else 0     # egyenletes elosztásnál a hosszabb védő
    if hmax >= rovid_vedo + kiadando and hmax:
        hossz_utes = max(felso, hmax - kiadando)
    else:
        hossz_utes = felso
    tobblet = max(0, hossz_utes - felso)
    # impassz: hiányzik egy H figura (B-ig), de van nálunk nagyobb ÉS a közvetlenül alatta lévő
    hianyzo = [r for r in vedo if r >= 11]
    impassz = any(any(x > r for x in mi) and (r - 1) in mi for r in hianyzo)
    # expassz (szöktetés): hiányzik H, nincs nagyobb nálunk, de megvan az alatta lévő, és kísérője is
    expassz = any(not any(x > r for x in mi) and (r - 1) in mi and
                  (len(d) >= 2 if (r - 1) in d else len(y) >= 2) for r in hianyzo)
    # eső figura: hiányzó K/D/B, minden nagyobb nálunk, és kevés lap van kint
    eso = any(all(x in mi for x in range(r + 1, 15)) for r in hianyzo if r <= 13) and kint <= 5
    # fenyegetés (beszorításhoz): egyetlen védőlap van a legjobb nem-felső lapunk fölött
    fenyeget = False
    if len(mi) > felso:
        nem_felso = mi[felso]
        fenyeget = sum(1 for r in vedo if r > nem_felso) == 1
    return {
        "egyutt": len(mi), "hossz_max": hmax, "hossz_min": hmin, "felso": felso,
        "kint": kint, "kiadando": kiadando, "tobblet": tobblet,
        "hianyzo_figura": len(hianyzo), "impasszolhato": impassz, "expasszolhato": expassz,
        "eso_figura": eso, "fenyegetes": fenyeget,
        "adu": sz == h.adu, "hivott": h.indulas is not None and h.indulas.szin == sz,
        "egy_fogas": felso == 1 or (felso == 0 and any(r >= 12 for r in mi) and hmax >= 2),
    }


def _vesztok(h: Helyzet, sz: str, mester: set[Lap], masik: set[Lap]) -> int:
    """Vesztők egy színben a „mester” kéz (a hosszabb adu) szemszögéből (Á, K, D)."""
    lm = sum(1 for l in mester if l.szin == sz)
    egyutt = {l.rang for l in mester | masik if l.szin == sz}
    n = min(3, lm)
    return max(0, n - sum(1 for r in (14, 13, 12)[:n] if r in egyutt))


def jellemzok(h: Helyzet) -> tuple[dict, dict[str, dict]]:
    """(globális fogalmak, {szín: színenkénti fogalmak})."""
    szinek = {sz: _szin_jellemzok(h, sz) for sz in SZINEK}
    biztos = sum(x["felso"] for x in szinek.values())
    g: dict = {"felvetel": "SZAN" if h.adu is None else "SZIN", "cel": h.cel,
               "biztos": biztos, "hiany": max(0, h.cel - biztos), "kiadhato": 13 - h.cel,
               "tobblet_osszes": sum(x["tobblet"] for x in szinek.values())}
    if h.adu:
        ad, ay = (sum(1 for l in k if l.szin == h.adu) for k in (h.kez, h.asztal))
        mester, masik = (h.kez, h.asztal) if ad >= ay else (h.asztal, h.kez)
        rovid, hosszu = (h.asztal, h.kez) if ad >= ay else (h.kez, h.asztal)
        rovid_adu = min(ad, ay)
        vesztok = sum(_vesztok(h, sz, mester, masik) for sz in SZINEK)
        lopas = 0
        rovidseg = {}
        for sz in SZINEK:
            if sz == h.adu:
                continue
            lr = sum(1 for l in rovid if l.szin == sz)
            lh = sum(1 for l in hosszu if l.szin == sz)
            rovidseg[sz] = (sum(1 for l in h.kez if l.szin == sz), sum(1 for l in h.asztal if l.szin == sz))
            if lh > lr and _vesztok(h, sz, hosszu, rovid) > 0:
                lopas += min(lh - lr, _vesztok(h, sz, hosszu, rovid))
        lopas = min(lopas, rovid_adu)
        adu_felso = sum(1 for r in (14, 13, 12, 11) if r in _rangok(h.kez | h.asztal, h.adu))
        # asztalfordítás: az asztal adui erősek (3+, 2+ a négy felsőből), a felvevő rövid egy
        # mellékszínben, amelyből az asztalon 3+ van
        asztalforditas = ay >= 3 and adu_felso >= 2 and ad >= ay and any(
            d_ <= 1 and y_ >= 3 for d_, y_ in rovidseg.values())
        keresztlopas = ad >= 3 and ay >= 3 and any(
            d_ <= 1 for d_, _ in rovidseg.values()) and any(y_ <= 1 for _, y_ in rovidseg.values()) \
            and not any(d_ <= 1 and y_ <= 1 for d_, y_ in rovidseg.values())
        g.update({"adu_d": ad, "adu_y": ay, "adu_egyutt": ad + ay, "rovid_adu": rovid_adu,
                  "adu_felso": adu_felso, "vesztok": vesztok,
                  "vesztok_tobblet": max(0, vesztok - (13 - h.cel)),
                  "lopas_rovid": lopas, "asztalforditas": asztalforditas,
                  "keresztlopas": keresztlopas})
    else:
        g.update({"adu_d": 0, "adu_y": 0, "adu_egyutt": 0, "rovid_adu": 0, "adu_felso": 0,
                  "vesztok": None, "vesztok_tobblet": None, "lopas_rovid": 0,
                  "asztalforditas": False, "keresztlopas": False})
    # vesztőcsere: egy szín nyerői többek, mint a másik kéz lapjai abban a színben
    dobas = 0
    for sz, x in szinek.items():
        if sz == h.adu:
            continue
        d_, y_ = (sum(1 for l in k if l.szin == sz) for k in (h.kez, h.asztal))
        dobas += max(0, x["felso"] + x["tobblet"] - min(d_, y_))
    g["dobas"] = dobas
    g["fenyegetes"] = sum(1 for x in szinek.values() if x["fenyegetes"] and not x["adu"])
    g["impassz_szinek"] = sum(1 for x in szinek.values() if x["impasszolhato"])
    # elimináció: adu mindkét kézben (a lopás-dobás fenyegetéséhez), és van szín, amelyet a
    # védőnek kedvező megnyitnia (impasszolható vagy szöktethető)
    g["eliminalhato"] = bool(h.adu) and g["adu_d"] >= 2 and g["adu_y"] >= 2 and any(
        (x["impasszolhato"] or x["expasszolhato"]) and not x["adu"] for x in szinek.values())
    # a szükséges plusz ütés: szanban a hiány (cél − biztos), színben a vesztők többlete
    g["szukseges_plusz"] = g["hiany"] if h.adu is None else g["vesztok_tobblet"]
    # ELVI ÜTÉSPOTENCIÁL típusonként (optimista: minden impassz / expassz bejön):
    # kimagasítás — a hosszból szerezhető ütések + színenként egy impassz/expassz
    g["pot_kimagasitas"] = sum(x["tobblet"] + (1 if (x["impasszolhato"] or x["expasszolhato"])
                                               and x["kiadando"] > 0 else 0)
                               for x in szinek.values())
    g["pot_lopas"] = g["lopas_rovid"] + (1 if g["asztalforditas"] or g["keresztlopas"] else 0)
    g["pot_dobas"] = g["dobas"] if h.adu else 0
    g["pot_vegjatek"] = 1 if g["eliminalhato"] else 0
    g["pot_beszoritas"] = 1 if g["fenyegetes"] >= 2 else 0
    hiv = szinek.get(h.indulas.szin) if h.indulas else None
    g["hivott_egy_fogas"] = bool(hiv and h.adu is None and hiv["egy_fogas"])
    g["hivott_kint"] = hiv["kint"] if hiv else 0
    return g, szinek


# --- 2. Feltételek -------------------------------------------------------------------

def _illik(ertek, felt) -> bool:
    if isinstance(felt, list):
        return any(_illik(ertek, f) for f in felt)
    if isinstance(felt, bool):
        return bool(ertek) is felt
    if ertek is None:
        return False
    if isinstance(felt, (int, float)) and not isinstance(felt, bool):
        return ertek == felt
    s = str(felt).strip()
    if s in ("igen", "nem"):
        return bool(ertek) is (s == "igen")
    if isinstance(ertek, str):
        return ertek == s
    if s.endswith("+"):
        return ertek >= float(s[:-1])
    if s.endswith("-") and s[:-1].lstrip("-").replace(".", "").isdigit():
        return ertek <= float(s[:-1])
    if "-" in s[1:]:
        a, b = s.split("-", 1)
        return float(a) <= ertek <= float(b)
    try:
        return ertek == float(s)
    except ValueError:
        return False


# --- 3. Tervsorok: betöltés, hivatkozás --------------------------------------------

@dataclass
class TervSor:
    kod: str
    fajta: str                        # TIPUS / VALTOZAT
    tipus: str                        # a típus kódja (a változatnál a hivatkozási lánc gyökere)
    nev: str = ""
    feltetel: dict = field(default_factory=dict)      # feloldva (öröklés + eltérés)
    szinenkent: bool = False
    cimkek: list[str] = field(default_factory=list)
    potencial: str | None = None      # a fogalom, amely a típus elvi ütésszámát adja


class TervHiba(ValueError):
    pass


def tervsorok_yamlbol(utak: list[str | Path]) -> list[TervSor]:
    """A tervsorok (YAML-fájlok vagy mappák) betöltése és a hivatkozások feloldása."""
    import yaml
    nyers: dict[str, dict] = {}
    for ut in utak:
        p = Path(ut)
        fajlok = sorted(p.glob("*.yaml")) if p.is_dir() else [p]
        for f in fajlok:
            for sor in yaml.safe_load(f.read_text(encoding="utf-8")) or []:
                kod = sor.get("tipus") or sor.get("valtozat")
                if not kod:
                    raise TervHiba(f"{f}: sor kód nélkül: {sor}")
                if kod in nyers:
                    raise TervHiba(f"{f}: kétszer szerepel: {kod}")
                nyers[kod] = dict(sor, _fajta="TIPUS" if "tipus" in sor else "VALTOZAT")
    kesz: dict[str, TervSor] = {}

    def felold(kod: str, lanc: tuple = ()) -> TervSor:
        if kod in kesz:
            return kesz[kod]
        if kod in lanc:
            raise TervHiba(f"körkörös hivatkozás: {' → '.join(lanc + (kod,))}")
        if kod not in nyers:
            raise TervHiba(f"ismeretlen hivatkozás: {kod}")
        s = nyers[kod]
        alap = s.get("alap")
        if alap:
            a = felold(alap, lanc + (kod,))
            felt, tipus = dict(a.feltetel), a.tipus
            szinenkent, cimkek = a.szinenkent, list(a.cimkek)
        else:
            felt, tipus, szinenkent, cimkek = {}, kod, False, []
        for k in s.get("kivon") or []:
            felt.pop(k, None)
        felt.update(s.get("szuro") or {})
        felt.update(s.get("ha") or {})
        felt.update((s.get("felulir") or {}).get("ha") or {})
        if "szinenkent" in s:
            szinenkent = bool(s["szinenkent"])
        if s.get("cimkek"):
            cimkek = list(s["cimkek"])
        potencial = s.get("potencial") or (kesz[alap].potencial if alap else None)
        kesz[kod] = TervSor(kod, s["_fajta"], tipus, s.get("nev", ""), felt, szinenkent, cimkek,
                            potencial)
        return kesz[kod]

    return [felold(k) for k in nyers]


def illeszkedik(sor: TervSor, glob: dict, szinek: dict[str, dict]) -> list[str] | None:
    """None, ha nem illik; különben azok a színek, amelyekre illik ([] = színtől független)."""
    g = {k: v for k, v in sor.feltetel.items() if not k.startswith("szin.")}
    s = {k[5:]: v for k, v in sor.feltetel.items() if k.startswith("szin.")}
    for k, v in g.items():
        if k not in glob:
            raise TervHiba(f"{sor.kod}: ismeretlen fogalom: {k}")
        if not _illik(glob[k], v):
            return None
    if not s and not sor.szinenkent:
        return []
    jo = [sz for sz, x in szinek.items()
          if all(_illik(x.get(k), v) for k, v in s.items())]
    return jo or None


def felismeres(sorok: list[TervSor], h: Helyzet) -> dict[str, list[str]]:
    """Mely típusok illenek (a típus szűrője ÉS legalább egy változata, ha van)?
    Vissza: {típus: [az illő változatok kódjai]} (változat nélküli típusnál a típus maga)."""
    glob, szinek = jellemzok(h)
    van_valtozat = {s.tipus for s in sorok if s.fajta == "VALTOZAT"}
    ki: dict[str, list[str]] = {}
    for s in sorok:
        if s.fajta == "TIPUS" and s.kod in van_valtozat:
            continue                 # absztrakt: a változatai döntenek (a szűrőt öröklik)
        if illeszkedik(s, glob, szinek) is not None:
            ki.setdefault(s.tipus, []).append(s.kod)
    return ki


def helyzet_partibol(p) -> Helyzet | None:
    """lejatszas_meres.Parti → a felvevő helyzete az indulás után."""
    k = p.kontraktus
    if k is None:
        return None
    asztal = kovetkezo_ules(k.felvevo, 2)
    indulas = Lap.parse(p.lapok[0]) if p.lapok else None
    return Helyzet(k.felvevo, k.szint, k.szin, set(p.leosztas.kezek[k.felvevo].lapok),
                   set(p.leosztas.kezek[asztal].lapok), indulas)


def elegendo(sorok: list[TervSor], h: Helyzet, fel: dict | None = None) -> dict:
    """
    Az ELVI elegendőség (2026-10-25, 1. szint): a felismert ütésforrás-típusok
    elvi ütéspotenciálja lefedi-e a szükséges plusz ütést. Ha egy típus egymagában
    elég, azok a típusok; ha egyik sem, a legkisebb kombináció (a YAML sorrendjében
    előbb álló típusok előnyben). Vissza: {"szukseges", "potencial": {típus: ütés},
    "elegendo": [[típus, ...], ...], "eleg": bool}.
    """
    glob, _ = jellemzok(h)
    fel = felismeres(sorok, h) if fel is None else fel
    tipus_sor = {s.kod: s for s in sorok if s.fajta == "TIPUS"}
    pot = {}
    for t in fel:
        s = tipus_sor.get(t)
        if s is not None and s.potencial and glob.get(s.potencial):
            pot[t] = glob[s.potencial]
    kell = glob.get("szukseges_plusz") or 0
    if kell <= 0:
        return {"szukseges": kell, "potencial": pot, "elegendo": [], "eleg": True}
    from itertools import combinations
    sorrend = [t for t in tipus_sor if t in pot]
    for n in range(1, len(sorrend) + 1):
        jo = [list(c) for c in combinations(sorrend, n) if sum(pot[t] for t in c) >= kell]
        if jo:
            return {"szukseges": kell, "potencial": pot, "elegendo": jo, "eleg": True}
    return {"szukseges": kell, "potencial": pot, "elegendo": [sorrend] if sorrend else [],
            "eleg": False}
