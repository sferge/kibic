import json, itertools
rows = json.load(open("/tmp/jatekmod_elemzes/rp_jegyek.json"))
szin = [r for r in rows if not r["szan"]]
G = ["KIMAGASITAS","LOPAS_ROVID","KERESZTLOPAS","ASZTALFORDITAS","VESZTOCSERE","ADUKONTROLL",
     "FELULLOPAS_ELLEN","VEGJATEK","BESZORITAS","VESZELYES_VEDO","ATMENETEK","ESELYEK","KARTYAOLVASAS"]
N = len(szin)
p = {g: sum(1 for r in szin if g in r["csoport"]) / N for g in G}
print("Együttjárás színjátékban (lift = P(A és B) / P(A)P(B); 1 = független, >1.5 együtt jár, <0.5 kizárja)")
for a, b in itertools.combinations(G, 2):
    nab = sum(1 for r in szin if a in r["csoport"] and b in r["csoport"])
    if p[a] * p[b] * N < 3: continue
    lift = nab / (p[a] * p[b] * N)
    if lift >= 1.6 or lift <= 0.45:
        print(f"  {a:17s} + {b:17s} {nab:3d} együtt, lift {lift:.2f}")
print("\nFelismerési szabályok (színjáték): pontosság = a szabályra illő partik hány %-a ilyen; lefedés = az ilyen partik hány %-ára illik")
def sz(nev, g, f):
    illo = [r for r in szin if f(r)]
    tal = [r for r in illo if g in r["csoport"]]
    ossz = [r for r in szin if g in r["csoport"]]
    print(f"  {nev:62s} illik {len(illo):4d}  pontosság {100*len(tal)/max(1,len(illo)):4.0f}% (alap {100*p[g]:3.0f}%)  lefedés {100*len(tal)/max(1,len(ossz)):4.0f}%")
sz("keresztlopás-szerkezet (két irányú rövidség)", "KERESZTLOPAS", lambda r: r["keresztlop_szerk"])
sz("ua. + hcp <= 24", "KERESZTLOPAS", lambda r: r["keresztlop_szerk"] and r["hcp"] <= 24)
sz("asztalford.: rövid adu >=3 lap, >=2 figura, egy irányú rövidség", "ASZTALFORDITAS",
   lambda r: r["adu_rovid"] >= 3 and r["rovid_adu_figura"] >= 2 and r["egy_iranyu_lopas"])
sz("lopás a rövid kézben: egy irányú rövidség", "LOPAS_ROVID", lambda r: r["egy_iranyu_lopas"])
sz("8 adu A-K, D nélkül", "LOPAS_ROVID", lambda r: r["adu_8_AK_D_nelkul"])
sz("beszorítás: hiány <= 2, hcp >= 26", "BESZORITAS", lambda r: r["hiany"] <= 2 and r["hcp"] >= 26)
sz("végjáték: nincs szingli/színhiány a két kézben", "VEGJATEK", lambda r: r["szingli_db"] == 0)
sz("adukontroll: 7 lapos adu", "ADUKONTROLL", lambda r: r["adu_egyutt"] <= 7)
sz("kimagasítás: mellékszín 7+ együtt, legalább 2 rövidség", "KIMAGASITAS", lambda r: r["hosszu_szin"] >= 7 and r["szingli_db"] >= 2)
