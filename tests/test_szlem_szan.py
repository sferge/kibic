"""Szlem szanban, a kétértelmű kulcslap-válasz a pontokból (a szerkesztő, 2026-10-25)."""
from test_konvenciok_2026_10_04 import _pbn


def _h(kez, menet, ules, rsz="MOHA_STAND"):
    from pathlib import Path
    from kibic.impex.rendszer_yaml import betolt
    from kibic.motor.kriterium import Parametertar
    from kibic.motor.rendszercheck import feloldas_forrasokbol
    from kibic.szolgaltatas.licit import licit_elemzes
    f = feloldas_forrasokbol(betolt([Path(__file__).resolve().parents[1] / "rendszerek" / "yaml"]), rsz)[0]
    v = licit_elemzes({"hand": _pbn(kez), "seat": ules, "dealer": "W", "vulnerability": "both",
                       "auction": menet.split(), "system": rsz, "test_mode": True},
                      lambda k, p, t=None: (f.sorok, Parametertar()))
    return v["call"] or "P"


def test_2025_10_25_6nt_6d_helyett():
    # Ny ♠AQJ ♥A3 ♦AJ3 ♣KQ954 (21), K ♠K53 ♥KJ ♦T964 ♣A732 (11): a „0 vagy 3”
    # a 20-21 pontos nyitónál csak 3 lehet; egy kulcslap hiányzik, az adu
    # dáma szanban nem számít: 6NT (DD: 12 ütés; a 6♦ bukik)
    menet = "2NT P 3C P 3NT P 4D P 4H P 4S P 4NT P"
    assert _h("K53.KJ.T964.A732", menet, "E") == "6NT"
