"""
A kiosztástervező (mohabridzs-deal-design/1.1) — a szolgáltatásfüggvény,
DDS és adatbázis nélkül: a licithez a YAML-rendszerek, a DD-hez egy hamis
motor (a valódi DDS a szerveren fut; a felülete ugyanez).
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol
from kibic.szolgaltatas import kiosztas as K


@pytest.fixture(scope="module")
def betolto():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    tar: dict = {}

    def bet(kod, par=None, teszt=None):
        if kod not in tar:
            tar[kod] = feloldas_forrasokbol(g, kod)[0].sorok
        return tar[kod], Parametertar()
    return bet


def _ervenyes(d):
    lapok = [c for u in "NESW" for c in d["hands"][u]]
    assert all(len(d["hands"][u]) == 13 for u in "NESW")
    assert len(set(lapok)) == 52
    assert d["dealer"] in "NESW" and d["vulnerability"] in K.BELIK


# --- alapok ------------------------------------------------------------------

def test_generalas_kezfeltetellel_es_seeddel():
    keres = {"count": 4, "seed": "abc", "target": {"hands": {
        "N": {"hcp": "15-17", "shape": "balanced"}, "S": {"suits": {"S": "5+"}}}}}
    v = K.kiosztas(keres)
    assert v["status"] == "ok" and len(v["deals"]) == 4
    for d in v["deals"]:
        _ervenyes(d)
        n = K.KezInfo(d["hands"]["N"])
        assert 15 <= n.hcp <= 17 and n.alak in K.ALAKOK["balanced"]
        assert K.KezInfo(d["hands"]["S"]).hossz["S"] >= 5
    # ugyanaz a seed: ugyanazok a kiosztások
    w = K.kiosztas(keres)
    assert [d["deal_id"] for d in w["deals"]] == [d["deal_id"] for d in v["deals"]]
    # tábla, osztó, beli a táblaszámból
    assert [d["board"] for d in v["deals"]] == [1, 2, 3, 4]
    assert [d["dealer"] for d in v["deals"]] == ["N", "E", "S", "W"]
    assert [d["vulnerability"] for d in v["deals"]] == ["none", "ns", "ew", "both"]
    assert v["interpretation"]["hands"]["N"] == {"hcp": [15, 17], "shape": "balanced"}


def test_seed_nelkul_is_visszaadja_a_seedet():
    v = K.kiosztas({"count": 1})
    assert v["interpretation"]["seed"] and v["deals"][0]["source"]["type"] == "generate"


def test_hibak():
    with pytest.raises(K.KiosztasHiba) as e:
        K.kiosztas({"protocol": "mohabridzs-deal-design/9.9"})
    assert e.value.kod == "unsupported_protocol"
    with pytest.raises(K.KiosztasHiba) as e:
        K.kiosztas({"text": "adj nekem stayman leosztásokat"})
    assert e.value.kod == "text_unsupported" and e.value.http == 422
    with pytest.raises(K.KiosztasHiba) as e:
        K.kiosztas({"target": {"preset": "NINCS_ILYEN"}})
    assert e.value.kod == "unknown_preset"
    with pytest.raises(K.KiosztasHiba) as e:
        K.kiosztas({"target": {"play": {"contract": "4S", "technique": "squeeze"}}})
    assert e.value.kod == "unsupported_target" and "tervezett" in str(e.value)
    with pytest.raises(K.KiosztasHiba) as e:
        K.kiosztas({"target": {"hands": {"N": {"hcp": "17-15"}}}})
    assert e.value.kod == "invalid_request"
    with pytest.raises(K.KiosztasHiba) as e:
        K.kezek_ellenoriz({"N": ["SA"] * 13, "E": [], "S": [], "W": []})
    assert e.value.kod == "invalid_deal"


def test_pbn_beolvasas_es_szures():
    pbn = """
[Event "Klubverseny"]
[Board "1"]
[Dealer "N"]
[Vulnerable "None"]
[Deal "N:AKQ2.KQ2.A32.432 J543.A54.KQ4.A65 T976.JT9.JT9.KQJ 8.8763.8765.T987"]
[Contract "3NT"]
[Declarer "N"]

