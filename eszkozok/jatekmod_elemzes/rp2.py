import json, collections, statistics, sys
sys.path.insert(0, "/tmp/jatekmod_elemzes")
from jegyek import jegyek
partik = json.load(open("/tmp/jatekmod_elemzes/rp.json"))
CSOPORT = {
 "KIMAGASITAS": ["Set up dummy’s suit", "Establish side suit", "Set up suit at notrump"],
 "LOPAS_ROVID": ["Ruff in short hand", "Delay drawing trumps", "Ruffing with 4-4 fit"],
 "KERESZTLOPAS": ["Crossruff"],
 "ASZTALFORDITAS": ["Dummy reversal"],
 "VESZTOCSERE": ["Loser-on-loser play", "Obtain early discard", "Shed loser to avert tap"],
 "VEGJATEK": ["Elimination technique", "Throw-in play", "Ruff/discard endplay", "Trump endplay"],
 "BESZORITAS": ["Automatic squeeze", "Positional squeeze", "Double squeeze", "Squeeze throw-in",
                "Ruffout squeeze", "Delayed-duck squeeze", "Vienna coup", "Isolate threat",
                "Correct loser count", "Unusual squeeze", "Pseudo squeeze", "Stepping-stone squeeze",
                "Crisscross squeeze"],
 "ADUKONTROLL": ["Trump management", "Keep trump control", "Force out high trump",
                 "Seven-card trump fit", "Survive bad break", "Avoid trump loser"],
 "ADUPUCCS": ["Trump coup"],
 "VESZELYES_VEDO": ["Holdup play", "Avoidance finesse", "Avoidance duck", "Break communication",
                    "Duck to keep control", "Erase dangerous entry", "Avoid enemy ruff"],
 "ATMENETEK": ["Communication/entries", "Create extra entry", "Duck to retain entry", "Overtaking play",
               "Unblocking play", "Use trumps as entries", "Jettison play", "Preserve entry",
               "Transfer ruff", "Ruff winner for entry"],
 "KARTYAOLVASAS": ["Placing enemy cards", "Count hand pattern", "Read enemy lead", "Read enemy tactics",
                   "Show-up finesse", "Restricted choice", "Watch spot cards"],
 "ESELYEK": ["Combine chances", "Play for best chance", "Pursue extra chance", "Play for only chance",
             "Shun finesse", "Go after sure trick", "Safety play", "Minimize risk"],
 "SZINKEZELES": ["Finessing technique", "Lead toward honor", "Ducking play", "Desperation finesse",
                 "Ruffing finesse", "Ruff out enemy honor"],
 "FELULLOPAS_ELLEN": ["Avert overruff", "Elopement play"],
 "IDOZITES": ["Timing the play", "Play to trick one"],
}
lab2 = {l: g for g, ls in CSOPORT.items() for l in ls}
rows = []
for p in partik:
    if not p["play"] or not p["decl"] or not p["contract"] or p["contract"][0] not in "1234567":
        continue
    try:
        f = jegyek(p["deal"], p["decl"], p["contract"])
    except Exception as e:
        continue
    f["csoport"] = sorted({lab2[l] for l in p["play"] if l in lab2})
    f["cimkek"] = p["play"]
    rows.append(f)
print(len(rows), "parti jegyekkel;", sum(1 for r in rows if r["szan"]), "szan")
nincs = collections.Counter(l for r in rows for l in r["cimkek"] if l not in lab2)
print("besorolatlan címkék:", sum(nincs.values()), nincs.most_common(12))
json.dump(rows, open("/tmp/jatekmod_elemzes/rp_jegyek.json", "w"), default=str)
cs = collections.Counter(g for r in rows for g in r["csoport"])
print("\ncsoport  partik  szan%")
for g, n in cs.most_common():
    sz = sum(1 for r in rows if g in r["csoport"] and r["szan"])
    print(f"{g:18s} {n:4d}  {100*sz/n:4.0f}%")
