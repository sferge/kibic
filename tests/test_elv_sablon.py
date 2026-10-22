"""ELV-SABLON (2026-10-05): a FOGASMUTATAS elv és a MOHA_STAND_ELV próba-rendszer.

A szerkesztő megfogalmazása: a várakozó 2M után a válaszoló új színe
természetes, FOGÁST mutat (nem ígér négy lapot, plusz erőt sem; GF marad),
az irány a 3NT. Ezt nem soronként (1♠-2♣-2♠-3♦, 1♥-2♦-2♥-3♣ …), hanem
egyetlen általános elvként írjuk le; a rendszer hivatkozása mondja meg, hol él.
"""
from pathlib import Path

import pytest

from kibic.motor.kriterium import Parametertar
from kibic.motor.rendszercheck import feloldas_forrasokbol

YAML = Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"
FEJEZET = "1M – 2m – 2M után: a válaszoló új színe és a nyitó felelete (Moha)"


@pytest.fixture(scope="module")
def forrasok():
    pytest.importorskip("yaml")
    from kibic.impex.rendszer_yaml import betolt
    return betolt([YAML])


@pytest.fixture(scope="module")
def elv(forrasok):
    return feloldas_forrasokbol(forrasok, "MOHA_STAND_ELV")[0]


@pytest.fixture(scope="module")
def regi(forrasok):
    return feloldas_forrasokbol(forrasok, "MOHA_STAND")[0]


def _pbn(s):
    return [sz + e for sz, lapok in zip("SHDC", s.split(".")) for e in lapok]


def _licit(sorok, kez, menet, oszto="N", rendszer="MOHA_STAND_ELV", **extra):
    from kibic.szolgaltatas.licit import licit_elemzes
    sorrend = "NESW"
    ules = sorrend[(sorrend.index(oszto) + len(menet)) % 4]
    k = {"hand": _pbn(kez), "seat": ules, "dealer": oszto, "vulnerability": "none",
         "auction": menet, "system": rendszer, "test_mode": True, "inference": False}
    k.update(extra)
    return licit_elemzes(k, lambda kod, p=None, t=None: (sorok, Parametertar()))


ALAP = ["1S", "P", "2C", "P", "2S", "P"]


# --- a sablon és a példányosítás ------------------------------------------

def test_sablon_betoltes(forrasok):
    s = forrasok["FOGASMUTATAS"]
    assert s.fajta == "ELV_SABLON"
    assert "FOGÁST mutat" in s.sablon["szoveg"]
    assert set(s.sablon["parameterek"]) >= {"FIT_MIN", "FIT_SZINEK", "TERMESZETES_FEDETT"}
    assert s.sablon["terulet"]["t"] == "FOGASMUTATAS"
    h = [x for x in forrasok["MOHA_STAND_ELV"].hivatkozasok if x.kod == "FOGASMUTATAS"][0]
    assert h.ervenyes == ["1M-2m-2M"] and h.beallitas == {"ervenyes": ["1M-2m-2M"]}


def test_peldany_helyorzo_nelkul_kontextussal(elv):
    import json
    sorok = [s for s in elv.sorok if s.rendszer_kod == "FOGASMUTATAS"]
    assert {s.kulcs for s in sorok} >= {"FOGASMUTATAS-2NT", "FOGASMUTATAS-3NT",
                                        "FOGASMUTATAS-SZIN", "FOGASMUTATAS-ISMETLES",
                                        "FOGASMUTATAS-KETSZINU", "FOGASMUTATAS-ONALLO",
                                        "FOGASMUTATAS-KETSEG"}
    for s in sorok:
        szoveg = json.dumps([s.feltetel, s.ha_feltetel, s.jelentes])
        assert '"sablon"' not in szoveg                 # minden helyőrző behelyettesítve
        assert "ELV_KONTEXTUS" in szoveg and "1M-2m-2M" in szoveg
        assert "{FIT_MIN}" not in (s.feltetel_szoveg or "")
    assert any("elv-terület: FOGASMUTATAS" in x for x in elv.tajekoztatasok)


