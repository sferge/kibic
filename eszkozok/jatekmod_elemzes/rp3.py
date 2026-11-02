import json, statistics as st
rows = json.load(open("/tmp/jatekmod_elemzes/rp_jegyek.json"))
def tabla(sor, cim, mezok, csoportok):
    print(f"\n== {cim} ({len(sor)} parti)")
    print(f"{'csoport':18s} {'n':>4} " + " ".join(f"{m[:10]:>10s}" for m in mezok))
    def atl(rr, m):
        v = [float(r[m]) for r in rr if m in r and r[m] is not None]
        return st.mean(v) if v else float("nan")
    print(f"{'(mind)':18s} {len(sor):4d} " + " ".join(f"{atl(sor, m):10.2f}" for m in mezok))
    for g in csoportok:
        rr = [r for r in sor if g in r["csoport"]]
        if len(rr) < 8: continue
        print(f"{g:18s} {len(rr):4d} " + " ".join(f"{atl(rr, m):10.2f}" for m in mezok))
szin = [r for r in rows if not r["szan"]]
szan = [r for r in rows if r["szan"]]
G = ["KIMAGASITAS","LOPAS_ROVID","KERESZTLOPAS","ASZTALFORDITAS","VESZTOCSERE","ADUKONTROLL","FELULLOPAS_ELLEN",
     "VEGJATEK","BESZORITAS","ADUPUCCS","VESZELYES_VEDO","ATMENETEK","ESELYEK","SZINKEZELES","KARTYAOLVASAS"]
tabla(szin, "SZÍNJÁTÉK", ["hcp","hiany","adu_egyutt","adu_rovid","adu_egyforma","rovid_adu_figura",
      "keresztlop_szerk","egy_iranyu_lopas","szingli_db","eloszlas_pont","kontroll","hosszu_szin","adu_8_AK_D_nelkul"], G)
tabla(szan, "SZANZADU", ["hcp","hiany","szint","hosszu_szin","tobblet","kontroll","szingli_db"], G)