[Board "2"]
[Dealer "E"]
[Vulnerable "NS"]
[Deal "E:AKQ2.KQ2.A32.432 J543.A54.KQ4.A65 T976.JT9.JT9.KQJ 8.8763.8765.T987"]
"""
    v = K.kiosztas({"source": {"type": "pbn", "pbn": pbn}})
    assert v["stats"]["returned"] == 2 and v["status"] == "ok" and v["stats"]["source_exhausted"]
    d1, d2 = v["deals"]
    assert d1["board"] == 1 and d1["source"]["event"] == "Klubverseny"
    assert d1["source"]["played"] == {"contract": "3NT", "declarer": "N"}
    assert d2["dealer"] == "E" and d2["vulnerability"] == "ns"
    assert d2["hands"]["E"][:3] == ["SA", "SK", "SQ"]
    # csak azok, ahol északnak 18+ pontja van
    v = K.kiosztas({"source": {"type": "pbn", "pbn": pbn},
                    "target": {"hands": {"N": {"hcp": "18+"}}}})
    assert [d["board"] for d in v["deals"]] == [1]


def test_kesz_kiosztasok_ellenorzese():
    kezek = K.pbn_kezek("N:AKQ2.KQ2.A32.432 J543.A54.KQ4.A65 T976.JT9.JT9.KQJ 8.8763.8765.T987")
    v = K.kiosztas({"source": {"type": "deals", "deals": [{"hands": kezek, "board": 7}]},
                    "include": ["pbn"]})
    assert v["deals"][0]["board"] == 7 and v["deals"][0]["dealer"] == "S"
    assert v["deals"][0]["pbn"].startswith("S:")


def test_szaraz_futas():
    v = K.kiosztas({"dry_run": True, "target": {"hands": {"N": {"hcp": "20-21"}}}})
    assert v["dry_run"] and v["stats"]["estimate"] == "feasible" and "deals" not in v


# --- licit: a rendszer dönt --------------------------------------------------

def test_stayman_helyzet_a_rendszer_licitjevel(betolto):
    v = K.kiosztas({"count": 2, "seed": "s1", "target": {"preset": "NT_STAYMAN"}}, betolto)
    assert v["status"] == "ok"
    for d in v["deals"]:
        _ervenyes(d)
        # a tanuló (S) a partner szerepben: N az osztó
        assert d["dealer"] == "N"
        assert [m["call"] for m in d["auction"][:3]] == ["1N", "P", "2C"]
        assert d["auction"][0]["seat"] == "N"
    assert v["interpretation"]["preset"] == "NT_STAYMAN"


def test_kuzdelmi_es_vedekezo_helyzet(betolto):
    v = K.kiosztas({"count": 1, "seed": "k", "target": {"preset": "NEGATIVE_DOUBLE"}}, betolto)
    d = v["deals"][0]
    assert d["auction"][2]["call"] == "X" and d["auction"][2]["seat"] == "S"
    assert K.ag(d["auction"], "S") == "competitive"
    v = K.kiosztas({"count": 1, "seed": "v", "target": {"preset": "OVERCALL"}}, betolto)
    d = v["deals"][0]
    assert d["dealer"] == "E" and K.ag(d["auction"], "S") == "defensive"


def test_elotag_tokenek():
    menet = [{"seat": "N", "call": "1N"}, {"seat": "E", "call": "P"}, {"seat": "S", "call": "2H"}]
    assert K.elotag_illik(menet, ["1N", "P", "2D|2H"])
    assert K.elotag_illik(menet, ["BID", "*", "!P"])
    assert not K.elotag_illik(menet, ["1N", "!P"])
    assert K.kontraktus(menet + [{"seat": "W", "call": "X"}]) == \
        {"level": 2, "strain": "H", "multiplier": 2, "declarer": "S"}


# --- lejátszás és ellenjáték (hamis DD) ----------------------------------------

class HamisDd(K.DdMotor):
    """Alapból 10 ütés mindenkinek; ha a kulcslap (♠K) Keletnél van, csak 9."""
    elerheto = True

    def __init__(self, kulcs="SK"):
        self.kulcs = kulcs

    def tablak(self, lista):
        ki = []
        for kezek in lista:
            u = 9 if self.kulcs in kezek["E"] else 10
            ki.append({s: {sz: u for sz in ("S", "H", "D", "C", "NT")} for s in "NESW"})
        return ki

    def indulasok(self, kezek, kon):
        vezeto = K.ULESEK[(K.ULESEK.index(kon["declarer"]) + 1) % 4]
        return [(c, 8 if c[0] == "H" else 10) for c in kezek[vezeto]]


def test_impassz_csere_teszttel():
    # a ♠K Nyugatnál (impassz sikerül), ÉD-nek ♠AQ villája van
    keres = {"count": 2, "seed": "f", "target": {
        "hands": {"W": {"cards": ["SK"]}, "S": {"cards": ["SA", "SQ"]}},
        "play": {"contract": "4S", "declarer": "S", "technique": "finesse"}}}
    v = K.kiosztas(keres, dd=HamisDd())
    assert v["status"] == "ok"
    for d in v["deals"]:
        t = d["checks"]["techniques"]
        assert {"suit": "S", "card": "SK", "seat": "W", "type": "finesse"} in t
        assert "finesse" in d["tags"] and d["checks"]["dd_tricks"] == 10


def test_expassz_ha_nincs_villa():
    # a hiányzó ♠A Nyugatnál, Délnek ♠K-ja van: a K felé kell játszani
    keres = {"count": 1, "seed": "x", "target": {
        "hands": {"W": {"cards": ["SA"]}, "S": {"cards": ["SK"]}},
        "play": {"contract": "4S", "declarer": "S", "technique": "expassz"}}}
    v = K.kiosztas(keres, dd=HamisDd("SA"))
    t = v["deals"][0]["checks"]["techniques"]
    assert {"suit": "S", "card": "SA", "seat": "W", "type": "expassz"} in t


def test_egy_szinbol_buktato_indulas(betolto):
    v = K.kiosztas({"count": 1, "seed": "l", "target": {
        "play": {"contract": "3N", "declarer": "N", "student": "leader",
                 "lead": "single_suit"}}}, betolto, dd=HamisDd())
    d = v["deals"][0]
    assert d["checks"]["leader"] == "E"
    assert {c[0] for c in d["checks"]["beating_leads"]} == {"H"}


def test_dds_nelkul_lejatszasi_cel_503(monkeypatch):
    monkeypatch.setattr(K, "dd_elerheto", lambda: False)
    with pytest.raises(K.KiosztasHiba) as e:
        K.kiosztas({"target": {"play": {"contract": "4S", "result": "makes"}}})
    assert e.value.kod == "dds_unavailable" and e.value.http == 503


def test_kepessegek():
    k = K.kepessegek()
    assert k["protocol"] == "mohabridzs-deal-design/1.1"
    kodok = {p["code"] for p in k["presets"]}
    assert {"NT_STAYMAN", "NT_TRANSFER", "WEAK_TWO", "PREEMPT_3", "NEGATIVE_DOUBLE",
            "OVERCALL", "FINESSE", "OPENING_LEAD"} <= kodok
    allapot = {t["code"]: t["status"] for t in k["targets"]["play"]["techniques"]}
    assert allapot["finesse"] == "supported" and allapot["squeeze"] == "planned"
    assert k["text"]["supported"] is False


def test_forgatas_ket_ulessel():
    kezek = K.pbn_kezek("N:AKQ2.KQ2.A32.432 J543.A54.KQ4.A65 T976.JT9.JT9.KQJ 8.8763.8765.T987")
    uj, o, b = K.forgat(kezek, "N", "ns", 2)
    assert uj["S"] == kezek["N"] and o == "S" and b == "ns"
    uj, o, b = K.forgat(kezek, "N", "ns", 1)
    assert uj["E"] == kezek["N"] and o == "E" and b == "ew"


def test_vegso_kontraktus_cel(betolto):
    # a 1NT-Stayman sorból csak a 3NT-vel végződők, ahol a tanuló vonala a felvevő
    v = K.kiosztas({"count": 1, "seed": "f3", "time_budget_ms": 60000,
                    "target": {"preset": "NT_STAYMAN",
                               "auction": {"final": {"contract": "3N", "side": "student"}}}},
                   betolto)
    k = K.kontraktus(v["deals"][0]["auction"])
    assert (k["level"], k["strain"]) == (3, "N") and k["declarer"] in "NS"
    with pytest.raises(K.KiosztasHiba):
        K.kiosztas({"target": {"auction": {"final": {"szint": 3}}}}, betolto)
