"""A szerkesztő 2026-10-04-i megjegyzései (7., 8., 9. leosztás).

* WALSH: 1♣-1♦-1NT után 6+ károval 2♦ = javítás (leállás), 3♦ = géminvit;
  a 2NT csak 5 káróval.
* MOHA_JACOBY: 1M/2M-2NT-3♣ után a 3♦ = gémforsz, rövidségkérdés; válasz
  4M = nincs rövidség, különben az eredeti válaszok egy lépcsővel feljebb.
* MOHA_3NT_4M: a partner 3NT-je után a 4m ORKC; 1. lépcső = "tetszik".
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol


@pytest.fixture(scope="module")
def kibic_stand():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    f, _ = feloldas_forrasokbol(g, "KIBIC_STAND")
    return f


def _pbn(s):
    return [sz + e for sz, lapok in zip("SHDC", s.split(".")) for e in lapok]


def _licit(sorok, kez, menet, oszto="N", zona="none"):
    from kibic.szolgaltatas.licit import licit_elemzes
    sorrend = "NESW"
    ules = sorrend[(sorrend.index(oszto) + len(menet)) % 4]
    return licit_elemzes({"hand": kez, "seat": ules, "dealer": oszto,
                          "vulnerability": zona, "auction": menet,
                          "system": "KIBIC_STAND", "test_mode": True},
                         lambda k, p, t=None: (sorok, Parametertar()))


WALSH_1NT = ["1C", "P", "1D", "P", "1NT", "P"]


@pytest.mark.parametrize("kez, vart", [
    ("J2.KQ.AJ98765.32", "3D"),        # 9. leosztás: 7 káró, 11 FP — kvázi GF színben
    ("32.J2.KJ9876.432", "2D"),        # gyenge, 6 káró: javítás
    ("32.K32.AQ432.K32", "2NT"),       # 5 káró, 12: marad a 2NT
])
def test_walsh_6_karo(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), WALSH_1NT)
    assert (v["call"] or "P") == vart


def test_walsh_3d_alertos_es_kenyszerito(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("J2.KQ.AJ98765.32"), WALSH_1NT)
    assert v["alert"] and "4♦-ig" in v["alert"]["text"]


@pytest.mark.parametrize("kez, vart", [
    ("KQ2.A32.32.KJ432", "3NT"),       # fogás mindkét nemesben
    ("Q32.K32.32.AJ432", "3NT"),       # minimummal is (4♦-ig kötelező)
    ("432.AQ2.Q2.KJ432", "3H"),        # csak kőrfogás: bemondja
    ("AQ2.432.Q2.KJ432", "3S"),        # csak pikkfogás
    ("432.432.AQ.AKJ32", "4D"),        # egyikben sem: 4♦ (nem 5♦)
])
def test_walsh_3d_utan_a_nyito(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), WALSH_1NT + ["3D", "P"])
    assert (v["call"] or "P") == vart


@pytest.mark.parametrize("kez, vart", [
    ("KQ2.2.AQJ8765.32", "3NT"),       # pikkfogás
    ("2.KQ2.AQJ8765.32", "5D"),        # nincs pikkfogás, de pikkben rövid
    ("32.K2.AQJ876.Q32", "4D"),        # nincs pikkfogás
])
def test_walsh_3d_3h_utan_az_invitalo(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), WALSH_1NT + ["3D", "P", "3H", "P"])
    assert (v["call"] or "P") == vart


def test_walsh_2d_es_4d_utan_passz(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("KQ2.A32.32.KJ432"), WALSH_1NT + ["2D", "P"])
    assert (v["call"] or "P") == "P"
    v = _licit(kibic_stand.sorok, _pbn("432.432.AQ.AKJ32"),
               WALSH_1NT + ["3D", "P", "4D", "P"])
    assert (v["call"] or "P") == "P"


# --- MOHA_JACOBY: 3♣ után 3♦ rövidségkérdés -------------------------------

GYENGE_KETTES = ["2H", "P", "2NT", "P", "3C", "P"]


def test_jacoby_3d_kerdes(kibic_stand):
    # 4 vesztő a partner fedői előtt: a gém a rövidségén múlik
    v = _licit(kibic_stand.sorok, _pbn("AKQ2.A32.AKQ2.32"), GYENGE_KETTES)
    assert v["call"] == "3D"
    assert v["alert"]


@pytest.mark.parametrize("kez, vart", [
    ("Q32.KJ9876.32.32", "4H"),        # 8. leosztás: nincs rövidség
    ("Q32.KJ9876.3.432", "3H"),        # szingli káró
    ("3.KJ9876.Q432.32", "3S"),        # szingli pikk
    ("Q32.KJ9876.432.3", "3NT"),       # szingli treff
    ("Q432.KJ9876.432.", "4C"),        # sikén treff
    ("Q432.KJ9876..432", "4D"),        # sikén káró
    (".KJ9876.Q432.432", "3S"),        # kőr adunál a pikk sikén is 3♠
])
def test_jacoby_3d_valaszok_gyenge_kettes_utan(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), GYENGE_KETTES + ["3D", "P"])
    assert (v["call"] or "P") == vart


def test_jacoby_3d_valasz_1s_utan(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("AKJ32.Q32.3.Q432"),
               ["1S", "P", "2NT", "P", "3C", "P", "3D", "P"])
    assert v["call"] == "3S"            # pikk adunál a 3♠ = szingli káró
    v = _licit(kibic_stand.sorok, _pbn("AKJ32..Q32.Q5432"),
               ["1S", "P", "2NT", "P", "3C", "P", "3D", "P"])
    assert v["call"] == "4H"            # sikén kőr


# --- MOHA_3NT_4M ------------------------------------------------------------

T7 = ["1S", "P", "2C", "P", "3NT", "P"]


def test_3nt_4c_tetszik_7_leosztas(kibic_stand):
    # 1♠-2♣-3NT-4♣: a 2♣ a 3NT előtt (indirekt ígéret) → A-ág, ORKC treffben;
    # 12 FP, a pontok gyorsütésekben, 3 treff + dubló: "tetszik"
    v = _licit(kibic_stand.sorok, _pbn("AKT32.A2.432.J32"), T7 + ["4C", "P"])
    assert v["call"] == "4D"
    assert v["alert"] is None           # 3NT fölött nincs alert


def test_3nt_4c_kerdes(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("32.AK2.KQ2.AKQ93"), T7)
    assert v["call"] == "4C"


def test_3nt_4c_rele_es_kulcslap(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("32.AK2.KQ2.AKQ93"), T7 + ["4C", "P", "4D", "P"])
    assert v["call"] == "4H"            # relé: kulcslapkérdés treff aduval
    v = _licit(kibic_stand.sorok, _pbn("AKT32.Q2.A32.J32"),
               T7 + ["4C", "P", "4D", "P", "4H", "P"])
    assert v["call"] == "5C"            # 2 kulcslap (♠A, ♦A), treff dáma nélkül


def test_3nt_4c_nem_tetszik_kulcslap(kibic_stand):
    # minimum, kevés gyorsütés: nem "tetszik" → kulcslap-válasz (A-ág: 4♠ = 1/4)
    v = _licit(kibic_stand.sorok, _pbn("KQT32.Q2.A32.J32"), T7 + ["4C", "P"])
    assert v["call"] == "4S"


def test_kulcs_adu_kifejezes():
    from kibic.impex.rendszer_yaml import forras_dict
    g = {}
    forras_dict({"rendszer": {"kod": "TKA", "fajta": "KONVENCIO"}, "szabalyok": [
        {"minta": "1S-2C-3NT-4C-4H", "kulcslapok": [0, 3], "kulcs_adu": "C"}]}, "t.yaml", g)
    s = g["TKA"].sorok[0]
    assert "treff király" in s.feltetel_szoveg


def test_3nt_4c_a_ag_treff_igerve(kibic_stand):
    # 1♦-1♠-2♣ (5 káró + 4 treff ígérve) - 3NT - 4♣: ORKC treffben, a 2. lépcső 0/3
    menet = ["1D", "P", "1S", "P", "2C", "P", "3NT", "P", "4C", "P"]
    v = _licit(kibic_stand.sorok, _pbn("AQ432.KQ2.J32.32"), menet)
    assert v["call"] == "4S"            # A-ág: 4♥ 0/3, 4♠ 1/4 (♠A)
    v = _licit(kibic_stand.sorok, _pbn("AQ432.KQ2.J32.K2"), menet)
    assert v["call"] == "4NT"           # 2 kulcslap (♠A, ♣K), treff dáma nélkül


def test_3nt_4d_orkc_karo(kibic_stand):
    # 1♠-2♦(5+ káró)-3NT: káróval a 4♦ a kérdés
    v = _licit(kibic_stand.sorok, _pbn("A2.K2.AKQ932.K32"), ["1S", "P", "2D", "P", "3NT", "P"])
    assert v["call"] == "4D"


# --- MOHA_SPIRAL ------------------------------------------------------------

KERDEZO = "32.AK2.KQ2.AKQ93"          # 3 kulcslap (♥A, ♣A, ♣K), a treff dáma nála
RELE = T7 + ["4C", "P", "4D", "P", "4H", "P"]


def test_spiral_kulcslap_utan_a_kerdezo_relez(kibic_stand):
    # a partner: 2 kulcslap, dáma nélkül (5♣) → nincs hiány; a ♠K kell a
    # nagyszlemhez: relé (L1, az adu és a 4NT kimarad) = 5♦
    v = _licit(kibic_stand.sorok, _pbn(KERDEZO), RELE + ["5C", "P"])
    assert v["call"] == "5D" and v["source"] == "SPIRAL"


@pytest.mark.parametrize("kez, vart", [
    ("AKT32.Q2.A32.J32", "5S"),        # ♠K megvan, a ♥K nincs: L2
    ("AQT32.J2.A32.J32", "5H"),        # a ♠K nincs: L1
])
def test_spiral_valasz(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), RELE + ["5C", "P", "5D", "P"])
    assert v["call"] == vart and v["source"] == "SPIRAL"


@pytest.mark.parametrize("valasz, vart", [
    ("5S", "7C"),                      # a ♠K megvan: nagyszlem
    ("5H", "6C"),                      # a ♠K nincs: kis szlem
])
def test_spiral_kerdezo_dont(kibic_stand, valasz, vart):
    v = _licit(kibic_stand.sorok, _pbn(KERDEZO), RELE + ["5C", "P", "5D", "P", valasz, "P"])
    assert v["call"] == vart and v["source"] == "SPIRAL"


def test_spiral_ket_kulcslap_hianyzik(kibic_stand):
    # a partner 4♠ = 1/4 (az A-ágon), nekem 2 → 3 kulcslap: leállás 5♣
    v = _licit(kibic_stand.sorok, _pbn("32.KQ2.KQ2.AKQ93"), T7 + ["4C", "P", "4S", "P"])
    assert v["call"] == "5C" and v["source"] == "SPIRAL"


def test_spiral_leallas_utan_passz(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("AKT32.Q2.A32.J32"),
               RELE + ["5C", "P", "6C", "P"])
    assert v["call"] == "P" and v["source"] == "SPIRAL"


def test_spiral_kor_adu_rkc(kibic_stand):
    # kőr adu, 4♠ RKC, 5♣ (1/4): a kérdező 4 kulcslappal → 5 megvan; a
    # relé 5♦ (L1) az adu dámát kérdezi
    from kibic.motor.spiral import tetelek
    t, r = tetelek("H", False)
    assert t[0] == ("Q", "H") and t[1] == ("K", "S") and r == [0, 1, 4, 7]


@pytest.mark.parametrize("menet, kez, vart", [
    # a Stayman 2♣ nem treffszín → B-ág: a 4♠ a 0/3 (a 3. lépcső)
    (["1NT", "P", "2C", "P", "2D", "P", "3NT", "P", "4C", "P"], "KQ32.K32.Q432.Q2", "4S"),
    # az 1♠ utáni 2♣ szín (lehet rövid is, de természetes) → A-ág: 4♠ = 1/4
    (["1S", "P", "2C", "P", "3NT", "P", "4C", "P"], "KQT32.Q2.A32.J32", "4S"),
])
def test_3nt_4c_csak_szinkent_mondott_minor(kibic_stand, menet, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), menet)
    assert v["call"] == vart


def test_stayman_2c_nem_szin(kibic_stand):
    # a propagálás beírja: a Stayman 2♣ nem ígér treffet, az 1M-2♣ igen (2+)
    from kibic.szolgaltatas.licit import licit_elemzes
    menet = ["1NT", "P", "2C", "P", "2D", "P", "3NT", "P"]
    v = _licit(kibic_stand.sorok, _pbn("AKQ.K32.Q32.AK32"), menet)
    assert v is not None
    from kibic.szolgaltatas.licit import _menet, vonalas_propagalo
    licitek = _menet(menet, "N")
    prop = vonalas_propagalo(kibic_stand.sorok, Parametertar(), None, "N", None, {})
    prop.kenyszertar(licitek, oszto="N")
    assert licitek[2]["szin_hossz_min"] == 0


# --- 1M-2♣ gémforsz után a nyitó (a szerkesztő, 2026-10-04) ----------------

@pytest.mark.parametrize("menet, kez, vart", [
    (["1S", "P", "2C", "P"], "AKJ32.Q2.K32.Q32", "2S"),     # 2. leosztás-típus: ♥-ben nincs fogás → várakozó 2♠
    (["1S", "P", "2C", "P"], "AQ432.K2.K32.Q32", "3NT"),    # fogás ♥ ♦ ♣, nincs plusz erő (14)
    (["1S", "P", "2C", "P"], "AQJ32.K2.KQ2.Q32", "2NT"),    # ugyanez plusz erővel
    (["1S", "P", "2C", "P"], "AQ432.KJ32.32.Q2", "2H"),     # 4-es kőr, nincs plusz erő
    (["1S", "P", "2C", "P"], "AQ432.AKJ2.32.Q2", "3H"),     # 4-es kőr, plusz erő
    (["1H", "P", "2C", "P"], "AQ32.AKJ32.32.Q2", "2S"),     # riverz
    (["1H", "P", "2C", "P"], "AQ32.QJ432.32.Q2", "2H"),     # 4 pikk plusz erő nélkül: várakozó
    (["1H", "P", "2C", "P"], "Q32.AQ432.K2.Q32", "3NT"),
    (["1H", "P", "2C", "P"], "2.AKJ932.Q32.KQ3", "3S"),     # önsplinter: 0-1 pikk, 6+ kőr
    (["1H", "P", "2D", "P"], "2.AKJ932.Q32.KQ3", "3S"),     # 2♦ után is (gémforsz)
    (["1S", "P", "2D", "P"], "AQ432.K2.Q32.Q32", "3NT"),    # fogás ♥ ♣ (a partner ♦-je felér egy fogással)
    (["1S", "P", "2D", "P"], "AQ432.K2.KJ32.K2", "3D"),     # plusz erő, 4+ káró — gémforsz marad
])
def test_1m_2c_utan_a_nyito(kibic_stand, menet, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), menet)
    assert v["call"] == vart


@pytest.mark.parametrize("kez, vart", [
    ("KJ32.Q2.K432.432", "4H"),        # kőr fit, nincs szlemérdek: gyors
    ("AKJ32.Q2.AK32.32", "3S"),        # kőr fit, szlemérdek: lassú
])
def test_1h_1s_3h_utan(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), ["1H", "P", "1S", "P", "3H", "P"])
    assert v["call"] == vart


def test_1h_1s_3h_3s_utan_a_kulcslicitet_erti(kibic_stand):
    # 1. leosztás-típus: a partner 4♦-je kulcslicit (MOHA_SZLEM), nem érthetetlen
    v = _licit(kibic_stand.sorok, _pbn("AKJ32.Q2.AK32.32"),
               ["1H", "P", "1S", "P", "3H", "P", "3S", "P", "4D", "P"])
    erts = v["auction_understanding"][8]
    assert erts["call"] == "4D" and erts["understood"]


def test_fogas_szarmaztatott_valtozoval():
    # a `fogas: [oM]` a származtatott színváltozóval is eldönthető (javítva)
    from kibic.domain import Kez
    from kibic.impex.rendszer_yaml import forras_dict
    from kibic.motor.kifejezes import Kontextus, kiertekel
    g = {}
    forras_dict({"rendszer": {"kod": "TFO", "fajta": "KONVENCIO"}, "szabalyok": [
        {"minta": "1M-2C-3NT", "fogas": ["oM"]}]}, "t.yaml", g)
    fa = g["TFO"].sorok[0].feltetel
    kez = Kez.pbn_bol("AQ432.K2.K32.Q32")
    assert kiertekel(fa, kez, Kontextus(kotesek={"M": "S"})) is True
    kez = Kez.pbn_bol("AQ432.32.K32.KQ2")
    assert kiertekel(fa, kez, Kontextus(kotesek={"M": "S"})) is False


def test_helyzeti_megallapodas_nem_altalanos_elv(kibic_stand):
    from kibic.szolgaltatas.atjaro import _magyarazat
    v = _licit(kibic_stand.sorok, _pbn("AKT32.A2.432.J32"), T7 + ["4C", "P"])
    assert v["source"] == "ELV" and v["situational_agreement"] == "MOHA_3NT_4M"
    assert _magyarazat(v, None).startswith("Helyzeti megállapodás (MOHA_3NT_4M)")
    assert "nincs rá konkrét megállapodás" not in v["explanation"]
    # az általános elv (passz-elv) marad "nincs rá megállapodás"
    v = _licit(kibic_stand.sorok, _pbn("432.432.5432.432"), ["1S"])
    assert v.get("situational_agreement") is None


@pytest.mark.parametrize("kez, vart", [
    ("AK2.Q2.KQ2.Q5432", "3NT"),       # sok pont, több fogás a pikkben
    ("Q2.2.KJ32.AQJ432", "4C"),        # nincs kőr fit, nincs pikkfogás: hosszú treff
    ("32.Q32.KJ2.AQJ32", "4H"),        # kőr fit
])
def test_onsplinter_utan_a_valaszolo(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), ["1H", "P", "2C", "P", "3S", "P"])
    assert v["call"] == vart


def test_moha_1m_2d_gemforsz_es_rossz_11(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("32.Q2.AKJ32.Q432"), ["1S", "P"])
    assert v["call"] == "2D"                       # 12 FP, 5 káró: gémforsz
    v = _licit(kibic_stand.sorok, _pbn("32.QJ2.QJ432.KQ2"), ["1S", "P"])
    assert v["call"] == "1NT"                      # 11, de rossz: 1NT


# --- 2026-10-04 este: 6. és 7. leosztás ------------------------------------

def test_kulcslicitre_kulcslicit_pikk_asszal(kibic_stand):
    # 1♥-1♠-3♥-3♠(szlemérdek)-4♦(kulcslicit): ♠A-val a pikk-kulcslicit a 4NT (a 4♠ RKC)
    v = _licit(kibic_stand.sorok, _pbn("AKJ32.Q2.AK32.32"),
               ["1H", "P", "1S", "P", "3H", "P", "3S", "P", "4D", "P"])
    assert v["call"] == "4NT"
    assert v.get("situational_agreement") == "RKC"


def test_pc_utan_passz_nem_gemforszban(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("AKJ32.Q2.K32.Q32"),
               ["1H", "P", "1S", "P", "3H", "P", "3S", "P", "4D", "P"])
    assert all(j["call"] != "P" for j in v["to_deliberate"])


def test_hezag_kvantitativ_4nt(kibic_stand):
    # 1♥ (2♠) X (3♠) P (P): 17 pont, nincs adu — nem 3NT ("kényszerből"), hanem 4NT
    v = _licit(kibic_stand.sorok, _pbn("A32.KQ.AJ32.K432"),
               ["1H", "2S", "X", "3S", "P", "P"])
    assert v["call"] == "4NT" and v["source"] == "HEZAG"


@pytest.mark.parametrize("kez, vart", [
    ("Q.AKJ32.KQ2.Q765", "6NT"),      # a sáv felső fele
    ("Q2.KJ932.K32.QJ5", "P"),        # alsó fele
])
def test_kvantitativ_4nt_valasz(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), ["1H", "2S", "X", "3S", "P", "P", "4NT", "P"])
    assert (v["call"] or "P") == vart


def test_kulcslicit_helyett_gem_ha_a_szlem_kizart(kibic_stand):
    # 15 pont, de 7,5 vesztő: a 16-17-es partner mellett a szlem kizárt → 4♥
    v = _licit(kibic_stand.sorok, _pbn("AKJ32.Q2.K32.Q32"),
               ["1H", "P", "1S", "P", "3H", "P", "3S", "P", "4D", "P"])
    assert v["call"] == "4H"


def test_negativ_kontra_eros_lap_magyarazata(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("A32.KQ.AJ32.K432"), ["1H", "2S"])
    assert v["call"] == "X" and "erős lap" in v["explanation"]


# --- 2026-10-05: a szlem nem állhat meg a gémben ---------------------------

SZLEM_MENET = ["1H", "P", "1S", "P", "3H", "P", "3S", "P", "4D", "P", "4NT", "P", "5H", "P"]


@pytest.mark.parametrize("kez, vart", [
    ("AKJ32.Q2.K32.AQ2", "6C"),       # 19 + 16 = 35, a felső 36: kulcslicit tovább (♣A)
    ("AKT32.Q2.K32.AJ2", "6H"),       # 17 + 16 = 33, a nagyszlem nem jön szóba: 6♥
])
def test_szin_szlem_a_gem_folott(kibic_stand, kez, vart):
    v = _licit(kibic_stand.sorok, _pbn(kez), SZLEM_MENET)
    assert v["call"] == vart and v["source"] == "HEZAG"


def test_szin_szlem_parosversenyen_dd_dont():
    # MP-n a 6♥ és a 6NT közül a végkontraktus-szimuláció választ
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.hezag import Hezag
    from kibic.motor.helyzet import Allas
    from kibic.domain import Kez
    from kibic.szolgaltatas.licit import _menet, vonalas_propagalo
    g = betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"])
    sorok = feloldas_forrasokbol(g, "KIBIC_STAND")[0].sorok
    lic = _menet(SZLEM_MENET, "N")
    prop = vonalas_propagalo(sorok, Parametertar(), None, "S", None, {})
    er = prop.kenyszertar(lic, oszto="N")
    allas = Allas(ules="S", licitek=lic, oszto="N", kenyszertar=er.kenyszertar)
    kerdes = []
    h = Hezag(Kez.pbn_bol("AKT32.Q2.K32.AJ2"), allas, prop, lic, "S", "N",
              ["P", "5S", "5NT", "6C", "6D", "6H", "6S", "6NT"],
              vegkontraktus=lambda hiv: (kerdes.append(hiv) or {"best": "6NT", "options": {}}),
              pontozas="MP").dont()
    assert h.licit == "6NT" and kerdes == [["6H", "6NT"]]
    h = Hezag(Kez.pbn_bol("AKT32.Q2.K32.AJ2"), allas, prop, lic, "S", "N",
              ["P", "5S", "5NT", "6C", "6D", "6H", "6S", "6NT"],
              vegkontraktus=lambda hiv: {"best": "6NT"}, pontozas="IMP").dont()
    assert h.licit == "6H"                  # csapatversenyen a biztosabb adu


def test_kulcslicit_a_gem_folott_nem_passzolhato(kibic_stand):
    v = _licit(kibic_stand.sorok, _pbn("Q4.AKJ985.AQ4.K3"), SZLEM_MENET + ["6C", "P"])
    assert v["call"] in ("6H", "7H")


# --- spirál: ugrás a szlembe egy játszható színben = leállás (2026-10-05) -----

def test_spiral_ugras_jatszhato_szinbe_passz(kibic_stand):
    # 1♦-1♥-3♣-3♦-3♠(4. szín)-3NT-4♣(ORKC treff)-5♣(2+D)-6♦: a 6♦ ugrás (L2+)
    # szlem-szintre az összeemelt káróban → nem relé, hanem a szlem: passz
    menet = ["1D", "P", "1H", "P", "3C", "P", "3D", "P", "3S", "P", "3NT", "P",
             "4C", "P", "5C", "P", "6D", "P"]
    v = _licit(kibic_stand.sorok, _pbn("Q2.KQJ32.Q432.K2"), menet)
    assert v["call"] == "P" and v["source"] == "SPIRAL"


def test_rele_lepcsok_ugras_kivetel():
    from kibic.motor.spiral import _rele_lepcsok
    l = _rele_lepcsok("5C", "C", {"D"})
    assert l[0] == "5D"                     # L1: relé (akkor is, ha játszható szín)
    assert "6D" not in l and "6NT" not in l  # ugrás a szlembe: leállás
    assert "5H" in l and "6H" in l           # a nem játszható szín relé marad


def test_orkc_5m_valasz_tetszik_elott(kibic_stand):
    # 1♠-2♣-3NT-4♣: "tetszik" lap (14 FP gyorsütésekben, 3 treff), de 2 kulcslap
    # + treff dáma → 5♣ (definíció szerint, a tetszik előtt)
    v = _licit(kibic_stand.sorok, _pbn("AKT32.A2.432.Q32"), T7 + ["4C", "P"])
    assert v["call"] == "5C"


@pytest.mark.parametrize("kez, vart", [
    ("KQT32.QJ32.A2.A2", "5C"),       # 2 kulcslap (♦A, ♣A), treff dáma nélkül; egyik minor sem "tetszik"
    ("KQT32.QJ32.A2.AQ", "5D"),       # 2 kulcslap + treff dáma
])
def test_ketutas_4c_ot_szintu_valaszok(kibic_stand, kez, vart):
    # Stayman 2♣ → a treff nem szín → kétutas 4♣: 5♣ = 2 dáma nélkül, 5♦ = 2 + ♣D
    menet = ["1NT", "P", "2C", "P", "2D", "P", "3NT", "P", "4C", "P"]
    v = _licit(kibic_stand.sorok, _pbn(kez), menet)
    assert v["call"] == vart


@pytest.mark.parametrize("ertek, paros", [
    ("MP", True), ("mp", True), ("BAM", True), ("matchpoints", True),
    ("IMP", False), (None, False), ("", False), ("TOTAL", False),
])
def test_scoring_ertekek(ertek, paros):
    from kibic.szolgaltatas.licit import parosverseny
    assert parosverseny(ertek) is paros


# --- kétértelmű kulcslap-válasz: a kérdező a rosszabbat tételezi fel -------

def test_kerdezo_a_rosszabb_esetet_tetelezi_fel(kibic_stand):
    # 4♥ = 0/3 (A-ág); a kérdezőnek 2 kulcslapja van: 0 esetén 3 hiányzik → 5♣
    v = _licit(kibic_stand.sorok, _pbn("32.KQ2.KQ2.AKQ93"), T7 + ["4C", "P", "4H", "P"])
    assert v["call"] == "5C" and v["source"] == "SPIRAL"


def test_valaszolo_a_jobbik_esettel_szlemet_mond(kibic_stand):
    # a válaszolónál a jobbik eset van (3 kulcslap): a kérdező 5♣-je után 6♣
    v = _licit(kibic_stand.sorok, _pbn("AQT32.A2.A32.J32"),
               T7 + ["4C", "P", "4H", "P", "5C", "P"])
    assert v["call"] == "6C" and v["source"] == "SPIRAL"
    # a rosszabbik esettel (0 kulcslap) passz
    v = _licit(kibic_stand.sorok, _pbn("KQT32.KQ.Q32.J32"),
               T7 + ["4C", "P", "4H", "P", "5C", "P"])
    assert v["call"] == "P"
