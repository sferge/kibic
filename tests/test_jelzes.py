"""Jelzésrendszerek: minta, lapválasztó, sorok, feloldás, kártya, import, néző."""
import json
from pathlib import Path

import pytest

from kibic.impex.rendszer_yaml import ForrasHiba, betolt, forras_dict
from kibic.motor.jelzes import (JelzesHiba, Minta, _valaszt, feloldas, jelzesek, lapok,
                                profil_kod, rendszer_dictbol, rendszerek_betolt,
                                sor_szoveg, szep)
from kibic.motor.kartya import jelzesek_db, kartya_html, kartya_yamlbol

GYOKER = Path(__file__).resolve().parents[1]
JELZESEK = GYOKER / "rendszerek" / "jelzesek"


# --- Minta és lapválasztó ----------------------------------------------

@pytest.mark.parametrize("minta,lapsor,illik", [
    ("AK+", "AK", True), ("AK+", "AKQ3", True), ("AK+", "AQ3", False),
    ("KQx", "KQ7", True), ("KQx", "KQ76", False), ("KQx", "KQJ", False),
    ("Kxx", "KJ5", False),            # a J nem kis lap
    ("Kxx", "KT5", True),             # a 10 igen
    ("KJT(x)", "KJT", True), ("KJT(x)", "KJT4", True), ("KJT(x)", "KJT42", False),
    ("xxx+", "8642", True), ("xxx+", "Q642", False), ("*", "Q", True),
])
def test_minta(minta, lapsor, illik):
    assert Minta.parse(minta).illik(lapok(lapsor)) is illik


def test_minta_hibak():
    for rossz in ("KA", "xK", "AK*", "KZ"):
        with pytest.raises(JelzesHiba):
            Minta.parse(rossz)


def test_magyar_lapjelek():
    assert lapok("ÁKD10") == ["A", "K", "Q", "T"]
    assert lapok("B 9 2") == ["J", "9", "2"]
    assert [szep(c) for c in lapok("AQJT")] == ["Á", "D", "B", "10"]


def _r(kod, sorok, **tobbi):
    meta = {"kod": kod, "nev": kod, "fajta": tobbi.pop("fajta", "ALAPRENDSZER"),
            "alap_allapot": tobbi.pop("alap_allapot", "ELFOGADOTT")}
    return rendszer_dictbol({"jelzesrendszer": meta, "sorok": sorok, **tobbi}, "teszt")


def _j(*rendszerek, kod=None, szint="KARTYA"):
    rr = {r.kod: r for r in rendszerek}
    return jelzesek(kod or rendszerek[0].kod, rr, szint)


def test_lapvalasztok():
    j = _j(_r("PROBA", [
        {"felvetel": "SZIN", "hossz": "3+", "lap": "PARATLAN_PAROS(LEGKISEBB;FELULROL(3))"},
        {"felvetel": "SZAN", "hossz": "4+", "legalabb": "T", "lap": "FELULROL(4)"},
        {"felvetel": "SZAN", "lap": "LEGNAGYOBB_NELKULOZHETO"},
        {"felvetel": "SZIN", "minta": ["AK+", "KQ+", "AQJ+", "KT9+"], "lap": "SOROZAT_TETEJE"},
    ]))
    assert j.indito_lap("K872", "SZIN")[0] == "7"       # párosból a harmadik
    assert j.indito_lap("K8752", "SZIN")[0] == "2"      # páratlanból a legkisebb
    assert j.indito_lap("K872", "SZAN")[0] == "2"       # 4. a tízesnél nagyobb lappal
    assert j.indito_lap("97542", "SZAN")[0] == "9"      # nincs 10: legnagyobb nélkülözhető
    # menet közben ugyanez a választó a finomabb definíció: a magában álló 9 fontos
    assert _valaszt("LEGNAGYOBB_NELKULOZHETO", lapok("97542"), helyzet="HIVAS") == "7"
    assert _valaszt("LEGNAGYOBB_KISLAP", lapok("T82")) == "T"
    assert j.indito_lap("AQJ4", "SZIN")[0] == "Q"       # belső sorozat teteje
    assert j.indito_lap("KT93", "SZIN")[0] == "T"
    assert j.indito_lap("AKQ3", "SZIN")[0] == "A"


