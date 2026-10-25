"""
MOHA_SPIRAL — a kulcslap-válasz utáni spirál-kérdezés (a szerkesztő, 2026-09-30;
gépi alak 2026-10-04). Emberi leírás: doc/moha-elvek.md.

A sorrend ÁLLANDÓ (nem rendeződik át, nem marad ki semmi):
  1. réteg: adu dáma (ha a kulcslap-válaszból nem derült ki);
  2. réteg: királyok a külső színekben, csökkenő sorrendben (♠ ♥ ♦ ♣);
  3. réteg: dámák ugyanígy;
  4. réteg: bubik — az adu bubi, majd a külső színek.
A partner TUDOTT sikénje királynak számít (és a kulcslap-válaszban
ásznak — az a válaszoló dolga).

KÉRDÉS (a kérdező): a kulcslap-válasz (vagy az előző spirál-válasz)
fölötti lépcsők, de az ADU SZÍN licitjei és a 4NT nem lépcsők — azok
LEÁLLÁS (a 4NT és az 5m reléként is leállás). R1 = relé: a következő
tétel; R2 = szuper-relé: a következő réteg eleje; R3: az azutáni réteg.
(R = a kérdező relé-lépcsője; L = a válaszoló lépcsője.)
KIVÉTEL (2026-10-05): ugrás (R2+) szlem-szintre egy posszibilisen
játszható színben (összeemelt vagy önállóan licitált) vagy szanban: a
szlem bemondása, passzolandó.

VÁLASZ (a válaszoló): a relé fölötti lépcsők — itt MINDEN licit lépcső
(a 4NT és az 5m is). L1 = "a kérdezett tétel nincs nálam"; L2 = "nálam
van, a következő nincs"; L3 = "mindkettő nálam, a harmadik nincs"... A
következő relé a TAGADOTT tétel utánitól kérdez.

A kérdező döntése (a gép mostani elve):
  * a kétértelmű válasznál (0/3, 1/4) a ROSSZABB esetet tételezi fel; ha a
    válaszolónál a jobbik van, és a kérdező a szlem alatt állt le, a
    válaszoló mondja a szlemet (a szerkesztő, 2026-10-05);
  * 2+ hiányzó kulcslap: leállás 5m-ben (ha a válasz épp az: passz);
    minor adunál 4NT-ben, ha a tudott fit legfeljebb 8 lapos, a vonal
    már licitált szant, és a kérdezőnek nincs renonsza, az adu nála
    legfeljebb 5 lapos (2026-10-23); a 4NT-re a válaszoló többlethosszal
    és nem szan jellegű lappal 5m-re javít;
  * 1 hiányzó kulcslap: kis szlem, ha az adu dáma megvan (vagy 10+ adu);
    ha a dáma ismeretlen, a spirál első tételével megkérdezi (ha a
    tagadó válasz még nem megy az 5m fölé); ha nincs meg: 5m;
  * 0 hiányzó kulcslap: nagyszlem-kutatás — a szükséges tételek (adu
    dáma, a külső királyok, ahol nekem nincs és nem vagyok sikén):
    ha mind megvan: 7m; ha valamelyik hiányzik: 6m; különben relé (vagy
    szuper-relé) a következő szükséges tételig, amíg a tagadó válasz 6m
    alatt marad.
A NAGYSZLEM-ítélet egyelőre csak a lapokat nézi (ütésszámolás nincs).
"""
from __future__ import annotations

from dataclasses import dataclass

from .helyzet import JELENTESEK, _licit_rang, fogas_kezben, kovetkezo_ules

_KULSO_RENDBEN = ("S", "H", "D", "C")
_SZIMB = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
_FIG = {"A": "A", "K": "K", "Q": "D", "J": "B"}
_FIG_NEV = {"K": "király", "Q": "dáma", "J": "bubi"}


@dataclass
class SpiralDontes:
    licit: str
    szerep: str               # "kerdezo" / "valaszolo"
    indok: str


def _rang(licit: str) -> int | None:
    return _licit_rang(licit) if licit and licit[0].isdigit() else None


def _licit_rangbol(r: int) -> str:
    return f"{r // 5 + 1}{JELENTESEK[r % 5]}"


