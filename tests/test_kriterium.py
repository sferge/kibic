"""Kritérium-motor: paraméterek háromszintű feloldása, összetett feltételek."""
import pytest

from kibic.domain import Kez
import kibic.domain.ertekelo  # noqa: F401
from kibic.motor.kriterium import (Kriterium, KriteriumKeszlet, Parameter,
                                   Parametertar, ParameterHiba)


@pytest.fixture
def pt():
    return Parametertar(parameterek={
        "NYITAS_MIN": Parameter("NYITAS_MIN", "Nyitási minimum", 12, "HCP", 10, 14, "nyitas"),
        "NYITAS_ZAR": Parameter("NYITAS_ZAR", "Zar-küszöb", 26, "ZAR", 24, 30, "nyitas"),
        "NYITAS_LTC": Parameter("NYITAS_LTC", "LTC-küszöb", 7, "LTC", 6, 8, "nyitas"),
        "1NT_MIN": Parameter("1NT_MIN", "1 szan min", 15, "HCP", 12, 16),
        "1NT_MAX": Parameter("1NT_MAX", "1 szan max", 17, "HCP", 14, 19),
    })


@pytest.fixture
def nyitas():
    """HCP kötelező; a Zar és az LTC közül legalább az egyik."""
    return KriteriumKeszlet("NYITAS_ERO", "Nyitási erő", [
        Kriterium("HCP", ">=", "NYITAS_MIN", kotelezo=True),
        Kriterium("ZAR", ">=", "NYITAS_ZAR"),
        Kriterium("LTC", "<=", "NYITAS_LTC"),
    ], min_teljesul=1)


def test_parameter_haromszintu_feloldas(pt):
    assert pt.ertek("NYITAS_MIN") == 12 and pt.honnan["NYITAS_MIN"] == "ALAP"
    pt.rendszer_ertek["NYITAS_MIN"] = 13
    assert pt.ertek("NYITAS_MIN") == 13 and pt.honnan["NYITAS_MIN"] == "RENDSZER"
    pt.par_ertek["NYITAS_MIN"] = 11
    assert pt.ertek("NYITAS_MIN") == 11 and pt.honnan["NYITAS_MIN"] == "PAR"


def test_ismeretlen_parameter_hibat_dob(pt):
    with pytest.raises(ParameterHiba):
        pt.ertek("NINCS_ILYEN")


def test_kiegyensulyozott_12_pont_nem_nyit(pt, nyitas):
    """4-3-3-3, 12 HCP: a kötelező HCP megvan, de sem Zar, sem LTC."""
    k = Kez.pbn_bol("AQ32.K54.Q76.J32")
    assert nyitas.kiertekel(k, pt).teljesul is False


def test_elosztasos_11_pont_nyit_alacsonyabb_kuszobbel(pt, nyitas):
    k = Kez.pbn_bol("AQ9765.KQ854.3.2")   # 11 HCP, 6-5-1-1
    assert nyitas.kiertekel(k, pt).teljesul is False          # 12-es küszöb
    pt2 = pt.masolat_felulirassal(NYITAS_MIN=11)
    assert nyitas.kiertekel(k, pt2).teljesul is True


def test_min_teljesul_nulla_eseten_csak_a_kotelezo_szamit(pt):
    csak_hcp = KriteriumKeszlet("X", "Csak HCP",
                                [Kriterium("HCP", ">=", "NYITAS_MIN", kotelezo=True)],
                                min_teljesul=0)
    assert csak_hcp.kiertekel(Kez.pbn_bol("AQ32.K54.Q76.J32"), pt).teljesul


def test_kozott_operator(pt):
    szan = KriteriumKeszlet("1NT", "1 szan", [
        Kriterium("HCP", "KOZOTT", "1NT_MIN", param_kod2="1NT_MAX", kotelezo=True)
    ], min_teljesul=0)
    assert szan.kiertekel(Kez.pbn_bol("AQ32.KJ4.Q76.KJ3"), pt).teljesul       # 16
    assert not szan.kiertekel(Kez.pbn_bol("AQ32.K54.Q76.J32"), pt).teljesul   # 12


def test_indoklas_ember_olvashato(pt, nyitas):
    e = nyitas.kiertekel(Kez.pbn_bol("AQ9765.KQ854.3.2"),
                         pt.masolat_felulirassal(NYITAS_MIN=11))
    m = e.magyarazat()
    assert "HCP=11" in m and "ZAR=" in m and "LTC=" in m