def test_hibas_sorok():
    for rossz in ({"minta": "KQx", "lap": "A"}, {"minta": "KQx", "lap": "nincs ilyen"},
                  {"lap": "PARATLAN_PAROS(HARMADIK_OTODIK;LEGKISEBB)"},
                  {"technika": "TT1", "esetek": [{"lap": "K"}]},           # konkrét lap: minta kell
                  {"technika": "TECH", "esetek": [{"lap": "LEGKISEBB", "pont": 3}]},
                  {"modszer": "ATTITUD"},
                  {"minta": "Kxx", "lap": "SOROZAT_TETEJE"}, {"racs": "VALAMI", "jel": "KERES"},
                  {"racs": "DOBAS", "jel": "ROMAI"}, {"elv": "E1"}, {"valami": 1}):
        with pytest.raises(JelzesHiba):
            _r("ROSSZ", [rossz])
    with pytest.raises(JelzesHiba):                    # kétszer ugyanaz a kulcs
        _r("ROSSZ", [{"modszer": "KERES", "ertek": "KICSI"},
                     {"modszer": "KERES", "ertek": "NAGY"}])


def test_legkonkretabb_nyer():
    j = _j(_r("PP", [{"felvetel": "SZAN", "lap": "LEGKISEBB"},
                    {"felvetel": "SZAN", "hossz": "4+", "legalabb": "T", "lap": "FELULROL(4)"},
                    {"felvetel": "SZAN", "minta": "KQ+", "lap": "K"}]))
    assert j.indito_lap("KQ72", "SZAN")[0] == "K"
    assert j.indito_lap("K872", "SZAN")[0] == "2"
    assert j.indito_lap("972", "SZAN")[0] == "2"
    jel = j.jeloltek("KQ72", "SZAN")
    assert [s.konkretsag for s in jel] == sorted((s.konkretsag for s in jel), reverse=True)


# --- Feloldás: hivatkozás, felülírás, törlés, kizárás -------------------------

def _alap():
    return _r("ALAP", [], fejezetek=[
        {"fejezet": "Indítás", "sorok": [
            {"felvetel": "SZIN", "minta": "AK+", "lap": "A"},
            {"felvetel": "SZAN", "minta": "KQ+", "lap": "K"},
            {"felvetel": "SZAN", "lap": "LEGKISEBB"}]},
        {"fejezet": "Rács", "sorok": [
            {"racs": "DOBAS", "felvetel": "*", "jel": "PREF"},
            {"racs": "FELVEVO_HIV", "felvetel": "SZAN", "jel": "SMITH"}]},
        {"fejezet": "Módszerek", "sorok": [
            {"modszer": "KERES", "ertek": "KICSI"},
            {"modszer": "LAPSZAM_ALAP", "ertek": "MARADEK"}]},
        {"fejezet": "Elvek", "sorok": [
            {"elv": "E1", "szoveg": "régi elv"}, {"elv": "E2", "szoveg": "marad"}]},
        {"fejezet": "Különleges", "sorok": [
            {"kulonleges": "SMITH", "szoveg": "régi Smith"}]},
    ])


def test_raepules():
    uj = _r("UJ", [
        {"felvetel": "SZIN", "minta": "AK+", "lap": "K"},                  # felülír
        {"racs": "FELVEVO_HIV", "felvetel": "SZAN", "jel": "SMITH",
         "mikor": "első hívás", "kulonben": "LAPSZAM"},                        # felülír
        {"modszer": "KERES", "ertek": "NAGY"},
        {"torol": "MODSZER/LAPSZAM_ALAP"}, {"torol": "ELV/E1"},
        {"kulonleges": "SMITH", "szoveg": "új Smith"}],
        fajta="RENDSZER", hivatkozasok=["ALAP"])
    j = _j(uj, _alap())
    assert j.lanc == ["UJ", "ALAP"]
    assert j.indito_lap("AK3", "SZIN")[0] == "K"
    assert j.indito_lap("KQ72", "SZAN")[0] == "K"                         # öröklve
    assert j.modszer == {"KERES": "NAGY"}
    assert j.racs["DOBAS"]["SZIN"][0]["jel"] == "PREF"                    # öröklve
    smith = j.racs["FELVEVO_HIV"]["SZAN"][0]
    assert smith["mikor"] == "első hívás" and smith["kulonben"] == "LAPSZAM"
    assert [t["szoveg"] for t in j.elvek] == ["marad"]
    assert [t["szoveg"] for t in j.kulonleges] == ["új Smith"]
    f = j.feloldas
    assert ("INDITAS/SZIN/AK+", "UJ", "ALAP") in f.felulirt
    assert ("ELV/E1", "UJ", "ALAP") in f.torolt


def test_fejezet_kizarasa():
    uj = _r("UJ", [{"felvetel": "SZAN", "lap": "LEGNAGYOBB"}], fajta="RENDSZER",
            hivatkozasok=["ALAP"], kizarasok=[{"kod": "ALAP", "fejezet": "Indítás"}])
    j = _j(uj, _alap())
    assert j.indito_lap("KQ72", "SZAN")[0] == "K"   # a saját sor: legnagyobb
    assert j.indito_lap("AK3", "SZIN") == (None, None)
    assert ("ALAP", "Indítás", "UJ") in j.feloldas.kizart
    assert j.racs["DOBAS"]                            # a többi fejezet megmaradt