def _tetel_nev(t: tuple[str, str], adu: str) -> str:
    fig, sz = t
    if sz == adu:
        return f"adu {_FIG_NEV[fig]} ({_SZIMB[sz]}{_FIG[fig]})"
    return f"{_SZIMB[sz]}{_FIG[fig]}"


def tetelek(adu: str, dama_ismert: bool) -> tuple[list[tuple[str, str]], list[int]]:
    """A spirál tételei és a rétegek kezdő indexei."""
    kulso = [sz for sz in _KULSO_RENDBEN if sz != adu]
    t: list[tuple[str, str]] = []
    retegek: list[int] = []
    if not dama_ismert:
        retegek.append(len(t))
        t.append(("Q", adu))
    retegek.append(len(t))
    t += [("K", sz) for sz in kulso]
    retegek.append(len(t))
    t += [("Q", sz) for sz in kulso]
    retegek.append(len(t))
    t += [("J", adu)] + [("J", sz) for sz in kulso]
    return t, retegek


def _reteg(pos: int, retegek: list[int]) -> int:
    r = 0
    for i, k in enumerate(retegek):
        if pos >= k:
            r = i
    return r


def _rele_lepcsok(utolso: str, adu: str, jatszhato: set[str] | None = None,
                  meddig: int = 34) -> list[str]:
    """
    A kérdező lépcsői az `utolso` fölött: az adu szín és a 4NT kimarad.
    UGRÁS (R2 vagy több) szlem-szintre (6/7) egy POSSZIBILISEN JÁTSZHATÓ
    színben (`jatszhato`: összeemelt vagy önállóan licitált szín) vagy szanban
    nem relé, hanem a szlem bemondása — passzolandó (a szerkesztő,
    2026-10-05: az ORKC a minor fedő-lapjait deríti ki, a szlem aztán
    ugrással a "tényleges" színben). Az R1 ilyenkor is relé.
    """
    ki = []
    r0 = _rang(utolso)
    if r0 is None:
        return ki
    for r in range(r0 + 1, meddig + 1):
        lic = _licit_rangbol(r)
        if lic[1:] == adu or lic == "4NT":
            continue
        if ki and int(lic[0]) >= 6 and (lic[1:] == "NT" or lic[1:] in (jatszhato or ())):
            continue                       # ugrás a szlembe: leállás, nem relé
        ki.append(lic)
    return ki


def _van(kez, t: tuple[str, str], sikenek: set[str]) -> bool:
    fig, sz = t
    if fig == "K" and sz in sikenek:
        return True
    return any(l.szin == sz and l.ertek == fig for l in kez.lapok)


def _szan_szlem_jo(kez, tar_partner, adu: str, adu_hossz: int) -> bool:
    """A szlem szanban (a szerkesztő, 2026-10-25): a 6NT mindig szóba jön, ha
    a lapok nem elosztásosak, és a partit nem lopásra / keresztlopásra /
    magasításra alapozzuk — szanban az ellenfél nem buktathat lopással.
    Gépben: nekem nincs 0-1 lapos színem, a partnernek sincs tudott
    rövidsége (két színe együtt sem 10+ lapos), minden nem-adu színt fog
    valamelyikünk (nálam fogás, vagy a partner 4+ lapja / ígért fogása), és
    az adu minor, vagy a nemes fit legfeljebb 8 lapos."""
    if any(kez.hossz(sz) <= 1 for sz in _KULSO_RENDBEN):
        return False
    if tar_partner is not None:
        if any(tar_partner.hossz(sz)[1] <= 1 for sz in _KULSO_RENDBEN):
            return False
        # a partner ígért hosszaiból következő elosztás: ha két színe legalább
        # 10 lapos (5-5, 6-4), a maradék két színben biztosan van 0-1 lapos
        # (vagy erősen elosztásos) — nem szanlap
        mins = sorted((tar_partner.hossz(sz)[0] for sz in _KULSO_RENDBEN), reverse=True)
        if mins[0] + mins[1] >= 10:
            return False
    # a meg nem mutatott színt fogni kell: ahol a partner nem ígért 4+ lapot
    # vagy fogást, ott nálam legyen fogás (A, Kx, Qxx, Jxxx) — különben az
    # ellenfél a 6NT-t a hosszú színével elviszi
    for sz in _KULSO_RENDBEN:
        if sz == adu or fogas_kezben(kez, sz):
            continue
        if tar_partner is not None and (tar_partner.hossz(sz)[0] >= 4
                                        or sz in (tar_partner.fogas or ())):
            continue
        return False
    return adu in ("C", "D") or adu_hossz <= 8


