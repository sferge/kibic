"""
A HÉZAG-ELV (2026-10-03, Moha) — amikor sem szabály, sem elv nem javasol
licitet, a kibic nem passzol vakon, hanem a KÖZÖS ERŐ és a KÉNYSZER alapján
dönt, és a licitek közül a JELENTÉSÜK szerint választ.

Miért nem YAML-sor? A YAML-elv így szól: „EZT a licitet mondd, ha a lap
ilyen”. A hézag ott van, ahol egyetlen sor sem javasol licitet. Ez az elv
fordítva gondolkodik: „a lap és a közös erő szerint válassz a hívások
közül aszerint, mit JELENTENEK a rendszerben” (lezáró, géminvit, egy körre
kényszerítő, gémforsz). A jelentést a propagáló adja — ugyanaz, amivel a
kibic a partnert érti.

A SZABÁLY (Moha, 0–4):
  A = saját pont + a partner ígért MINIMUMA
  F = saját pont + a partner (valószínű) MAXIMUMA (legfeljebb 37 − a saját
      pont − az ellenfelek ígért minimuma)
  gémküszöb: nemes fittel 25, minor fittel 27, szanban 24 egyenlő elosztásnál
  (a kifejezes.gemesely szabálya).

  0. Kényszer (a partner forszolt, és az ellenfél nem oldotta fel; vagy
     gémforszban vagyunk): passz NEM lehet.
  1. A >= gém: gémforsz licit, ha van; különben gém. Passz soha.
  2. F >= gém > A: gém alatti géminvit, ha van; ha nincs, a gém esélye dönt
     (a partner sávjának alja valószínűbb; küszöb mansban 45%, bellben 37%):
     gém; közepes eséllyel (25%+) gém alatti egy körre kényszerítő leíró
     licit; különben a 3. pont.
  3. F < gém: kényszer nélkül, ha a mostani felvétel a miénk és játszható,
     és nincs sokkal jobb (a fit legalább 2 lappal hosszabb máshol): passz;
     ha nem játszható / van sokkal jobb: a legolcsóbb javítás oda. Kényszerben:
     a legolcsóbb leíró licit (vagy a fit színe, vagy a saját hosszú szín).
  5. Ha a partner büntetőre kontrázta a felvételüket: büntető passz, ha a
     szimuláció (DD-mintavétel) szerint a bukás jobb; szimuláció nélkül a
     védőütések becsléséből (az enyéim + a partneré ~2) a bukás értéke a
     saját (gém- vagy rész-) felvételünk várható értékével szemben.
  4. Ha a partner utolsó licitjét NEM értjük (nincs rá szabály), a partner a
     „kapitány”: ő tudja, mit kérdez. Ilyenkor a saját ígért sávom szerint
     válaszolok — a sáv felső felével gém a fitben, az alsóval a legolcsóbb
     lezárás a legjobb fitben (pass, ha már ott vagyunk).

A „játszható” itt a fit számolása (a saját lapjaim + a partner ígért minimuma,
és ha arról nincs tudás, a maradék lapok átlagos része): 8+ lap igen; 7 lap
5-2-ben igen, 4-3-ban csak rövidséggel a 3 lapos adu mellett (Moha: a rövid
aduból lopás plusz ütés). A 3NT-hez fogás kell az ellenfél színeiben.
DD-mintavétel később, ha a határidő engedi.
"""
from __future__ import annotations

from dataclasses import dataclass

SZINEK = ("S", "H", "D", "C")
NEMES = ("S", "H")
GEMSZINT = {"S": 4, "H": 4, "D": 5, "C": 5, "NT": 3}
# szan-szlem küszöbök (a szerkesztő: szanban 33+, nagyszlem 37+) — a terv
# 1. fázisában paraméter lesz
SZAN_SZLEM = 33
SZAN_NAGYSZLEM = 37
SZIN_SZLEM = 30         # szín-szlem (a szerkesztő: 30+)
SZIN_NAGYSZLEM = 35     # szín-nagyszlem (35+)
SAV_LIMIT = 6          # a partner sávja ennél szűkebb: "limitált" (invitálható)
# gémforszban a partner nyitott felső határa két licit után legfeljebb
# minimum + ennyi (fékezés: a többleterőt meg kellett volna mutatnia)
GF_FEKEZES = 4
_RANG = {"C": 0, "D": 1, "H": 2, "S": 3, "NT": 4}
_HCP = {"A": 4, "K": 3, "Q": 2, "J": 1}


@dataclass
class HezagDontes:
    licit: str
    pont: str            # melyik pontja (0-4) döntött
    indok: str


def _hcp(kez) -> int:
    return sum(_HCP.get(l.ertek, 0) for l in kez.lapok)


def _bont(h: str):
    if not h or not h[0].isdigit():
        return None
    sz = h[1:]
    return int(h[0]), ("NT" if sz in ("N", "NT") else sz)


def _rang(h: str) -> tuple:
    b = _bont(h)
    return (b[0], _RANG[b[1]]) if b else (0, -1)


def _gem_alatt(h: str) -> bool:
    b = _bont(h)
    return bool(b) and b[0] < GEMSZINT[b[1]]


def _gemkuszob_eleri(sajat: int, p: int, kez, ig, fit_nemes: bool, fit_minor: bool,
                     szan_lehet: bool = True) -> bool:
    ossz = sajat + p
    if fit_nemes and ossz >= 25:
        return True
    if fit_minor and ossz >= 27:
        return True
    # a 24 pontos (szan-)gém csak akkor, ha a 3NT még mondható (2026-10-21:
    # 1♠-2♦-2♠-3♥-4♦ után nincs 3NT — a 4m-nél a kvázi gémforsz is véget ért)
    if ossz >= 24 and szan_lehet:
        hosszu = max(max(kez.hossz(sz) for sz in SZINEK),
                     max(ig.hossz(sz)[0] for sz in SZINEK))
        elteres = abs(sajat - p)
        return elteres <= 4 or (elteres <= 13 and hosszu >= 5) or hosszu >= 6
    return False