def test_allapot_szintek():
    r = _r("PP", [{"felvetel": "SZAN", "lap": "LEGKISEBB"},
                 {"felvetel": "SZAN", "minta": "KQ+", "lap": "K", "allapot": "JAVASOLT"},
                 {"felvetel": "SZAN", "minta": "AK+", "lap": "A", "allapot": "JEGELT"}])
    assert _j(r, szint="ELES").indito_lap("KQ72", "SZAN")[0] == "2"
    assert _j(r, szint="TESZT").indito_lap("KQ72", "SZAN")[0] == "K"
    assert _j(r, szint="KARTYA").indito_lap("AK72", "SZAN")[0] == "2"   # a jegelt soha


def test_javasolt_felulirasa_elesben_nem_er():
    alap = _r("ALAP", [{"felvetel": "SZAN", "lap": "LEGKISEBB"}])
    uj = _r("UJ", [{"felvetel": "SZAN", "lap": "LEGNAGYOBB", "allapot": "JAVASOLT"}],
            fajta="RENDSZER", hivatkozasok=["ALAP"])
    assert _j(uj, alap, szint="ELES").indito_lap("972", "SZAN")[0] == "2"
    assert _j(uj, alap, szint="TESZT").indito_lap("972", "SZAN")[0] == "9"


def test_hianyzo_es_korkoros():
    uj = _r("UJ", [], fajta="RENDSZER", hivatkozasok=["NINCS"])
    assert _j(uj).hianyzo == ["NINCS"]
    # mint a licitnél: a körkörös hivatkozás nem hiba, csak kimarad (és látszik)
    a = _r("AA", [], hivatkozasok=["BB"])
    b = _r("BB", [], hivatkozasok=["AA"])
    f = feloldas("AA", {"AA": a, "BB": b})
    assert f.lanc == [("AA", 0), ("BB", 1)] and f.korkoros == ["AA -> BB -> AA"]


def test_szelessegi_bejaras_mint_a_licitnel():
    """A -> [B, C], B -> D: a C (1. szint) kulcsa nyer a D-é (2. szint) előtt,
    pedig mélységi bejárásban a D előbb jönne."""
    d = _r("DD", [{"modszer": "KERES", "ertek": "NAGY"}])
    c = _r("CC", [{"modszer": "KERES", "ertek": "KICSI"}])
    b = _r("BB", [], hivatkozasok=["DD"])
    a = _r("AA", [], fajta="RENDSZER", hivatkozasok=["BB", "CC"])
    j = _j(a, b, c, d)
    assert j.lanc == ["AA", "BB", "CC", "DD"]
    assert j.modszer == {"KERES": "KICSI"}
    assert ("MODSZER/KERES", "CC", "DD") in j.feloldas.felulirt


def test_kizaras_csak_a_kizaro_alatt_hat():
    """A -> [B, C]; B kizárja D-t, C is hivatkozik D-re: a D a C úton belép."""
    d = _r("DD", [{"modszer": "KERES", "ertek": "NAGY"}])
    b = _r("BB", [], hivatkozasok=["DD"], kizarasok=["DD"])
    c = _r("CC", [], hivatkozasok=["DD"])
    a = _r("AA", [], fajta="RENDSZER", hivatkozasok=["BB", "CC"])
    j = _j(a, b, c, d)
    assert ("DD", None, "BB") in j.feloldas.kizart
    assert j.modszer == {"KERES": "NAGY"} and "DD" in j.lanc
    # a semmire nem ható kizárás figyelmeztetés
    e = _r("EE", [], fajta="RENDSZER", hivatkozasok=["CC"], kizarasok=["BB"])
    assert _j(e, c, d).feloldas.hatastalan_kizarasok == [("EE", "BB", None)]


def test_fajta_es_terulet():
    r = _alap()
    t = {s.kulcs: (s.fajta, s.terulet) for s in r.sorok}
    assert t["INDITAS/SZIN/AK+"] == ("SZABALY", "INDITAS")
    assert t["RACS/DOBAS/SZIN/1"] == ("SZABALY", "JELZES")
    assert t["MODSZER/KERES"] == ("SZABALY", "MODSZER")
    assert t["ELV/E1"] == ("ELV", None)
    assert t["KULONLEGES/SMITH"] == ("SZABALY", "KULONLEGES")
    k = _r("KK", [{"helyzet": "HIVAS", "lap": "LEGKISEBB"},
                  {"elv": "E1", "terulet": "INDITAS", "szoveg": "x"}])
    assert [(s.fajta, s.terulet) for s in k.sorok] == [("SZABALY", "HIVAS"), ("ELV", "INDITAS")]
    with pytest.raises(JelzesHiba):
        _r("KK", [{"elv": "E1", "terulet": "VALAMI", "szoveg": "x"}])


