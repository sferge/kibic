"""
A MOHABRIDZS GATEWAY-ADAPTER próbája — adatbázis és webapp nélkül.

Amit igazol (a szerződés MUST-jai sorban):

  * a válasz `action.call`-ja MINDIG a `legal_actions.calls` eleme —
    akkor is, ha a kibicnek nincs szabálya (ilyenkor tartalék, és ezt
    a `meta.source` ki is mondja);
  * a `request_id` változatlanul visszamegy;
  * a dróton `N` a szan, nem `NT`;
  * ugyanaz az idempotenciakulcs ugyanazt a választ adja, más törzzsel
    ütközést;
  * ismeretlen jövőbeli mező nem hibázik;
  * a kijátszás kényszerű lapot ad, egyébként tartalékot.
"""
import pytest

from kibic.szolgaltatas.atjaro import (
    Idempotenciatar, Utkozes, bid_dontes, drotra, munkamenet_kulcs,
    play_dontes)
from kibic.szolgaltatas.licit import LicitHiba

from test_licit_szolgaltatas import KEZ, _betolto

KELET = ["SA", "SJ", "S7", "H9", "H4", "DA", "DQ", "D8", "D3",
         "CK", "CJ", "C6", "C2"]


def _keres(**kw):
    alap = {
        "protocol": "mohabridzs-ai/1.0",
        "request_id": "5aa92d15:17:0:1:bid:6",
        "decision": "bid",
        "deadline_ms": 20000,
        "game": {"match_id": "5aa92d15", "state_version": 17,
                 "round_number": 1, "board_number": 3, "table_index": 0,
                 "vulnerability": "ns"},
        "actor": {"player_index": 4, "seat": "S", "acting_for_seat": "S",
                  "is_declarer": False, "controls_dummy": False,
                  "profile_code": "kibic"},
        "state": {"phase": "bidding", "dealer": "N", "current_seat": "S",
                  "contract": None, "declarer": None, "dummy": None,
                  "visible_hands": {"S": KEZ},
                  "current_trick": [], "completed_tricks": [],
                  "ns_tricks": 0},
        "history": {"auction": [{"seat": "N", "call": "1S"},
                                {"seat": "E", "call": "P"}],
                    "play": []},
        "legal_actions": {"calls": ["P", "X", "2C", "2D", "2H", "2S", "2N"]},
    }
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(alap.get(k), dict):
            alap[k] = {**alap[k], **v}
        else:
            alap[k] = v
    return alap


# --- A szerződés kötelező pontjai -------------------------------------

def test_szabaly_alapjan_dont_es_model_forrasu():
    v = bid_dontes(_keres(), _betolto)
    assert v["action"] == {"type": "bid", "call": "2S"}
    assert v["meta"]["source"] == "model"
    assert v["meta"]["fallback_reason"] is None
    assert v["meta"]["kibic"]["rule_source"] == "SZABALY"


def test_request_id_valtozatlanul_visszamegy():
    v = bid_dontes(_keres(request_id="akármi:42"), _betolto)
    assert v["request_id"] == "akármi:42"


def test_ha_nincs_szabaly_akkor_is_szabalyos_akcio():
    """A kibic néma; a gateway viszont nem fogad el nemleges választ."""
    v = bid_dontes(_keres(history={"auction": [
        {"seat": "N", "call": "1S"}, {"seat": "E", "call": "2N"}]}), _betolto)
    assert v["action"]["call"] in _keres()["legal_actions"]["calls"]
    assert v["action"]["call"] == "P"
    # 2026-10-03: a vak passz helyett a hézag-elv dönt (itt: nincs kényszer, passz)
    assert v["meta"]["source"] == "model" and "hézag-elv" in v["explanation"]
    assert not v["meta"]["fallback_reason"]
    assert "E:2NT" in v["meta"]["kibic"]["unknown_calls"]


