"""
A LEJÁTSZÁS MÉRÉSE (2026-10-23): lapankénti DD-veszteség.

Minden kijátszott lapról megmondható, hány ütést ad el a lehető legjobbhoz
képest, ha a teljes osztás ismert (double dummy, a valódi lapokkal). Ez a
lejátszás tiszta mércéje — a licitben ilyen nem volt. Két forrás:

  1. A KIBIC NAPLÓJA (KIBIC_ATJARO_NAPLO, a kérésekkel: ..._NAPLO_KERES=1).
     Egy leosztás kéréseiből a teljes osztás visszaállítható (a látható
     kezek + a lejátszott lapok; ami hiányzik, az a renonszokból). Így a
     kibic minden lapjáról: DD-veszteség, és hogy megváltoztatta-e az
     eredményt (teljesítés / bukás).

  2. VALÓDI PARTIK (LIN-fájl vagy az adatbázis `jatszma` táblája): a
     lejátszás minden pontján megkérdezzük a kibicet, mit tenne ugyanabban
     a helyzetben (ugyanaz az előzmény, ugyanaz a látható lap), és a lapját
     DD-ben összevetjük azzal, amit az ember tett. Döntésenkénti kibic–ember
     összevetés (a kibic itt nem a saját előzményén játszik, hanem az
     emberén — a döntés minősége így közvetlenül összevethető).

FIGYELEM: a DD-veszteség FELSŐ korlát. A lap, amely nyílt lapokkal ütést ad
el, a valódi információ birtokában lehet ésszerű (találgatás). Ezért a mérés
mellé a kibic és az ember EGYMÁSHOZ mért eredménye a beszédes: ugyanazon a
helyzeten melyikük ad el többet.

A modul NEM nyúl adatbázishoz és hálózathoz: a DD-függvényt és a kibic
döntését kívülről kapja (cli/jatekmeres.py köti össze).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from itertools import combinations

from ..domain import LAPOK, SZINEK, ULESEK, Kez, Lap, Leosztas, kovetkezo_ules, vonal
from . import lejatszas as lj


@dataclass
class DontesMeres:
    tabla: str                      # a leosztás azonosítója (meccs/tábla/asztal vagy fájl#sor)
    ules: str                       # aki a lapot tette (az asztal lapjánál az asztal ülése)
    utes: int                       # hányadik ütés (1-13)
    helyzet: str                    # INDITAS / HIVAS / SZINADAS / DOBAS / FELVEVO / KENYSZER
    lap: str                        # a kibic lapja
    veszt: int                      # ennyi ütést ad el a legjobbhoz képest (DD)
    eredmeny_veszt: bool            # a legjobb lap teljesít / buktat, ez nem
    legjobb: list[str] = field(default_factory=list)
    szabaly: str | None = None      # a jelzésrendszer kulcsa, ha az döntött
    felvevo_oldal: bool = False     # a felvevő vonala játszott-e
    emberi_lap: str | None = None   # valódi partinál: amit az ember tett
    emberi_veszt: int | None = None
    emberi_eredmeny_veszt: bool | None = None
    ido_ms: int | None = None
    # a napló nem egyértelmű osztásánál: a veszteség a lehetséges kiegészítéseken
    # `veszt`..`veszt_max` között van — ez nem számít az összesítésbe
    bizonytalan: bool = False
    veszt_max: int | None = None
    megallt: str | None = None      # a mintavétel miért állt meg (BIZTOS / IDO / MAX / KIMERITO …)
    # IMP-veszteség (2026-10-23): a legjobb lap pontszámához képest, a beliállás
    # és a kontra szerint — IMP-ben a felülütés alig számít, a teljesítés sokat
    imp_veszt: int | None = None
    emberi_imp_veszt: int | None = None
    minta: int | None = None        # ennyi mintán döntött

    def szotar(self) -> dict:
        return asdict(self)


# --- Segédek ------------------------------------------------------------------------

def _lap(x) -> Lap:
    return x if isinstance(x, Lap) else lj.lap_drotrol(str(x))


def _nyertes(utes: list[tuple[str, Lap]], adu: str | None) -> str:
    """Az ütés nyertese (teljes ütésre)."""
    legjobb = utes[0]
    for u, l in utes[1:]:
        b = legjobb[1]
        if (l.szin == b.szin and l.rang > b.rang) or (adu and l.szin == adu and b.szin != adu):
            legjobb = (u, l)
    return legjobb[0]


def ulesek_sorrendben(lapok: list[Lap], kijatszo: str, adu: str | None) -> list[str]:
    """A lapok (időrendben) mellé, hogy ki tette őket."""
    ki, soron, utes = [], kijatszo, []
    for l in lapok:
        ki.append(soron)
        utes.append((soron, l))
        if len(utes) == 4:
            soron = _nyertes(utes, adu)
            utes = []
        else:
            soron = kovetkezo_ules(soron)
    return ki


def _cel(k) -> int:
    return 6 + k.szint


def eredmeny_ertekeles(dd: dict[str, object], lap: str, felvevo_oldal: bool, cel: int
                       ) -> tuple[int, bool, list[str]]:
    """
    (veszteség ütésben, az eredményt rontotta-e, a legjobb lapok) — a
    `dd`: {lap: LapErtekeles}. Az eredmény: felvevőként a teljesítés,
    védőként a bukás.
    """
    legtobb = max(e.utesek for e in dd.values())
    legjobb = sorted(l for l, e in dd.items() if e.utesek == legtobb)
    e = dd[lap]

    def cel_ok(x) -> bool:
        return x.felvevo_osszesen >= cel if felvevo_oldal else x.felvevo_osszesen < cel
    jo_eredmeny = any(cel_ok(x) for x in dd.values())
    return legtobb - e.utesek, bool(jo_eredmeny and not cel_ok(e)), legjobb


def imp_ertekeles(dd: dict[str, object], lap: str, felvevo_oldal: bool, kontraktus,
                  beliallas: str) -> int:
    """IMP-veszteség a DD szerinti legjobb lap pontszámához képest (a lapot
    tevő oldal szemszögéből)."""
    from ..domain.pontozas import imp, pontszam

    def ertek(x) -> int:
        p = pontszam(kontraktus, x.felvevo_osszesen, beliallas or "NONE")
        return p if felvevo_oldal else -p
    return imp(max(ertek(x) for x in dd.values()) - ertek(dd[lap]))


def _dd_szotar(dd_fv, leosztas: Leosztas, jatszott: list[str], kontraktus) -> dict:
    ki = {}
    for e in dd_fv(leosztas, jatszott, kontraktus):
        ki[str(_lap(e.lap))] = e
    return ki


# --- 1. A napló ------------------------------------------------------------------

def tabla_kulcs(keres: dict, sor: dict | None = None) -> str:
    g = keres.get("game") or {}
    if g.get("match_id") is not None and g.get("board_number") is not None:
        return f"{g.get('match_id')}/{g.get('board_number')}/{g.get('table_index', 0)}"
    s = (sor or {}).get("session") or ""
    return s.rsplit(":", 1)[0] if s else str(keres.get("request_id", "?"))


MAX_KIEGESZITES = 60


def osztasok_kerelmekbol(kerelmek: list[dict], hatar: int = MAX_KIEGESZITES) -> list[Leosztas]:
    """
    A teljes osztás(ok) egy leosztás kéréseiből: a látható kezek és a lejátszott
    lapok uniója ülésenként; ami még hiányzik (pl. a napló a parti vége előtt
    ér véget), azt a renonszok szerint minden lehetséges módon kiosztjuk.
    Ha ez `hatar`-nál több, vagy ellentmondás van: üres lista.
    """
    lapok: dict[str, set[Lap]] = {u: set() for u in ULESEK}
    utolso = None
    for k in kerelmek:
        st = k.get("state") or {}
        for u, v in (st.get("visible_hands") or {}).items():
            u = str(u).upper()
            if u in lapok:
                lapok[u] |= {_lap(x) for x in v}
        for x in ((k.get("history") or {}).get("play") or []):
            u = str(x.get("seat") or "").upper()
            if u in lapok:
                lapok[u].add(_lap(x.get("card")))
        if utolso is None or len((k.get("history") or {}).get("play") or []) >= \
                len((utolso.get("history") or {}).get("play") or []):
            utolso = k
    osszes = [l for u in ULESEK for l in lapok[u]]
    if len(osszes) != len(set(osszes)) or any(len(v) > 13 for v in lapok.values()):
        return []
    st = (utolso or {}).get("state") or {}
    oszto = str(st.get("dealer") or "N").upper()[:1]
    oszto = oszto if oszto in ULESEK else "N"
    marad = [Lap(sz, e) for sz in SZINEK for e in LAPOK if Lap(sz, e) not in set(osszes)]
    hiany = {u: 13 - len(lapok[u]) for u in ULESEK if len(lapok[u]) < 13}
    if not hiany:
        return [Leosztas({u: Kez(frozenset(v)) for u, v in lapok.items()}, oszto=oszto)]
    try:
        renonsz = lj.allas_keresbol(utolso).renonszok() if utolso else {}
    except lj.LejatszasHiba:
        renonsz = {}
    megoldas: list[dict] = []
    ulesek = list(hiany)

    def rek(i, maradek, hely):
        if len(megoldas) > hatar:
            return
        u = ulesek[i]
        if i == len(ulesek) - 1:
            if all(l.szin not in renonsz.get(u, ()) for l in maradek):
                megoldas.append({**hely, u: list(maradek)})
            return
        for v in combinations(maradek, hiany[u]):
            if any(l.szin in renonsz.get(u, ()) for l in v):
                continue
            vs = set(v)
            rek(i + 1, [l for l in maradek if l not in vs], {**hely, u: list(v)})
    rek(0, marad, {})
    if not megoldas or len(megoldas) > hatar:
        return []
    return [Leosztas({u: Kez(frozenset(lapok[u] | set(m.get(u, ())))) for u in ULESEK},
                     oszto=oszto) for m in megoldas]


def osztas_kerelmekbol(kerelmek: list[dict]) -> Leosztas | None:
    """Az osztás, ha egyértelműen visszaállítható; különben None."""
    o = osztasok_kerelmekbol(kerelmek, hatar=1)
    return o[0] if len(o) == 1 else None


def naplo_meres(sorok: list[dict], dd_fv=None) -> tuple[list[DontesMeres], dict]:
    """
    A napló play-sorai (a kéréssel együtt) -> döntésenkénti mérés.
    Visszaadja: (mérések, {"tablak", "visszaallitva", "kihagyva", "keres_nelkul"}).
    """
    if dd_fv is None:
        from ..solver.dds import lap_elemzes as dd_fv
    tablak: dict[str, list[dict]] = {}
    keres_nelkul = 0
    for d in sorok:
        if d.get("decision") != "play":
            continue
        if "request" not in d:
            keres_nelkul += 1
            continue
        tablak.setdefault(tabla_kulcs(d["request"], d), []).append(d)
    ki: list[DontesMeres] = []
    stat = {"tablak": len(tablak), "visszaallitva": 0, "reszben": 0, "kihagyva": 0,
            "bizonytalan_dontes": 0, "keres_nelkul": keres_nelkul}
    for kulcs, dk in tablak.items():
        osztasok = osztasok_kerelmekbol([x["request"] for x in dk])
        if not osztasok:
            stat["kihagyva"] += 1
            continue
        stat["visszaallitva" if len(osztasok) == 1 else "reszben"] += 1
        for d in dk:
            k = d["request"]
            try:
                a = lj.allas_keresbol(k)
            except lj.LejatszasHiba:
                continue
            lap = str(_lap((d.get("action") or {}).get("card")))
            jatszott = [str(l) for _, l in a.lejatszott]
            fo = vonal(a.ules) == vonal(a.felvevo)
            # ha a hiányzó lapok helye nem egyértelmű: csak az számít, ami
            # MINDEN lehetséges kiegészítésben ugyanaz
            ertekek = set()
            legjobb = []
            for osztas in osztasok:
                dd = _dd_szotar(dd_fv, osztas, jatszott, a.kontraktus)
                if lap not in dd:
                    break
                v, e_, legjobb = eredmeny_ertekeles(dd, lap, fo, _cel(a.kontraktus))
                ertekek.add((v, e_, imp_ertekeles(dd, lap, fo, a.kontraktus, a.beliallas)))
            if not ertekek:
                continue
            bizonytalan = len(ertekek) > 1
            stat["bizonytalan_dontes"] += int(bizonytalan)
            veszt = min(v for v, _, _ in ertekek)
            ered = all(e_ for _, e_, _ in ertekek)
            mk = ((d.get("meta") or {}).get("kibic") or {})
            helyzet = mk.get("situation") or ("KENYSZER" if len(a.legalis) == 1 else "?")
            ki.append(DontesMeres(tabla=kulcs, ules=a.ules, utes=len(jatszott) // 4 + 1,
                                  helyzet=helyzet, lap=lap, veszt=veszt, eredmeny_veszt=ered,
                                  legjobb=[] if bizonytalan else legjobb, szabaly=mk.get("rule"),
                                  felvevo_oldal=fo, ido_ms=(d.get("meta") or {}).get("elapsed_ms"),
                                  bizonytalan=bizonytalan,
                                  veszt_max=max(v for v, _, _ in ertekek) if bizonytalan else None,
                                  megallt=mk.get("stopped"), minta=mk.get("samples"),
                                  imp_veszt=min(i for _, _, i in ertekek)))
    return ki, stat


# --- 2. Valódi parti, pozícióról pozícióra -----------------------------------------

@dataclass
class Parti:
    """Egy lejátszott parti a méréshez (LIN-ből vagy az adatbázisból)."""
    azonosito: str
    leosztas: Leosztas
    kontraktus: object              # domain.Kontraktus (felvevővel)
    licit: list[dict]               # [{"ules", "licit"}]
    lapok: list[str]                # időrendben
    pontozas: str = "IMP"
    jatekosok: dict = field(default_factory=dict)


_SZIN_DROT = {"NT": "NT", "S": "S", "H": "H", "D": "D", "C": "C"}


def pozicio_keres(p: Parti, i: int, rendszer: str = "KIBIC_STAND") -> dict:
    """
    A gateway-kérés (mohabridzs-ai 1.x) a parti i-edik lapja ELŐTT, annak a
    szemszögéből, aki azt a lapot teszi (az asztal lapjánál a felvevő játszik
    érte). Ugyanaz a látható lap és előzmény, amit az ember látott.
    """
    k = p.kontraktus
    adu = None if k.szin == "NT" else k.szin
    felvevo = k.felvevo
    asztal = kovetkezo_ules(felvevo, 2)
    lapok = [_lap(x) for x in p.lapok]
    ulesek = ulesek_sorrendben(lapok, kovetkezo_ules(felvevo), adu)
    ules = ulesek[i]
    cselekvo = felvevo if ules == asztal else ules
    eddig = lapok[:i]
    letett = {u: {l for l, uu in zip(eddig, ulesek) if uu == u} for u in ULESEK}

    def maradek(u):
        return sorted((l for l in p.leosztas.kezek[u].lapok if l not in letett[u]),
                      key=lambda l: (l.szin, -l.rang))
    lathato = {cselekvo: maradek(cselekvo)}
    if i >= 1:                                   # az indítás után az asztal látszik
        lathato[asztal] = maradek(asztal)
    if ules == asztal:
        lathato[asztal] = maradek(asztal)
    sajat = maradek(ules)
    n = i % 4
    hivott = eddig[i - n].szin if n else None
    legalis = [l for l in sajat if l.szin == hivott] if hivott else []
    legalis = legalis or sajat
    kontra = {"": 1, "X": 2, "XX": 4}.get(getattr(k, "kontra", "") or "", 1)
    return {
        "protocol": "mohabridzs-ai/1.1", "request_id": f"{p.azonosito}:{i}",
        "decision": "play", "deadline_ms": 60000,
        "game": {"scoring": p.pontozas, "match_id": p.azonosito, "board_number": 0,
                 "table_index": 0, "vulnerability": {"NONE": "none", "NS": "ns", "EW": "ew",
                                                     "ALL": "both"}.get(p.leosztas.beliallas, "none"),
                 "systems": {"NS": rendszer, "EW": rendszer}},
        "actor": {"seat": cselekvo, "acting_for_seat": ules,
                  "is_declarer": cselekvo == felvevo, "controls_dummy": cselekvo == felvevo},
        "state": {"phase": "play", "dealer": p.leosztas.oszto, "current_seat": ules,
                  "contract": {"level": k.szint, "strain": _SZIN_DROT.get(k.szin, k.szin),
                               "multiplier": kontra},
                  "declarer": felvevo, "dummy": asztal,
                  "visible_hands": {u: [str(l) for l in v] for u, v in lathato.items()}},
        "history": {"auction": [{"seat": x.get("ules"),
                                 "call": str(x.get("licit")).replace("PASS", "P")}
                                for x in p.licit],
                    "play": [{"seat": u, "card": str(l)} for u, l in zip(ulesek, eddig)]},
        "legal_actions": {"cards": [str(l) for l in legalis]},
    }


def parti_meres(p: Parti, dontes_fv, dd_fv=None, ulesek: set[str] | None = None,
                felvevo_oldal: bool | None = None, kenyszer: bool = False,
                rendszer: str = "KIBIC_STAND", max_dontes: int | None = None
                ) -> list[DontesMeres]:
    """
    A parti minden (szűrt) pozícióján a kibic döntése és az emberé, DD-ben.
    `dontes_fv(keres) -> (lap, meta)`; `ulesek`: csak ezek a ülések lapjai;
    `felvevo_oldal`: True csak a felvevő vonala, False csak a védők, None mind;
    `kenyszer`: a kényszerű (egyetlen szabályos) lapokat is mérje-e.
    """
    import time
    if dd_fv is None:
        from ..solver.dds import lap_elemzes as dd_fv
    k = p.kontraktus
    adu = None if k.szin == "NT" else k.szin
    lapok = [_lap(x) for x in p.lapok]
    ulesek_ = ulesek_sorrendben(lapok, kovetkezo_ules(k.felvevo), adu)
    ki: list[DontesMeres] = []
    for i in range(min(len(lapok), 52)):
        u = ulesek_[i]
        fo = vonal(u) == vonal(k.felvevo)
        if ulesek and u not in ulesek:
            continue
        if felvevo_oldal is not None and fo != felvevo_oldal:
            continue
        keres = pozicio_keres(p, i, rendszer)
        if not kenyszer and len(keres["legal_actions"]["cards"]) == 1:
            continue
        if max_dontes is not None and len(ki) >= max_dontes:
            break
        dd = _dd_szotar(dd_fv, p.leosztas, [str(l) for l in lapok[:i]], k)
        emberi = str(lapok[i])
        if emberi not in dd:
            continue
        t0 = time.time()
        lap, meta = dontes_fv(keres)
        lap = str(_lap(lap))
        if lap not in dd:
            continue
        cel = _cel(k)
        veszt, ered, legjobb = eredmeny_ertekeles(dd, lap, fo, cel)
        e_veszt, e_ered, _ = eredmeny_ertekeles(dd, emberi, fo, cel)
        beli = p.leosztas.beliallas
        mk = (meta or {}).get("kibic") or {}
        ki.append(DontesMeres(
            tabla=p.azonosito, ules=u, utes=i // 4 + 1,
            helyzet=mk.get("situation") or "?", lap=lap, veszt=veszt, eredmeny_veszt=ered,
            legjobb=legjobb, szabaly=mk.get("rule"), felvevo_oldal=fo,
            emberi_lap=emberi, emberi_veszt=e_veszt, emberi_eredmeny_veszt=e_ered,
            ido_ms=int((time.time() - t0) * 1000), megallt=mk.get("stopped"),
            minta=mk.get("samples"), imp_veszt=imp_ertekeles(dd, lap, fo, k, beli),
            emberi_imp_veszt=imp_ertekeles(dd, emberi, fo, k, beli)))
    return ki


# --- Teljes lejátszás (2026-10-25) ------------------------------------------------
# A döntésenkénti mérés mindig az EMBER útján halad tovább: a kibic sosem kerül
# a saját hibája utáni helyzetbe. Itt a kibic a valódi indulástól a végéig maga
# játssza a felvevőt (és az asztalt); a védők a valódi lapok ismeretében
# tökéletesen (DD; egyenlőségnél a legkisebb lappal) — vagy, `vedo_fv`-vel, egy
# másik döntéshozó szerint. Az eredmény a parti végén: hány ütés, teljesült-e,
# és mennyi lett volna tökéletes felvevőjátékkal (DD az indulás után).

@dataclass
class TeljesMeres:
    tabla: str
    kontraktus: str
    felvevo: str
    cel: int
    utesek: int                 # a kibic felvevőként (a végén)
    dd_indulas_utan: int        # tökéletes felvevőjátékkal a valódi indulás után
    teljesult: bool
    dd_teljesul: bool
    imp_veszt: int              # a DD-hez képest (beliállással, kontrával)
    hibak: list[dict] = field(default_factory=list)   # ahol a kibic lapja ütést vesztett (DD)
    ido_ms: int = 0

    def szotar(self) -> dict:
        return dict(self.__dict__)


def teljes_lejatszas(p: Parti, dontes_fv, dd_fv=None, vedo_fv=None,
                     rendszer: str = "KIBIC_STAND") -> TeljesMeres | None:
    """A valódi indulás után a kibic játssza végig a felvevőt (lásd fent)."""
    import time
    from dataclasses import replace
    from ..domain.pontozas import imp, pontszam
    if dd_fv is None:
        from ..solver.dds import lap_elemzes as dd_fv
    if not p.lapok:
        return None
    t0 = time.time()
    k = p.kontraktus
    adu = None if k.szin == "NT" else k.szin
    felvevo = k.felvevo
    sor = [_lap(p.lapok[0])]                     # a valódi indulás
    dd0 = _dd_szotar(dd_fv, p.leosztas, [str(sor[0])], k)
    if not dd0:
        return None
    ul0 = ulesek_sorrendben(sor + [sor[0]], kovetkezo_ules(felvevo), adu)
    fo0 = vonal(ul0[1]) == vonal(felvevo)
    dd_ertek = (max if fo0 else min)(e.felvevo_osszesen for e in dd0.values())
    hibak: list[dict] = []
    while len(sor) < 52:
        ules = ulesek_sorrendben(sor + [sor[0]], kovetkezo_ules(felvevo), adu)[len(sor)]
        jatszott = [str(l) for l in sor]
        dd = _dd_szotar(dd_fv, p.leosztas, jatszott, k)
        fo = vonal(ules) == vonal(felvevo)
        if len(dd) == 1:
            lap = next(iter(dd))
        elif fo or vedo_fv is not None:
            p2 = replace(p, lapok=jatszott + [jatszott[0]])
            keres = pozicio_keres(p2, len(sor), rendszer)
            lap, _ = (dontes_fv if fo else vedo_fv)(keres)
            lap = str(_lap(lap))
            if lap not in dd:                    # nem lehet, de ne álljon meg
                lap = max(dd, key=lambda x: dd[x].utesek)
        else:
            legj = max(e.utesek for e in dd.values())
            lap = str(min((_lap(x) for x, e in dd.items() if e.utesek == legj),
                          key=lambda l: (l.rang, l.szin)))
        if fo and len(dd) > 1:
            legjobb = max(e.felvevo_osszesen for e in dd.values())
            if dd[lap].felvevo_osszesen < legjobb:
                hibak.append({"utes": len(sor) // 4 + 1, "ules": ules, "lap": lap,
                              "veszt": legjobb - dd[lap].felvevo_osszesen,
                              "legjobb": sorted(x for x, e in dd.items()
                                                if e.felvevo_osszesen == legjobb)})
        sor.append(_lap(lap))
    utes = 0
    ulesek_ = ulesek_sorrendben(sor, kovetkezo_ules(felvevo), adu)
    for t in range(13):
        utes_ = list(zip(ulesek_[4 * t:4 * t + 4], sor[4 * t:4 * t + 4]))
        if vonal(_nyertes(utes_, adu)) == vonal(felvevo):
            utes += 1
    cel = _cel(k)
    beli = p.leosztas.beliallas
    veszt = imp(pontszam(k, dd_ertek, beli) - pontszam(k, utes, beli)) if utes < dd_ertek else 0
    return TeljesMeres(p.azonosito, str(k), felvevo, cel, utes, dd_ertek, utes >= cel,
                       dd_ertek >= cel, veszt, hibak, int((time.time() - t0) * 1000))


# --- Összesítés --------------------------------------------------------------------

def osszesit(meresek: list[DontesMeres]) -> dict:
    """Helyzetenként (és összesen): darab, ütésveszteség, eredményt rontó lapok.
    A bizonytalan (nem egyértelmű osztású) döntések kimaradnak."""
    meresek = [m for m in meresek if not m.bizonytalan]
    def blokk(xs: list[DontesMeres]) -> dict:
        b = {"db": len(xs), "veszt_ossz": sum(x.veszt for x in xs),
             "hibas_lap": sum(1 for x in xs if x.veszt > 0),
             "eredmeny_veszt": sum(1 for x in xs if x.eredmeny_veszt),
             "imp_ossz": sum(x.imp_veszt or 0 for x in xs)}
        emb = [x for x in xs if x.emberi_veszt is not None]
        if emb:
            # ki volt a jobb: IMP-ben (ha van), egyenlőségnél ütésben
            def kulcs(x, ember):
                return ((x.emberi_imp_veszt if ember else x.imp_veszt) or 0,
                        x.emberi_veszt if ember else x.veszt)
            b.update({"ember_veszt_ossz": sum(x.emberi_veszt for x in emb),
                      "ember_hibas_lap": sum(1 for x in emb if x.emberi_veszt > 0),
                      "ember_eredmeny_veszt": sum(1 for x in emb if x.emberi_eredmeny_veszt),
                      "ember_imp_ossz": sum(x.emberi_imp_veszt or 0 for x in emb),
                      "kibic_jobb": sum(1 for x in emb if kulcs(x, False) < kulcs(x, True)),
                      "ember_jobb": sum(1 for x in emb if kulcs(x, False) > kulcs(x, True))})
        return b
    helyzetek = sorted({x.helyzet for x in meresek})
    return {"osszes": blokk(meresek),
            "felvevo": blokk([x for x in meresek if x.felvevo_oldal]),
            "vedo": blokk([x for x in meresek if not x.felvevo_oldal]),
            "helyzetenkent": {h: blokk([x for x in meresek if x.helyzet == h]) for h in helyzetek}}