def test_kihagyas_es_regi_nev():
    uj = _r("UJ", [{"kihagy": "ELV/E1"}, {"torol": "ELV/E2"}],
            fajta="RENDSZER", hivatkozasok=["ALAP"])
    assert [s.fajta for s in uj.sorok] == ["KIHAGYAS", "KIHAGYAS"]
    j = _j(uj, _alap())
    assert j.elvek == []
    assert {k for k, _, _ in j.feloldas.torolt} == {"ELV/E1", "ELV/E2"}
    with pytest.raises(JelzesHiba):                    # nincs mit kihagyni
        _r("UJ", [{"kihagy": "ELV/E1"}])


def test_kivetel():
    r = _r("KV", [
        {"elv": "KIRE", "terulet": "INDITAS", "szoveg": "gyengén a partnerre"},
        {"kivetel": "HOSSZU", "alol": "KIRE", "terulet": "INDITAS", "szoveg": "6 lapos sorozat: kicsi"},
        {"felvetel": "SZAN", "lap": "LEGNAGYOBB"},
        {"felvetel": "SZAN", "minta": "KQ+", "hossz": "6", "lap": "LEGKISEBB",
         "fajta": "KIVETEL", "alol": "KIRE"}])
    j = _j(r)
    assert j.indito_lap("KQ7652", "SZAN")[0] == "2"     # a kivétel szabályként él
    assert [(e["kod"], e["fajta"]) for e in j.elvek] == [("KIRE", "ELV"), ("HOSSZU", "KIVETEL")]
    assert not j.feloldas.kivetel_elv_nelkul
    assert sor_szoveg(r.sorok[1]).startswith("Kivétel (a(z) KIRE elv alól)")
    with pytest.raises(JelzesHiba):                    # melyik elv alól?
        _r("KV", [{"kivetel": "X1", "szoveg": "x"}])
    magany = _j(_r("KV", [{"kivetel": "X1", "alol": "NINCS", "szoveg": "x"}]))
    assert magany.feloldas.kivetel_elv_nelkul == ["KIVETEL/X1"]


def test_partner_szine_az_inditasra_esik_vissza():
    j = _j(_r("PP", [{"minta": "AK+", "lap": "A"},
                    {"helyzet": "PARTNER_SZINE", "hossz": "3", "lap": "LEGNAGYOBB"}]))
    assert j.indito_lap("852", "SZAN", "PARTNER_SZINE")[0] == "8"
    assert j.indito_lap("AK2", "SZAN", "PARTNER_SZINE")[0] == "A"
    assert j.indito_lap("852", "SZAN")[0] is None


def test_sor_szoveg():
    r = _alap()
    szovegek = [sor_szoveg(s) for s in r.sorok]
    assert szovegek[0] == "Indítás szín ellen — ÁK+: Á"
    assert any(s.startswith("Jelzés: első dobás, szín ellen, 1.: preferencia") for s in szovegek)


# --- A valódi jelzésrendszerek ----------------------------------------------------

@pytest.fixture(scope="module")
def rr():
    return rendszerek_betolt([JELZESEK])


@pytest.fixture(scope="module")
def szm(rr):
    return jelzesek("SZEGEDI_MRAZ", rr)


@pytest.mark.parametrize("lapsor,felv,vart", [
    ("AK52", "SZIN", "A"), ("AKQ3", "SZIN", "A"), ("KQJ4", "SZIN", "K"),
    ("KJT3", "SZIN", "J"), ("KT94", "SZIN", "T"), ("K872", "SZIN", "7"),
    ("Q8642", "SZIN", "2"), ("86", "SZIN", "8"), ("9", "SZIN", "9"),
    ("KQJ4", "SZAN", "K"), ("AQJ4", "SZAN", "Q"), ("K872", "SZAN", "2"),
    ("T743", "SZAN", "3"), ("97542", "SZAN", "9"), ("8642", "SZAN", "8"),
])
def test_szm_inditasok(szm, lapsor, felv, vart):
    lap, sor = szm.indito_lap(lapsor, felv)
    assert lap == vart, (lapsor, felv, sor)


def test_szm_igert_harom_lap(szm):
    assert szm.indito_lap("8642", "SZIN")[0] == "4"
    assert szm.indito_lap("8642", "SZIN", kontextus={"IGERT_HAROM"})[0] == "8"