def test_a_javaslat_csak_a_legalis_hivasok_kozul_johet():
    v = bid_dontes(_keres(legal_actions={"calls": ["P", "X"]}), _betolto)
    assert v["action"]["call"] in ("P", "X")
    # a szabály szerinti 2S nem szabályos itt; a hézag-elv a megengedettekből választ
    assert v["meta"]["source"] in ("fallback", "model")


def test_szan_a_droton_rovid_n():
    assert drotra("1NT") == "1N"
    assert drotra("2S") == "2S"
    assert drotra(None) is None


def test_magyarazat_legfeljebb_500_karakter():
    v = bid_dontes(_keres(), _betolto)
    assert len(v["explanation"]) <= 500
    assert 0.0 <= v["confidence"] <= 1.0


def test_ismeretlen_jovobeli_mezo_nem_hiba():
    v = bid_dontes(_keres(jovobeli_mezo={"x": 1}, protocol_extra="?"),
                   _betolto)
    assert v["action"]["call"] == "2S"


def test_belso_hiba_eseten_is_szabalyos_valasz():
    def rossz_betolto(rendszer, par):
        raise LicitHiba("nincs ilyen rendszer")
    v = bid_dontes(_keres(), rossz_betolto)
    assert v["action"]["call"] == "P"
    assert v["meta"]["source"] == "fallback"
    assert "nincs ilyen rendszer" in v["meta"]["fallback_reason"]


@pytest.mark.parametrize("keres,resz", [
    ({"legal_actions": {"calls": []}}, "legal_actions"),
    ({"actor": {"acting_for_seat": "Q", "seat": "Q"}}, "acting_for_seat"),
    ({"state": {"visible_hands": {}}}, "visible_hands"),
])
def test_hibas_gateway_keres_beszedes(keres, resz):
    from kibic.szolgaltatas.atjaro import AtjaroHiba
    with pytest.raises(AtjaroHiba) as e:
        bid_dontes(_keres(**keres), _betolto)
    assert resz in str(e.value)


# --- Idempotencia ------------------------------------------------------

def test_ugyanaz_a_kulcs_ugyanazt_adja():
    tar = Idempotenciatar()
    k = _keres()
    assert tar.olvas("kulcs1", k) is None
    tar.ir("kulcs1", k, {"action": {"call": "2S"}})
    assert tar.olvas("kulcs1", k) == {"action": {"call": "2S"}}


def test_ugyanaz_a_kulcs_mas_torzzsel_utkozes():
    tar = Idempotenciatar()
    tar.ir("kulcs1", _keres(), {"action": {"call": "2S"}})
    with pytest.raises(Utkozes):
        tar.olvas("kulcs1", _keres(deadline_ms=5000))


def test_a_tar_korlatos():
    tar = Idempotenciatar(meret=3)
    for i in range(5):
        tar.ir(f"k{i}", {"i": i}, {"v": i})
    assert tar.olvas("k0", {"i": 0}) is None      # kiesett
    assert tar.olvas("k4", {"i": 4}) == {"v": 4}


def test_munkamenet_kulcs_ulesenkent_kulonbozik():
    a = munkamenet_kulcs(_keres())
    b = munkamenet_kulcs(_keres(actor={"seat": "N"}))
    assert a != b
    assert a == "bridge:5aa92d15:0:3:S"


# --- Kijátszás ---------------------------------------------------------

def test_kenyszeru_lap():
    v = play_dontes({"request_id": "r", "decision": "play",
                     "legal_actions": {"cards": ["D6"]}})
    assert v["action"] == {"type": "play", "card": "D6"}
    assert v["meta"]["source"] == "model"
    assert v["confidence"] == 1.0


def test_kenyszeru_lapnal_is_gondolkodik(monkeypatch):
    """A kényszerű (szingli) lapra se jöjjön azonnal a válasz — az elárulná."""
    import time
    from kibic.szolgaltatas import atjaro
    monkeypatch.setattr(atjaro, "GONDOLKODAS_MS", "120-150")
    t = time.time()
    v = play_dontes({"request_id": "r", "decision": "play",
                     "legal_actions": {"cards": ["D6"]}})
    assert v["action"]["card"] == "D6"
    assert time.time() - t >= 0.11