def test_kizart_fejezet_es_terulet(elv, regi):
    assert any(s.fejezet == FEJEZET for s in regi.sorok)
    assert not any(s.fejezet == FEJEZET for s in elv.sorok)
    # a KIBICEGY 1M-2♣-2M-3NT „leállás”-a az elv területén nem él
    k = [s for s in elv.sorok if s.minta == "1M-2C-2M-3NT"]
    assert k and all(s.elnyomo for s in k)
    assert not any(s.elnyomo for s in regi.sorok if s.minta == "1M-2C-2M-3NT")


def test_sablon_parameter_hiba(forrasok):
    from kibic.impex.rendszer_yaml import ForrasHiba, forras_dict, fajtak_ellenorzese
    g = dict(forrasok)
    forras_dict({"rendszer": {"kod": "PROBA_ELV", "fajta": "GYUJTEMENY"},
                 "hivatkozasok": [{"kod": "FOGASMUTATAS", "parameterek": {"NINCS_ILYEN": 1}}]},
                "proba.yaml", g)
    with pytest.raises(ForrasHiba, match="ismeretlen sablon-paraméter"):
        fajtak_ellenorzese(g, hierarchia=False)


def test_behelyettesites():
    from kibic.motor.sablon import behelyettesit, ertekek
    d = {"parameterek": {"X": {"alap": 8}, "Y": {"alap": "nemes"}}}
    e = ertekek(d, {"parameterek": {"X": 7}})
    assert e == {"X": 7, "Y": "nemes"}
    assert behelyettesit({"a": [{"sablon": "X"}], "b": {"sablon": "Y"}}, e) == {"a": [7], "b": "nemes"}
    with pytest.raises(KeyError):
        behelyettesit({"sablon": "Z"}, e)


# --- a licit -----------------------------------------------------------------

@pytest.mark.parametrize("kez, vart", [
    ("4.32.AQJ5.AKJ532", "3D"),        # káró fogás
    ("74.32.K82.AQJ532", "3D"),        # három lappal, plusz erő nélkül is
    ("74.K32.982.AKJ32", "3H"),        # kőr fogás
    ("74.Q32.KJ5.AQJ32", "3NT"),       # mindkettő
    ("74.Q32.AQJ5.AKJ3", "2NT"),       # mindkettő, plusz erő: a lassú 2NT
    ("74.32.982.AKQJ32", "3C"),        # fogás nélkül: a saját szín (nem a fogás nélküli 3NT)
])
def test_valaszolo(elv, kez, vart):
    v = _licit(elv.sorok, kez, ALAP)
    assert v["call"] == vart


@pytest.mark.parametrize("kez, vart", [
    ("KQJ862.AKT.73.84", "3NT"),       # a szerkesztő leosztása
    ("KQJ862.QT2.73.A4", "3NT"),
    ("KQJ862.432.73.AK", "3S"),        # nincs kőrfogás: 6+ pikk
])
def test_nyito_a_fogasmutatas_utan(elv, kez, vart):
    v = _licit(elv.sorok, kez, ALAP + ["3D", "P"])
    assert v["call"] == vart


def test_a_fogas_a_kenyszertarban(elv):
    v = _licit(elv.sorok, "KQJ862.AKT.73.84", ALAP + ["3D", "P"])
    assert v["constraints"]["S"]["stoppers"] == ["D"]      # a partner kárófogása
    meg = [m for m in v["auction_understanding"] if m["call"] == "3D"]
    assert meg and meg[0]["understood"]


def test_ugras_nem_fogasmutatas(elv):
    """A splinter-ugrás (3♠ a 2♥ után) nem az elv területe."""
    v = _licit(elv.sorok, "K.K98.KJT84.AT53", ["1H", "P", "2D", "P", "2H", "P"])
    assert v["call"] == "3S"