@pytest.mark.parametrize("lapsor,vart", [
    ("T642", "6"), ("T942", "T"), ("JT2", "T"), ("9542", "5"), ("9842", "9"),
    ("8642", "8"), ("T", "T"), ("AKQ", "Q"), ("KT2", "2"), ("T9", "T"),
])
def test_legnagyobb_nelkulozheto(lapsor, vart):
    from kibic.motor.jelzes import legnagyobb_nelkulozheto
    assert legnagyobb_nelkulozheto(lapok(lapsor)) == vart


@pytest.mark.parametrize("lapsor,vart", [
    ("A", "A"), ("K5", "K"), ("72", "7"),                 # rövid színek: a fejezet sorai
    ("K72", "2"), ("K872", "7"), ("K8752", "2"), ("K87532", "7"),   # harmadik-ötödik
    ("8642", "8"), ("T642", "6"), ("872", "8"),           # figura nélkül: legnagyobb nélkülözhető
    ("97542", "7"), ("T82", "8"),                         # menet közben a magában álló 10 / 9 marad
])
def test_szm_hivas(szm, lapsor, vart):
    lap, sor = szm.indito_lap(lapsor, "SZIN", "HIVAS")
    assert lap == vart, (lapsor, sor)


def test_szm_hivas_a_racsbol_jon(szm):
    _, sor = szm.indito_lap("K872", "SZAN", "HIVAS")
    assert sor.kulcs == "RACS/VEDO_HIV/SZAN/1 › MODSZER/ATTITUD › TECHNIKA/HARMADIK_OTODIK"
    assert sor.cel == "KER" and sor.hossz == (3, 4)
    assert szm.technikak["HARMADIK_OTODIK"][1] == {"hossz": "5", "lap": "LEGKISEBB"}
    assert not szm.figyelmeztetesek


def test_technika_es_figyelmeztetesek():
    r = _r("TT", [
        {"technika": "MASODIK", "esetek": [{"hossz": "3+", "lap": "FELULROL(2)"}, {"lap": "LEGKISEBB"}]},
        {"felvetel": "SZIN", "lap": "MASODIK"},
        {"felvetel": "SZAN", "lap": "NINCS_ILYEN"},
        {"racs": "VEDO_HIV", "felvetel": "*", "jel": "KERES"}])          # a KERES-nek nincs `hivas:`
    j = _j(r)
    assert j.indito_lap("8642", "SZIN")[0] == "6" and j.indito_lap("82", "SZIN")[0] == "2"
    assert j.indito_lap("8642", "SZAN") == (None, None)
    assert any("ismeretlen technika: NINCS_ILYEN" in x for x in j.figyelmeztetesek)
    assert any("MODSZER/KERES" in x for x in j.figyelmeztetesek)
    assert sor_szoveg(r.sorok[0]) == ("Technika — MASODIK: 3+ lapból felülről a 2.; "
                                      "különben a legkisebb")


@pytest.mark.parametrize("lapsor,vart", [("KQT2", 1), ("KQ92", 2), ("KQJ", 0), ("AK72", 5),
                                         ("KQ", None)])
def test_hezag(lapsor, vart):
    from kibic.motor.jelzes import hezag
    assert hezag(lapok(lapsor)) == vart


def test_hezag_feltetel():
    r = _r("HZ", [{"felvetel": "SZAN", "minta": "KQ+", "hossz": "3+", "hezag": "1-",
                   "lap": "SOROZAT_TETEJE"},
                  {"felvetel": "SZAN", "lap": "LEGKISEBB"}])
    assert r.sorok[0].kulcs == "INDITAS/SZAN/KQ+/h3+/g1-"
    assert sor_szoveg(r.sorok[0]).endswith("(3+ lap, a 2. és 3. lap között legfeljebb 1 hely): a sorozat teteje")
    j = _j(r)
    assert j.indito_lap("KQT2", "SZAN")[0] == "K" and j.indito_lap("KQ92", "SZAN")[0] == "2"
    with pytest.raises(JelzesHiba):
        _r("HZ", [{"felvetel": "SZAN", "hezag": "sok", "lap": "LEGKISEBB"}])


