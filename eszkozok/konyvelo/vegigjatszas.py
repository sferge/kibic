"""Egy leosztás végigjátszása a /plan és /step szolgáltatáson át (a gépi védők a mindent látó lapjaikkal).

Használat (a repó gyökeréből): python eszkozok/konyvelo/vegigjatszas.py S N W E szint szín(S/H/D/C/NT) indulás [ERŐLTETETT]
Példa (BM A-12): ... AKQJT9.A2.K32.32 432.K43.Q94.KQJT 876.T98765.T5.A4 5.QJ.AJ876.98765 5 S DT ""
ERŐLTETETT: "1E:DA" = az 1. ütésben Kelet a ♦Á-t teszi.
A licit kényszertára adatbázis nélkül (LICIT_KENYSZER), környezeti változóban:
KIBIC_DRV_LICIT="W:D6-6,P5-10;E:P0-12" (ülés: színhossz és pontsáv)."""
import sys, os, shutil, pathlib
sys.path.insert(0, "src")
from kibic.domain import Lap, Leosztas
from kibic.domain.kartya import Kez
from kibic.domain.pontozas import Kontraktus
from kibic.motor import tervjatszo as tj
from kibic.szolgaltatas import tervmuhely as tm
from kibic.solver.dds import lap_elemzes
def kez(s):
    return {Lap.parse(sz + c) for sz, r in zip("SHDC", s.split(".")) for c in r if c != "-"}
Sk, Nk, Wk, Ek, szint, szin, lead = sys.argv[1:8]
kenyszer = [x.split(":") for x in (sys.argv[8].split(",") if len(sys.argv) > 8 else []) if x]
K = {"S": kez(Sk), "N": kez(Nk), "W": kez(Wk), "E": kez(Ek)}
assert len(set().union(*K.values())) == 52, [len(v) for v in K.values()]
adu = None if szin == "NT" else szin
lead = Lap.parse(lead)
if os.getenv("KIBIC_DRV_LICIT"):
    from kibic.motor.helyzet import Igeret
    _tar = {}
    for resz in os.environ["KIBIC_DRV_LICIT"].split(";"):
        u, kk = resz.split(":")
        ig = Igeret()
        for x in kk.split(","):
            a, b = x[1:].split("-")
            if x[0] == "P":
                ig.pont_min, ig.pont_max = float(a), float(b)
            else:
                ig.hossz_min[x[0]], ig.hossz_max[x[0]] = int(a), int(b)
        _tar[u] = ig
    tm.LICIT_FV = lambda keres, F: _tar
tm.TAR = pathlib.Path("/tmp/drvtar"); shutil.rmtree(tm.TAR, ignore_errors=True)
lo = Leosztas({u: Kez(frozenset(K[u])) for u in "NESW"}); k = Kontraktus(int(szint), szin, "", "S")
j = tj.Jatek({u: set(K[u]) for u in "NESW"}, "S", adu, [("W", lead)], tj.Terv(()))
def keres(j):
    u = j.soron(); utes = j.aktualis()
    van = [l for l in j.kezek[u] if utes and l.szin == utes[0][1].szin]
    return {"protocol": "mohabridzs-ai/1.0", "request_id": "x", "decision": "play", "deadline_ms": 60000,
            "game": {"match_id": "drv", "table_index": 0, "board_number": 1},
            "actor": {"seat": "S", "acting_for_seat": u},
            "state": {"phase": "play", "dealer": "N", "contract": {"level": int(szint), "strain": "N" if szin == "NT" else szin, "multiplier": 1},
                      "declarer": "S", "dummy": "N", "visible_hands": {x: sorted(str(l) for l in j.kezek[x]) for x in "SN"}},
            "history": {"auction": [], "play": [{"seat": s, "card": str(l)} for s, l in j.lapok]},
            "legal_actions": {"cards": sorted(str(l) for l in (van or j.kezek[u]))}}
v = tm.plan_valasz(keres(j)); print("TERV:", v["summary"][:200])
for c in v.get("assessment", {}).get("candidates", [])[:8]: print("   ", c)
while len(j.lapok) < 52:
    u = j.soron()
    if u in "EW":
        l = None
        ksz = kenyszer[0][0] if kenyszer else ""
        ut_no = len(j.lapok) // 4 + 1
        if kenyszer and ksz[-1] == u and (len(ksz) == 1 or int(ksz[:-1]) == ut_no):
            c = Lap.parse(kenyszer[0][1])
            ut = j.aktualis()
            if c in j.kezek[u] and (not ut or c.szin == ut[0][1].szin or not j.szin(u, ut[0][1].szin)):
                l = c; kenyszer.pop(0)
        if l is None:
            l = tj._vedo_lap(lap_elemzes(lo, [str(x) for _, x in j.lapok], k))
        why = ""
    else:
        v = tm.step_valasz(keres(j), None, None)
        if not v.get("action"):
            print("NINCS LAP:", v.get("status"), v.get("summary")); break
        l = Lap.parse(v["action"]["card"]); why = v["summary"][:170]
    j.tesz(u, l)
    if u not in "EW":
        print(f"{(len(j.lapok) - 1) // 4 + 1:2}. {u}{l}  {why}")
    if len(j.lapok) % 4 == 0:
        print("    ütés:", " ".join(f"{a}{b}" for a, b in j.lapok[-4:]))
ny = sum(1 for i in range(13) if j.nyertes(j.lapok[4 * i:4 * i + 4])[0] in "NS")
print("ÜTÉS:", ny)