def test_kontextuson_kivul_nem_el(elv):
    """Az 1M-2m-2M-en kívül (pl. 1♠-2♣-2♥ után) az elv nem szól bele."""
    v = _licit(elv.sorok, "74.32.AQ82.AKJ32", ["1S", "P", "2C", "P", "2H", "P"])
    assert not v["call"] or "fogás ebben a színben" not in (v.get("explanation") or "")


def test_minor_fit_parameter(forrasok):
    """FIT_SZINEK: nemes (alap) — a minor fit nem állítja meg; barmely — igen."""
    from kibic.impex.rendszer_yaml import forras_dict, fajtak_ellenorzese
    g = dict(forrasok)
    forras_dict({"rendszer": {"kod": "PROBA_BARMELY", "fajta": "GYUJTEMENY"},
                 "hivatkozasok": [{"kod": "FOGASMUTATAS", "ervenyes": ["1M-2m-2M"],
                                   "parameterek": {"FIT_SZINEK": "barmely"}},
                                  "KIBIC_STAND"],
                 "kizarasok": [{"kod": "MOHA_1M", "fejezet": FEJEZET}]}, "proba.yaml", g)
    fajtak_ellenorzese(g, hierarchia=False)
    barmely = feloldas_forrasokbol(g, "PROBA_BARMELY")[0]
    elv = feloldas_forrasokbol(g, "MOHA_STAND_ELV")[0]
    kez, menet = "AK7.AT762.QJ52.T", ["1H", "P", "2D", "P", "2H", "P", "3C", "P"]
    assert _licit(elv.sorok, kez, menet)["call"] == "3NT"
    assert _licit(barmely.sorok, kez, menet, rendszer="PROBA_BARMELY")["call"] != "3NT"


def test_regi_rendszer_valtozatlan(regi):
    """A MOHA_STAND (a régi, sorokra bontott alak) ugyanígy licitál."""
    assert _licit(regi.sorok, "KQJ862.AKT.73.84", ALAP + ["3D", "P"],
                  rendszer="MOHA_STAND")["call"] == "3NT"


def test_arnyek_masik_rendszer(regi, elv):
    from kibic.szolgaltatas.licit import licit_elemzes
    tar = {"MOHA_STAND": regi.sorok, "MOHA_STAND_ELV": elv.sorok}
    v = licit_elemzes({"hand": _pbn("74.Q32.AQJ5.AKJ3"), "seat": "S", "dealer": "N",
                       "vulnerability": "none", "auction": ALAP, "system": "MOHA_STAND",
                       "test_mode": True, "inference": False,
                       "shadow": ["rendszer:MOHA_STAND_ELV"]},
                      lambda kod, p=None, t=None: (tar[kod], Parametertar()))
    a = v["shadow"][0]
    assert a["name"] == "rendszer:MOHA_STAND_ELV" and a["call"] == "2NT" and a["same"]


def test_leiras_mutatja_az_elvet(forrasok):
    from kibic.szolgaltatas.leiras import leiras_md, leiras_yamlbol
    md = leiras_md(leiras_yamlbol(forrasok, "MOHA_STAND_ELV"))
    assert "**Az elv**" in md and "**Hol él:** 1M-2m-2M" in md
    assert "`FIT_MIN` = **8**" in md


# --- a hézag-elv: hamis fogást nem ígér ----------------------------------------

def test_hezag_nem_mond_fogas_nelkul_3nt_t(regi):
    """1♦-1♥-3♣-3♠ (negyedik szín: pikkfogást kér): pikkfogás nélkül nem 3NT."""
    v = _licit(regi.sorok, "2.K62.AQ963.AK75", ["P", "1D", "P", "1H", "P", "3C", "P", "3S", "P"],
               oszto="W", rendszer="MOHA_STAND")
    assert v["call"] != "3NT"


# --- a szerkesztő 2026-10-05 esti megjegyzései ---------------------------------

