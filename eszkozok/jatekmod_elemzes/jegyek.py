"""Kezdőjegyek a felvevő + asztal kezéből (a lejátszás előtt)."""
HCP = {"A": 4, "K": 3, "Q": 2, "J": 1}
RANG = "23456789TJQKA"
SEATS = "NESW"

def kezek(deal):
    first, rest = deal.split(":")
    i = SEATS.index(first)
    ki = {}
    for j, h in enumerate(rest.split()):
        s = SEATS[(i + j) % 4]
        ki[s] = dict(zip("SHDC", h.split(".")))
    return ki

def jegyek(deal, decl, contract):
    k = kezek(deal)
    D = k[decl]; U = k[SEATS[(SEATS.index(decl) + 2) % 4]]
    strain = contract.rstrip("X")[1:] if contract else ""
    strain = "N" if strain.startswith("N") else strain[:1]
    adu = None if strain == "N" else strain
    level = int(contract[0])
    f = {"szan": adu is None, "szint": level}
    hcp = lambda h: sum(HCP.get(c, 0) for s in h.values() for c in s)
    f["hcp"] = hcp(D) + hcp(U)
    f["hcp_kul"] = abs(hcp(D) - hcp(U))
    # biztos ütések (felső lapok egymás után), vesztők (LTC a hosszabb kéz szerint)
    biztos = 0; ellen = 0
    for s in "SHDC":
        mi = sorted(set(D[s]) | set(U[s]), key=lambda c: -RANG.index(c))
        n = 0
        for i, c in enumerate("AKQJT98765432"):
            if c in mi: n += 1
            else: break
        biztos += min(n, max(len(D[s]), len(U[s])))
    f["biztos"] = biztos
    f["hiany"] = max(0, 6 + level - biztos)
    # rövidségek
    def rovid(h, s): return len(h[s])
    oldal = [s for s in "SHDC" if s != adu]
    f["szinhiany_D"] = sum(1 for s in oldal if len(D[s]) == 0)
    f["szinhiany_U"] = sum(1 for s in oldal if len(U[s]) == 0)
    f["szingli_db"] = sum(1 for h in (D, U) for s in oldal if len(h[s]) <= 1)
    # aszimmetria: egy mellékszín rövid (<=1) az egyik kézben és >=3 a másikban — és fordítva egy másik
    r_D = [s for s in oldal if len(D[s]) <= 1 and len(U[s]) >= 3]
    r_U = [s for s in oldal if len(U[s]) <= 1 and len(D[s]) >= 3]
    f["keresztlop_szerk"] = bool(r_D and r_U)
    f["egy_iranyu_lopas"] = bool(r_D) != bool(r_U)
    # leghosszabb mellékszín (együtt), többlet a rövidebb kéz felett
    f["hosszu_szin"] = max(len(D[s]) + len(U[s]) for s in oldal)
    f["tobblet"] = max(max(len(D[s]), len(U[s])) - min(len(D[s]), len(U[s])) for s in oldal)
    # kontrollok (A=2, K=1) a mellékszínekben
    f["kontroll"] = sum(2 * (("A" in D[s]) or ("A" in U[s])) + (("K" in D[s]) or ("K" in U[s])) for s in oldal)
    if adu:
        a1, a2 = len(D[adu]), len(U[adu])
        f["adu_egyutt"] = a1 + a2
        f["adu_hosszu"], f["adu_rovid"] = max(a1, a2), min(a1, a2)
        f["adu_egyforma"] = a1 == a2
        f["adu_figurak"] = sum(1 for c in "AKQ" if c in D[adu] or c in U[adu])
        f["adu_8_AK_D_nelkul"] = (a1 + a2 == 8 and "A" in D[adu] + U[adu] and "K" in D[adu] + U[adu]
                                 and "Q" not in D[adu] + U[adu])
        # a rövid adus kéz figurái (asztalfordítás: erős rövid adu)
        rov = U if a2 < a1 else D
        f["rovid_adu_figura"] = sum(1 for c in "AKQJ" if c in rov[adu])
        f["eloszlas_pont"] = sum(max(0, 3 - len(h[s])) for h in (D, U) for s in oldal)
    return f