@pytest.mark.parametrize("lapsor,szan,hivas,szin", [
    ("KQ72", "2", "2", "K"), ("KQ92", "2", "2", "K"), ("KQT2", "K", "K", "K"),
    ("KQJ2", "K", "K", "K"), ("QJ93", "Q", "Q", "Q"), ("AK72", "2", "2", "A"),
    ("KJT2", "J", "J", "J"), ("AQJ5", "Q", "Q", "Q"),
])
def test_moha_ket_erintkezo_figura(rr, lapsor, szan, hivas, szin):
    """A hézag-szabály (legfeljebb 1 hely) a Moha szan elleni indításában és
    játék közben; szín ellen marad a sorozat teteje; a belső sorozat játék
    közben is a teteje."""
    j = jelzesek("MOHA_STAND", rr)
    assert j.indito_lap(lapsor, "SZAN")[0] == szan
    assert j.indito_lap(lapsor, "SZIN", "HIVAS")[0] == hivas
    assert j.indito_lap(lapsor, "SZIN")[0] == szin


@pytest.mark.parametrize("lapsor,vart", [
    ("A", "A"), ("K5", "5"), ("72", "2"),                 # 2 lapból: a kisebb
    ("872", "8"), ("Q72", "7"), ("K72", "7"),             # 3: a legnagyobb nélkülözhető (nem a figura)
    ("8642", "2"), ("K872", "2"), ("K8752", "8"), ("T82", "T"),   # 3 kis lapból a legnagyobb
])
def test_moha_hivas_lapszam(rr, lapsor, vart):
    lap, sor = jelzesek("MOHA_STAND", rr).indito_lap(lapsor, "SZIN", "HIVAS")
    assert lap == vart, (lapsor, sor)


def test_szm_minden_inditasra_van_szabaly(szm):
    for lapsor in ("A", "Q2", "J97", "AJ84", "KQ953", "T87643", "AKJ", "Q"):
        for f in ("SZIN", "SZAN"):
            assert szm.indito_lap(lapsor, f)[0] is not None, (lapsor, f)


def test_szm_ketlapos_sorozat_javasolt(rr):
    assert jelzesek("SZEGEDI_MRAZ", rr, "TESZT").indito_lap("KQ72", "SZAN")[0] == "K"
    assert jelzesek("SZEGEDI_MRAZ", rr, "ELES").indito_lap("KQ72", "SZAN")[0] == "2"


def test_moha_stand(rr):
    j = jelzesek("MOHA_STAND", rr)
    assert j.lanc == ["MOHA_STAND", "SZEGEDI_MRAZ"]
    assert j.indito_lap("K872", "SZIN")[0] == "7"                 # öröklött indítás
    assert j.modszer["SMITH"] == "NAGY_POZITIV" and "LAPSZAM_ALAP" not in j.modszer
    assert [c["jel"] for c in j.racs["FELVEVO_HIV"]["SZIN"]] == ["LAPSZAM", "MARADEK"]
    assert not any(c["feltetelezes"] for h in j.racs.values() for f in h.values() for c in f)
    kodok = [t["kod"] for t in j.elvek]
    assert "PARTNER_SZUKSEGLETE" not in kodok and "KERES_KORLATA" in kodok
    assert any(t.get("merlegelo") for t in j.elvek)
    assert {"HIVAS_HARMADIK_FIGURA", "NELKULOZHETO_KOZEPLAP"} <= set(kodok)
    assert j.racs["VEDO_HIV"]["SZIN"][0]["jel"] == "LAPSZAM"
    assert not j.figyelmeztetesek
    kv = next(t for t in j.elvek if t["kod"] == "SAJAT_HOSSZU_SZIN")
    assert kv["fajta"] == "KIVETEL" and kv["alol"] == "KIRE_INDULUNK"
    assert kodok.index("SAJAT_HOSSZU_SZIN") == kodok.index("KIRE_INDULUNK") + 1
    assert next(t for t in j.kulonleges if t["kod"] == "SMITH")["rendszer"] == "MOHA_STAND"
    # a Szegedi–Mráz önmagában a forrást adja vissza
    s = jelzesek("SZEGEDI_MRAZ", rr)
    assert s.modszer["SMITH"] == "KICSI_POZITIV"
    assert any("Második ütésben" in t["szoveg"] for t in s.kulonleges)


# --- Rendszer-YAML és kártya ----------------------------------------------------

def test_rendszer_yaml_profil():
    g = forras_dict({"rendszer": {"kod": "R1", "fajta": "RENDSZER", "csalad": "NATURAL"},
                     "jelzesek": "MOHA_STAND"}, "r")
    assert g["R1"].jelzesek == {"rendszer": "MOHA_STAND"}
    g = forras_dict({"rendszer": {"kod": "R3", "fajta": "RENDSZER", "csalad": "NATURAL"},
                     "jelzesek": {"rendszer": "SZEGEDI_MRAZ"}}, "r")
    assert g["R3"].jelzesek == {"rendszer": "SZEGEDI_MRAZ"}
    with pytest.raises(ForrasHiba):
        forras_dict({"rendszer": {"kod": "R2"}, "jelzesek": {"csomagok": ["X"]}}, "r")
    assert profil_kod(None) is None


