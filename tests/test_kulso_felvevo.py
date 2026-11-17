"""A mérőpad külső felvevője: a rövid kérésből a teljes mohabridzs-ai/1.0 kérés."""
from kibic.cli.kulso_felvevo import mb10_keres


def _keres(jatszott):
    return {
        "protocol": "mohabridzs-ai/1.1", "request_id": "p#1:5", "decision": "play", "deadline_ms": 60000,
        "game": {"scoring": "IMP", "match_id": "p#1", "vulnerability": "none"},
        "actor": {"seat": "S", "acting_for_seat": "S", "is_declarer": True, "controls_dummy": True},
        "state": {"phase": "play", "dealer": "N", "current_seat": "S",
                  "contract": {"level": 4, "strain": "H", "multiplier": 1},
                  "declarer": "S", "dummy": "N", "visible_hands": {"S": ["HA", "C2"], "N": ["H2"]}},
        "history": {"auction": [], "play": jatszott},
        "legal_actions": {"cards": ["HA", "C2"]},
    }


def test_utesek_es_nyertesek():
    jatszott = [{"seat": "W", "card": "SA"}, {"seat": "N", "card": "S2"},
                {"seat": "E", "card": "S3"}, {"seat": "S", "card": "H4"},     # Dél lop: NS ütés
                {"seat": "S", "card": "C5"}]
    k = mb10_keres(_keres(jatszott), "futas", 1, 30000)
    assert k["protocol"] == "mohabridzs-ai/1.0"
    assert k["state"]["completed_tricks"] == [{"cards": jatszott[:4], "winner": "S"}]
    assert k["state"]["current_trick"] == jatszott[4:]
    assert k["state"]["ns_tricks"] == 1
    assert k["game"]["match_id"] == "futas:p#1" and k["game"]["state_version"] == 5
    assert k["deadline_ms"] == 30000 and k["actor"]["player_index"] == 0


def test_szan_es_szinnyeres():
    jatszott = [{"seat": "W", "card": "SK"}, {"seat": "N", "card": "SA"},
                {"seat": "E", "card": "H3"}, {"seat": "S", "card": "S2"}]
    kr = _keres(jatszott)
    kr["state"]["contract"]["strain"] = "NT"
    k = mb10_keres(kr, "f", 1, 1000)
    assert k["state"]["contract"]["strain"] == "N"
    assert k["state"]["completed_tricks"][0]["winner"] == "N"     # szanban a kőr nem üt