@pytest.mark.parametrize("kez, vart", [
    ("62.AK86.Q653.QT8", "1NT"),       # B1: rossz 11 (üres Q10x)
    ("7.QJ6.J962.AK876", "2C"),        # B2: az 5 lapos treff jó 11-et csinál (2026-10-05 este)
    ("Q.AK98.J754.J986", "1NT"),       # B6: szingli dáma
    ("Q5.KJ8.KQT.87543", "2C"),        # B7: ugyanígy
    ("8.K953.AJ85.KT54", "2C"),        # jó 11: marad a 2/1
    ("86.AQ5.K762.Q875", "2C"),
])
def test_rossz_11_valasz_1nt(elv, kez, vart):
    assert _licit(elv.sorok, kez, ["1S", "P"])["call"] == vart


@pytest.mark.parametrize("kez, menet", [
    ("A7.A73.A97.QJ763", ["1H", "P", "2C", "P", "2H", "P"]),
    ("KJ2.AQ6.A3.Q9653", ALAP),
])
def test_harom_lapos_tamogatassal_emeles_nem_minor(elv, kez, menet):
    """C: 3 lapos nemes támogatással a 2M után emelés, nem a minor ismétlése."""
    assert _licit(elv.sorok, kez, menet)["call"] == "3" + menet[0][1]


NT2 = ["1S", "P", "2C", "P", "2S", "P", "2NT", "P"]


@pytest.mark.parametrize("kez, menet, vart", [
    ("AT9432.KJ3.76.K9", NT2, "3H"),                    # 6+ pikk, kőrfogás: 3♥ (a 2♠ tagadta a 4 kőrt)
    ("AT9432.432.K7.KJ", NT2, "3S"),                    # 6+ pikk, nincs kőrfogás: még egy nemes licit
    ("AKQJ876.Q82.84.5", NT2, "4S"),                    # önállóan játszható
    ("KJT872.T.75.AK75", NT2, "3C"),                    # második szín, szinglivel
    ("T.KJ982.Q52.KQ98", ["1H", "P", "2D", "P", "2H", "P", "2NT", "P"], "3C"),
    ("QT3.KJ642.K96.Q6", ["1H", "P", "2D", "P", "2H", "P", "2NT", "P"], "3NT"),
    ("KQJ862.AKT.73.84", ALAP + ["3D", "P"], "3NT"),   # van még le nem fedett szín: 3NT
])
def test_ha_minden_lefedve(elv, kez, menet, vart):
    assert _licit(elv.sorok, kez, menet)["call"] == vart


def test_6os_ismetlesre_2_lappal_merlegeles(elv):
    v = _licit(elv.sorok, "K3.A6.AJT83.QJ54", NT2 + ["3S", "P"], oszto="N")
    assert sorted(j["call"] for j in v["to_deliberate"]) == ["3NT", "4S"]
    assert v["call"] == "4S"            # szimuláció nélkül a hézag-elv: a 8 lapos fit


def test_ketseg(elv):
    """Rövid szín, amit csak a partner fogása fed: kétség (nem rögtön 3NT)."""
    menet = ["1H", "P", "2D", "P", "2H", "P", "2NT", "P", "3C", "P", "3D", "P"]
    v = _licit(elv.sorok, "T.KJ982.Q52.KQ98", menet)
    assert v["call"] == "3S"
    # a partner: kétszeres fogással 3NT (ÁDB), különben a nemes gém az 5-2 fitben
    assert _licit(elv.sorok, "AQJ.A6.AJT83.Q54", menet + ["3S", "P"])["call"] == "3NT"
    assert _licit(elv.sorok, "K32.A6.AJT83.Q54", menet + ["3S", "P"])["call"] == "4H"


