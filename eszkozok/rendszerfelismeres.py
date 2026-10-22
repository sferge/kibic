"""Robot- és rendszerfelismerés az alertek alapján."""
import json, os, re, sys
from collections import Counter, defaultdict
import pymysql

conn = pymysql.connect(host=os.getenv("KIBIC_HOST","localhost"),
                       user=os.getenv("KIBIC_USER","kibic"),
                       password=os.getenv("KIBIC_PASS",""),
                       database=os.getenv("KIBIC_DB","kibic"), charset="utf8mb4")
cur = conn.cursor()
cur.execute("SELECT j.id, j.licit, j.n_jatekos_id, j.e_jatekos_id,"
            "       j.s_jatekos_id, j.w_jatekos_id"
            "  FROM jatszma j WHERE j.licit IS NOT NULL")

GEP_MINTAK = ("total points", "hcp;", "!c;", "!d;", "!h;", "!s;",
              "could have", "suit opening --")
SZAN_RE = re.compile(r"\b(\d{2})\s*[-+ ]\s*(\d{2})\b")

gepi = Counter(); parok = defaultdict(Counter)
szan = defaultdict(Counter); treff = defaultdict(Counter)
osszes_alert = 0

for jid, licit_j, n,e,s,w in cur.fetchall():
    try: licitek = json.loads(licit_j)
    except Exception: continue
    ules_jatekos = {"N":n,"E":e,"S":s,"W":w}
    for i,b in enumerate(licitek):
        if not b.get("alert") or not b.get("magyarazat"): continue
        osszes_alert += 1
        mag = b["magyarazat"].lower()
        u = b.get("ules"); jid_ = ules_jatekos.get(u)
        par = None
        if u in ("N","S") and n and s: par = tuple(sorted((n,s)))
        elif u in ("E","W") and e and w: par = tuple(sorted((e,w)))
        gep = any(m in mag for m in GEP_MINTAK)
        if gep: gepi[par] += 1
        if par: parok[par][("gep" if gep else "ember")] += 1
        # nyitó licit?
        nyito = all((x.get("licit") or "").upper() in ("PASS","P")
                    for x in licitek[:i])
        if not nyito or not par: continue
        L = (b.get("licit") or "").upper()
        if L in ("1NT","1N"):
            m = SZAN_RE.search(mag)
            if m: szan[par][f"{m.group(1)}-{m.group(2)}"] += 1
        if L == "1C":
            if any(x in mag for x in ("art","str","prec","16+","17+")):
                treff[par]["ERŐS"] += 1
            elif any(x in mag for x in ("2+","3+","1+","min")):
                treff[par]["NATÚR"] += 1

print(f"Alertelt licit: {osszes_alert}")
print(f"Gépi magyarázatú: {sum(gepi.values())}  ({100*sum(gepi.values())/max(1,osszes_alert):.0f}%)")
print(f"Pár, akinél VAN gépi magyarázat: {len(gepi)}")
print()
cur.execute("SELECT id, nev, partik FROM par WHERE partik>=30 ORDER BY partik DESC")
parinfo = {r[0]:(r[1],r[2]) for r in cur.fetchall()}
cur.execute("SELECT id, jatekos_a, jatekos_b, nev, partik FROM par")
kulcs = {(r[1],r[2]): (r[0], r[3], r[4]) for r in cur.fetchall()}

print(f"{'PÁR':<34}{'parti':>6}{'gépi':>6}{'szan':>10}{'1C':>8}")
print("-"*66)
sorok=[]
for par, c in parok.items():
    info = kulcs.get(par)
    if not info: continue
    pid, nev, partik = info
    if partik < 20: continue
    sz = szan[par].most_common(1)
    t = treff[par].most_common(1)
    sorok.append((partik, nev or str(par), c["gep"], 
                  sz[0][0] if sz else "-", t[0][0] if t else "-"))
for partik, nev, gep, sz, t in sorted(sorok, reverse=True)[:22]:
    print(f"{nev[:33]:<34}{partik:>6}{gep:>6}{sz:>10}{t:>8}")
conn.close()
