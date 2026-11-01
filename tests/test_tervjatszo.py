from kibic.domain import Lap
from kibic.motor import tervjatszo as tj


def _l(s):
    return {Lap.parse(x) for x in s.split()}


def _kis_vedo(j, u):
    utes = j.aktualis()
    van = [l for l in j.kezek[u] if utes and l.szin == utes[0][1].szin]
    return min(van or j.kezek[u], key=lambda l: l.rang)


def test_jeloltek_es_lejatszas():
    kezek = {"S": _l("SA SK SQ SJ HA HQ H2 DA D2 D3 CA C2 C3"),
             "N": _l("S2 S3 S4 S5 H3 H4 H5 D4 D5 D6 C4 C5 C6"),
             "W": _l("S6 S7 S8 HK H6 H7 D7 D8 D9 C7 C8 C9 CT"),
             "E": _l("S9 ST H8 H9 HT HJ DT DJ DQ DK CJ CQ CK")}
    d, y = kezek["S"], kezek["N"]
    lead = Lap.parse("C7")

    def kint(sz):
        return [l for l in tj._osszes(sz) if l not in d and l not in y and l != lead]
    tervek = tj.jeloltek(d, y, "S", kint)
    assert tervek and any(any(l.fajta == "IMPASSZ" for l in t.lepesek) for t in tervek)
    for t in tervek[:5]:
        ut = tj.lejatszik(kezek, "S", "S", [("W", lead)], t, _kis_vedo)
        assert 0 <= ut <= 13