@pytest.mark.parametrize("kez, menet, vart", [
    ("AQ972.QT.A932.64", [], "P"),        # rossz 12 (üres Q10)
    ("762.AQJT8.843.A4", [], "P"),        # 8 vesztő, 11 FP
    ("762.AQJT8.843.A4", ["P", "P"], "1H"),   # 3. kézben indul
    ("AT73.AQJ863.J7.3", [], "1H"),       # a hosszúsági pont kiváltja a levonást
    ("KQJ862.AKT.73.84", [], "1S"),
])
def test_felmentes(regi, kez, menet, vart):
    assert _licit(regi.sorok, kez, menet, rendszer="MOHA_STAND")["call"] == vart


def test_felmentes_passz_nem_jelent_rossz_lapot(regi):
    from kibic.szolgaltatas.magyarazat import licit_jelentese
    r = licit_jelentese(regi.sorok, Parametertar(), [{"ules": "N", "licit": "P"}], 0, "N")
    assert r["shows"] is None and "Felmentés" not in r["text"]


# --- 2026-10-05 késő este: gyenge kettesek, 2 fedős emelés, HELP, kvázi GF ---

def _zonas(sorok, kez, zona, rendszer="MOHA_STAND"):
    from kibic.szolgaltatas.licit import licit_elemzes
    return licit_elemzes({"hand": _pbn(kez), "seat": "N", "dealer": "N", "vulnerability": zona,
                          "auction": [], "system": rendszer, "test_mode": True, "inference": False},
                         lambda kod, p=None, t=None: (sorok, Parametertar()))["call"]


@pytest.mark.parametrize("kez, vart", [
    ("AKQJT4.943.T63.J", {"ew": "P", "none": "2S", "both": "2S", "ns": "2S"}),
    ("QT7.AQJ743.8.Q93", {"ew": "P", "none": "2H", "both": "2H", "ns": "2H"}),
    ("Q86.Q.AQJ942.JT4", {"ew": "P", "none": "P", "both": "P", "ns": "2D"}),
    # „fele a színben”: a máshol álló üres dáma/bubi leértékelve (2026-10-05 23:12)
    ("AJ8642.Q32.Q32.Q", {"none": "2S", "both": "2S", "ns": "2S"}),   # ÁB vs három üres D
    ("A9863.K32.J32.J3", {"none": "2S"}),                             # Á vs Kxx és két Bxx
])
def test_gyenge_kettes_rossz_nyitoerovel(regi, kez, vart):
    assert {z: _zonas(regi.sorok, kez, z) for z in vart} == vart


@pytest.mark.parametrize("kez, nyitas, vart", [
    ("J3.K84.QJT3.KJ97", "1H", "2H"),     # 2 fedő, nem jó 11: emelés
    ("4.AT2.KQ6532.Q85", "1H", "2H"),     # a hosszú káró itt nem segít: emelés
    ("KQ3.54.Q97.AT983", "1S", "2S"),
    ("J53.-.QJT8653.AK9", "1H", "2D"),    # nincs támogatás: 2♦
    ("J53.-.QJT8653.AK9", "1S", "2D"),    # 7 lapos káró: „túl hosszú” — 2♦, nem emelés
])
def test_nem_jo_11_ket_fedovel_emel(regi, kez, nyitas, vart):
    assert _licit(regi.sorok, kez.replace("-", ""), [nyitas, "P"], rendszer="MOHA_STAND")["call"] == vart


def test_help_es_kvazi_gemforsz(elv):
    menet = ["1H", "P", "2D", "P", "2H", "P", "3C", "P", "3D", "P", "3H", "P"]
    assert _licit(elv.sorok, "762.AQJT8.843.A4", menet)["call"] == "3S"            # HELP
    assert _licit(elv.sorok, "K4.K6.KQT52.KJ32", menet + ["3S", "P"])["call"] == "3NT"
    assert _licit(elv.sorok, "54.K6.KQT52.KJ32", menet + ["3S", "P"])["call"] == "4D"
    # a 4♦ a kvázi gémforsz miatt passzolható
    assert _licit(elv.sorok, "762.AQJT8.843.A4", menet + ["3S", "P", "4D", "P"])["call"] == "P"


