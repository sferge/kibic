"""PBN-olvasó: rotáció-visszafejtés, alertek, claim."""
from kibic.impex import pbn

MINTA = """[Event "Teszt"]
[Board "1"]
[Dealer "N"]
[Vulnerable "None"]
[Deal "W:Q954.KT62.K965.4 J3.9.AQT8.AQJ763 AT6.A754.42.KT85 K872.QJ83.J73.92"]
[Declarer "N"]
[Contract "3CX"]
[Result "10"]
[Score "NS 570"]
[Auction "N"]
1C =1= X 1H
X 2C Pass Pass
2D 3C X Pass
Pass Pass
[Note "1:Better minor, 3+ clubs"]
[Note "2:Negative double"]
[Note "3:Competitive"]
[Play "E"]
D4 DJ DK DA
SA S2 S5 SJ
*
"""


def test_egy_rekordot_olvas_a_sok_note_ellenere():
    """A [Note] címkék NEM rekordhatárok — ez volt az 1164 fantomrekord oka."""
    js = pbn.olvas(MINTA)
    assert len(js) == 1
    assert js[0].leosztas is not None
    assert js[0].figyelmeztetesek == []


def test_alert_a_licithez_kapcsolodik():
    j = pbn.olvas(MINTA)[0]
    elso = j.licit[0]
    assert elso["licit"] == "1C" and elso.get("alert") is True
    assert "minor" in elso["magyarazat"].lower()


def test_lejatszas_idorendbe_kerul():
    """A PBN sorai ülés-rotációban állnak, nem időrendben."""
    j = pbn.olvas(MINTA)[0]
    # 1. ütés: E kezd (a felvevő N-től balra). DA viszi -> N hív a 2.-ban.
    assert j.lapok[:4] == ["D4", "DJ", "DK", "DA"]
    assert j.lapok[4:8] == ["SJ", "SA", "S2", "S5"]


def test_claim_eszlelese():
    j = pbn.olvas(MINTA)[0]
    assert len(j.lapok) == 8
    assert j.claim_utes == 3
