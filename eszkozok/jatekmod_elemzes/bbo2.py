import json, statistics as st, itertools
rows = [r for r in json.load(open("/tmp/jatekmod_elemzes/bbo_jegyek.json")) if r["felvevo_szoveg"]]
szin = [r for r in rows if not r["szan"]]
M = ["hcp","hiany","adu_egyutt","adu_rovid","rovid_adu_figura","keresztlop_szerk","egy_iranyu_lopas","szingli_db","eloszlas_pont","hosszu_szin"]
def atl(rr, m):
    v = [float(r[m]) for r in rr if r.get(m) is not None]; return st.mean(v) if v else float("nan")
print(f"BBO, színjáték, felvevő-központú ({len(szin)})")
print(f"{'csoport':16s} {'n':>4} " + " ".join(f"{m[:9]:>9s}" for m in M))
print(f"{'(mind)':16s} {len(szin):4d} " + " ".join(f"{atl(szin,m):9.2f}" for m in M))
for g in ["LOPAS_ROVID","KERESZTLOPAS","KIMAGASITAS","VESZTOCSERE","VEGJATEK","BESZORITAS","ADUPUCCS","ADUKONTROLL","ATMENETEK"]:
    rr = [r for r in szin if g in r["csoport"]]
    if len(rr) >= 6:
        print(f"{g:16s} {len(rr):4d} " + " ".join(f"{atl(rr,m):9.2f}" for m in M))
N=len(szin); G=["LOPAS_ROVID","KERESZTLOPAS","KIMAGASITAS","VESZTOCSERE","VEGJATEK","BESZORITAS","ATMENETEK","IMPASSZ"]
p={g:sum(1 for r in szin if g in r["csoport"])/N for g in G}
print("\nEgyüttjárás (BBO): lift")
for a,b in itertools.combinations(G,2):
    nab=sum(1 for r in szin if a in r["csoport"] and b in r["csoport"])
    if p[a]*p[b]*N<3: continue
    print(f"  {a:14s}+{b:14s} {nab:3d} lift {nab/(p[a]*p[b]*N):.2f}")