def test_gondolkodasi_ido_szabalyai(monkeypatch):
    import random
    import time
    from kibic.szolgaltatas import atjaro
    rng = random.Random(1)
    most = time.time()
    monkeypatch.setattr(atjaro, "GONDOLKODAS_MS", "1500-3000")
    assert 1400 <= atjaro.gondolkodasi_ido({}, most, rng) <= 3000
    # a határidő 30%-áig
    assert atjaro.gondolkodasi_ido({"deadline_ms": 2000}, most, rng) <= 600
    # ami a döntésre már elment, az levonódik
    assert atjaro.gondolkodasi_ido({}, most - 5, rng) == 0
    # az utolsó ütésben nincs
    tele = {"history": {"play": ["C2"] * 48}}
    assert atjaro.gondolkodasi_ido(tele, most, rng) == 0
    monkeypatch.setattr(atjaro, "GONDOLKODAS_MS", "0")
    assert atjaro.gondolkodasi_ido({}, most, rng) == 0
    monkeypatch.setattr(atjaro, "GONDOLKODAS_MS", "2000")
    assert 1900 <= atjaro.gondolkodasi_ido({}, most, rng) <= 2000
    monkeypatch.setattr(atjaro, "GONDOLKODAS_MS", "hibás")
    assert atjaro.gondolkodasi_ido({}, most, rng) == 0


def test_ertelmezhetetlen_allasnal_tartalek_es_ezt_be_is_vallja():
    v = play_dontes({"request_id": "r", "decision": "play",
                     "legal_actions": {"cards": ["DT", "D6", "C6"]}})
    assert v["action"]["card"] == "C6"      # legkisebb rang, C D H S
    assert v["meta"]["source"] == "fallback"
    assert v["meta"]["fallback_reason"]


# --- EGY app, mind a négy végpont -------------------------------------

def test_egy_appban_van_a_dd_es_a_gateway_is():
    """
    A DD-elemzés és a MohaBridzs-gateway UGYANAZON az alkalmazáson él.

    Ez nem stíluskérdés: ha valaha kettéválna, két folyamatot kellene
    futtatni két porton, és a rendszer-gyorsítótár is kétszer töltődne.
    A próba akkor is véd, ha valaki „rendet rak" a modulok között.
    """
    fastapi = pytest.importorskip("fastapi")   # noqa: F841
    from kibic.szolgaltatas.api import app

    utak = {r.path for r in app.routes}
    for kell in ("/v1/kibic/dd", "/v1/kibic/licit", "/v1/kibic/allapot",
                 "/v1/bridge/bid", "/v1/bridge/play"):
        assert kell in utak, f"hiányzik a(z) {kell} végpont"


def test_a_ket_titok_kulon_all():
    """
    A gateway titka nem kötheti titokhoz a MÁR MŰKÖDŐ DD-hívásokat.

    Ha csak a `KIBIC_AI_SHARED_SECRET` van beállítva, a `/v1/kibic/dd`
    továbbra is titok nélkül hívható.
    """
    import importlib
    import os

    pytest.importorskip("fastapi")
    regi = {k: os.environ.get(k) for k in
            ("KIBIC_SHARED_SECRET", "KIBIC_AI_SHARED_SECRET")}
    try:
        os.environ.pop("KIBIC_SHARED_SECRET", None)
        os.environ["KIBIC_AI_SHARED_SECRET"] = "csak-a-gatewaynek"
        api = importlib.reload(
            importlib.import_module("kibic.szolgaltatas.api"))
        assert api.TITOK == ""
        assert api.ATJARO_TITOK == "csak-a-gatewaynek"
        api._jogosultsag(None)                    # a DD marad nyitva
        with pytest.raises(Exception):
            api._jogosultsag_atjaro(None)         # a gateway nem
    finally:
        for k, v in regi.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(importlib.import_module("kibic.szolgaltatas.api"))