class Hezag:
    """Egy döntési helyzet (a kérés idején ismert minden tudással)."""

    def __init__(self, kez, allas, prop, licitek, ules, oszto, legalis,
                 megertes=None, valoszinu=None, buntetes=None, vegkontraktus=None,
                 pontozas=None):
        _p = str(pontozas or "IMP").strip().upper()      # MP / BAM / IMP
        self.pontozas = "MP" if _p in ("MP", "MPS", "PAIRS", "MATCHPOINTS") else _p
        self.buntetes = buntetes                # szimuláció: büntető passz vagy a miénk
        self.vegkontraktus = vegkontraktus      # szimuláció: melyik végkontraktus (DD)
        self.kez, self.allas, self.prop = kez, allas, prop
        self.licitek, self.ules, self.oszto = licitek, ules, oszto
        self.legalis = [h for h in (legalis or [])]
        self.megertes = megertes or []
        self.valoszinu = valoszinu or {}
        self.partner = allas.partner
        self.tar = allas.kenyszertar
        self.p = self.tar[self.partner]

    # -- tudás --

    def sajat(self) -> int:
        return _hcp(self.kez)

    def partner_sav(self) -> tuple[int, int]:
        lo = int(self.p.pont_min)
        hi = self.p.pont_max
        v = self.valoszinu.get(self.partner)
        if v is not None:
            hi = min(hi, v.pont_max)
        ellen_min = sum(self.tar[u].pont_min for u in (self.allas.bal, self.allas.jobb))
        hi = min(hi, 37 - self.sajat() - ellen_min)
        # FÉKEZÉS (a szerkesztő, 2026-10-05): gémforszban a partner nyitott
        # felső határa (pl. a 2/1 „12+”) nem 37 — ha már legalább kétszer
        # licitált, és egyik licitje sem mutatott többleterőt (a minimuma nem
        # nőtt), a lapja a minimum közelében van: legfeljebb minimum + GF_FEKEZES.
        if hi - lo > GF_FEKEZES + 6 and self._partner_licitjei() >= 2:
            from .helyzet import kiertekel
            if kiertekel({"t": "GEMFORSZ"}, self.allas, {}) is True:
                hi = min(hi, lo + GF_FEKEZES)
        return lo, int(max(lo, hi))

    def _partner_licitjei(self) -> int:
        return sum(1 for e in self.licitek if e.get("ules") == self.partner
                   and str(e.get("licit", "")).upper() not in ("P", "PASS"))

    def partner_hossz(self, sz: str) -> float:
        """A partner valószínű hossza: az ígért minimum, vagy a maradék lapok átlagos része."""
        mn = self.p.hossz(sz)[0]
        v = self.valoszinu.get(self.partner)
        if v is not None:
            mn = max(mn, v.hossz(sz)[0])
        ismert = sum(self.tar[u].hossz(sz)[0] for u in (self.allas.bal, self.allas.jobb))
        maradek = max(0, 13 - self.kez.hossz(sz) - ismert)
        return max(float(mn), min(maradek / 3.0, float(self.p.hossz(sz)[1])))

    def fit(self, sz: str) -> float:
        return self.kez.hossz(sz) + self.partner_hossz(sz)

    def biztos_fit(self, sz: str) -> int:
        return self.kez.hossz(sz) + self.p.hossz(sz)[0]

    def legjobb_fit(self) -> str | None:
        jelolt = [(self.fit(sz), sz in NEMES, _RANG[sz], sz) for sz in SZINEK]
        legjobb = max(jelolt)
        return legjobb[3] if legjobb[0] >= 7 else None

    def kenyszer(self) -> bool:
        """
        Passz nem lehet, ha a partner utolsó licitje EGY KÖRRE kényszerít (és az
        ellenfél nem oldotta fel), vagy GÉMFORSZBAN vagyunk és még gém alatt.
        A gémforsz a gémig kötelez: gémszinten már teljesült.
        """
        from .helyzet import kiertekel
        if self.partner_kontrazta():
            return False                       # a partner kontráját (büntetés) passzolhatjuk
        _, utolso = self.utolso_licit()
        gem_alatt = not utolso or _bont(utolso)[0] < GEMSZINT[_bont(utolso)[1]]
        # a partner NEM ÉRTETT licitjének forsz-állapotát nem ismerjük: az előző
        # licitjéé nem öröklődhet rá
        if self.partner_utolso_ertve() and \
                kiertekel({"t": "PARTNER_FORSZOL"}, self.allas, {}) is True:
            if self.p.forsz == "EGY_MENET" or gem_alatt:
                return True
        # kvázi gémforsz (Moha 1M-2m): 4 minorig kötelez — onnan passzolható
        if hasattr(self.allas, "gf_teljesult") and self.allas.gf_teljesult():
            return False
        return bool(gem_alatt and kiertekel({"t": "GEMFORSZ"}, self.allas, {}))

    def partner_utolso_ertve(self) -> bool:
        for i in range(len(self.licitek) - 1, -1, -1):
            e = self.licitek[i]
            if e.get("ules") == self.partner and str(e.get("licit")).upper() not in ("P", "PASS"):
                if i < len(self.megertes):
                    return bool(self.megertes[i].get("understood", True))
                return True
        return True

    def utolso_licit(self):
        """(ülés, hívás) az utolsó színes/szan licit."""
        for e in reversed(self.licitek):
            h = str(e.get("licit", "")).upper()
            if _bont(h):
                return e.get("ules"), h
        return None, None

    # -- hívások --

    def legolcsobb(self, szin: str) -> str | None:
        kov = self.allas.kovetkezo_licit("NT" if szin in ("N", "NT") else szin)
        if kov is None:
            return None
        h = f"{kov[0]}{kov[1]}"
        return h if h in self.legalis else None

    def fogas(self, sz: str) -> bool:
        """Van-e fogásom a színben (A, Kx, Qxx, Jxxx)."""
        lapok = {l.ertek for l in self.kez.lapok if l.szin == sz}
        n = len(lapok)
        return "A" in lapok or ("K" in lapok and n >= 2) or ("Q" in lapok and n >= 3) \
            or ("J" in lapok and n >= 4)

    def ellenfel_szinei(self) -> list[str]:
        """Az ellenfél színei: amit 4+ lappal ígértek, és a KONTRÁVAL ígért
        nemes is (a szerkesztő, 2026-10-22: „1♥-ünk kontrája pikket ígér”)."""
        ki = []
        for sz in SZINEK:
            for u in (self.allas.bal, self.allas.jobb):
                mn = self.tar[u].hossz(sz)[0]
                # a kontra változatainak uniója az alakot elveszítheti (az erős,
                # „bármi” ág): a kontrázott nemest a licitből vesszük
                if mn >= 4 or (sz in NEMES and self._kontrazott(u)
                               and sz not in self.allas.termeszetes_szinek("mi")):
                    ki.append(sz)
                    break
        return ki

    def _kontrazott(self, ules: str) -> bool:
        return any(e.get("ules") == ules and str(e.get("licit", "")).upper() == "X"
                   for e in self.licitek)

    def _partner_fogaskeres(self, licit: str) -> bool:
        """A partner licitjének EGYETLEN jelentése a fogáskérés (a FOGASKERES
        elv sora) — más konvenció (pl. a felüllicites emelés, Lebensohl) nem."""
        i = max((k for k, e in enumerate(self.licitek) if e.get("ules") == self.partner
                 and str(e.get("licit", "")).upper() == licit), default=None)
        if i is None:
            return False
        try:
            lista = self.prop.jelentes_sorokkal(self.licitek[:i], self.partner, licit,
                                                self.tar, self.oszto)
        except Exception:                  # noqa: BLE001
            return False
        # van fogáskérés-értelmezése, és nincs konkrét (SZABALY) megállapodás
        # a licitre — az általános elvek (pl. az erős ugrás) nem írják felül
        fk = [s for s, _ in lista if str(getattr(s, "kulcs", "")).startswith("FOGASKERES")]
        konkret = [s for s, _ in lista if getattr(s, "szabaly_fajta", "SZABALY") != "ELV"]
        return bool(fk) and not konkret

    def _mondtuk_korabban(self, sz: str) -> bool:
        """A vonalunk a partner utolsó licitje ELŐTT mondta-e már (természetesen) a színt."""
        from ..domain import vonal
        lic = [e for e in self.licitek]
        utolso_i = max((i for i, e in enumerate(lic) if e.get("ules") == self.partner
                        and str(e.get("licit", "")).upper() not in ("P", "PASS")), default=-1)
        return any(vonal(e.get("ules")) == vonal(self.ules) and _bont(str(e.get("licit", "")).upper())
                   and _bont(str(e.get("licit", "")).upper())[1] == sz
                   for e in lic[:utolso_i])

    def fel_fogas(self, sz: str) -> bool:
        """Fél fogás (a szerkesztő): Qx, Jxx, xxxx — a partner fél fogásával együtt elég."""
        lapok = {l.ertek for l in self.kez.lapok if l.szin == sz}
        n = self.kez.hossz(sz)
        return ("Q" in lapok and n >= 2) or ("J" in lapok and n >= 3) or n >= 4

    def fogaskeres(self) -> str | None:
        """A 3NT alatti FOGÁSKÉRÉS: az egyetlen fogás nélküli ellenfél-szín
        legolcsóbb licitje, ha 3NT alatt van (a szerkesztő, 2026-10-22)."""
        if self.allas.mondta("NT", "p"):
            return None
        partneri = self.partner_kontrazott_szinei()
        hiany = [sz for sz in self.ellenfel_szinei() if not self.fogas(sz) and sz not in partneri]
        if len(hiany) != 1:
            return None
        # csak ha a vonalunk már legalább két saját licitet mondott (nyitás és
        # válasz) — a válaszoló első licitje az ő színükben fésű vagy
        # felüllicites emelés (a szerkesztő, 2026-10-22)
        from ..domain import vonal
        sajat_licitek = [e for e in self.licitek if vonal(e.get("ules")) == vonal(self.ules)
                         and _bont(str(e.get("licit", "")).upper())]
        if len(sajat_licitek) < 2:
            return None
        sz = hiany[0]
        h = self.legolcsobb(sz)
        if not h:
            return None
        # ha csak ÍGÉRTÉK (kontrával), a legolcsóbb licit természetes marad:
        # a fogáskérés egy szinttel feljebb (1♥-(X)-2♦-(P)-3♠)
        if not self.allas.mondta(sz, "ok"):
            h = f"{int(h[0]) + 1}{sz}"
            if h not in self.legalis:
                return None
        return h if h[0] != "1" and _rang(h) < _rang("3NT") else None

    def szan_fogas_nelkul(self, ossz: int) -> bool:
        """3NT fogás nélkül is (a szerkesztő, 2026-10-22), ha a fogáskérésre
        nincs hely: valószínűleg 5+ lapunk van együtt az ellenfél színében,
        gémerő (24+), nincs 8 lapos nemes fit, és az 5m sem jobb (nincs 8
        lapos minor fit 27+ ponttal)."""
        hiany = [sz for sz in self.ellenfel_szinei() if not self.fogas(sz)]
        if not hiany or ossz < 24:
            return False
        if any(self.biztos_fit(m) >= 8 for m in NEMES):
            return False
        if any(self.biztos_fit(m) >= 8 for m in ("C", "D")) and ossz >= 27:
            return False
        return all(self.kez.hossz(sz) + self.partner_hossz(sz) >= 5 for sz in hiany)

    def partner_kontrazott_szinei(self) -> set[str]:
        """
        Az ellenfél színei, amelyeket a partner 3-as szinten vagy följebb
        megkontrázott: az ilyen kontra büntető, tehát ott fogása van (Moha).
        """
        ki: set[str] = set()
        utolso = None                                   # (ülés, szint, szín)
        for e in self.licitek:
            h = str(e.get("licit", "")).upper()
            b = _bont(h)
            if b:
                utolso = (e.get("ules"), b[0], b[1])
            elif h == "X" and e.get("ules") == self.partner and utolso:
                u, szint, sz = utolso
                if u not in (self.ules, self.partner) and szint >= 3 and sz in SZINEK:
                    ki.add(sz)
        return ki

    def partner_kontrazta(self) -> bool:
        """Az ellenfél jelenlegi felvételét a partner kontrázta (még áll a kontra)."""
        if getattr(self.allas, "kontra_allas", "NINCS") != "MI":
            return False
        for e in reversed(self.licitek):
            h = str(e.get("licit", "")).upper()
            if h == "X":
                return e.get("ules") == self.partner
            if h not in ("P", "PASS"):
                return False
        return False

    def szan_mehet(self) -> bool:
        """3NT: minden tudott ellenfél-színben fogás — nálam, vagy a partner
        szant mondott, vagy büntetőre kontrázta azt a színt."""
        if self.allas.mondta("NT", "p"):
            return True
        partneri = self.partner_kontrazott_szinei()
        return all(self.fogas(sz) or sz in partneri for sz in self.ellenfel_szinei())

    # -- büntető passz: a partner kontrázta a felvételüket --

    def vedo_utesek(self, adu: str | None) -> float:
        """A saját védőütéseim becslése (gyorsütések; az aduszínben a figurák)."""
        ki = 0.0
        for sz in SZINEK:
            r = {l.ertek for l in self.kez.lapok if l.szin == sz}
            n = len(r)
            if sz == adu:
                ki += ("A" in r) + ("K" in r and n >= 2) + 0.5 * ("Q" in r and n >= 3) \
                    + 0.5 * (n >= 4)
            elif "A" in r and "K" in r:
                ki += 2
            elif "A" in r and "Q" in r:
                ki += 1.5
            elif "A" in r or ("K" in r and "Q" in r):
                ki += 1
            elif "K" in r and n >= 2:
                ki += 0.5
        return ki

    def buntetes_heurisztika(self) -> tuple[bool, str]:
        """Hagyjuk-e bent a kontrát (szimuláció nélküli becslés)?"""
        from ..domain import vonal
        ki_mondta, utolso = self.utolso_licit()
        szint, szin = _bont(utolso)
        adu = None if szin == "NT" else szin
        en = self.vedo_utesek(adu)
        partner = 2.0                                  # a büntető kontra ~2 ütést ígér
        bukas = int(en + partner - (7 - szint) + 0.25)
        beli = str(getattr(self.allas, "beliallas", "NONE")).upper()
        ok_vonal = vonal(ki_mondta)
        ok_beli = beli in ("ALL", "BOTH") or beli == ok_vonal
        tabla = [0, 200, 500, 800, 1100, 1400] if ok_beli else [0, 100, 300, 500, 800, 1100]
        nyereseg = tabla[max(0, min(bukas, 5))]
        mi_beli = self._beliben()
        sajat = (620 if mi_beli else 420) * 0.7 if self._gem_valoszinu() else 110
        indok = (f"büntető passz becslése: a védőütéseim ~{en:g}, a partneré ~{partner:g}, "
                 f"{utolso} kontrázva ~{bukas} bukás = {nyereseg}; a saját felvételünk ~{sajat:.0f}")
        return nyereseg > sajat, indok

    def _gem_valoszinu(self) -> bool:
        """Megvan-e (valószínűleg) a saját gémünk: a pontok a partner minimumával,
        vagy hosszú színnel a játékütések (az enyéim + a partneré ~ pont/3)."""
        plo, _ = self.partner_sav()
        if self.sajat() + plo >= 24:
            return True
        from ..domain import ERTEKELOK
        try:
            jatek = float(ERTEKELOK["J_KLASSZIKUS"](self.kez))
        except Exception:                      # noqa: BLE001
            return False
        return max(self.kez.hossz(sz) for sz in SZINEK) >= 6 and jatek + plo / 3.0 >= 9.5

    def jatszhato(self, sz: str) -> bool:
        """
        Játszható-e a felvétel ebben a színben (DD-mérés helyett, egyelőre):
          * 8+ lapos fit: igen;
          * 7 lapos: 5-2 igen; 4-3 csak akkor, ha a 3 lapos adu mellett rövidség
            (szingli / sikén) van — a rövid aduból lopás plusz ütés (Moha).
        """
        if sz == "NT":
            return True
        en, p = self.kez.hossz(sz), self.partner_hossz(sz)
        if en + p >= 8:
            return True
        if en + p < 7:
            return False
        if max(en, p) >= 5:
            return True
        if en <= 3:                                  # a 3 lapos adu nálam
            return any(self.kez.hossz(m) <= 1 for m in SZINEK if m != sz)
        return any(self.p.hossz(m)[1] <= 1 for m in SZINEK if m != sz)

    def gem(self) -> str | None:
        """
        A természetes gém: nemes fittel 4M; 3NT, ha az ellenfél színeiben van
        fogás; minor fittel 5m. Fogás nélkül: gémforsz licit (pl. fogáskérő
        felüllicit), 7 lapos játszható nemes fit, végül a 3NT.
        """
        fit = self.legjobb_fit()
        if fit in NEMES and self.fit(fit) >= 8 and f"4{fit}" in self.legalis:
            return f"4{fit}"
        if self.szan_mehet() and "3NT" in self.legalis and self.fogas_rendben("3NT"):
            return "3NT"
        # fogás nélkül: fogáskérés az ellenfél színében, ha 3NT alatt van hely
        fk = self.fogaskeres()
        if fk and not (fit in ("C", "D") and self.fit(fit) >= 8 and self.sajat() + self.partner_sav()[0] >= 27):
            return fk
        if fit in ("C", "D") and self.fit(fit) >= 8 and f"5{fit}" in self.legalis:
            return f"5{fit}"
        if "3NT" in self.legalis and self.szan_fogas_nelkul(self.sajat() + self.partner_sav()[0]):
            return "3NT"
        gf = [h for h, o in self.jelentesek() if o == "GF"]
        if gf:
            return gf[0]
        for m in NEMES:
            if self.jatszhato(m) and self.fit(m) >= 7 and f"4{m}" in self.legalis:
                return f"4{m}"
        return "3NT" if "3NT" in self.legalis and self.fogas_rendben("3NT") else None

    def fogas_rendben(self, hivas: str) -> bool:
        """
        A hívás rendszerbeli jelentése nem ígér-e olyan FOGÁST, ami nincs
        meg (2026-10-05, FOGASMUTATAS: ott a 3NT = fogás minden még le nem
        fedett színben). Ha a hívásnak nincs ismert jelentése, nincs mit
        megsérteni: rendben.
        """
        try:
            lista = self.prop.jelentes_sorokkal(self.licitek, self.ules, hivas,
                                                self.tar, self.oszto)
        except Exception:                  # noqa: BLE001
            return True
        if not lista:
            return True
        return any(all(self.fogas(sz) for sz in (getattr(ig, "fogas", ()) or ()))
                   for _s, ig in lista)

    def _szin_szlem(self, sajat: int, plo: int, phi: int,
                    utolso: str | None) -> HezagDontes | None:
        """
        Megállapodott adu (a kényszertár szerint 8+ lap) és a közös erő
        ALSÓ határa is eléri a szín-szlemet (30+): nem állunk meg a gémben
        (a szerkesztő, 2026-10-05: 1♥-1♠-3♥-3♠-4♦-4NT-5♥ után passz helyett 6).
        Ha a felső határ a nagyszlemig (35+) ér, és van gém fölötti
        kulcslicit (ász vagy sikén) a 6-os adu alatt: kulcslicit, tovább a
        nagyszlem felé. Párosversenyen (MP/BAM) a 6-os adu és a 6NT közül a
        DD-minta dönt, ha a szimuláció engedélyezett (a szan +10 pont, ha nem
        kell lopás); csapatversenyen (IMP) a biztosabb: az adu.
        """
        adu = self.allas.adu() if self.tar else None
        if adu is None:
            return None
        also, felso = sajat + plo, sajat + phi
        if also < SZIN_SZLEM:
            return None
        kis = f"6{adu}"
        if utolso and _rang(utolso) >= _rang(kis):
            return None                             # már szlemben (vagy fölötte) vagyunk
        osszeg = f"A = {sajat}+{plo} = {also}, F = {sajat}+{phi} = {felso}"
        # ha még lehet, előbb kulcslapot kérdezünk (nemes adu: 4♠ / 4NT)
        rkc = {"H": "4S", "S": "4NT"}.get(adu)
        if rkc and rkc in self.legalis and (not utolso or _rang(rkc) > _rang(utolso)):
            return HezagDontes(rkc, "1", f"{osszeg}: az alsó határral is szlem — kulcslapkérdés")
        if felso >= SZIN_NAGYSZLEM:
            for sz in ("C", "D", "H", "S"):
                if sz == adu:
                    continue
                for szint in (5, 6):
                    lic = f"{szint}{sz}"
                    if lic in self.legalis and _rang(lic) < _rang(kis) and \
                            (not utolso or _rang(lic) > _rang(utolso)):
                        if any(l.szin == sz and l.ertek == "A" for l in self.kez.lapok) \
                                or self.kez.hossz(sz) == 0:
                            return HezagDontes(lic, "1", f"{osszeg}: a szlem biztos (szín: "
                                               f"{SZIN_SZLEM}+), a nagyszlem nem kizárt — "
                                               f"kulcslicit ({lic})")
                        break
        if kis not in self.legalis:
            return None
        valasz = kis
        indok = f"{osszeg}: az alsó határral is szlem (szín: {SZIN_SZLEM}+)"
        if self.pontozas in ("MP", "BAM") and "6NT" in self.legalis \
                and self.vegkontraktus is not None:
            try:
                m = self.vegkontraktus([kis, "6NT"]) or {}
            except Exception:                       # noqa: BLE001
                m = {}
            if m.get("best") in (kis, "6NT"):
                valasz = m["best"]
                indok += (f"; párosversenyen a DD-minta szerint {valasz} "
                          f"({m.get('options')})")
        return HezagDontes(valasz, "1", indok)

    def _szan_szlem(self, also: int, felso: int, szelesseg: int = 0) -> tuple[str, str] | None:
        """
        Szan-szlem a közös erőből (a szerkesztő küszöbei, 2026-10-04: szanban
        33+ a kis szlem, 37+ a nagy), ha nincs megállapodott adu — különben a
        4NT ászkérdés volna. Felső becsléssel eléri, alsóval nem: 4NT
        (kvantitatív szleminvit); alsóval is eléri: 6NT, és ha a felső a
        nagyszlemet is eléri: 5NT (nagyszlem-invit); alsóval a nagyszlem: 7NT.
        A 3NT "kényszerből" hangzana, pedig nyers erő van mögötte.
        Invitálni (4NT / 5NT) csak a partner LIMITÁLT sávjával lehet (legfeljebb
        SAV_LIMIT pont széles): nyitott sávnál a felső becslés semmit nem mond.
        """
        if self.tar and any(self.biztos_fit(sz) >= 8 for sz in SZINEK):
            return None
        valaszt = None
        if also >= SZAN_NAGYSZLEM:
            valaszt = ("7NT", f"az alsó határral is nagyszlem (szanban {SZAN_NAGYSZLEM}+)")
        elif also >= SZAN_SZLEM and felso >= SZAN_NAGYSZLEM and szelesseg <= SAV_LIMIT:
            valaszt = ("5NT", f"kis szlem biztos, a nagyszlem a felső határon: nagyszlem-invit")
        elif also >= SZAN_SZLEM:
            valaszt = ("6NT", f"az alsó határral is szlem (szanban {SZAN_SZLEM}+)")
        elif felso >= SZAN_SZLEM and szelesseg <= SAV_LIMIT:
            valaszt = ("4NT", f"a felső határral szlem (szanban {SZAN_SZLEM}+): kvantitatív szleminvit")
        if valaszt and valaszt[0] in self.legalis:
            return valaszt
        return None

    def jelentesek(self) -> list[tuple[str, str]]:
        """[(hívás, osztály)] a szabályos hívásokra, amelyeknek a rendszerben van
        jelentése, és a lapom (tűréssel) illik rá. Osztály: NF / GI / F1 / GF."""
        ki = []
        sajat = self.sajat()
        for h in self.legalis:
            if h in ("P", "X", "XX"):
                continue
            try:
                lista = self.prop.jelentes_sorokkal(self.licitek, self.ules, h, self.tar, self.oszto)
            except Exception:              # noqa: BLE001 — egy rossz sor ne állítsa meg
                continue
            for _sor, ig in lista:
                # a csak megértést szolgáló sor (pl. TERMESZETES_ALAP) nem
                # leíró licit a kibic számára (2026-10-21)
                if (getattr(_sor, "jelentes", None) or {}).get("csak_megertes"):
                    continue
                if not (ig.pont_min - 1 <= sajat <= ig.pont_max + 1):
                    continue
                if any(self.kez.hossz(sz) < ig.hossz(sz)[0] - 1 or
                       self.kez.hossz(sz) > ig.hossz(sz)[1] + 1 for sz in SZINEK):
                    continue
                # a fogás-ígéretnek nincs tűrése: hamis fogást nem mutatunk
                # (2026-10-05, FOGASMUTATAS: a 3♥ = fogás a kőrben)
                if any(not self.fogas(sz) for sz in getattr(ig, "fogas", ()) or ()):
                    continue
                osztaly = ("GF" if ig.forsz in ("GEMFORSZ", "SZLEMFORSZ") else
                           "GI" if ig.gi else
                           "F1" if ig.forsz == "EGY_MENET" else "NF")
                ki.append((h, osztaly))
                break
        return sorted(ki, key=lambda x: _rang(x[0]))

    # -- a döntés --

    def dont(self) -> HezagDontes | None:
        # 5. a partner (büntetőre) kontrázta a felvételüket: bent hagyjuk, vagy a miénk?
        if self.partner_kontrazta() and "P" in self.legalis:
            if self.buntetes is not None:
                try:
                    m = self.buntetes() or {}
                except Exception:              # noqa: BLE001
                    m = {}
                if "imp_difference" in m:
                    jobb = m.get("penalty_better")
                    if jobb is None:
                        jobb = (m.get("mp_win_rate", 0) > 0.5) if self.pontozas in ("MP", "BAM") \
                            else m["imp_difference"] > 0
                    if jobb:
                        return HezagDontes("P", "5", f"büntető passz: a szimuláció szerint a "
                                                     f"bukás {m['imp_difference']:+.1f} IMP-vel jobb "
                                                     f"({m.get('summary', '')})")
                    self.buntetes_info = m
            if self.buntetes is None or not getattr(self, "buntetes_info", None):
                jobb, indok = self.buntetes_heurisztika()
                if jobb:
                    return HezagDontes("P", "5", indok)
        sajat = self.sajat()
        plo, phi = self.partner_sav()
        fit = self.legjobb_fit()
        fit_nemes = any(self.biztos_fit(m) >= 8 for m in NEMES) or \
            (fit in NEMES and self.fit(fit) >= 8)
        fit_minor = any(self.biztos_fit(m) >= 8 for m in ("C", "D")) or \
            (fit in ("C", "D") and self.fit(fit) >= 8)
        szan_lehet = True   # (a 3NT-feltételt nem szűkítjük — 2026-10-21, mellékhatások)
        also = _gemkuszob_eleri(sajat, plo, self.kez, self.p, fit_nemes, fit_minor, szan_lehet)
        # a felső határ: a partner sávjának BÁRMELY értékével (a szanfeltétel nem
        # monoton: nagy eltérésnél hosszú szín kell)
        felso = any(_gemkuszob_eleri(sajat, p, self.kez, self.p, fit_nemes, fit_minor, szan_lehet)
                    for p in range(plo, phi + 1))
        kenyszer = self.kenyszer()
        ki_mondta, utolso = self.utolso_licit()
        from ..domain import vonal
        mienk = ki_mondta is not None and vonal(ki_mondta) == vonal(self.ules)
        gem_folott = bool(utolso) and _bont(utolso)[0] >= GEMSZINT[_bont(utolso)[1]]
        osszeg = f"A = {sajat}+{plo} = {sajat + plo}, F = {sajat}+{phi} = {sajat + phi}"

        # a partner az ellenfél színét mondta 3NT alatt: FOGÁSKÉRÉS (2026-10-22)
        # — fogással vagy fél fogással 3NT, anélkül a közös fitbe (menekülőút)
        if mienk and ki_mondta == self.partner and utolso and not gem_folott \
                and _bont(utolso)[1] in self.ellenfel_szinei() \
                and not self._mondtuk_korabban(_bont(utolso)[1]) \
                and _rang(utolso) < _rang("3NT") and "3NT" in self.legalis \
                and self._partner_fogaskeres(utolso):
            sz = _bont(utolso)[1]
            if self.fogas(sz) or self.fel_fogas(sz):
                return HezagDontes("3NT", "1", f"{osszeg}: a partner {utolso}-ja fogáskérés — "
                                               f"{'fogásom' if self.fogas(sz) else 'fél fogásom'} van: 3NT")
            if fit is not None:
                h = self.legolcsobb(fit)
                if fit in ("C", "D") and sajat + plo >= 27 and f"5{fit}" in self.legalis:
                    h = f"5{fit}"
                if h:
                    return HezagDontes(h, "1", f"{osszeg}: a partner {utolso}-ja fogáskérés — "
                                               f"fogásom nincs: a közös fitbe ({h})")

        # 4. a partner utolsó licitjét nem értjük: ő a kapitány
        if mienk and not self.partner_utolso_ertve() and not gem_folott:
            en = self.tar[self.ules]
            lo, hi = en.pont_min, min(en.pont_max, 37)
            felso_fel = hi > lo and sajat >= (lo + hi) / 2
            if felso_fel and felso:
                g = self.gem()
                if g:
                    return HezagDontes(g, "4", f"a partner licitjét nem értem; a sávom "
                                                f"felső felében vagyok ({sajat}, sáv {lo:g}-{hi:g}): gém")
            return self._lezaras("4", f"a partner licitjét nem értem; a sávom alsó felében "
                                      f"vagyok ({sajat} pont): a legjobb fitben lezárok", kenyszer)

        # a partner (nem értett) 3NT-je, de MEGÁLLAPODOTT nemes adunk van (mindketten
        # tudjuk: 8+ lap): a nemes gém (Moha, 2026-10-04: 1♥-1♠-3♥-3♠-3NT után 4♥)
        if gem_folott and mienk and utolso == "3NT" and ki_mondta == self.partner \
                and not self.partner_utolso_ertve():
            for m in NEMES:
                if self.biztos_fit(m) >= 8 and self.p.hossz(m)[0] >= 5 \
                        and f"4{m}" in self.legalis:
                    return HezagDontes(f"4{m}", "4", f"a partner 3NT-jét nem értem, de a "
                                                     f"{m} adu megállapodott ({self.biztos_fit(m)} lap): "
                                                     f"a nemes gém")
        # a partner gém fölötti, NEM adu-színű licitje megállapodott adu mellett
        # kulcslicit (szlemkutatás) — nem passzolható: vissza az aduba
        if mienk and ki_mondta == self.partner and utolso and self.tar:
            adu = self.allas.adu()
            sz_, szin_ = _bont(utolso)
            if adu and szin_ not in (adu, "NT") and sz_ >= 4:
                cel = self.allas.kovetkezo_licit(adu)
                if cel:
                    lic = f"{cel[0]}{cel[1]}"
                    if (sajat + plo >= SZIN_NAGYSZLEM and cel[0] < 7 and f"7{adu}" in self.legalis):
                        lic = f"7{adu}"
                    if lic in self.legalis:
                        return HezagDontes(lic, "1", f"{osszeg}: a partner {utolso}-ja kulcslicit a "
                                                     f"megállapodott adu ({adu}) mellett — nem passzolható")
        # szín-szlem a megállapodott aduban (a szerkesztő küszöbe: 30+): ha
        # a közös erő alsó határa is eléri, nem állunk meg a gémben
        if mienk or not utolso:
            sz = self._szin_szlem(sajat, plo, phi, utolso)
            if sz is not None:
                return sz
        if gem_folott and mienk and not kenyszer:
            return HezagDontes("P", "3", "már gémben vagyunk, és nincs kényszer")

        # a KVÁZI gémforsz határa (4m): a partner épp ott állt meg, minimális
        # lappal passz (a szerkesztő, 2026-10-21: 1♠-2♦-2♠-3♥-4♦ — „csak a
        # passz jó”); csak bőven a minimum fölött megyünk tovább
        if mienk and ki_mondta == self.partner and utolso and not kenyszer \
                and self.allas.gf_teljesult() and _bont(utolso)[1] in ("C", "D") \
                and self.allas.adu() not in ("H", "S") and "P" in self.legalis:
            en = self.tar[self.ules]
            if sajat < en.pont_min + 4:
                return HezagDontes("P", "2", f"{osszeg}: a kvázi gémforsz a {utolso}-nál "
                                             f"véget ért, minimális lappal ({sajat}) passz")

        # 1. az alsó határral is gém
        if also:
            gf = [h for h, o in self.jelentesek() if o == "GF"]
            if gf:
                return HezagDontes(gf[0], "1", f"{osszeg}: az alsó határral is gém — gémforsz")
            g = self.gem()
            if g == "3NT" and not (gem_folott and mienk):
                sz = self._szan_szlem(sajat + plo, sajat + phi, phi - plo)
                if sz is not None:
                    return HezagDontes(sz[0], "1", f"{osszeg}: {sz[1]}")
            if g and not (gem_folott and mienk):
                return HezagDontes(g, "1", f"{osszeg}: az alsó határral is gém")
            if gem_folott and mienk:
                return HezagDontes("P", "1", f"{osszeg}: már gémben vagyunk")
        # 2. csak a felső határral gém: géminvit (gém alatti), ha van; ha nincs,
        #    a gém esélye dönt — közepes eséllyel egy gém alatti, egy körre
        #    kényszerítő leíró licit is jó (nyitva tartja a gémet)
        if felso and not also:
            # a gém esélye a partner sávjában: a sáv alja valószínűbb (mértani,
            # 0,8-as csökkenő súly); küszöb: mansban 45%, bellben 37% (IMP)
            sulyok = {p: 0.8 ** (p - plo) for p in range(plo, phi + 1)}
            jo = sum(w for p, w in sulyok.items()
                     if _gemkuszob_eleri(sajat, p, self.kez, self.p, fit_nemes, fit_minor, szan_lehet))
            esely = jo / max(1e-9, sum(sulyok.values()))
            kuszob = 0.37 if self._beliben() else 0.45
            jel = [(h, o) for h, o in self.jelentesek() if _gem_alatt(h)]
            gi = [h for h, o in jel if o == "GI"]
            if gi:
                return HezagDontes(gi[0], "2", f"{osszeg}: gém csak a felső határral — géminvit")
            if esely >= kuszob:
                g = self.gem()
                if g:
                    return HezagDontes(g, "2", f"{osszeg}: nincs géminvit-licit, a gém esélye "
                                                f"{esely:.0%} (küszöb {kuszob:.0%}): gém")
            f1 = [h for h, o in jel if o == "F1"]
            if f1 and esely >= 0.25:
                return HezagDontes(f1[0], "2", f"{osszeg}: nincs géminvit-licit, a gém esélye "
                                                f"{esely:.0%}: gém alatti, kényszerítő leíró licit")
            return self._lezaras("2", f"{osszeg}: nincs géminvit-licit, a gém esélye csak "
                                      f"{esely:.0%}", self.kenyszer())
        # 3. gém alatt
        return self._lezaras("3", f"{osszeg}: nincs gémesély", kenyszer)

    def _beliben(self) -> bool:
        from ..domain import vonal
        b = str(getattr(self.allas, "beliallas", "NONE")).upper()
        return b in ("ALL", "BOTH") or b == vonal(self.ules)

    def _lezaras(self, pont: str, indok: str, kenyszer: bool) -> HezagDontes | None:
        from ..domain import vonal
        ki_mondta, utolso = self.utolso_licit()
        fit = self.legjobb_fit()
        mienk = ki_mondta is not None and vonal(ki_mondta) == vonal(self.ules)
        if mienk and not kenyszer:
            szin = _bont(utolso)[1]
            # DD-mintavétellel, ha van rá idő (szimuláció): a passz (a mostani
            # felvétel marad) vagy a legolcsóbb javítás a játszható fitekbe
            if self.vegkontraktus is not None:
                jeloltek = ["P"] + [h for h in (self.legolcsobb(m) for m in SZINEK
                                                if m != szin and self.fit(m) >= 7)
                                    if h and _gem_alatt(h)]
                if len(jeloltek) > 1:
                    try:
                        r = self.vegkontraktus(jeloltek) or {}
                    except Exception:          # noqa: BLE001
                        r = {}
                    if r.get("best"):
                        return HezagDontes(r["best"], pont, indok + f" — DD-minta ({r.get('samples')} "
                                                                    f"leosztás): {r.get('options')}")
            jatszhato = self.jatszhato(szin)
            sokkal_jobb = fit is not None and fit != szin and \
                self.fit(fit) >= (self.fit(szin) if szin != "NT" else 7) + 2
            if jatszhato and not sokkal_jobb:
                return HezagDontes("P", pont, indok + f" — a {utolso} játszható, passz")
            if fit is not None:
                h = self.legolcsobb(fit)
                if h:
                    return HezagDontes(h, pont, indok + f" — a {utolso} helyett a jobb fit: {h}")
            return HezagDontes("P", pont, indok + " — nincs jobb, passz")
        if not kenyszer:
            return HezagDontes("P", pont, indok + " — nincs kényszer, passz")
        # kényszerben: ha van (megállapodott / valószínű 8+) fit, oda a legolcsóbban
        # (ha a mostani felvétel nem már az); különben a legolcsóbb leíró licit
        if fit is not None and self.fit(fit) >= 8:
            jelen = _bont(utolso)[1] if utolso else None
            h = self.legolcsobb(fit)
            if h and jelen != fit:
                return HezagDontes(h, "0", indok + f" — kényszerben, a fitbe: {h}")
        leiro = [h for h, o in self.jelentesek() if o in ("NF", "F1")]
        if leiro:
            return HezagDontes(leiro[0], "0", indok + " — kényszerben: a legolcsóbb leíró licit")
        for sz in ([fit] if fit else []) + sorted(SZINEK, key=lambda s: -self.kez.hossz(s)):
            h = self.legolcsobb(sz)
            if h:
                return HezagDontes(h, "0", indok + f" — kényszerben (passz nem lehet): {h}")
        h = self.legolcsobb("NT")
        if h:
            return HezagDontes(h, "0", indok + " — kényszerben: szan")
        return None


def hezag_dontes(kez, allas, prop, licitek, ules, oszto, legalis,
                 megertes=None, valoszinu=None, buntetes=None,
                 vegkontraktus=None, pontozas=None) -> HezagDontes | None:
    """A belépő: None, ha a hézag-elv sem tud dönteni. A `buntetes` (opcionális)
    a szimulációs összemérés (büntető passz vagy a saját felvétel)."""
    try:
        return Hezag(kez, allas, prop, licitek, ules, oszto, legalis,
                     megertes, valoszinu, buntetes, vegkontraktus, pontozas).dont()
    except Exception:                      # noqa: BLE001 — a tartalék nem dőlhet el
        return None
