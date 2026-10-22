"""TERMESZETES_ALAP (2026-10-21) és a Leaping Michaels kiterjesztése.

A leosztás: (2♠)-P-(3♠)-4♦-(P)-4♥-(P)-5♣-(P)-? — a kibic passzolt 5♦ helyett.
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol

YAML = Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"


@pytest.fixture(scope="module")
def elv():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    return feloldas_forrasokbol(betolt([YAML]), "MOHA_STAND_ELV")[0]


def _pbn(s):
    return [sz + e for sz, lapok in zip("SHDC", s.split(".")) for e in lapok]


def _licit(sorok, kez, menet, ules="W", oszto="S"):
    from kibic.szolgaltatas.licit import licit_elemzes
    k = {"hand": _pbn(kez), "seat": ules, "dealer": oszto, "vulnerability": "none",
         "auction": menet.split(), "system": "MOHA_STAND_ELV", "test_mode": True,
         "inference": False}
    return licit_elemzes(k, lambda kod, p=None, t=None: (sorok, Parametertar()))


W = "Q93.KQJT93.A54.7"


def test_termeszetes_ket_szin_utan_a_jobb_fitbe(elv):
    # 1♠ után a 4♦ természetes (nincs LM), az 5♣ a második szín: 3 káró > 1 treff
    assert _licit(elv.sorok, W, "1S P 3S 4D P 4H P 5C P")["call"] == "5D"


def test_termeszetes_jobb_minor_fit_maradunk(elv):
    assert _licit(elv.sorok, "Q93.KQJT93.4.A54", "1S P 3S 4D P 4H P 5C P")["call"] == "P"


def test_leaping_michaels_2s_p_3s_utan(elv):
    # (2♠)-P-(3♠)-4♦ = Leaping Michaels: káró + kőr — a kőr a jobb fit
    assert _licit(elv.sorok, W, "2S P 3S 4D P 4H P 5C P")["call"] == "5H"


def test_csak_megertes_nem_leiro_licit_a_hezagban(elv):
    # a természetes-alap sor nem ad a kibicnek "leíró licitet" (3 lapos színre)
    # (2026-10-22 óta itt a 2♠ FOGÁSKÉRÉS a pikkben — a hézag-elvtől, nem leíró licitként)
    v = _licit(elv.sorok, "T94.AJT96.A7.KT8", "P P 1H X 2D P", ules="E", oszto="W")
    assert v["call"] != "2S" or "Természetes" not in (v["explanation"] or "")


# --- Szokatlan 4NT és a természetes szan a blokkra (2026-10-21) --------------

@pytest.mark.parametrize("kez, menet, ules, vart", [
    ("AK.A.KQ863.AKJ32", "2S P 3S", "E", "4NT"),          # a leosztás E-je: két minor
    ("Q93.KQJT93.A54.7", "2S P 3S 4NT P", "W", "5D"),     # választás: a jobb minor
    ("AK2.AQ3.KQ54.Q32", "2S P 3S", "E", "3NT"),          # nem ugró szan: természetes
    ("AKJ.AQ3.KQ54.KQ2", "2S X P 3H P", "W", "3NT"),      # kontra, majd szan
])
def test_szan_a_blokkra(elv, kez, menet, ules, vart):
    assert _licit(elv.sorok, kez, menet, ules=ules)["call"] == vart


# --- 2026-10-21 (2.): közbeszólás = nyitás, Multi-Landy, vesztő-alapú ugrás ----

def _licit_r(kez, menet, ules, oszto, zona="none", rendszer="MOHA_STAND"):
    from kibic.cli.aranykeszlet import yaml_betolto, kez_pbnbol, _keres
    from kibic.szolgaltatas.licit import licit_elemzes
    b = yaml_betolto([str(YAML)])
    return licit_elemzes(_keres(kez_pbnbol(kez), ules, oszto, zona, menet.split(),
                                rendszer, False), b)["call"]


def test_kozbeszolas_nyitas_kvazi_gf_es_varakozo():
    # (1♠)-2♥-(P)-3♦ = mint 1♥-2♦; a 3♥ várakozó (a 3NT nyitva)
    assert _licit_r("5.AJ732.KJ3.K754", "1S 2H P 3D P", "S", "E") == "3H"


def test_multi_landy_valasz_a_hosszabb_nemes():
    assert _licit_r("T94.63.A98762.KT", "P 1NT 2C P", "N", "N") == "2S"


def test_direkt_2nt_a_gyenge_kettesre_16_19():
    assert _licit_r("Q76.543.AT32.AKQ", "P 2S", "W", "W") == "P"


@pytest.mark.parametrize("zona, vart", [("none", "4NT"), ("ns", "P"), ("ew", "4NT")])
def test_szokatlan_4nt_vesztokkel(zona, vart):
    # 5 vesztő: mi bellben, ők mansban legfeljebb 4
    assert _licit_r("J.T5.AQJT7.AQT97", "2S", "N", "E", zona=zona) == vart


# --- 2026-10-21 (3.): Michaels vesztő-alapon, exclusion, kvázi GF vége -------

@pytest.mark.parametrize("kez, menet, ules, oszto, zona, vart", [
    ("AKT54.QJT3.862.6", "P 1D", "W", "E", "ew", "1S"),            # 7 vesztő: nem Michaels
    ("AKJ54.KQJ53.8.62", "P 1D", "W", "E", "none", "2D"),          # 5-5, 5 vesztő: Michaels
    ("AKJ54.KQJ53.8.62", "P 1D 2D P 3S P", "W", "E", "none", "P"), # a 3♠ blokk: passz
    ("AKJ54.AKQ53.8.62", "P 1D 2D P 3S P", "W", "E", "none", "P"), # a 3♠ blokk: passz
])
def test_michaels_vesztokkel(kez, menet, ules, oszto, zona, vart):
    assert _licit_r(kez, menet, ules, oszto, zona=zona) == vart


def test_exclusion_a_21_leosztas():
    assert _licit_r("KT8754.KT83.AKQ.", "1C P 1S P 2C P 3H P 3S P", "S", "N") == "5C"
    assert _licit_r("AQ.AQ.876.KT9763", "1C P 1S P 2C P 3H P 3S P 5C P", "N", "N") == "5NT"
    assert _licit_r("KT8754.KT83.AKQ.", "1C P 1S P 2C P 3H P 3S P 5C P 5NT P", "S", "N") == "7S"


def test_exclusion_valasz_csak_ugrasra():
    # az RKC-válasz (5♣) utáni 5♦ spirál-relé, nem exclusion-válasz
    menet = "1H P 2C P 2H P 3H P 4H P 4S P 5C P 5D P"
    assert _licit_r("KQT.AQ986.T92.93", menet, "N", "N") == "5NT"


def test_kvazi_gemforsz_a_4m_nel_megszunik():
    assert _licit_r("5.AJ732.KJ3.K754", "1H P 2D P 2H P 4D P", "N", "N") == "P"


def test_egyre_ketto_kozbeszolas_utan_varakozo():
    assert _licit_r("AQ5.KQJ93.K4.763", "1C 1H P 2D P", "S", "E") == "2H"


# --- 2026-10-21 (4.): udvariassági kulcslicit, kontrázó emelése, 18+ kontra ----

def test_udvariassagi_kulcslicit_a_partner_kulcslicitjere():
    # 4♣ kulcslicitre 4♥ kulcslicit: gém fölött az ász (5♦) — hajlandóság
    menet = "1C P 1S P 2C P 3H P 3S P 4C P 4H P"
    assert _licit_r("KT8754.KT83.AKQ.", menet, "S", "N") == "5D"


def test_partner_kulcslicitjenek_szinere_nem_kulcslicitelunk():
    menet = "1S P 2D P 2S P 3S P 4C P 4D P 4H P"
    assert _licit_r("T52.AJ62.AKQT32.", menet, "S", "N") == "4S"


def test_negyedik_szin_nem_el_megallapodott_adu_mellett():
    menet = "1C P 1S P 2C P 3H P 3S P 4C P 4H P 5D P"
    assert _licit_r("AQ.AQ.876.KT9763", menet, "N", "N") != "6C"


@pytest.mark.parametrize("kez, menet, vart", [
    ("AQT5.AQJ72.KQ.82", "P P 1D", "X"),             # 18 pont: kontra
    ("AQ5.AQJ72.KQ.832", "P P 1D X P 1S P", "2H"),   # kontra, majd saját szín
    ("AQT5.AQJ72.KQ.82", "P P 1D X P 1S P", "2S"),   # a kontrázó emelése (16-18)
    ("AT9.A95.Q98.AKJ4", "P 1C", "1NT"),              # egyenletes 18: 1NT marad
])
def test_eros_kontra(kez, menet, vart):
    assert _licit_r(kez, menet, "S", "W" if menet.startswith("P P") else "N") == vart


# --- 2026-10-21 (5.): felmentés-kontra, a kvázi gémforsz határa -------------

@pytest.mark.parametrize("kez, menet, ules, oszto, zona, vart", [
    ("Q963.A9754.K32.T", "P P P 1C", "W", "W", "none", "X"),  # 9 pont, 9 nemes lap
    ("Q9862.KJ93.6.K53", "1D", "E", "S", "ew", "X"),
    ("KQJ3.QJ962.93.J2", "1D", "N", "W", "ew", "P"),          # rossz pontok (1 kontroll)
])
def test_felmentes_kontra(kez, menet, ules, oszto, zona, vart):
    assert _licit_r(kez, menet, ules, oszto, zona=zona) == vart


def test_kvazi_gf_hataran_minimummal_passz():
    assert _licit_r("Q.KQJ2.AJ543.T43", "1S P 2D P 2S P 3H P 4D P", "S", "N") == "P"


# --- 2026-10-21 (6.): a Michaels teljes válaszrendje (Michaels.pdf) -----------

@pytest.mark.parametrize("kez, menet, ules, vart", [
    ("Q4.9743.K9754.AQ", "1S 2S P", "W", "4H"),         # 11 pont, 4 lapos adu: gém
    ("Q4.AK43.K9754.AQ", "1S 2S P", "W", "3S"),         # az ő színük: gémforsz, szleminvit
    ("4.QJ873.82.KQJ74", "1S 2S P 3S P", "E", "4H"),    # minimum: a legolcsóbb színem
    ("4.QJ873.82.KQJ74", "1S 2S P 2NT P", "E", "3C"),   # a minorom
])
def test_michaels_valaszok(kez, menet, ules, vart):
    assert _licit_r(kez, menet, ules, "N") == vart


# --- 2026-10-22: fogáskérés az ellenfél (kontrával ígért) színében ----------

@pytest.mark.parametrize("kez, menet, ules, vart", [
    ("T94.AJT96.A7.KT8", "P P 1H X 2D P", "E", "3S"),          # csak ígérték: ugró fogáskérés
    ("Q652.K82.KQJ84.3", "P P 1H X 2D P 3S P", "W", "3NT"),    # fogással 3NT
    ("652.K82.KQJ84.A3", "P P 1H X 2D P 3S P", "W", "4D"),     # anélkül a közös fitbe
    ("KJ985.KJ2.A6.J53", "P P 1S 2C 3C P", "E", "4S"),         # a 3♣ itt emelés, nem fogáskérés
])
def test_fogaskeres(kez, menet, ules, vart):
    assert _licit_r(kez, menet, ules, "W") == vart


def test_fesu_a_szokatlan_2nt_utan_invit():
    # 1♦-(2NT): a fésű szerint a természetes 3♦ PONTOSAN invit (9-12)
    assert _licit_r("K854.Q83.AQ94.75", "P P P 1D 2NT", "S", "E", zona="both") == "3D"