def test_kibic_stand_kartya_jelzesekkel():
    k = kartya_yamlbol(betolt([GYOKER / "rendszerek" / "yaml"]), "KIBIC_STAND")
    sorok = {r["minta"]: r for cs in k["leads"]["csoportok"] for r in cs["sorok"]}
    kq = sorok["KQx"]["SZIN"]
    assert kq["tokens"] == ["K", "D", "x"] and kq["idx"] == 0
    assert sorok["Kxxx"]["SZAN"]["idx"] == 3
    assert sorok["KQx"]["SZAN"]["javasolt"] is True
    sig = k["signals"]
    assert sig["rendszer"]["code"] == "MOHA_STAND"
    assert sig["alapja"] == ["Szegedi–Mráz jelzésrendszer (2008)"]
    assert sig["lanc"] == ["MOHA_STAND", "SZEGEDI_MRAZ"]
    assert [c["jel"] for c in sig["racs"][1]["SZIN"]] == ["Lapszám", "Maradék lapszám"]
    smith = sig["racs"][1]["SZAN"][0]
    assert smith["jel"] == "Smith" and smith["kulonben"] == "Lapszám" and smith["mikor"]
    assert any("első hívásában" in x for x in sig["kulonleges"])
    vedo = next(r for r in sig["racs"] if r["helyzet"] == "Menet közben mi hívunk")
    assert vedo["SZIN"][0]["jel"] == "Lapszám (2+)"
    lsz = next(m for m in sig["modszer"] if m["cim"] == "Lapszám")
    assert "menet közbeni hívásnál páratlanból" in lsz["szoveg"]
    assert not any("kire induljunk" in x.lower() for x in sig["elvek"])   # mérlegelő: nem kártyára
    html = kartya_html(k)
    assert "Indító kijátszás" in html and 'class="lap-ki"' in html
    assert "Moha standard jelzések" in html and "<sup>1</sup>" in html
    assert "Természetes:" in html
    kozep = html.split("Indító kijátszás")[1].split('<div class="fej">')[0]
    assert "kitöltendő" not in kozep


def test_kartya_profil_nelkul_a_kezzel_irt_szoveg_marad():
    g = {}
    forras_dict({"rendszer": {"kod": "ALAP", "fajta": "ALAPRENDSZER"},
                 "szabalyok": [{"minta": "1NT", "pont": "15-17"}]}, "a", g)
    forras_dict({"rendszer": {"kod": "KR", "fajta": "RENDSZER", "csalad": "NATURAL"},
                 "hivatkozasok": ["ALAP"], "kartya": {"jelzesek": "kis lap kér"}}, "k", g)
    k = kartya_yamlbol(g, "KR")
    assert k["signals"] == "kis lap kér" and k["leads"] is None


# --- Adatbázis (hamis kapcsolattal) ----------------------------------------------

class _Cur:
    def __init__(self, valaszok):
        self.valaszok, self.hivasok, self._utolso = list(valaszok), [], []

    def execute(self, sql, par=None):
        self.hivasok.append((sql, par))
        self._utolso = self.valaszok.pop(0) if self.valaszok else []

    def fetchall(self):
        return self._utolso

    def fetchone(self):
        return self._utolso[0] if self._utolso else None


class _Conn:
    def __init__(self, valaszok):
        self.c = _Cur(valaszok)

    def cursor(self):
        return self.c


def _db_sorok(rr):
    """A 031-es szerkezet: a hivatkozás is sor (tipus = HIVATKOZAS)."""
    rendszer, idk, menet = [], [], []
    id_ = {k: i for i, k in enumerate(rr, 1)}
    for kod, i in id_.items():
        r = rr[kod]
        rendszer.append((i, r.kod, r.nev, r.fajta, r.verzio, r.forras, r.leiras, r.jegyzet,
                         json.dumps(r.fejezet_jegyzetek)))
        idk.append((i, r.kod))
        for n, h in enumerate(r.hivatkozasok, 1):
            menet.append((i, "HIVATKOZAS", "SZABALY", None, f"HIV/{h}", "{}", "Hivatkozások",
                          n, "ELFOGADOTT", None, None, None, id_[h], "BE", 1, None))
        for s in r.sorok:
            menet.append((i, "SZABALY", s.fajta, s.terulet, s.kulcs, s.tartalom(), s.fejezet,
                          s.seq, s.allapot, s.megjegyzes, s.jegyzet, None, None, None, 1, None))
    return rendszer, idk, menet