def test_eredeti_leosztas_fogas_nelkul_help_6_pikkel_ismetles(elv):
    assert _licit(elv.sorok, "KQJ86.432.A73.K4", ALAP + ["3D", "P"])["call"] == "3H"   # HELP
    assert _licit(elv.sorok, "KQJ862.432.73.AK", ALAP + ["3D", "P"])["call"] == "3S"   # 6+ pikk


def test_kvazi_gemforsz_hezag_kenyszer(elv):
    from kibic.motor.helyzet import Allas, Igeret
    ig = Igeret(nyilatkozott=True, gemforsz=True, gf_hatar="4C")
    a = Allas(ules="N", licitek=[{"ules": "N", "licit": "1H"}, {"ules": "S", "licit": "4D"}],
              kenyszertar={"N": Igeret(nyilatkozott=True, gemforsz=True), "S": ig})
    assert a.gf_teljesult()


def test_teljes_ujrajatszas():
    from kibic.cli.aranykeszlet import _szep, jatszma, leosztas, yaml_betolto
    b = yaml_betolto([str(YAML)])
    m = jatszma(b, leosztas(1, 18), "S", "ew", "MOHA_STAND")
    assert m[:2] == ["P", "2S"] and _szep("3NT") == "3NT" and _szep("4S") == "4♠"


@pytest.mark.parametrize("kez, vart", [
    ("K32.Q32.AJ32.J32", "1D"),     # 11, 3-3 nemes: könnyített 1♦
    ("K32.Q32.AJ2.J432", "1C"),     # 11, 3-3 nemes, 4 treff
    ("K2.Q32.AJ32.J432", "P"),      # 11, nincs 3-3 nemes
    ("K2.Q32.AJ32.Q432", "P"),      # rossz 12, nincs 3-3 nemes: felmentés
    ("Q32.K32.AQ32.J32", "1D"),     # jó 12: rendes nyitás
    ("Q32.J32.Q432.J32", "P"),      # 10 alatt nincs nyitás
])
def test_harmadik_kez_minor_indulo_ero_nelkul(regi, kez, vart):
    """A szerkesztő (2026-10-05 23:12): 4-es nemes nélkül 10 alatt nem, 10+ csak 3-3 nemessel."""
    assert _licit(regi.sorok, kez, ["P", "P"], rendszer="MOHA_STAND")["call"] == vart


def test_elso_kezben_nincs_konnyitett_minor(regi):
    assert _licit(regi.sorok, "K32.Q32.AJ32.J32", [], rendszer="MOHA_STAND")["call"] == "P"


@pytest.mark.parametrize("menet, kez, vart", [
    ("1S P 2C P 2S P 2NT P 3S P", "K4.AQ3.K52.QJ952", {"3NT", "4S"}),
    ("1H P 2C P 2H P 2NT P 3H P", "AQ3.K4.K52.QJ952", {"3NT", "4H"}),
])
def test_letezik_kotes_egy_sor_mindket_nemesre(elv, menet, kez, vart):
    """2026-10-19: a „.. 3NT” sor M-je a feltételből kötődik (van olyan nemes,
    amelyben a partner 6+ lapot ígért) — egy sor 4M, nem külön 4♥ és 4♠."""
    v = _licit(elv.sorok, kez, menet.split(), oszto="N")
    assert {c["call"] for c in v["to_deliberate"]} == vart
    kulcsok = {s.kulcs for s in elv.sorok if s.rendszer_kod == "FOGASMUTATAS"}
    assert {"FOGASMUTATAS-VALASZT-3NT", "FOGASMUTATAS-VALASZT-4M", "FOGASMUTATAS-KETSEG-4M"} <= kulcsok
    assert not any(k.endswith(("-S-3NT", "-H-3NT", "KETSEG-4S", "KETSEG-4H")) for k in kulcsok)