# --- 1.1: a vonalak rendszere és az alert a licitmenetben --------------

def test_vonalak_rendszere_naplozva(monkeypatch):
    from kibic.szolgaltatas import atjaro, profil
    monkeypatch.setattr(profil, "KINALT_FORRAS",
                        lambda: [{"system": "PRECISION"}])
    rendszer = atjaro.profil_feloldas({})["system"]
    v = bid_dontes(_keres(game={"systems": {"NS": rendszer, "EW": "precision"}}),
                   _betolto)
    r = v["meta"]["kibic"]["systems"]
    assert r["own"] == rendszer.upper() and r["opponents"] == "PRECISION"
    assert r["opponents_known"] is True and r["opponents_system"] == "PRECISION"
    v = bid_dontes(_keres(game={"systems": {"NS": "MAS_RENDSZER", "EW": None}}),
                   _betolto)
    r = v["meta"]["kibic"]["systems"]
    assert r["own_mismatch"] is True and r.get("opponents") is None


def test_systems_nelkul_nincs_bejegyzes_es_alert_a_menetben_nem_hiba():
    menet = {"auction": [{"seat": "N", "call": "1S"},
                         {"seat": "E", "call": "P", "alert": None}],
             "play": []}
    v = bid_dontes(_keres(history=menet), _betolto)
    # game.systems nélkül: a profilból, és a napló figyelmeztet
    assert "game.systems" in v["meta"]["kibic"]["systems"]["warning"]
    assert v["action"]["call"] in ["P", "X", "2C", "2D", "2H", "2S", "2N"]


# --- Információkérés (mohabridzs-ai 1.1, 2026-10-04) ---------------------

_INFO_MENET = [{"seat": "N", "call": "1S"}, {"seat": "E", "call": "2D"}]


def _info_keres(menet, protokoll="mohabridzs-ai/1.1"):
    return _keres(protocol=protokoll, history={"auction": menet, "play": []},
                  legal_actions={"calls": ["P", "X", "2H", "2S", "2N", "3C"]})


def test_info_keres_ha_nem_erti_az_ellenfelet():
    v = bid_dontes(_info_keres(_INFO_MENET), _betolto)
    assert v["action"]["type"] == "request_information"
    assert v["action"]["bid_indices"] == [1]
    assert "call" not in v["action"]


def test_info_keres_utan_licital_es_hasznalja_a_valaszt():
    menet = [dict(_INFO_MENET[0]),
             dict(_INFO_MENET[1], information={"status": "available",
                                               "text": "5+ káró, 8-15 pont", "alerted": False})]
    v = bid_dontes(_info_keres(menet), _betolto)
    assert v["action"]["type"] == "bid"
    assert v["action"]["call"] in ("P", "X", "2H", "2S", "2N", "3C")
    assert "E:2D" in (v["meta"]["kibic"].get("understood_from_alert") or [])


@pytest.mark.parametrize("status", ["none", "error"])
def test_info_keres_nem_ismetlodik(status):
    menet = [dict(_INFO_MENET[0]), dict(_INFO_MENET[1], information={"status": status})]
    v = bid_dontes(_info_keres(menet), _betolto)
    assert v["action"]["type"] == "bid"


def test_info_keres_nincs_1_0_protokollnal():
    v = bid_dontes(_info_keres(_INFO_MENET, "mohabridzs-ai/1.0"), _betolto)
    assert v["action"]["type"] == "bid"


def test_info_keres_kikapcsolhato(monkeypatch):
    import kibic.szolgaltatas.atjaro as a
    monkeypatch.setattr(a, "INFO_KERES", False)
    v = bid_dontes(_info_keres(_INFO_MENET), _betolto)
    assert v["action"]["type"] == "bid"
