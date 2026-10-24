"""A szerkesztő 2026-10-23-i döntései (17. leosztás és az aranykészlet).

* A hézag-elv nem választ mesterséges (alertos) licitet (#48, #138).
* A 3NT utáni 4m ORKC-t az kérdezi, akinek a partner ígért ALSÓ határával
  sem kockázatos az 5m (27+), a FELSŐ határával szlemerő jön ki (31+).
* A nyitó egyszerű új színe (nem riverz) 12-16 (rossz 17); az ugró új szín
  17-19 (5-5-tel jó 16, legfeljebb 5 vesztő); az ugró saját szín 17-19, jó
  6+ színnel (szinglivel is játszható).
* A negyedik színre a szan-válasz a teljes laperőt mutatja.
"""
import pytest

from test_konvenciok_2026_10_04 import _licit, _pbn, kibic_stand, T7  # noqa: F401


def _h(f, kez, menet, oszto="N"):
    v = _licit(f.sorok, _pbn(kez), menet.split(), oszto=oszto)
    return v["call"] or "P"


@pytest.mark.parametrize("kez, menet, oszto, vart", [
    ("7.AKQ984.AJ5.K65", "P 1D P 1H P 1S P 2C P 2NT P", "N", "3H"),   # #48: nem a 4♦ ORKC; lassan
    ("KJT.QT7.AQJ952.8", "P P 1D P 1S P 2D P 2NT P", "S", "3NT"),     # #138: nem splinter
    ("7.AQ9653.AT4.AJ2", "P 1H P 1NT P", "N", "P"),                    # #254: 3 lappal nem új szín
])
def test_hezag_nem_valaszt_alertos_licitet(kibic_stand, kez, menet, oszto, vart):
    assert _h(kibic_stand, kez, menet, oszto) == vart


@pytest.mark.parametrize("kez, menet, oszto, vart", [
    ("AK876.5.K98.A943", "P 1H P 1S P 2D P 3C P 3NT P", "N", "P"),    # 17. leosztás
    ("A53.A64.K82.T432", "P 1C P 2NT P 3NT P", "E", "P"),             # #97: limitált
    ("2.KQT9.KQ92.J976", "P 1C 1S 2S P 3NT P", "S", "P"),             # #286
    ("7.QJ6.J962.AK876", "1S P 2C P 2S P 3D P 3NT P", "N", "P"),      # #11058
    ("A6.9.KQ862.KJ972", "1S P 2D P 2S P 3C P 3NT P", "N", "P"),      # #13383
    ("AT.Q54.AKJ8.Q972", "1H P 2C P 2H P 2NT P 3NT P", "N", "4C"),    # #7693
    (".32.AQ72.AQ87532", "1S P 2C P 2S P 3D P 3NT P", "N", "4C"),     # #14835: 4 vesztő (misfittel is)
    ("76..AK93.AT98642", "1H P 2C P 2H P 3D P 3NT P", "N", "P"),      # #17858: 5 vesztő
])
def test_3nt_utan_4m_ki_kerdezhet(kibic_stand, kez, menet, oszto, vart):
    assert _h(kibic_stand, kez, menet, oszto) == vart


def test_3nt_utan_4m_moha_peldaja(kibic_stand):
    assert _h(kibic_stand, "32.KQ2.KQ2.AKQ93", " ".join(T7)) == "4C"


@pytest.mark.parametrize("kez, menet, vart", [
    ("A2.AQJ74.KQ32.32", "1H P 1S P", "2D"),     # 16: egyszerű új szín
    ("A2.AQJ74.KQ32.Q2", "1H P 1S P", "3D"),     # 18: ugró új szín
    ("Q2.AQ874.KQJ3.K2", "1H P 1S P", "3D"),     # 17, nem rossz
    ("2.AKQJ74.K32.A32", "1H P 1S P", "3H"),     # 18, jó 6+ kőr
    ("2.KQ9742.A32.A32", "1H P 1S P", "2H"),     # 14, 6 kőr
    ("A2.AKQJ74.K32.32", "1H P 1NT P", "3H"),    # 1M-1NT-3M: 17, jó szín
    ("A2.K2.AKQJ74.432", "1D P 1H P", "3D"),     # 1m-1M-3m
])
def test_nyito_masodik_licitje(kibic_stand, kez, menet, vart):
    assert _h(kibic_stand, kez, menet) == vart