def _partner_max_pont(kez, adu: str, kizart, v: int) -> int:
    """A partner legnagyobb lehetséges figurapontja, ha `v` kulcslapja van:
    40 − az enyém − a nála NEM lévő (tehát az ellenfélnél lévő) kulcslapok
    értéke (a legolcsóbbakat feltételezve az ellenfélnél)."""
    ertek = {"A": 4, "K": 3}
    enyem = {(l.szin, l.ertek) for l in kez.lapok}
    kulcsok = list(dict.fromkeys([(sz, "A") for sz in ("S", "H", "D", "C") if sz != kizart] + [(adu, "K")]))
    nem_enyem = sorted(ertek[f] for (sz, f) in kulcsok if (sz, f) not in enyem)
    ellenfelnel = max(0, len(nem_enyem) - v)
    return 40 - _hcp(kez) - sum(nem_enyem[:ellenfelnel])


def _hcp(kez) -> int:
    return sum({"A": 4, "K": 3, "Q": 2, "J": 1}.get(l.ertek, 0) for l in kez.lapok)


def spiral_dontes(kez, allas, er, licitek: list[dict],
                  engedelyezett: list[str] | None = None) -> SpiralDontes | None:
    """
    Ha a menet a kulcslap-válasz után a spirálban jár, és én következem,
    a spirál szerinti licit; különben None (a többi réteg dönt).
    """
    en = allas.ules
    partner = kovetkezo_ules(en, 2)
    mieink = {en, partner}
    tar = getattr(er, "kenyszertar", None) or {}

    # 1. az utolsó kulcslap-VÁLASZ a vonalunkon
    i_v, kl = None, None
    for i, e in enumerate(licitek):
        if e.get("ules") not in mieink:
            continue
        info = (getattr(er, "licitenkent", None) or {}).get(i) or {}
        ig = info.get("igeret")
        if ig is not None and getattr(ig, "kulcslap", None):
            i_v, kl = i, ig.kulcslap
    if i_v is None:
        return None
    valaszolo = licitek[i_v]["ules"]
    kerdezo = kovetkezo_ules(valaszolo, 2)
    adu = kl["adu"]
    if adu not in _SZIMB:
        return None

    # 2. a válasz utáni licitek: az ellenfél közbeszólása vagy a mi passzunk = vége
    sor: list[tuple[str, str]] = []
    for e in licitek[i_v + 1:]:
        u, lic = e.get("ules"), str(e.get("licit", "")).upper()
        if u in mieink:
            if lic in ("P", "PASS"):
                return None
            sor.append((u, lic))
        elif lic not in ("P", "PASS"):
            return None
    # felváltva: kérdező, válaszoló, ...
    for k, (u, _) in enumerate(sor):
        if u != (kerdezo if k % 2 == 0 else valaszolo):
            return None

    # posszibilisen játszható színek (az adun kívül): összeemelt (a vonal
    # ismert össz-hossza 7+), vagy valamelyikünk önállóan (6+ lappal) licitálta
    jatszhato: set[str] = set()
    for sz in _KULSO_RENDBEN:
        if sz == adu:
            continue
        hosszak = [tar[u].hossz(sz)[0] for u in mieink if tar.get(u) is not None]
        if sum(hosszak) >= 7 or any(h >= 6 for h in hosszak):
            jatszhato.add(sz)

    dama = kl.get("dama")
    t_lista, retegek = tetelek(adu, dama is not None)
    sikenek_v = {sz for sz in _KULSO_RENDBEN
                 if tar.get(valaszolo) is not None and tar[valaszolo].hossz(sz)[1] == 0}
    megvan: set[int] = set()
    hianyzik: set[int] = set()

    # 3. visszajátszás
    pos = 0
    utolso = licitek[i_v]["licit"].upper()
    leallt = False
    for k, (u, lic) in enumerate(sor):
        if u == kerdezo:
            lepcsok = _rele_lepcsok(utolso, adu, jatszhato)
            if lic not in lepcsok:
                leallt = True                    # adu szín / 4NT: leállás
                if k != len(sor) - 1:
                    return None
                break
            n = lepcsok.index(lic) + 1
            if n > 1:
                cel = _reteg(min(pos, len(t_lista) - 1), retegek) + (n - 1)
                if cel >= len(retegek):
                    return None
                pos = retegek[cel]
            utolso = lic
        else:
            r_u, r_l = _rang(utolso), _rang(lic)
            if r_u is None or r_l is None or r_l <= r_u:
                return None
            s = r_l - r_u
            for j in range(pos, min(pos + s - 1, len(t_lista))):
                megvan.add(j)
            if pos + s - 1 < len(t_lista):
                hianyzik.add(pos + s - 1)
            pos = min(pos + s, len(t_lista))
            utolso = lic

    van_e = lambda lic: (not engedelyezett) or lic in engedelyezett  # noqa: E731

    # 4a. VÁLASZOLÓ vagyok, és a partner relézett (vagy leállt)
    if en == valaszolo:
        if not sor or sor[-1][0] != kerdezo:
            return None
        if leallt:
            # A kérdező a kétértelmű válasznál (0/3, 1/4) a ROSSZABB esetet
            # tételezi fel (a szerkesztő, 2026-10-05). Ha nálam a JOBBIK van,
            # és ő a szlem alatt állt le, én mondom a szlemet.
            leallas = sor[-1][1]
            ertekek = sorted(set(int(x) for x in kl.get("ertek") or []))
            aszok_ = sum(1 for l in kez.lapok if l.ertek == "A" and l.szin != kl.get("kizart"))
            sajat_kl_ = aszok_ + any(l.szin == adu and l.ertek == "K" for l in kez.lapok)
            kis_ = f"6{adu}"
            ig_k = tar.get(kerdezo)
            adu_h_ = kez.hossz(adu) + (ig_k.hossz(adu)[0] if ig_k is not None else 0)
            if _szan_szlem_jo(kez, ig_k, adu, adu_h_) and \
                    (not engedelyezett or "6NT" in engedelyezett):
                kis_ = "6NT"
            if len(ertekek) > 1 and sajat_kl_ == max(ertekek) and \
                    _rang(leallas) < _rang(kis_) and \
                    (leallas[1:] == adu or leallas == "4NT") and \
                    (not engedelyezett or kis_ in engedelyezett):
                return SpiralDontes(kis_, "valaszolo",
                                    f"Spirál: a partner {leallas}-sal leállt a rosszabb esetet "
                                    f"feltételezve ({min(ertekek)} kulcslap), de nálam a jobbik "
                                    f"van ({sajat_kl_}): szlem")
            # A 4NT-leállásra (minor adu, a szerkesztő, 2026-10-23): ha van még
            # nem mondott többlethosszam az aduban, és a lapom nem szan jellegű
            # (van 0-1 lapos színem), az 5m reálisabb: javítok.
            if leallas == "4NT" and adu in ("C", "D"):
                sajat_ig = tar.get(en)
                igert = sajat_ig.hossz(adu)[0] if sajat_ig is not None else 0
                rovid = any(kez.hossz(sz) <= 1 for sz in _KULSO_RENDBEN)
                ot_ = f"5{adu}"
                if kez.hossz(adu) > igert and rovid and van_e(ot_):
                    return SpiralDontes(ot_, "valaszolo",
                                        f"Spirál: a partner 4NT-vel leállt; többlethosszam van "
                                        f"az aduban ({kez.hossz(adu)} lap), és a lapom nem szan "
                                        f"jellegű: javítás {ot_}-ra")
            return SpiralDontes("P", "valaszolo",
                                f"Spirál: a partner {leallas} licitje leállás — passz")
        sajat_siken = {sz for sz in _KULSO_RENDBEN
                       if tar.get(en) is not None and tar[en].hossz(sz)[1] == 0}
        db = 0
        while pos + db < len(t_lista) and _van(kez, t_lista[pos + db], sajat_siken):
            db += 1
        s = db + 1
        r = _rang(utolso) + s
        if r > 34:
            return None
        lic = _licit_rangbol(r)
        if not van_e(lic):
            return None
        if pos >= len(t_lista):
            leiras = "nincs több kérdezhető tétel"
        elif db == 0:
            leiras = f"nincs nálam: {_tetel_nev(t_lista[pos], adu)}"
        else:
            vannak = ", ".join(_tetel_nev(t_lista[j], adu) for j in range(pos, pos + db))
            leiras = f"megvan: {vannak}" + (
                f"; nincs: {_tetel_nev(t_lista[pos + db], adu)}" if pos + db < len(t_lista) else "")
        return SpiralDontes(lic, "valaszolo", f"Spirál-válasz, {s}. lépcső — {leiras}")

    # 4b. KÉRDEZŐ vagyok, és a partner válaszolt
    if en != kerdezo or (sor and sor[-1][0] != valaszolo):
        return None

    kizart = kl.get("kizart")          # exclusion: e szín ásza nem kulcslap
    osszes = 4 if kizart else 5
    aszok = sum(1 for l in kez.lapok if l.ertek == "A" and l.szin != kizart)
    sajat_kl = aszok + any(l.szin == adu and l.ertek == "K" for l in kez.lapok)
    ig_p = tar.get(partner)
    ertekek = sorted(set(int(x) for x in kl.get("ertek") or [0]))
    # A kétértelmű válasznál (0/3, 1/4) a ROSSZABB eset (a szerkesztő,
    # 2026-10-05) — ha a partnernél a jobbik van, ő mondja a szlemet.
    lehet = [v for v in ertekek if sajat_kl + v <= osszes]
    # A PONTOK is dönthetnek (a szerkesztő, 2026-10-25): ha a partner ígért
    # minimuma a rosszabb esettel ki sem jöhetne (a hiányzó kulcslapok az
    # ellenfélnél, és a maradék figurapont sem elég), a jobbik eset áll.
    if len(lehet) > 1 and ig_p is not None and ig_p.pont_min > 0:
        lehet = [v for v in lehet
                 if _partner_max_pont(kez, adu, kizart, v) >= ig_p.pont_min] or lehet
    p_kl = min(lehet) if lehet else min(ertekek)
    hiany = osszes - (sajat_kl + p_kl)

    sajat_dama = any(l.szin == adu and l.ertek == "Q" for l in kez.lapok)
    adu_hossz = kez.hossz(adu) + (ig_p.hossz(adu)[0] if ig_p is not None else 0)
    if dama is True or sajat_dama:
        dama_ok = True
    elif dama is False:
        dama_ok = False
    else:
        dama_ok = True if 0 in megvan else False if 0 in hianyzik else None
    if adu_hossz >= 10 and dama_ok is not True:
        dama_ok = True

    r_last = _rang(utolso)

    # Leállás 4NT-ben 5m helyett (a szerkesztő, 2026-10-23): minor adu,
    # legfeljebb 8 lapos tudott fit, és a vonalunk már licitált szant
    # (a 4NT reális alternatíva).
    mi_szan = any(e.get("ules") in mieink and str(e.get("licit", "")).upper() in
                  ("1NT", "2NT", "3NT") for e in licitek[:i_v])
    # A saját lapom se zárja ki a szant: nincs renonszom, és az adu
    # legfeljebb 5 lapos nálam (hosszú minorral / renonsszal az 5m a reális).
    szan_jellegu = all(kez.hossz(sz) >= 1 for sz in _KULSO_RENDBEN) and kez.hossz(adu) <= 5
    szan_leallas = adu in ("C", "D") and adu_hossz <= 8 and mi_szan and szan_jellegu

    szlem_szan = _szan_szlem_jo(kez, ig_p, adu, adu_hossz)

    def cel(szint: int, indok: str) -> SpiralDontes:
        if szint == 6 and szlem_szan and _rang("6NT") > r_last and van_e("6NT"):
            return SpiralDontes("6NT", "kerdezo", indok + " — szanban (nem elosztásos "
                                "lapok, a szanban nincs lopásveszély)")
        if szint == 5 and szan_leallas and _rang("4NT") > r_last and van_e("4NT"):
            return SpiralDontes("4NT", "kerdezo",
                                indok + f" — leállás 4NT-ben (legfeljebb {adu_hossz} lapos "
                                "minor fit, a szan reális)")
        lic = f"{szint}{adu}"
        r = _rang(lic)
        if r > r_last and van_e(lic):
            return SpiralDontes(lic, "kerdezo", indok)
        if r == r_last:
            return SpiralDontes("P", "kerdezo", indok + " (a partner licitje épp ez)")
        if szint == 5:
            return cel(6, indok + "; az 5-ös szint már elmúlt")
        if van_e("6NT") and _rang("6NT") > r_last:
            return SpiralDontes("6NT", "kerdezo", indok + "; a 6-os adu már elmúlt")
        return SpiralDontes(f"7{adu}", "kerdezo", indok + "; a 6-os szint már elmúlt")

    lepcsok = _rele_lepcsok(utolso, adu, jatszhato)

    def rele(n: int, mit: str, hatar: int) -> SpiralDontes | None:
        """Az n. relé, ha a tagadó (L1) válasz a `hatar` rang alatt marad."""
        if len(lepcsok) < n:
            return None
        lic = lepcsok[n - 1]
        if _rang(lic) + 1 > hatar or not van_e(lic):
            return None
        nev = "relé" if n == 1 else "szuper-relé"
        return SpiralDontes(lic, "kerdezo", f"Spirál-{nev} (R{n}): kérdezi: {mit}")

    if hiany >= 2:
        return cel(5, f"Leállás: {hiany} kulcslap hiányzik")
    if hiany == 1:
        # szanban az adu dáma nem számít: egy hiányzó kulcslappal kis szlem
        # (a szerkesztő, 2026-10-25)
        if szlem_szan and dama_ok is not True:
            return cel(6, "Kis szlem szanban: 1 kulcslap hiányzik, az adu dáma szanban nem számít")
        if dama_ok is True:
            return cel(6, "Kis szlem: 1 kulcslap hiányzik, az adu dáma megvan")
        if dama_ok is False:
            return cel(5, "Leállás: 1 kulcslap és az adu dáma hiányzik")
        if pos == 0 and t_lista and t_lista[0] == ("Q", adu):
            d = rele(1, _tetel_nev(t_lista[0], adu), _rang(f"5{adu}"))
            if d is not None:
                return d
        becsles = _hcp(kez) + (ig_p.pont_min if ig_p is not None else 0)
        if becsles >= 31:
            return cel(6, "Kis szlem: 1 kulcslap hiányzik, az adu dáma kérdezése már túl magas (közös erő 31+)")
        return cel(5, "Leállás: 1 kulcslap hiányzik, az adu dáma ismeretlen")

    # minden kulcslap megvan: nagyszlem-kutatás
    sajat_siken = {sz for sz in _KULSO_RENDBEN if kez.hossz(sz) == 0}
    kell: list[int] = []
    for j, t in enumerate(t_lista):
        fig, sz = t
        if t == ("Q", adu):
            if dama_ok is not True:
                kell.append(j)
        elif fig == "K" and sz not in sajat_siken and sz not in sikenek_v \
                and not _van(kez, t, set()):
            kell.append(j)
    if dama_ok is False or any(j in hianyzik for j in kell):
        return cel(6, "Kis szlem: minden kulcslap megvan, de a nagyszlemhez hiányzik egy fontos lap")
    nyitott = [j for j in kell if j not in megvan]
    if not nyitott:
        return cel(7, "Nagyszlem: minden kulcslap, az adu dáma és a külső királyok megvannak")
    n_cel = min(nyitott)
    if n_cel < pos:
        return cel(6, "Kis szlem")
    lepes = 1 + max(0, _reteg(n_cel, retegek) - _reteg(min(pos, len(t_lista) - 1), retegek))
    d = rele(lepes, _tetel_nev(t_lista[retegek[_reteg(n_cel, retegek)]] if lepes > 1
                               else t_lista[pos], adu), _rang(f"6{adu}") - 1)
    if d is not None:
        return d
    return cel(6, "Kis szlem: minden kulcslap megvan, a további kérdés már túl magas")
