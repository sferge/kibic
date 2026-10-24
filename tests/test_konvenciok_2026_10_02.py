"""
2026-10-02: Timbuktu, Rubensohl, Junk Stayman, a törvény (LoTT), az alert
szövegének értelmezése, a magyarázatkérés, a feltételes felülírás és a
téma-foglalás csak használható sorokkal.
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


def _pbn(s):
    return [sz + e for sz, l in zip("SHDC", s.split(".")) for e in l]


@pytest.fixture(scope="module")
def gyujto():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    return betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])


@pytest.fixture(scope="module")
def betolto(gyujto):
    tar: dict = {}

    def bet(kod, par=None, teszt=None):
        if kod not in tar:
            tar[kod] = feloldas_forrasokbol(gyujto, kod)[0].sorok
        return tar[kod], Parametertar()
    return bet


def _licit(bet, pbn, menet, ules="E", ellen=None, csaladok=None, oszto="N"):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": oszto,
                          "vulnerability": "none", "auction": menet,
                          "system": "KIBIC_STAND", "opponent_system": ellen,
                          "families": csaladok or {}, "test_mode": True}, bet)


def _alert(v):
    return (v.get("alert") or {}).get("text") or ""


# --- Timbuktu ---------------------------------------------------------

def _licit_z(bet, pbn, menet, ules, ellen, csaladok, zona):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N",
                          "vulnerability": zona, "auction": menet,
                          "system": "KIBIC_STAND", "opponent_system": ellen,
                          "families": csaladok, "test_mode": True}, bet)


def test_timbuktu_eros_treff_ellen(betolto):
    # 5 vesztő, 5,5 játékütés: kontra (kevés játékütés)
    v = _licit(betolto, "AQJ32.KQ932.3.43", ["1C"], "E", "STRONG_CLUB", {"NS": "STRONG_CLUB"})
    assert v["call"] == "X" and "Timbuktu" in _alert(v)
    # több játékütéssel (6,25): 2♣
    v = _licit(betolto, "AKQ32.QJT92.3.43", ["1C"], "E", "STRONG_CLUB", {"NS": "STRONG_CLUB"})
    assert v["call"] == "2C" and "több játékütéssel" in _alert(v)


def test_timbuktu_vesztok_a_zona_szerint(betolto):
    # 6 vesztő: ők bellben (kedvező) igen, senki bellben nem
    kez, menet, cs = "KQJ32.QJ932.3.43", ["1C"], {"NS": "STRONG_CLUB"}
    assert _licit_z(betolto, kez, menet, "E", "STRONG_CLUB", cs, "ns")["call"] == "X"
    assert _licit_z(betolto, kez, menet, "E", "STRONG_CLUB", cs, "none")["call"] != "X"


def test_timbuktu_csak_ott_irja_felul_az_informativ_kontrat(betolto):
    # természetes 1♣ ellen az információs kontra él (a Timbuktu nem írta felül)
    v = _licit(betolto, "AK32.KJ32.Q432.2", ["1C"], "E", "NATURAL", {"NS": "NATURAL"})
    assert v["call"] == "X" and "Információs" in _alert(v)
    # erős treff ellen az információs kontra nem él (4-4 nemes: nem Timbuktu-kéz)
    v = _licit(betolto, "AK32.KJ32.Q432.2", ["1C"], "E", "STRONG_CLUB", {"NS": "STRONG_CLUB"})
    assert v["call"] != "X"


def test_timbuktu_negativ_1karo_utan(betolto):
    v = _licit_z(betolto, "2.32.AQJ432.K432", ["1C", "P", "1D"], "W",
                 "STRONG_CLUB", {"NS": "STRONG_CLUB"}, "ns")
    assert v["call"] == "1H" and "minor" in _alert(v)


def test_timbuktu_eros_2treff_ellen_igen_az_eros_treffesek_2treffje_ellen_nem(betolto):
    v = _licit(betolto, "AQJ32.KQ932.3.43", ["2C"], "E", "NATURAL", {"NS": "NATURAL"})
    assert v["call"] == "X"
    v = _licit(betolto, "AQJ32.KQ932.3.43", ["2C"], "E", "STRONG_CLUB", {"NS": "STRONG_CLUB"})
    assert "Timbuktu" not in _alert(v)


# --- Rubensohl (nem a KIBIC_STAND része: egy próbakártyán) -----------

@pytest.fixture(scope="module")
def rub_betolto(gyujto):
    from kibic.impex.rendszer_yaml import forras_dict
    g = dict(gyujto)
    forras_dict({"rendszer": {"kod": "PROBA_RUB", "fajta": "RENDSZER", "csalad": "NATURAL"},
                 "hivatkozasok": ["RUBENSOHL", "KIBIC_STAND"]}, "r.yaml", g)
    tar: dict = {}

    def bet(kod, par=None, teszt=None):
        if kod not in tar:
            tar[kod] = feloldas_forrasokbol(g, kod)[0].sorok
        return tar[kod], Parametertar()
    return bet


def _rub(bet, pbn, menet, ules="S"):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N",
                          "vulnerability": "none", "auction": menet,
                          "system": "PROBA_RUB", "test_mode": True}, bet)


@pytest.mark.parametrize("kez,hivas,szoveg", [
    ("KQ2.32.QJ8432.32", "3C", "káróra"),           # 2♥ alatti szín: erős küzdelmi
    ("KQJ32.A32.432.32", "3H", "pikkre"),           # 2♥ fölötti szín: invit+
    ("K432.32.AQ32.K32", "3D", "felüllicit"),       # transzfer az ő színükre: 4 pikk GF
])
def test_rubensohl(rub_betolto, kez, hivas, szoveg):
    v = _rub(rub_betolto, kez, ["1NT", "2H"])
    assert v["call"] == hivas and szoveg in _alert(v)


def test_rubensohl_transzfer_kozbeszolas_utan(rub_betolto):
    # 1NT (2♦ = transzfer kőrre, az alert szerint) 3♣ = 4 pikk, gémforsz
    v = _rub(rub_betolto, "K432.32.AQ32.K32",
             ["1NT", {"seat": "E", "call": "2D", "alert": "transzfer: 5+ kőr"}])
    assert v["call"] == "3C" and "4 pikk" in _alert(v)


def test_rubensohl_capelletti_utan(rub_betolto):
    # 1NT (2♦ = mindkét nemes) X: legalább invit, jó káró (büntetésre is)
    menet = ["1NT", {"seat": "E", "call": "2D", "alert": "Capelletti: mindkét nemes"}]
    v = _rub(rub_betolto, "K32.32.AQJ93.K32", menet)
    assert v["call"] == "X"
    # ... X (P) P (2♥): 6+ káróval gémforsz 3♦
    v = _rub(rub_betolto, "K2.32.AQJ932.K32", menet + ["X", "P", "P", "2H"])
    assert v["call"] == "3D"


def test_a_kibic_stand_lebensohlt_jatszik(betolto):
    v = _licit(betolto, "KQ2.32.QJ8432.32", ["1NT", "2H"], "S")
    assert "Rubensohl" not in _alert(v)


# --- Junk Stayman -----------------------------------------------------

def test_junk_stayman_gyengevel(betolto):
    v = _licit(betolto, "J432.Q432.432.32", ["1NT", "P"], "S")
    assert v["call"] == "2C" and "Junk" in _alert(v)
    v = _licit(betolto, "J8432.Q9432.32.2", ["1NT", "P", "2C", "P", "2D", "P"], "S")
    assert v["call"] == "2H"


def test_junk_stayman_5_4_invit_fogadas(betolto):
    v = _licit(betolto, "KQ2.AQ2.K32.Q432", ["1NT", "P", "2C", "P", "2D", "P", "2S", "P"], "N")
    assert v["call"] == "3H"


# --- a törvény --------------------------------------------------------

def _moha(bet, pbn, menet, ules):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N",
                          "vulnerability": "none", "auction": menet,
                          "system": "MOHA_STAND", "test_mode": True}, bet)


def test_lott_9_lapos_fittel_harmas_szint(betolto):
    v = _moha(betolto, "A2.KQJ932.K32.32", ["1H", "1S", "2H", "2S"], "N")
    assert v["call"] == "3H" and v["source"] == "ELV"
    # a válaszolóra is: 1♥-2♥-P-P-X után 4 lappal 3♥
    v = _moha(betolto, "K32.Q932.J432.32", ["1H", "P", "2H", "P", "P", "X"], "S")
    assert v["call"] == "3H"
    # a KIBIC_STAND-on nincs törvény (a 3♥ ott a „küzdelmi” elvből jöhet,
    # amely a zavartalan menet óta él — 2026-10-24)
    v = _licit(betolto, "A2.KQJ932.K32.32", ["1H", "1S", "2H", "2S"], "N")
    assert "törvény" not in (v.get("explanation") or "")


def test_lott_8_lapos_fittel_nem_megyunk_a_harmas_szintre(betolto):
    v = _moha(betolto, "Q32.K43.Q432.432", ["1H", "1S", "2H", "2S", "P", "P"], "S")
    assert v["call"] == "P"


# --- alert, magyarázatkérés -------------------------------------------

def test_alert_ertelmezes():
    from kibic.motor.alert_ertelmezes import alert_igeret
    ig = alert_igeret("11-15, 5+ kőr", "1H")
    assert (ig.pont_min, ig.pont_max, ig.hossz_min) == (11, 15, {"H": 5})
    assert alert_igeret("Erős treff, 16+", "1C").pont_min == 16
    ig = alert_igeret("Timbuktu: káró, vagy mindkét nemes", "X")
    assert ig is None                                  # vagylagos: semmi biztos
    assert alert_igeret("Natural, 5-4 in the majors", "2H").hossz_min == {"H": 4}
    assert alert_igeret("12-14 balanced", "1NT").hossz_max["S"] == 5
    assert alert_igeret("", "1C") is None


def test_az_alert_elobb_jon_mint_a_mi_rendszerunk(betolto):
    # a mi rendszerünkben a 2♦ gyenge kettes; az ellenfél elmondta: Multi
    v = _licit(betolto, "A32.K32.Q32.J432",
               [{"seat": "W", "call": "2D", "alert": "Multi: gyenge kettes kőrben vagy pikkben, 5-10"}],
               "N", oszto="W")
    m = v["auction_understanding"][0]
    assert m["source"] == "alert" and v["constraints"]["W"]["points"] == [5, 10]
    assert "W:2D" in v["coverage"]["from_alert"]


def test_magyarazatkeres_alertalt_szoveg_nelkul(betolto):
    v = _licit(betolto, "A32.K32.Q32.J432",
               [{"seat": "W", "call": "2D", "alert": True}], "N", oszto="W")
    assert v["explain_requests"] == [{"index": 0, "seat": "W", "call": "2D",
                                      "reason": "alerted_without_explanation"}]


def test_szabalyos_hivasok():
    from kibic.szolgaltatas.licit import szabalyos_hivasok
    menet = [{"ules": "N", "licit": "1H"}, {"ules": "E", "licit": "1S"},
             {"ules": "S", "licit": "2H"}, {"ules": "W", "licit": "2S"}]
    h = szabalyos_hivasok(menet, "N")
    assert "2H" not in h and "3H" in h and "X" in h and "XX" not in h


# --- feloldás ---------------------------------------------------------

def _forras(dok, g):
    from kibic.impex.rendszer_yaml import forras_dict
    forras_dict(dok, "t.yaml", g)


def test_temat_csak_hasznalhato_sorokkal_lehet_elfoglalni():
    pytest.importorskip("yaml")
    g: dict = {}
    _forras({"rendszer": {"kod": "UJ", "fajta": "KONVENCIO", "tema": "T"},
             "fejezetek": [{"fejezet": "x", "szabalyok": [
                 {"minta": "1NT-2C", "pont": "0+", "prioritas": 50}]}]}, g)
    _forras({"rendszer": {"kod": "REGI", "fajta": "KONVENCIO", "tema": "T"},
             "fejezetek": [{"fejezet": "x", "szabalyok": [
                 {"minta": "1NT-2C", "pont": "8+", "prioritas": 50, "allapot": "ELFOGADOTT"}]}]}, g)
    _forras({"rendszer": {"kod": "KARTYA_T", "fajta": "RENDSZER", "csalad": "NATURAL"},
             "hivatkozasok": ["UJ", "REGI"]}, g)
    teszt = feloldas_forrasokbol(g, "KARTYA_T")[0]
    assert {s.rendszer_kod for s in teszt.sorok} == {"UJ"}
    eles = feloldas_forrasokbol(g, "KARTYA_T", csak_elfogadott=True)[0]
    assert {s.rendszer_kod for s in eles.sorok} == {"REGI"}


def test_felteteles_felulirasnal_az_alap_megmarad():
    pytest.importorskip("yaml")
    g: dict = {}
    _forras({"rendszer": {"kod": "VED", "fajta": "KONVENCIO"},
             "fejezetek": [{"fejezet": "x", "szabalyok": [
                 {"minta": "(1C) X", "ha": {"ellenfel_pont": "16+"}, "pont": "0+",
                  "prioritas": 70}]}]}, g)
    _forras({"rendszer": {"kod": "TERM", "fajta": "KONVENCIO"},
             "fejezetek": [{"fejezet": "x", "szabalyok": [
                 {"minta": "(1C) X", "pont": "12+", "prioritas": 60}]}]}, g)
    _forras({"rendszer": {"kod": "KARTYA_T", "fajta": "RENDSZER", "csalad": "NATURAL"},
             "hivatkozasok": ["VED", "TERM"]}, g)
    f = feloldas_forrasokbol(g, "KARTYA_T")[0]
    sorok = {s.rendszer_kod: s for s in f.sorok}
    assert set(sorok) == {"VED", "TERM"}
    assert sorok["TERM"].elnyomo and f.felteteles_felulirasok


# --- 1-re 1, riverz, a válaszoló újralicitje, splinter-elv, alert 3NT fölött

def test_gemerovel_nem_passzolunk_1re1_utan(betolto):
    # a tesztparti: 1♣-1♦ (12 FP, 5 káró) - 1♥: nem passz
    v = _licit(betolto, "Q32.32.AQ954.KJ2", ["1C", "P", "1D", "P", "1H", "P"], "S")
    assert v["call"] == "3NT"
    # 6 ponttal sem passz (1-re 1 kényszerít)
    v = _licit(betolto, "432.Q2.J9543.K32", ["1C", "P", "1D", "P", "1H", "P"], "S")
    assert v["call"] not in ("P", None)


def test_riverz_18_plusszal(betolto):
    v = _licit(betolto, "AK2.AQ32.4.KQ932", ["1C", "P", "1D", "P"], "N")
    assert v["call"] == "2H" and "Riverz" in _alert(v)


def test_splinter_elv_es_nincs_alert_3nt_folott(betolto):
    v = _licit(betolto, "A2.KQ32.4.AKQ932", ["1C", "P", "1H", "P"], "N")
    assert v["call"] == "4D" and v.get("alert") is None
    v = _licit(betolto, "2.KQ32.A4.AKQ932", ["1C", "P", "1H", "P"], "N")
    assert v["call"] == "3S" and "Splinter" in _alert(v)


def test_junk_stayman_3m_nem_fogadja(betolto):
    v = _licit(betolto, "K2.Q32.AQJ32.K32",
               ["1NT", "P", "2C", "P", "2D", "P", "2S", "P"], "N")
    assert v["call"] == "3D"


# --- délután: negyedik szín, gémesély, Walsh egyenetlen, Junk 3♥ ---------

def test_negyedik_szin_elv(betolto):
    # a negyedik szín kvázi gémforsz (2026-10-23): gémforsz-erő kell hozzá
    v = _licit(betolto, "K2.AQ932.Q32.A32", ["1D", "P", "1H", "P", "1S", "P"], "S")
    assert v["call"] == "2C" and "Negyedik szín" in _alert(v)
    # lapleírás: fogás a negyedik színben -> szan; a negyedik szín kvázi
    # gémforsz (2026-10-23): minimummal 3NT (gyors), plusz erővel 2NT (lassú)
    v = _licit(betolto, "AQ32.32.KJ432.A2",
               ["1D", "P", "1H", "P", "1S", "P", "2C", "P"], "N")
    assert v["call"] == "3NT"
    v = _licit(betolto, "AQ32.32.KQJ43.AQ",
               ["1D", "P", "1H", "P", "1S", "P", "2C", "P"], "N")
    assert v["call"] == "2NT"


def test_gemesely():
    from kibic.motor.helyzet import Igeret
    from kibic.motor.kifejezes import gemesely
    from kibic.szolgaltatas.licit import _kez

    def ig(lo, hi, **hossz):
        i = Igeret(nyilatkozott=True)
        i.szukit_pont(lo, hi)
        i.hossz_min.update(hossz)
        return i
    egyenletes = _kez(_pbn("K32.Q32.K432.Q32"))           # 10 FP, 4-3-3-3
    assert gemesely(egyenletes, ig(12, 14)) is True        # 10+14: 24, 10-14 eloszlás
    assert gemesely(egyenletes, ig(12, 13)) is False       # 23
    gyenge = _kez(_pbn("432.432.J432.432"))                # 1 FP
    assert gemesely(gyenge, ig(20, 21)) is False           # 22, és egyenetlen
    fit = _kez(_pbn("K432.KQ32.32.432"))                   # 8 FP, 4 kőr
    assert gemesely(fit, ig(16, 18, H=4)) is True          # nemes fit: 25
    minor = _kez(_pbn("32.Q32.K432.Q432"))                 # 7 FP, 4 treff
    assert gemesely(minor, ig(16, 18, C=4)) is False       # minor fittel 27 kell; szanban 18-7 hosszú szín nélkül kevés


def test_walsh_1m_csak_nagyon_egyenetlen_lappal(betolto):
    v = _licit(betolto, "A432.KJ32.32.A42", ["1C", "P", "1D", "P"], "N")
    assert v["call"] == "1NT"


def test_junk_2pikk_utan_3kor_termeszetes(betolto):
    v = _licit(betolto, "Q432.KQJ32.43.32", ["1NT", "P", "2C", "P", "2S", "P"], "S")
    assert v["call"] == "3H" and v.get("alert") is None


# --- este: pozitív szabad licit, negatív kontra „minden más”, következtetés --

@pytest.fixture(scope="module")
def param_betolto(gyujto):
    """Mint a betolto, de a rendszer YAML-paramétereivel (SZABAD_LICIT_MIN)."""
    tar: dict = {}

    def bet(kod, par=None, teszt=None):
        if kod not in tar:
            tar[kod] = feloldas_forrasokbol(gyujto, kod)[0].sorok
        p = {k: (float(v) if str(v).isdigit() else v)
             for k, v in gyujto[kod].parameterek.items()}
        return tar[kod], Parametertar(rendszer_ertek=p)
    return bet


def _rsz(bet, pbn, menet, ules, rendszer, **extra):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes(dict({"hand": _pbn(pbn), "seat": ules, "dealer": "N",
                               "vulnerability": "none", "auction": menet,
                               "system": rendszer, "test_mode": True}, **extra), bet)


def test_pozitiv_szabad_licit_parameterrel(param_betolto):
    # 10 FP, 5 káró: a KIBIC_STAND-on (10) szabad licit, a MOHA_STAND-on (11) kontra
    assert _rsz(param_betolto, "K32.32.KQ932.Q32", ["1H", "2C"], "S", "KIBIC_STAND")["call"] == "2D"
    v = _rsz(param_betolto, "K32.32.KQ932.Q32", ["1H", "2C"], "S", "MOHA_STAND")
    assert v["call"] == "X"
    assert _rsz(param_betolto, "K32.32.AQ932.Q32", ["1H", "2C"], "S", "MOHA_STAND")["call"] == "2D"


def test_negativ_kontra_minden_mas(param_betolto):
    # 12 FP, nincs 4 pikk, nincs ötös szín: kontra (invit erővel nem passzolunk)
    assert _rsz(param_betolto, "K32.32.KJ32.AJ32", ["1H", "2C"], "S", "KIBIC_STAND")["call"] == "X"


def test_kizarasos_kovetkeztetes(param_betolto):
    # a partner passzolta az 1♥-et: valószínűleg nincs válaszereje
    v = _rsz(param_betolto, "AQ432.AKJ32.32.2", ["1H", "P", "P", "2C"], "N", "KIBIC_STAND",
             inference_ms=5000)
    assert v["inferred"]["S"]["points"][1] <= 6
    assert "amit nem licitált" in v["auction_understanding"][2]["inferred"]
    # a partner negatív kontrája: nem volt kőr fitje (különben emel)
    v = _rsz(param_betolto, "AQ432.AKJ32.32.2", ["1H", "2C", "X", "P"], "N", "MOHA_STAND",
             inference_ms=5000)
    assert v["inferred"]["S"]["suits"]["H"][1] <= 2
    # kikapcsolva nincs
    v = _rsz(param_betolto, "AQ432.AKJ32.32.2", ["1H", "P", "P", "2C"], "N", "KIBIC_STAND",
             inference=False)
    assert v["inferred"] == {}


# --- 21:29: a nyitó a negatív kontra után, gyenge ugró licitek ------------

def test_nyito_a_negativ_kontra_utan(betolto):
    menet = ["1H", "2C", "X", "P"]
    # 4 pikk: a kontra ígéretét teljesítjük
    assert _licit(betolto, "AJ32.AKJ32.32.32", menet, "N")["call"] == "2S"
    # 6 jó kőr: a színem
    assert _licit(betolto, "32.AKQJ32.K2.432", menet, "N")["call"] == "2H"
    # új szín (4 káró), pikk nélkül
    assert _licit(betolto, "K3.AKJ32.KQJ2.32", menet, "N")["call"] == "2D"
    # kínunkban: nincs más, a színünket ismételjük
    assert _licit(betolto, "Q3.AKJ32.K32.432", menet, "N")["call"] == "2H"
    # erős treff-tartás: 3NT, de a büntető passz mérlegelendő jelölt
    v = _licit(betolto, "K3.AKJ32.32.KQJ9", menet, "N")
    assert v["call"] in ("3NT", "P")
    merlegelendo = {j.get("call") for j in v.get("to_deliberate") or []}
    assert "P" in merlegelendo or v["call"] == "P"


def test_gyenge_ugro_valasz_minor_utan(betolto):
    v = _licit(betolto, "32.KJ9832.32.432", ["1C", "P"], "S")
    assert v["call"] == "2H" and "Gyenge ugró" in _alert(v)
    v = _licit(betolto, "QJ9832.32.432.32", ["1D", "P"], "S")
    assert v["call"] == "2S"
    # a nyitó: 2NT kérdés dubló támogatással és erővel, gyengébbel passz
    v = _licit(betolto, "AK2.Q3.KJ32.AJ32", ["1C", "P", "2H", "P"], "N")
    assert v["call"] == "2NT"
    assert _licit(betolto, "AK2.32.KJ32.AJ32", ["1C", "P", "2H", "P"], "N")["call"] == "P"
    # a válaszoló: minimummal a színe, maximummal mellékszín (alulról)
    m = ["1C", "P", "2H", "P", "2NT", "P"]
    assert _licit(betolto, "32.KJ9832.32.432", m, "S")["call"] == "3H"
    assert _licit(betolto, "32.KJT832.K2.432", m, "S")["call"] == "3D"


def test_valasz_a_gyenge_ugro_kozbeszolasra(betolto):
    # felüllicit: kényszerítő emelés
    v = _licit(betolto, "A32.K32.A432.K32", ["1C", "2H", "P"], "W")
    assert v["call"] == "3C" and "Felüllicit" in _alert(v)
    # 2NT: kérdés jó lappal, támogatás nélkül
    v = _licit(betolto, "A2.Q32.AJ32.K432", ["1D", "2S", "P"], "W")
    assert v["call"] == "2NT" and "Kérdez" in _alert(v)
    # gyenge lap: passz
    assert _licit(betolto, "32.32.A432.K5432", ["1C", "2H", "P"], "W")["call"] == "P"
    # a közbeszóló: minimum = a színe, maximum = ász/király mellékszín
    m = ["1C", "2H", "P", "2NT", "P"]
    assert _licit(betolto, "32.QJ9832.K32.32", m, "E")["call"] == "3H"
    assert _licit(betolto, "32.KJ9832.A2.432", m, "E")["call"] == "3D"


# --- este: a gyenge ugrás ELV (nem konkrét helyzet) ------------------------

def test_gyenge_ugras_elv_szabad_licit_helyzetben(betolto):
    # 1♦ (1♠): a 2♥ (szabad licit) definiált, a 3♥ ugrás — gyenge
    v = _licit(betolto, "32.KJ9832.32.432", ["1D", "1S"], "S")
    assert v["call"] == "3H" and v["source"] == "ELV" and "Gyenge ugrás" in _alert(v)
    # a közbeszóló partnere: (1♣) 1♦ (P) — az 1♥ helyett 2♥
    v = _licit(betolto, "32.KJ9832.32.432", ["1C", "1D", "P"], "W")
    assert v["call"] == "2H" and v["source"] == "ELV"
    # 1♠ (2♣) 3♥
    assert _licit(betolto, "432.KJ9832.32.32", ["1S", "2C"], "S")["call"] == "3H"


def test_gyenge_ugras_megertese_nem_ero(betolto):
    # a partner ugrása: gyenge, és kevesebb, mint az alacsonyabb licit minimuma
    v = _licit(betolto, "A2.AKJ32.K32.432", ["1D", "1S", "3H", "P"], "N")
    s = v["constraints"]["S"]
    assert s["forcing"] == "KIZARO" and s["points"][1] < 10 and s["suits"]["H"][0] >= 6


def test_gyenge_ugras_helyzet():
    from kibic.motor.helyzet import Allas, kiertekel
    def allas(menet, ules, oszto="N"):
        sorrend = "NESW"
        i = sorrend.index(oszto)
        return Allas(ules=ules, oszto=oszto,
                     licitek=[{"ules": sorrend[(i + k) % 4], "licit": l}
                              for k, l in enumerate(menet)])
    minden = lambda h: h in ("1H", "2H")        # noqa: E731  (2H/1H definiált)
    a = allas(["1C", "P"], "S")
    n1, n2 = {"t": "GYENGE_UGRAS", "lepes": 1}, {"t": "GYENGE_UGRAS", "lepes": 2}
    assert kiertekel(n1, a, {"_licit": "2H", "_definialt": lambda h: h == "1H"}) is True
    assert kiertekel(n2, a, {"_licit": "3H", "_definialt": lambda h: h == "1H"}) is True
    # ha maga az ugrás konkrétan definiált, annak a jelentése él
    assert kiertekel(n1, a, {"_licit": "2H", "_definialt": minden}) is False
    # a partner színe nem új szín
    assert kiertekel(n1, a, {"_licit": "3C", "_definialt": lambda h: h == "2C"}) is False
    # aki már licitált (a nyitó újralicitje), annak az ugrása nem ez
    b = allas(["1C", "P", "1H", "P"], "N")
    assert kiertekel(n1, b, {"_licit": "2S", "_definialt": lambda h: h == "1S"}) is False
    # szabálykészlet nélkül nem eldönthető
    assert kiertekel(n1, a, {"_licit": "2H"}) is None


def test_eros_ugras_masodik_megszolalaskent():
    from kibic.motor.helyzet import Allas, kiertekel
    def allas(menet, ules):
        return Allas(ules=ules, oszto="N",
                     licitek=[{"ules": "NESW"[k % 4], "licit": l} for k, l in enumerate(menet)])
    n = {"t": "EROS_UGRAS"}
    nincs = lambda h: False                     # noqa: E731
    # a nyitó ugrása új színben: erő
    a = allas(["1C", "P", "1H", "P"], "N")
    assert kiertekel(n, a, {"_licit": "2S", "_definialt": nincs}) is True
    assert kiertekel({"t": "EN_NYITOTTAM"}, a, {}) is True
    # ha konkrétan definiált (pl. riverz), annak a jelentése él
    assert kiertekel(n, a, {"_licit": "2S", "_definialt": lambda h: h == "2S"}) is False
    # első megszólalásként nem ez (az a gyenge ugrás)
    b = allas(["1C", "P"], "S")
    assert kiertekel(n, b, {"_licit": "2H", "_definialt": nincs}) is False
    assert kiertekel({"t": "EN_NYITOTTAM"}, b, {}) is False
    # aki korábban limitálta a lapját, annak az ugrása nem ígér 15+-t
    c = allas(["1S", "P", "1NT", "P", "2C", "P"], "S")
    c.kenyszertar["S"].szukit_pont(maximum=12)
    assert kiertekel(n, c, {"_licit": "3H", "_definialt": nincs}) is False