@pytest.mark.parametrize("kez, menet, vart", [
    # a legolcsóbb szan a 3NT: 3NT = az ígért sáv alja, 4NT = a teteje
    ("Q2.AQJT7.Q532.K7", "P 1H P 1S P 2D P 3C P", "3NT"),
    ("2.AQJT7.KQ32.KJ2", "P 1H P 1S P 2D P 3C P", "4NT"),
    # gémforszban, 2NT-vel: gyors-lassú — 2NT plusz erő, 3NT minimum
    ("Q2.KQJT7.Q32.QJ2", "1H P 1S P 2C P 2D P", "3NT"),
    ("K2.KQJT7.Q32.KJ2", "1H P 1S P 2C P 2D P", "2NT"),
])
def test_negyedik_szinre_szan(kibic_stand, kez, menet, vart):
    assert _h(kibic_stand, kez, menet) == vart


@pytest.mark.parametrize("kez, menet, vart", [
    # a negyedik szín kvázi gémforsz (4m-ig): a minimum 3NT-vel (gyors) válaszol
    ("A983.73.KT964.AJ", "P 1D P 1H P 1S P 2C P", "3NT"),
])
def test_negyedik_szin_kvazi_gemforsz(kibic_stand, kez, menet, vart):
    assert _h(kibic_stand, kez, menet) == vart


@pytest.mark.parametrize("kez, vart", [
    ("KT8.J3.QT2.J9873", "P"),       # #73: 7 pont — passz
    ("KT8.Q32.QT2.J987", "P"),       # rossz 8 (üres dáma) — passz
    ("K98.A32.T92.Q987", "2C"),      # 9, egyenletes — invit a Staymanen (MOHA_1NT, 2026-10-24)
    ("J8.QT872.T32.987", "2D"),      # gyenge 5 kőr: transzfer
])
def test_1nt_passz_hatara(kibic_stand, kez, vart):
    assert _h(kibic_stand, kez, "1NT P") == vart


@pytest.fixture(scope="module")
def moha_stand():
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    return feloldas_forrasokbol(g, "MOHA_STAND")[0]


def test_fedokereso_dubloban(moha_stand):
    # #142: 6 vesztő, nincs 3+ lapos 2,5-3 vesztős mellékszín: a fedőt a
    # legolcsóbb 2 vesztős dublóban keresi
    assert _h(moha_stand, "62.AKQJ4.92.AJ93", "P 1H P 2H P") == "2S"


def test_1nt_6_lapos_minorral_invit(kibic_stand):
    # #255: 8 pont, 6 treff, nemes nélkül — nem passz (DD), hanem treff-
    # transzfer (MOHA_1NT, 2026-10-24)
    assert _h(kibic_stand, "86.A3.654.A97632", "1NT P") == "2S"


@pytest.mark.parametrize("kez, vart", [
    ("AQ732.952.K5.AQ6", "1S"),      # #200: 5 pikk, 3 kőr — előbb a pikk
    ("AQ73.952.K52.AQ6", "1S"),      # 4 pikk, 3 kőr — a 4-4 fit jobb az 5-3-nál
    ("AQ7.9532.K52.AQ6", "2C"),      # 4 kőr: felüllicites emelés
])
def test_kozbeszolasra_elobb_a_nemes(kibic_stand, kez, vart):
    assert _h(kibic_stand, kez, "1C 1H P", oszto="N") == vart
