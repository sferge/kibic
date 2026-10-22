"""FOLYTATÁS "mint X után" (2026-09-30): 2♣-2♦-2NT -> mint a 2NT után
(ponteltolással), 2M-2NT -> mint az 1M-2NT után (az ígérthez mért
minimummal); Puppet Stayman; önállóan játszható adu."""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


def _pbn(s):
    return [sz + e for sz, l in zip("SHDC", s.split(".")) for e in l]


@pytest.fixture(scope="module")
def kartya():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "KIBIC_STAND")
    return f


def _licit(f, pbn, menet, ules):
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N",
                       "vulnerability": "none", "auction": menet,
                       "system": "KIBIC_STAND", "test_mode": True},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    return v["call"] or "P"


A2 = ["2C", "P", "2D", "P", "2NT", "P"]


def test_2c_2d_2nt_mint_a_2nt_utan(kartya):
    # 5 pont, 3-3 nemes: Puppet a 2NT-ág szabályából (2 pont eltolással)
    assert _licit(kartya, "K32.Q32.5432.432", A2, "S") == "3C"
    assert _licit(kartya, "32.32.K5432.Q432", A2, "S") == "3NT"


@pytest.mark.parametrize("pbn, vart", [
    ("AKQ32.KQ2.AK2.K2", "3S"),      # 5-ös pikk
    ("AK32.KQ2.AK2.KQ2", "3D"),      # 4-es nemes, nincs 5-ös
    ("AK2.KQ2.AK32.KQ2", "3NT"),     # nincs 4-es nemes sem
])
def test_puppet_a_2c_2d_2nt_utan(kartya, pbn, vart):
    assert _licit(kartya, pbn, A2 + ["3C", "P"], "N") == vart


P3D = ["2NT", "P", "3C", "P", "3D", "P"]


@pytest.mark.parametrize("pbn, vart", [
    ("KJ32.Q32.K432.32", "3H"),      # nincs 4 kőr (4 pikk van)
    ("Q32.QJ2.K432.J32", "3H"),      # nincs 4 kőr (4 pikk sincs)
    ("Q32.KJ32.K432.32", "3S"),      # nincs 4 pikk, van 4 kőr
    ("KJ32.QJ32.K43.32", "3NT"),     # mindkét nemes négyes
])
def test_puppet_tagadas(kartya, pbn, vart):
    assert _licit(kartya, pbn, P3D, "S") == vart


def test_puppet_tagadas_folytatas(kartya):
    # 3♥ után a szanos nem ugrik gémre: 4 pikkel 3♠, különben 3NT
    assert _licit(kartya, "AK32.KQ2.AK2.KQ2", P3D + ["3H", "P"], "N") == "3S"
    assert _licit(kartya, "AK2.KQ32.AK32.K2", P3D + ["3H", "P"], "N") == "3NT"
    # a 3♠-ra a válaszoló 4 pikkel gém, különben 3NT
    assert _licit(kartya, "KJ32.Q32.K432.32", P3D + ["3H", "P", "3S", "P"], "S") == "4S"
    assert _licit(kartya, "Q32.QJ2.K432.J32", P3D + ["3H", "P", "3S", "P"], "S") == "3NT"
    # a 3NT-re (mindkét nemes) a szanos gémet mond vagy passzol
    assert _licit(kartya, "AK2.KQ32.AK32.K2", P3D + ["3NT", "P"], "N") == "4H"
    assert _licit(kartya, "AK32.KQ2.AK2.KQ2", P3D + ["3NT", "P"], "N") == "4S"


def test_kenyszertar_az_atiranyitott_menetben():
    """A partner 3♣-ját (Puppet) a 2♣-2♦-2NT után is érti a kibic, és a
    pontsávját visszatolja (2NT-3♣: 4+ -> itt 2+)."""
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.propagal import Propagalo
    from kibic.szolgaltatas.licit import _menet
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "KIBIC_STAND")
    er = Propagalo(f.sorok, Parametertar()).kenyszertar(
        _menet(A2 + ["3C", "P"], "N"), oszto="N")
    assert not er.nem_ertett
    assert er.kenyszertar["S"].pont_min == 2


@pytest.mark.parametrize("pbn, vart", [
    ("KQJ432.2.Q32.432", "3H"),      # 8 pont a 4-10-es sáv felső felében: szingli kőr
    ("KQ9432.2.Q32.432", "3C"),      # 7 pont: minimum (az ígérthez mérve)
])
def test_2m_2nt_mint_az_1m_2nt_utan(kartya, pbn, vart):
    assert _licit(kartya, pbn, ["2S", "P", "2NT", "P"], "N") == vart


def test_onallo_adu_eselyek():
    from kibic.motor.adu_esely import legfeljebb_egy_veszto
    R = "23456789TJQKA"

    def p(s):
        return legfeljebb_egy_veszto(tuple(R.index(c) for c in s))
    assert abs(p("AKQJ32") - 0.927) < 0.005
    assert abs(p("AKQ432") - 0.622) < 0.005
    assert abs(p("AKJ5432") - 0.517) < 0.005
    assert abs(p("AK765432") - 0.678) < 0.005


@pytest.mark.parametrize("pbn, vart", [
    ("AQ432.K32.K32.32", "4S"),      # 12 pont: minimum (11-21 sáv 35%-a: 11-14)
    ("AQ432.K2.K32.K32", "3S"),      # 15 pont, nincs rövidség: nem minimális
])
def test_1m_2nt_minimum_a_sav_35_szazaleka(kartya, pbn, vart):
    assert _licit(kartya, pbn, ["1S", "P", "2NT", "P"], "N") == vart


def _licit_zona(f, pbn, menet, ules, zona):
    from kibic.szolgaltatas.licit import licit_elemzes
    v = licit_elemzes({"hand": _pbn(pbn), "seat": ules, "dealer": "N",
                       "vulnerability": zona, "auction": menet,
                       "system": "KIBIC_STAND", "test_mode": True},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    return v["call"] or "P"


@pytest.mark.parametrize("zona, vart", [
    ("none", "2NT"),                 # mansban: sok adu + szingli -> kérdez (mentés is)
    ("ew", "2NT"),                   # mans bell ellen: ugyanígy
    ("ns", "4S"),                    # bellben: nincs gémesély a 2NT-hez
])
def test_2m_2nt_a_szkorhelyzettol_fugg(kartya, zona, vart):
    assert _licit_zona(kartya, "QJ32.2.K5432.432", ["2S", "P"], "S", zona) == vart


def test_2m_2nt_utan_gem_jo_fittel(kartya):
    # az induló szingli treffje (3NT) a mi xxx treffünkkel szemben: 2 fedő,
    # 5 vesztőből 3 marad: gém
    menet = ["2S", "P", "2NT", "P", "3NT", "P"]
    assert _licit_zona(kartya, "AQJ2..AK7654.432", menet, "S", "none") == "4S"
    # ugyanez 7 vesztővel: 5 marad — de a 3NT mesterséges, a gémforsz
    # teljesült: a megállapodott aduban a gém (MOHA_SZLEM, 2026-10-04)
    assert _licit_zona(kartya, "QJ32.2.AK432.432", menet, "S", "none") in ("P", "4S")
    # szingli kőr a mi szinglink mellett: nincs jó fit, leállás 3♠
    menet = ["2S", "P", "2NT", "P", "3H", "P"]
    assert _licit_zona(kartya, "QJ32.2.K5432.432", menet, "S", "none") == "3S"
