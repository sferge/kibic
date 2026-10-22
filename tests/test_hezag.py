"""
A hézag-elv (2026-10-03, Moha): ha sem szabály, sem elv nem javasol licitet,
a közös erő és a kényszer dönt — nem a vak passz. A kiosztások a tanári
asztalról és a generált sorokból jöttek.
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


def _pbn(s):
    return [sz + e for sz, l in zip("SHDC", s.split(".")) for e in l]


@pytest.fixture(scope="module")
def bet():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    tar: dict = {}

    def b(kod, par=None, teszt=None):
        if kod not in tar:
            tar[kod] = feloldas_forrasokbol(g, kod)[0].sorok
        return tar[kod], Parametertar()
    return b


def _l(bet, pbn, menet, ules, oszto, zona="none", **extra):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes(dict({"hand": _pbn(pbn), "seat": ules, "dealer": oszto,
                               "vulnerability": zona, "auction": menet,
                               "system": "KIBIC_STAND", "test_mode": True}, **extra), bet)


def test_ertetlen_partnerlicit_utan_vissza_a_fitbe(bet):
    # 2♥ – 2NT (fitet jelöl) – 3♣ (minimum) – 3♠ (nincs rá szabály): a kőr fitbe,
    # a 3♠ fölött a legolcsóbb: 4♥. (A 3♦ 2026-10-04 óta rövidségkérdés —
    # MOHA_JACOBY —, arra a szingli pikk 3♠.)
    # (2026-10-04 óta a MOHA_SZLEM is a kártyán: a megállapodott aduban a gém
    # elvből jön; a hézag-elv csak a kikapcsolt elvek mellett dönt)
    v = _l(bet, "9.QJ953.QT7.7652", ["2H", "P", "2N", "P", "3C", "P", "3S", "P"], "S", "S", "ew")
    assert v["call"] == "4H" and v["source"] in ("HEZAG", "ELV")
    v = _l(bet, "9.QJ953.QT7.7652", ["2H", "P", "2N", "P", "3C", "P", "3D", "P"], "S", "S", "ew")
    assert v["call"] == "3S" and v["source"] != "HEZAG"


def test_kenyszerben_nem_passzol(bet):
    # 1♥ – 1♠ – 3♥ – 3♠: 17 pont, a partner forszolt; az alsó határral is gém
    v = _l(bet, "6.AKJ963.AJ3.KJ3", ["1H", "P", "1S", "P", "3H", "P", "3S", "P"], "N", "N")
    assert v["call"] not in ("P", None)


def test_geminvitre_gem(bet):
    # 1♣ – 1♦ – 1♥ – 3♦ (invit): 14 ponttal 3NT
    v = _l(bet, "AQ95.A432.A.T965", ["P", "1C", "P", "1D", "P", "1H", "P", "3D", "P"],
           "N", "W", "both")
    assert v["call"] == "3NT" and v["source"] == "HEZAG"


def test_gemforsz_gemszinten_teljesult(bet):
    # 2♠ – 2NT – 3NT (mesterséges): gém alatt nincs; a megállapodott aduban
    # (MOHA_SZLEM) a gém 4♠ — a mesterséges 3NT nem végkontraktus
    v = _l(bet, "QJ32.2.AK432.432", ["2S", "P", "2NT", "P", "3NT", "P"], "S", "N")
    assert v["call"] in ("P", None, "4S")


def test_kikapcsolhato(bet):
    # 1♥ – 1♠ – 2♥ – 4♦ (nincs rá szabály, nincs megállapodott adu)
    v = _l(bet, "K2.AQJ953.Q7.765", ["1H", "P", "1S", "P", "2H", "P", "4D", "P"], "N", "N",
           "none", gap_principle=False)
    assert v["source"] != "HEZAG"


def test_eros_lappal_nem_passzol_gem_alatt(bet):
    # 1♥ (2♠) X (3♠) P (P): 22 ponttal a passz-elv nem passzolhat (gémesély)
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn("A2.KQ3.AKJ4.KQ32"), "seat": "S", "dealer": "N",
                       "vulnerability": "none", "auction": ["1H", "2S", "X", "3S", "P", "P"],
                       "system": "MOHA_STAND", "test_mode": True}, bet)
    assert v["call"] not in ("P", None) and v["source"] == "HEZAG"


def test_szan_fogas_nelkul_nem(bet):
    # fogás nélkül a pikkben nem 3NT
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn("Q2.K3.AJ542.Q432"), "seat": "S", "dealer": "N",
                       "vulnerability": "none", "auction": ["1H", "2S", "X", "3S", "P", "P"],
                       "system": "MOHA_STAND", "test_mode": True}, bet)
    assert v["call"] != "3NT"


def test_jatszhato_4_3_fit_rovidseggel():
    from kibic.domain import Kez
    from kibic.motor.hezag import Hezag
    from kibic.motor.helyzet import Allas
    a = Allas(ules="S", oszto="N", licitek=[{"ules": "N", "licit": "1H"}, {"ules": "E", "licit": "P"}])
    a.kenyszertar["N"].szukit_hossz("H", 4)
    a.kenyszertar["N"].szukit_hossz("S", 0, 3)
    a.kenyszertar["N"].szukit_hossz("D", 0, 3)
    a.kenyszertar["N"].szukit_hossz("C", 0, 3)
    rovid = Hezag(Kez.pbn_bol("KQ32.Q32.K5432.2"), a, None, a.licitek, "S", "N", [])
    hosszu = Hezag(Kez.pbn_bol("KQ3.Q32.K543.432"), a, None, a.licitek, "S", "N", [])
    assert rovid.jatszhato("H") and not hosszu.jatszhato("H")


MENET_7 = ["P", "1S", "P", "2D", "2H", "P", "P", "3D", "3H", "P", "P", "X", "4C", "P", "P", "X", "P"]


def _moha(bet, pbn, menet, ules, oszto, zona="both"):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": oszto,
                          "vulnerability": zona, "auction": menet,
                          "system": "MOHA_STAND", "test_mode": True}, bet)


def test_buntetes_passz_a_partner_kontrajara(bet):
    # 2026-10-04, a tanári asztal 7. leosztása: a partner büntetőre kontrázta a
    # 4♣-t (gémforsz menetben); jó védekezéssel bent hagyjuk
    v = _moha(bet, "AKJ72.AQ9.43.QT5", MENET_7, "W", "S")
    assert v["call"] == "P" and v["source"] == "HEZAG" and v["gap"]["rule"] == "5"
    # gyenge védekezéssel (hosszú pikk, semmi más) a saját gémünk
    v = _moha(bet, "AKQJ972.5.43.T95", MENET_7, "W", "S")
    assert v["call"] != "P"


def test_gemforsz_menetben_fogassal_3nt(bet):
    # ugyanott, a 3♥ után: kőrfogással 3NT (nem a passz)
    v = _moha(bet, "AKJ72.AQ9.43.QT5", MENET_7[:9], "W", "S")
    assert v["call"] == "3NT"


def test_dd_mintavetel_donthet_a_vegkontraktusrol():
    # ha van szimuláció, a passz és a javítás közül a DD-minta dönt
    from kibic.domain import Kez
    from kibic.motor.hezag import Hezag
    from kibic.motor.helyzet import Allas
    menet = [{"ules": "N", "licit": "1S"}, {"ules": "E", "licit": "P"},
             {"ules": "S", "licit": "1NT"}, {"ules": "W", "licit": "P"},
             {"ules": "N", "licit": "2D"}, {"ules": "E", "licit": "P"}]
    a = Allas(ules="S", oszto="N", licitek=menet)
    a.kenyszertar["N"].szukit_hossz("S", 5)
    a.kenyszertar["N"].szukit_hossz("D", 4)
    kerdes = []

    def szim(hivasok):
        kerdes.append(list(hivasok))
        return {"best": "2S", "samples": 40, "options": {"P": 90, "2S": 120}}
    h = Hezag(Kez.pbn_bol("Q32.K5432.32.432"), a, None, menet, "S", "N",
              ["P", "2H", "2S", "2NT", "3C"], vegkontraktus=szim)
    d = h._lezaras("3", "teszt", False)
    assert d.licit == "2S" and "DD-minta" in d.indok
    assert kerdes and kerdes[0][0] == "P" and "2S" in kerdes[0]


def test_megallapodott_nemes_adu_a_3nt_helyett(bet):
    # 1♥-1♠-3♥-3♠ (GF, fit) – 3NT (nincs rá szabály): a kőr adu megállapodott -> 4♥
    v = _moha(bet, "AQ32.K4.AK32.Q32", ["1H", "P", "1S", "P", "3H", "P", "3S", "P", "3NT", "P"],
              "S", "N", "none")
    # 18 pont a 16-17 mellé: a kőr adu megállapodott — gém vagy kulcslicit (MOHA_SZLEM)
    assert v["call"] in ("4H", "4C", "4D")


def test_1h_1s_2h_3nt_csak_16_pontig(bet):
    # 17 ponttal és két kőrrel nem „leállás” 3NT (Moha: szlemgyanú)
    v = _moha(bet, "AQ32.K4.AJ32.QJ2", ["1H", "P", "1S", "P", "2H", "P"], "S", "N", "none")
    assert v["call"] != "3NT"
    v = _moha(bet, "AQ32.K4.AJ32.Q32", ["1H", "P", "1S", "P", "2H", "P"], "S", "N", "none")
    assert v["call"] == "3NT"
