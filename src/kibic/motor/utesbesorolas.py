"""
Ütésbesorolás: egy végigjátszott parti ütéseiből kiolvassuk a technikákat
(2026-10-25, játék-szál).

A DD-elemző csak ütésszámot ad; a lapsor viszont lapról lapra végigjátszható
vele (`dd_lapsor`), és a négy kéz ismeretében minden ütés utólag besorolható:
lopás (kinek a hívását), kimagasodott lap, impassz / expassz (szöktetés), a
védő által meghívott impassz, eső figura, dobás (vesztő a vesztőre, dobás
nyerőre), őrzőlap-dobás (beszorítás), lopás-dobás, kihagyás.

FIGYELEM: egy DD-lapsor egyetlen világban mindent „eltalál” (stratégiai
összeolvadás) — a technikák gyakoriságát sok sorsolt világon érdemes nézni.
Egyenlő értékű lapoknál a lapsor a legkisebb lapot teszi.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..domain import Lap, kovetkezo_ules, vonal

FIGURA = 11          # B-től felfelé


def _nyertes(utes: list[tuple[str, Lap]], adu: str | None) -> tuple[str, Lap]:
    legjobb = utes[0]
    for u, l in utes[1:]:
        b = legjobb[1]
        if (l.szin == b.szin and l.rang > b.rang) or (adu and l.szin == adu and b.szin != adu):
            legjobb = (u, l)
    return legjobb


def dd_lapsor(leosztas, kontraktus, eleje: list[str], dd_fv=None) -> list[str]:
    """A megadott lapok után mind a négy kéz DD szerint játszik (egyenlőségnél a
    legkisebb lappal). Vissza: az 52 lap időrendben (szövegként)."""
    if dd_fv is None:
        from ..solver.dds import lap_elemzes as dd_fv
    from .lejatszas_meres import _lap
    sor = [str(_lap(x)) for x in eleje]
    while len(sor) < 52:
        ered = dd_fv(leosztas, sor, kontraktus)
        if not ered:
            break
        legj = max(e.utesek for e in ered)
        lap = min((_lap(e.lap) for e in ered if e.utesek == legj), key=lambda l: (l.rang, l.szin))
        sor.append(str(lap))
    return sor


_ULESEK = "NESW"


def szin_utesek(kezek: dict[str, frozenset[int]], mi: str) -> int:
    """Egyetlen szín DD ütésszáma a mi oldalunknak, ha mindig mi hívunk (bármelyik
    kezünkből — az átmeneteket nem nézzük). A lapok helye számít (impassz)."""
    from functools import lru_cache

    @lru_cache(maxsize=None)
    def ertek(allas: tuple) -> int:
        k = dict(zip(_ULESEK, allas))
        if not any(k[u] for u in _ULESEK if vonal(u) == mi):
            return 0
        best = -1
        for hivo in (u for u in _ULESEK if vonal(u) == mi and k[u]):
            best = max(best, kor(allas, hivo, 0, (), None))
        return best

    def osztalyok(lapok: frozenset[int], osszes: set[int]) -> list[int]:
        # egyenértékű lapok: a szín maradék lapjai között szomszédosak ugyanannál
        ki, s_ = [], sorted(osszes)
        for r in sorted(lapok):
            i = s_.index(r)
            if i > 0 and s_[i - 1] in lapok and s_[i - 1] in ki:
                continue
            ki.append(r)
        return ki

    def kor(allas: tuple, hivo: str, n: int, tett: tuple, _x) -> int:
        k = dict(zip(_ULESEK, allas))
        if n == 4:
            # az ütés eldőlt
            nyero = max(tett, key=lambda x: x[1]) if tett else None
            uj = tuple(frozenset(k[u]) for u in _ULESEK)
            return (1 if nyero and vonal(nyero[0]) == mi else 0) + ertek(uj)
        u = _ULESEK[(_ULESEK.index(hivo) + n) % 4]
        if not k[u]:
            return kor(allas, hivo, n + 1, tett, None)
        osszes = set().union(*k.values()) | {r for _, r in tett}   # az asztalon lévő is számít
        jelolt = osztalyok(k[u], osszes)
        vals = []
        for r in jelolt:
            uj = list(allas)
            uj[_ULESEK.index(u)] = k[u] - {r}
            vals.append(kor(tuple(uj), hivo, n + 1, tett + ((u, r),), None))
        return max(vals) if vonal(u) == mi else min(vals)

    return ertek(tuple(frozenset(kezek.get(u, ())) for u in _ULESEK))


@dataclass
class Esemeny:
    utes: int            # 1-től
    fajta: str
    ules: str            # aki a technikát végrehajtotta / elszenvedte
    lap: str
    szin: str


@dataclass
class Besorolas:
    esemenyek: list[Esemeny] = field(default_factory=list)
    felvevo_utes: int = 0

    def fajtak(self) -> Counter:
        return Counter(e.fajta for e in self.esemenyek)


def besorol(kezek: dict[str, list[Lap]], felvevo: str, adu: str | None,
            lapok: list[Lap]) -> Besorolas:
    """`kezek`: a négy kéz az induláskor; `lapok`: a lejátszott lapok időrendben."""
    mi = vonal(felvevo)
    asztal = kovetkezo_ules(felvevo, 2)
    maradek = {u: set(ls) for u, ls in kezek.items()}
    kezdo_adu = {u: sum(1 for l in kezek[u] if l.szin == adu) if adu else 0 for u in (felvevo, asztal)}
    rovid_adu_kez = min((felvevo, asztal), key=lambda u: (kezdo_adu[u], u != asztal))
    b = Besorolas()
    hivo = kovetkezo_ules(felvevo)
    # őrzőlap-dobások: (szín, ülés, a dobás ütése, a mi akkori legjobb lapunk a színben)
    orzo: list[tuple[str, str, int, int]] = []
    szoritott_ut: dict[int, set] = {}

    def kint(sz, kivul=()):  # a védők még meglévő lapjai egy színben
        return [l for u in maradek if vonal(u) != mi and u not in kivul for l in maradek[u] if l.szin == sz]

    def mi_lapok(sz):
        return [l for u in maradek if vonal(u) == mi for l in maradek[u] if l.szin == sz]

    for t in range(len(lapok) // 4):
        ul = []
        soron = hivo
        for l in lapok[4 * t:4 * t + 4]:
            ul.append((soron, l))
            soron = kovetkezo_ules(soron)
        hivott = ul[0][1].szin
        ny_ules, ny_lap = _nyertes(ul, adu)
        mi_nyert = vonal(ny_ules) == mi
        ut = t + 1
        # --- állapot az ütés ELŐTT (a besoroláshoz) ---
        elotte = {u: set(s) for u, s in maradek.items()}

        def kint_elotte(sz, kivul=()):
            return [l for u in elotte if vonal(u) != mi and u not in kivul for l in elotte[u] if l.szin == sz]

        # lopás
        if adu and ny_lap.szin == adu and hivott != adu:
            if mi_nyert:
                fajta = "LOPAS_SAJAT_HIVAS" if vonal(ul[0][0]) == mi else "LOPAS_VEDO_HIVAS"
                b.esemenyek.append(Esemeny(ut, fajta, ny_ules, str(ny_lap), hivott))
                if ny_ules == rovid_adu_kez:
                    b.esemenyek.append(Esemeny(ut, "LOPAS_ROVID_KEZBEN", ny_ules, str(ny_lap), hivott))
                else:
                    b.esemenyek.append(Esemeny(ut, "LOPAS_HOSSZU_KEZBEN", ny_ules, str(ny_lap), hivott))
                # lopás-dobás: a védő hívott, mindkét kezünk színhiányos, az egyik lop, a másik dob
                if vonal(ul[0][0]) != mi:
                    masik = [(u, l) for u, l in ul if vonal(u) == mi and u != ny_ules]
                    if masik and masik[0][1].szin not in (hivott, adu):
                        b.esemenyek.append(Esemeny(ut, "LOPAS_DOBAS", ny_ules, str(ny_lap), hivott))
            else:
                b.esemenyek.append(Esemeny(ut, "VEDO_LOP", ny_ules, str(ny_lap), hivott))
        elif mi_nyert:
            # nem lopással nyert ütés: magasabb lap még kint (impassz / expassz)?
            fent = [l for l in kint_elotte(hivott) if l.rang > ny_lap.rang]
            nyero_poz = [u for u, _ in ul].index(ny_ules)
            if fent:
                tartok = {u for u in elotte if vonal(u) != mi and any(
                    l.szin == hivott and l.rang > ny_lap.rang for l in elotte[u])}
                elotte_jatszott = {u for u, _ in ul[:nyero_poz]}
                if tartok and tartok <= elotte_jatszott:
                    nagyobb_nalunk = any(l.rang > max(x.rang for x in fent) for l in
                                         [l for u in elotte if vonal(u) == mi for l in elotte[u]
                                          if l.szin == hivott])
                    if vonal(ul[0][0]) == mi:
                        fajta = "IMPASSZ" if nagyobb_nalunk else "EXPASSZ"
                    else:
                        fajta = "VEDO_HIVTA_IMPASSZ"
                    b.esemenyek.append(Esemeny(ut, fajta, ny_ules, str(ny_lap), hivott))
                else:
                    b.esemenyek.append(Esemeny(ut, "VEDO_KIENGEDETT", ny_ules, str(ny_lap), hivott))
            else:
                # kimagasodott: az induláskor volt nála nagyobb védőlap a színben
                kezdo_fent = [l for u in kezek if vonal(u) != mi for l in kezek[u]
                              if l.szin == hivott and l.rang > ny_lap.rang]
                if kezdo_fent:
                    fajta = "KIMAGASODOTT_HOSSZ" if not kint_elotte(hivott) else "KIMAGASODOTT_FIGURA"
                    b.esemenyek.append(Esemeny(ut, fajta, ny_ules, str(ny_lap), hivott))
            # eső figura: a védő színt adva az utolsó lapjaként figurát tett a nyerőnk alá
            for u, l in ul:
                if vonal(u) != mi and l.szin == hivott == ny_lap.szin and FIGURA <= l.rang < ny_lap.rang \
                        and not any(x.szin == hivott and x != l for x in elotte[u]):
                    b.esemenyek.append(Esemeny(ut, "ESO_FIGURA", u, str(l), hivott))
        # kihagyás: a védők hívtak, nálunk volt a szín legnagyobb lapja, mégsem ütöttünk
        if not mi_nyert and vonal(ul[0][0]) != mi and (not adu or hivott != adu):
            legnagyobb = max((l for u in elotte for l in elotte[u] if l.szin == hivott),
                             key=lambda l: l.rang, default=None)
            if legnagyobb is not None and any(legnagyobb in elotte[u] for u in elotte if vonal(u) == mi):
                b.esemenyek.append(Esemeny(ut, "KIHAGYAS", ny_ules, str(legnagyobb), hivott))
        # dobások
        for u, l in ul:
            if l.szin == hivott or (adu and l.szin == adu):
                continue
            if vonal(u) == mi:
                # dobás nyerőre: a dobott lap színében nincs nálunk nyerő (vesztő volt), a 10.
                # ütés előtt; vesztő a vesztőre: színfelvételnél adunk van, mégsem lopunk
                vedo_kint = kint_elotte(l.szin)
                van_nyero = vedo_kint and any(
                    x.rang > max(v.rang for v in vedo_kint) for x in
                    [x for v in elotte if vonal(v) == mi for x in elotte[v] if x.szin == l.szin])
                if not vedo_kint or van_nyero:
                    continue
                if mi_nyert and ut <= 10:
                    b.esemenyek.append(Esemeny(ut, "DOBAS_NYERORE", u, str(l), l.szin))
                elif not mi_nyert and adu and any(x.szin == adu for x in elotte[u]):
                    b.esemenyek.append(Esemeny(ut, "VESZTO_A_VESZTORE", u, str(l), l.szin))
            else:
                # beszorítás: a védőnek nincs üres lapja — bármit dob, egy színben ütést ad
                if adu is None or not any(x.szin == adu for x in elotte[u]):
                    if u not in szoritott_ut.get(ut, ()):
                        koltseg = {}
                        for sz in {x.szin for x in elotte[u]} - {hivott}:
                            alap_k = {v: frozenset(x.rang for x in elotte[v] if x.szin == sz) for v in elotte}
                            elo = szin_utesek(alap_k, mi)
                            legkisebb = min(x.rang for x in elotte[u] if x.szin == sz)
                            dob_k = dict(alap_k)
                            dob_k[u] = alap_k[u] - {legkisebb}
                            koltseg[sz] = szin_utesek(dob_k, mi) - elo
                        if len(koltseg) >= 2 and min(koltseg.values()) >= 1:
                            b.esemenyek.append(Esemeny(ut, "BESZORITOTT_VEDO", u, str(l), l.szin))
                        szoritott_ut.setdefault(ut, set()).add(u)
                # védő dob: őrzőlap? a mi legjobb lapunk a színben, amelyet ez a lap megfogott
                mieink = [x for x in mi_lapok(l.szin)]
                if not mieink:
                    continue
                mi_max = max(x.rang for x in mieink)
                tars = [v for v in elotte if vonal(v) != mi and v != u][0]
                tars_fent = [x for x in elotte[tars] if x.szin == l.szin and x.rang > mi_max]
                sajat = [x for x in elotte[u] if x.szin == l.szin]
                mi_hossz = max(sum(1 for x in maradek[v] if x.szin == l.szin) for v in maradek if vonal(v) == mi)
                tars_hossz = sum(1 for x in elotte[tars] if x.szin == l.szin)
                rang_orzo = l.rang > mi_max and not tars_fent
                hossz_orzo = mi_hossz > 0 and len(sajat) == mi_hossz and tars_hossz < mi_hossz
                if rang_orzo or hossz_orzo:
                    orzo.append((l.szin, u, ut, mi_max))
        # a lapok kikerülnek
        for u, l in ul:
            maradek[u].discard(l)
        if mi_nyert:
            b.felvevo_utes += 1
            # az őrzőlap-dobás beszorítás volt, ha ebben a színben később (most) ütöttünk
            # olyan lappal, amely a dobáskor nem volt felső
            if ny_lap.szin == hivott:
                for o in list(orzo):
                    if o[0] == hivott and o[2] < ut and ny_lap.rang <= o[3]:
                        b.esemenyek.append(Esemeny(o[2], "ORZOLAP_DOBAS", o[1], str(ny_lap), hivott))
                        orzo.remove(o)
        hivo = ny_ules
    return b


# --- a technikák és a tervtípusok megfeleltetése ------------------------------------

TIPUS_ESEMENY = {
    "KIMAGASITAS": ("IMPASSZ", "EXPASSZ", "KIMAGASODOTT_HOSSZ", "KIMAGASODOTT_FIGURA", "ESO_FIGURA"),
    "LOPAS": ("LOPAS_ROVID_KEZBEN",),
    "VESZTOCSERE": ("DOBAS_NYERORE", "VESZTO_A_VESZTORE"),
    "VEGJATEK": ("VEDO_HIVTA_IMPASSZ", "LOPAS_DOBAS"),
    "BESZORITAS": ("BESZORITOTT_VEDO",),
    "VESZELYES_VEDO": ("KIHAGYAS",),
}


def tipusok(b: Besorolas) -> set[str]:
    f = b.fajtak()
    return {t for t, es in TIPUS_ESEMENY.items() if any(f[e] for e in es)}