def test_jelzesek_db(rr):
    rendszer, idk, menet = _db_sorok(rr)
    j = jelzesek_db(_Conn([rendszer, idk, menet]), "MOHA_STAND")
    assert j.lanc == ["MOHA_STAND", "SZEGEDI_MRAZ"]
    assert j.indito_lap("KQ7", "SZIN")[0] == "K"
    assert j.modszer == jelzesek("MOHA_STAND", rr).modszer
    assert jelzesek_db(_Conn([]), None) is None


def test_import_jovahagyas_megorzese():
    from kibic.cli.rendszerimport import jelzes_uj_allapotok
    r = _r("PP", [{"felvetel": "SZAN", "lap": "LEGKISEBB"},                    # változatlan
                 {"felvetel": "SZIN", "lap": "LEGNAGYOBB"},                   # megváltozott
                 {"modszer": "KERES", "ertek": "KICSI"},                      # új
                 {"modszer": "SMITH", "ertek": "NAGY_POZITIV", "allapot": "JAVASOLT"}],
           alap_allapot="ELFOGADOTT")
    s0, s1 = r.sorok[0], r.sorok[1]
    regi = [(s0.fajta, s0.kulcs, s0.tartalom(), "JEGELT", "sanyi", "2026-10-20"),
            (s1.fajta, s1.kulcs, '{"regi": 1}', "ELFOGADOTT", "sanyi", "2026-10-20"),
            ("MODSZER", "MODSZER/SMITH", "{}", "ELFOGADOTT", "x", None)]
    ki = jelzes_uj_allapotok(r.sorok, regi)
    assert ki[0] == ("JEGELT", "sanyi", "2026-10-20")
    assert ki[1][0] == "FELULVIZSGALANDO"
    assert ki[2][0] == "ELFOGADOTT"
    assert ki[3][0] == "JAVASOLT"                      # a YAML kimondta


def test_import_iras(rr):
    from kibic.cli.rendszerimport import jelzesrendszer_ir
    # fej (INSERT, SELECT id), régi sorok, DELETE, a hivatkozott id-je, aztán a beszúrások
    cur = _Cur([[], [(7,)], [], [], [(3,)], *[[]] * 200])
    stat = jelzesrendszer_ir(cur, rr["MOHA_STAND"])
    sqls = [h[0] for h in cur.hivasok]
    assert sqls[0].startswith("INSERT INTO jelzesrendszer")
    assert any(s.startswith("DELETE FROM jelzesmenet") for s in sqls)
    beszur = [h for h in cur.hivasok if h[0].startswith("INSERT INTO jelzesmenet")]
    hiv = [h for h in beszur if "'HIVATKOZAS'" in h[0]]
    assert len(hiv) == 1 and hiv[0][1][0] == 7 and hiv[0][1][-1] == 3 and "'BE'" in hiv[0][0]
    szab = [h for h in beszur if h not in hiv]
    assert len(szab) == len(rr["MOHA_STAND"].sorok) == sum(stat.values())
    assert {h[1][3] for h in szab} <= {"SZABALY", "ELV", "KIVETEL", "KIHAGYAS"}


def test_migraciok_leteznek():
    s = (GYOKER / "schema" / "030_jelzesmenet.sql").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS `jelzesrendszer`" in s
    assert "CREATE TABLE IF NOT EXISTS `jelzesmenet`" in s
    assert "DROP TABLE IF EXISTS `jelzes_csomag`" in s
    assert "'SZINADAS'" in (GYOKER / "schema" / "032_jelzes_szinadas.sql").read_text(encoding="utf-8")
    s = (GYOKER / "schema" / "031_jelzesmenet_szerkezet.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN `terulet`" in s and "'HIVATKOZAS'" in s
    assert "SET `szabaly_fajta` = 'KIHAGYAS' WHERE `szabaly_fajta` = 'TORLES'" in s


def test_cli_jelzes(capsys):
    from kibic.cli.jelzes import main
    assert main(["--rendszer", "SZEGEDI_MRAZ", "--lap", "KQ72"]) == 0
    ki = capsys.readouterr().out
    assert "KD72" in ki and "SZAN -> K" in ki and "mögötte" in ki
    assert main(["--rendszer", "SZEGEDI_MRAZ", "--lap", "KQ72", "--szint", "ELES"]) == 0
    assert "SZAN -> 2" in capsys.readouterr().out
    assert main(["--rendszer", "MOHA_STAND", "--lap", "KQ72"]) == 0     # a hézag-szabály
    assert "SZAN -> 2" in capsys.readouterr().out
    assert main(["--rendszer", "MOHA_STAND"]) == 0
    ki = capsys.readouterr().out
    assert "MOHA_STAND -> SZEGEDI_MRAZ" in ki and "KIHAGYVA" in ki and "FELÜLÍRVA" in ki
