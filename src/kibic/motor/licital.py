"""
Licitmotor: mit licitáljunk egy adott állásban?

Bemenet: a licitmenet eddigi része, a saját kéz, és a rendszer feloldott
szabálylistája. Kimenet: a döntés, a JELÖLTHALMAZ és az indoklás.

A JELÖLTHALMAZ a fontos újdonság. A motor nem csak egy licitet ad
vissza, hanem minden illeszkedő szabályt — mert ahol több jelölt van,
ott a rendszer önmagában NEM DÖNT. Ez automatikusan kirajzolja a
bizonytalan helyzeteket, amelyeknél a további megfontolások (beliállás,
a verseny állása, a partner és az ellenfél stílusa) számítanának.

DÖNTÉSI MÓDOK
-------------
SORREND        A legmagasabb prioritású illeszkedő nyer. Ez reprodukálja
               a LICREN viselkedését (ott a fájlbeli sorrend növekvő
               fontosság), és ez a viszonyítási alap.
SPECIFIKUSSAG  A legspecifikusabb minta nyer, sorrendtől függetlenül.
MERLEGELO      A jelölthalmazt változtatás nélkül visszaadja, döntés
               nélkül — a hívó (a C mód) dönt további megfontolásokkal.

HÁROMÉRTÉKŰ LOGIKA
------------------
Egy szabály lehet IGAZ, HAMIS vagy ELDÖNTHETETLEN (ha feloldatlan
metrikára hivatkozik). Az eldönthetetlenek külön gyűlnek: nem
tekintjük őket sem illeszkedőnek, sem kizártnak, de MEGSZÁMOLJUK.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..domain import Kez
from .feloldas import Sor
from .kifejezes import Kontextus, kiertekel
from .minta import (negyedik_kotes, alias_elozmenyek, aliasok_sorokbol, JELENTESEK, VALTOZOK, Minta, MintaHiba, Token, _szin_feloldas,
                    illeszkedik, kanonizal, minta_parse)

MODOK = ("SORREND", "SPECIFIKUSSAG", "MERLEGELO")


@dataclass
class Jelolt:
    """Egy illeszkedő szabály."""
    licit: str
    sor: Sor
    kotesek: dict[str, str]
    minta_specifikussag: int

    @property
    def indoklas(self) -> str:
        # Az EMBERI magyarázat az első; a gépies feltétel-szöveg csak ha
        # nincs más ("figurapont >= 10 és kőr hossz >= 5 ...").
        return self.sor.magyarazat or self.sor.feltetel_szoveg or ""


_SZIN_RANG = {"C": 0, "D": 1, "H": 2, "S": 3, "NT": 4, "N": 4}
_HIVAS_RANG = {"P": -3, "X": -2, "XX": -1}


# a kvázi gémforsz küszöbe: saját figurapont + a partner ígért minimuma
KVAZI_GF = 25


def licit_rang(licit: str | None) -> tuple:
    """Licitek sorrendje a Bánky-szabályhoz: P < X < XX < 1♣ < ... < 7NT."""
    if not licit:
        return (99,)
    if licit in _HIVAS_RANG:
        return (_HIVAS_RANG[licit],)
    try:
        return (int(licit[0]) * 5 + _SZIN_RANG[licit[1:]],)
    except (ValueError, KeyError):
        return (98,)


# Az általános elvek (nem konvenciók): ezekre "nincs rá megállapodás".
ALTALANOS_ELVEK = {"EGYRE_EGY", "NEGYEDIK_SZIN", "PASSZ_ELV", "EMELES_ELV",
                   "GYENGE_UGRAS_ELV", "VALASZOLO_ELV"}


@dataclass
class Dontes:
    licit: str | None = None
    mod: str = "SORREND"
    jeloltek: list[Jelolt] = field(default_factory=list)
    eldonthetetlen: int = 0
    megvizsgalt: int = 0
    indoklas: str = ""
    bizonytalan: bool = False       # egynél több jelölt volt
    elvre_esett: bool = False
    kvazi_gf: bool = False          # a kvázi gémforsz elv szűrt (a szerkesztő, 2026-10-31)
    """Igaz, ha a döntés az ELVEK rétegéből jött, mert konkrét szabály
    nem illeszkedett. Ez a lefedettség őszinte mérőszáma: az elvvel
    "lefedett" helyzet nem ugyanaz, mint amire van megállapodásunk."""
    gyoztes: "Jelolt | None" = None
    nyom: list[dict] | None = None
    """Ha a hívó kéri (teszt / debug): minden szabály, amelyik ebben a
    helyzetben SZÓBA JÖTT (a minta illett), a kiértékelés eredményével és
    — ha nem teljesült — azzal, hogy miért nem."""
    banky: list[str] | None = None
    """Ha a győztest a Bánky-szabály választotta ki az egyformán jó
    jelöltek közül: ezek voltak azok (a legalacsonyabb nyert)."""
    merlegelendo: list["Jelolt"] = field(default_factory=list)
    """Olyan jelöltek, amelyek szabálya kimondja, hogy NEM ő dönt
    (`dontesi_mod='MERLEGELO'`). Ezek nem nyerhetnek szabály alapon: a
    hívónak kell összemérnie őket (motor/merlegel.py). Ha ezt a listát
    figyelmen kívül hagyjuk, a licit egyszerűen elmarad — inkább ne
    kontrázzunk, mint hogy rosszul tegyük."""

    def osszefoglalo(self) -> str:
        if self.licit is None:
            if self.merlegelendo:
                mik = ", ".join(sorted({j.licit for j in self.merlegelendo}))
                return f"nincs szabály-döntés; mérlegelendő: {mik}"
            return "nincs illeszkedő szabály"
        s = f"{self.licit}"
        if self.indoklas:
            s += f" — {self.indoklas}"
        if self.bizonytalan:
            mas = [j.licit for j in self.jeloltek if j.licit != self.licit]
            s += f"  (jelöltek voltak még: {', '.join(sorted(set(mas)))})"
        if self.merlegelendo:
            mik = ", ".join(sorted({j.licit for j in self.merlegelendo}))
            s += f"  [mérlegelendő: {mik}]"
        if self.elvre_esett:
            kod = self.helyzeti_megallapodas
            s += (f"  [helyzeti megállapodás: {kod}]" if kod
                  else "  [ELV — nincs rá konkrét megállapodás]")
        return s

    @property
    def helyzeti_megallapodas(self) -> str | None:
        """
        Ha az ELV-réteg döntött, de a győztes sor egy KONVENCIÓ helyzeti
        alakja (RKC, MOHA_3NT_4M, MOHA_SZLEM, GYORS_LASSU …), akkor az
        megállapodás, nem "általános elv": a rendszer kódja. Az általános
        elvekre (passz-, emelés-, gyenge ugrás-elv, 1-re 1, negyedik szín)
        None.
        """
        if not self.elvre_esett or self.gyoztes is None:
            return None
        kod = getattr(self.gyoztes.sor, "rendszer_kod", None) or ""
        if not kod or kod.endswith("_ELV") or kod in ALTALANOS_ELVEK:
            return None
        return kod


def _hivatkozik(fa, valtozo: str) -> bool:
    """Hivatkozik-e a feltételfa a `@valtozo` színre?"""
    import json
    if not fa:
        return False
    szoveg = json.dumps(fa, ensure_ascii=False)
    return f'"@{valtozo}"' in szoveg or f'"@{valtozo}:' in szoveg


class Licitmotor:
    """
    Egy rendszer feloldott szabálylistájából licitál.

    A minták elemzése egyszer történik meg, a példány létrehozásakor —
    így a mérés több ezer állásra is gyors.
    """

    def __init__(self, sorok: list[Sor], ktx: Kontextus | None = None,
                 mod: str = "SORREND"):
        if mod not in MODOK:
            raise ValueError(f"Ismeretlen döntési mód: {mod!r}")
        self.mod = mod
        self.ktx = ktx or Kontextus()
        # KÉT RÉTEG. Az elv nem versenyez a szabályokkal: MÖGÖTTÜK áll.
        # Prioritással ezt nem lehet jól megoldani, mert az csak azonos
        # `kulcs`-on belül rendez — két külön kulcsú sor (egy konvenció
        # és egy elv) így mindkettő jelölt maradna. Az elv viszont
        # FALLBACK: csak akkor szólal meg, ha semmi konkrétabb nem
        # illeszkedett.
        self.szabalyok: list[tuple[Minta, Sor]] = []     # SZABALY, KIVETEL
        self.elvek: list[tuple[Minta, Sor]] = []         # ELV
        self.hibas_mintak: list[str] = []
        for s in sorok:
            if not s.minta:
                continue
            elv = getattr(s, "szabaly_fajta", "SZABALY") == "ELV"
            # Az elvnek tipikusan NINCS kéz-feltétele (nem licitet
            # javasol, hanem jelentést ad); a szabálynak kell.
            if not elv and s.feltetel is None:
                continue
            try:
                parolt = (minta_parse(s.minta), s)
            except MintaHiba as e:
                self.hibas_mintak.append(f"{s.minta}: {e}")
                continue
            (self.elvek if elv else self.szabalyok).append(parolt)
        self.aliasok = aliasok_sorokbol(sorok)

    # -- döntés --

    def licital(self, licitek: list[dict], ules: str, kez: Kez,
                beliallas: str = "NONE",
                engedelyezett: list[str] | None = None,
                allas=None, oszto: str | None = None,
                nyomkovetes: bool = False) -> Dontes:
        """
        Mit licitáljunk?

        `licitek`: az eddigi licitmenet [{ules, licit}, ...]
        `ules`:    a mi ülésünk
        `kez`:     a mi lapunk
        `engedelyezett`: ha meg van adva, csak ezekből választunk
                         (a játékprotokoll `legal_actions` listája)
        `allas`:   kész `motor.helyzet.Allas` FELTÖLTÖTT kényszertárral
                   (motor.propagal.allas_kenyszertarral). Enélkül a
                   helyzeti feltételek és a fésű-kötések nem
                   értékelhetők ki — a motor ilyenkor csak azokat a
                   szabályokat látja, amelyek a puszta licitmenetből
                   eldönthetők.
        """
        from .helyzet import Allas
        from .helyzet import kiertekel as helyzet_kiertekel

        if allas is None:
            allas = Allas(ules=ules, beliallas=beliallas,
                          licitek=list(licitek), oszto=oszto)
        elo_kotes = allas.fesu_kotesek()
        # A licitmenet kanonizálása a MI szemszögünkből, a soron
        # következő licittel kiegészítve — a minta a definiált licittel
        # végződik, ezért minden jelölt licitre külön illesztünk.
        ktx = Kontextus(ules=ules, beliallas=beliallas,
                        parametertar=self.ktx.parametertar,
                        keszletek=self.ktx.keszletek,
                        metrika=self.ktx.metrika,
                        allas=allas)

        d = Dontes(mod=self.mod)
        if nyomkovetes:
            d.nyom = []

        def jegyez(sor, licit, eredmeny, miert=None, reteg="SZABALY"):
            if d.nyom is None:
                return
            d.nyom.append({
                "call": licit, "rule": sor.minta,
                "system": sor.rendszer_kod, "priority": sor.prioritas,
                "layer": reteg, "result": eredmeny,
                "why_not": miert or [],
                "explanation": sor.magyarazat or sor.feltetel_szoveg or "",
                "rule_id": sor.licitmenet_id,
                "source": getattr(sor, "forras", None),
            })

        # Az eddigi licitmenet kanonizálva, a MI szemszögünkből.
        try:
            _, elozmeny = kanonizal(licitek, ules) if licitek else ("", [])
        except Exception:          # noqa: BLE001
            return d

        defi: list = [None]     # a konkrét réteg „definiált-e” kérdése (lustán)

        def _menet(reteg, elozmeny=elozmeny):
          for minta, sor in reteg:
            d.megvizsgalt += 1
            # A minta UTOLSÓ tokenje a definiált licit; az ELŐTTE lévők
            # az előzményre illeszkednek. A változók (M, m, A...) ott
            # kötődnek — és a kötésekből SZÁMÍTJUK ki, mit licitálunk.
            tal = self._elozmeny_illesztes(minta, elozmeny, elo_kotes)
            if tal is None:
                continue
            # Ha a definiált licit színe SZABAD változó ("1M-2M-+A": a
            # legolcsóbb licit abban a színben, amelyikre a feltétel
            # igaz), a motor minden lehetséges színt kipróbál — a
            # kibontás csak itt, a memóriában történik.
            # Csak akkor, ha a feltétel RÓLA szól (hivatkozik a változóra):
            # különben minden szín egyformán "igaz" volna, és a licit
            # önkényes — ilyenkor marad a régi viselkedés (nincs licit).
            utolso = minta.tokenek[-1]
            if (not utolso.hivas and utolso.szin in VALTOZOK
                    and utolso.szin not in tal[0]
                    and _hivatkozik(sor.feltetel, utolso.szin)):
                valtozatok = [dict(tal[0], **{utolso.szin: sz})
                              for sz in VALTOZOK[utolso.szin]]
            else:
                valtozatok = [tal[0]]
            # LÉTEZIK-KÖTÉS (2026-10-19): a feltételben szereplő, de a
            # mintában NEM kötött színváltozó (pl. a „.. 3NT” sor
            # „partner_szin: {M: 6}”-ja) jelentése: van olyan szín, amelyre
            # a feltétel igaz. Így egy elv egyetlen sorral írható le (4M,
            # nem külön 4♥ és 4♠). Az első igaz kötés dönt.
            szabad = [v for v in VALTOZOK
                      if v not in tal[0] and v != utolso.szin
                      and (_hivatkozik(sor.feltetel, v) or _hivatkozik(sor.ha_feltetel, v))]
            for v in szabad:
                valtozatok = [dict(k_, **{v: sz}) for k_ in valtozatok for sz in VALTOZOK[v]]
            for kotes in valtozatok:
                elotte = len(d.jeloltek) + len(d.merlegelendo)
                _jelolt(minta, sor, kotes, tal[1])
                if szabad and len(d.jeloltek) + len(d.merlegelendo) > elotte:
                    break

        def _jelolt(minta, sor, kotes, spec):
            # csak a MEGÉRTÉST szolgáló sor (pl. a természetes alapjelentés):
            # a kibic maga nem ennek alapján licitál
            if (getattr(sor, "jelentes", None) or {}).get("csak_megertes"):
                return
            kotes = negyedik_kotes(elozmeny, kotes)
            licit = self._licit_feloldas(minta.tokenek[-1], kotes, elozmeny,
                                         allas)
            if licit is None:
                return
            reteg_nev = "ELV" if getattr(sor, "szabaly_fajta", "") == "ELV" \
                else "SZABALY"
            if engedelyezett is not None and licit not in engedelyezett:
                jegyez(sor, licit, "NEM_LEGALIS", reteg=reteg_nev)
                return
            # HELYZETI feltétel: ami ebben az állásban nem licitálható,
            # az meg sem vizsgálandó. Az ISMERETLEN itt megengedő —
            # inkább jelölt legyen és a mérlegelés dobja ki, mint hogy
            # csendben elvesszen.
            ha_kotes = dict(kotes, _licit=licit)   # a „negyedik szín”, „splinter” helyzethez
            if reteg_nev == "ELV":
                # a gyenge ugrás elve: definiált-e a hívás a konkrét rétegben
                if defi[0] is None:
                    from .propagal import definialo
                    defi[0] = definialo(self.szabalyok, elozmeny, elo_kotes,
                                        allas, self.ktx.parametertar)
                ha_kotes["_definialt"] = defi[0]
            if sor.ha_feltetel is not None and \
                    helyzet_kiertekel(sor.ha_feltetel, allas, ha_kotes,
                                      self.ktx.parametertar) is False:
                jegyez(sor, licit, "HELYZET_NEM",
                       [getattr(sor, "ha_feltetel_szoveg", None)
                        or "a helyzeti feltétel nem teljesül"], reteg_nev)
                return
            if getattr(sor, "elnyomo", None) and any(
                    helyzet_kiertekel(e, allas, ha_kotes, self.ktx.parametertar) is True
                    for e in sor.elnyomo):
                jegyez(sor, licit, "HELYZET_NEM",
                       ["ebben a helyzetben egy előrébb álló konvenció él"], reteg_nev)
                return
            # A kéz-feltétel a MINTA kötéseivel értékelődik: az `1M-2M`
            # szabály így tud arról a színről beszélni, amit a partner
            # ténylegesen mondott. A `_licit` a definiált licit (a
            # "gém alatt" típusú feltételhez).
            ktx.kotesek = dict(kotes, _licit=licit)
            e = True if sor.feltetel is None else kiertekel(sor.feltetel,
                                                            kez, ktx)
            if d.nyom is not None:
                if e is True:
                    jegyez(sor, licit, "IGAZ", reteg=reteg_nev)
                else:
                    from .kifejezes import miert_nem
                    jegyez(sor, licit, "HAMIS" if e is False else "ISMERETLEN",
                           miert_nem(sor.feltetel, kez, ktx), reteg_nev)
            if e is None:
                d.eldonthetetlen += 1
            elif e is True:
                j = Jelolt(licit, sor, kotes, sor.specifikussag or spec)
                if getattr(sor, "dontesi_mod", "SORREND") == "MERLEGELO":
                    d.merlegelendo.append(j)
                else:
                    d.jeloltek.append(j)

        _menet(self.szabalyok)
        # FOLYTATÁS "mint X után": ha a konkrét réteg néma, a menet
        # átirányított változatán (2♣-2♦-2NT -> 2NT) is keresünk, a
        # ponthatárok eltolásával.
        if not d.jeloltek and not d.merlegelendo and self.aliasok:
            for uj_elozmeny, eltolas in alias_elozmenyek(self.aliasok, elozmeny):
                ktx.pont_eltolas = eltolas
                _menet(self.szabalyok, uj_elozmeny)
            ktx.pont_eltolas = 0.0
        # FALLBACK: az elvek csak akkor jönnek, ha a konkrét réteg néma
        # maradt. "Az elvhez hozzá kell tenni, hogy a konkrét helyzetre
        # nincs érvényes konvenció."
        konkret_ures = not d.jeloltek and not d.merlegelendo
        if konkret_ures and self.elvek:
            _menet(self.elvek)
        # ZAVARTALAN MENET (a szerkesztő, 2026-10-24): ha a versenyhelyzetre
        # nincs saját szabály vagy elv (legfeljebb a „nincs megállapodás:
        # passz”), és az ellenfél akciói nem zavartak meg minket (közbeszólás
        # nélkül is ugyanezt mondhattuk volna), a páros menet szabályai,
        # majd elvei érvényesek. A szan ilyenkor fogást is ígér az ellenfél
        # licitált színében.
        if licitek and all(getattr(j_.sor, "rendszer_kod", "") == "PASSZ_ELV"
                           for j_ in d.jeloltek + d.merlegelendo):
            from .minta import zavartalan_menet
            zm = zavartalan_menet(licitek, ules)
            if zm is not None:
                from .propagal import definialo
                def_verseny = definialo(self.szabalyok, elozmeny, elo_kotes,
                                        allas, self.ktx.parametertar)

                def _zavartalan_jo(j_):
                    if getattr(j_.sor, "rendszer_kod", "") == "PASSZ_ELV":
                        return False
                    if zavartalan_menet(licitek, ules, j_.licit) is None:
                        return False
                    # ha a hívásnak a versenyhelyzetben saját szabálya van
                    # (pl. 1♦ (1♥) 1♠ = 5+), az a jelentése, nem a páros menet
                    if def_verseny(j_.licit):
                        return False
                    if j_.licit.upper().endswith("NT") and zm[1]:
                        from .helyzet import fogas_kezben
                        return all(fogas_kezben(kez, sz) for sz in zm[1])
                    return True
                regi_j, regi_m = d.jeloltek, d.merlegelendo
                for reteg_ in (self.szabalyok, self.elvek):
                    d.jeloltek, d.merlegelendo = [], []
                    _menet(reteg_, zm[0])
                    d.jeloltek = [x for x in d.jeloltek if _zavartalan_jo(x)]
                    d.merlegelendo = [x for x in d.merlegelendo if _zavartalan_jo(x)]
                    if d.jeloltek or d.merlegelendo:
                        break
                if not d.jeloltek and not d.merlegelendo:
                    d.jeloltek, d.merlegelendo = regi_j, regi_m
        if konkret_ures and self.elvek:
            d.elvre_esett = bool(d.jeloltek or d.merlegelendo)

        # KVÁZI GÉMFORSZ (a szerkesztő, 2026-10-31): ha a pontjaim és a partner
        # ígért minimuma együtt legalább KVAZI_GF, passzolható licitet nem
        # adunk (gém alatti, nem kényszerítő licit, passz) — ha van más jelölt:
        # gém, riverz / álriverz, felüllicit, kényszerítő ugrás.
        if len(d.jeloltek) > 1 and allas.kenyszertar:
            p_ig = allas.kenyszertar.get(allas.partner)
            from .hezag import _gem_alatt, _hcp
            if p_ig is not None and p_ig.nyilatkozott and \
                    _hcp(kez) + int(p_ig.pont_min) >= KVAZI_GF:

                def _passzolhato(j_):
                    if j_.licit == "P":
                        return True
                    if j_.licit in ("X", "XX"):   # a büntető kontra erős akció
                        return False
                    forsz = getattr(j_.sor, "forsz", None) or "NEM"
                    return forsz == "NEM" and _gem_alatt(j_.licit)
                nem_p = [j_ for j_ in d.jeloltek if not _passzolhato(j_)]
                if nem_p and len(nem_p) < len(d.jeloltek):
                    d.jeloltek = nem_p
                    d.kvazi_gf = True

        d.bizonytalan = len({j.licit for j in d.jeloltek}) > 1
        if not d.jeloltek:
            return d
        if self.mod == "MERLEGELO":
            return d               # a hívó dönt

        if self.mod == "SORREND":
            rang = lambda j: (j.sor.prioritas, j.minta_specifikussag)  # noqa: E731
        else:
            rang = lambda j: (j.minta_specifikussag, j.sor.prioritas)  # noqa: E731
        legjobb = max(rang(j) for j in d.jeloltek)
        elso = [j for j in d.jeloltek if rang(j) == legjobb]
        # BÁNKY ZOLI SZABÁLYA: ha több, egyformán jónak ítélt licit van,
        # a legalacsonyabbat add le. Eddig ilyenkor a szabályok sorrendje
        # döntött — ami önkényes. (A passz és a kontrák a színlicitek
        # "alatt" állnak: egyenlő jelöltek közt a legkevésbé elkötelező.)
        gyoztes = min(elso, key=lambda j: licit_rang(j.licit))
        if len({j.licit for j in elso}) > 1:
            d.banky = sorted({j.licit for j in elso}, key=licit_rang)
        d.licit = gyoztes.licit
        d.indoklas = gyoztes.indoklas
        d.gyoztes = gyoztes
        return d

    # -- segédek --

    @staticmethod
    def _elozmeny_illesztes(minta: Minta, elozmeny: list[Token],
                            elo_kotes: dict[str, str] | None = None):
        """
        A minta ELŐZMÉNY-részét (az utolsó token nélkül) illeszti a
        licitmenetre. Visszaad: (kötések, specifikusság) vagy None.
        Az `elo_kotes` a kényszertárból hozott I1/I2/V1/V2 kötés.
        """
        if not minta.tokenek:
            return None
        elozo = Minta(minta.nyers, minta.tokenek[:-1], minta.paroslicit,
                      {p for p in minta.barmennyi
                       if p < len(minta.tokenek) - 1})
        if not elozo.tokenek:
            # ".. 4NT": az elv BÁRMILYEN előzmény után illik
            if 0 in minta.barmennyi:
                return (dict(elo_kotes or {}), minta.specifikussag)
            # Nyitás: csak akkor illik, ha még nem licitáltunk
            return ((dict(elo_kotes or {}), minta.specifikussag)
                    if not elozmeny else None)
        tal = illeszkedik(elozo, elozmeny, elo_kotes)
        return (tal.kotesek, minta.specifikussag) if tal else None

    @staticmethod
    def _licit_feloldas(t: Token, kotesek: dict[str, str],
                        elozmeny: list[Token], allas=None) -> str | None:
        """
        A definiált licit konkrét alakja a kötések alapján.
        A `2M` a kötött nemesre, a `2Q` a negyedik színre oldódik fel.
        """
        if t.ellenfel or t.helyettesito:
            return None
        if t.hivas:
            return t.hivas
        if t.szint == "n":
            return None          # nyitott szint: nem tudjuk, mit mondjunk

        if t.szin in JELENTESEK:
            szin = t.szin
        else:
            lehet = _szin_feloldas(t, kotesek, elozmeny)
            if len(lehet) != 1:
                return None      # nem egyértelmű (kötetlen változó)
            szin = next(iter(lehet))

        if t.szint == "+":
            # A LEGKISEBB SZABAD LICIT ebben a színben. Ehhez ismerni
            # kell az állást; enélkül a szabály nem alkalmazható.
            if allas is None:
                return None
            kov = allas.kovetkezo_licit(szin)
            return None if kov is None else f"{kov[0]}{kov[1]}"
        return f"{t.szint}{szin}"
