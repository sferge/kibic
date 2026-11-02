import re, glob, json, collections, sys
sys.path.insert(0, "/tmp/jatekmod_elemzes")
from jegyek import jegyek
MINTA = {
 "KERESZTLOPAS": r"cross-?ruff",
 "ASZTALFORDITAS": r"dummy reversal|revers(e|ing) the dummy|reverse dummy",
 "LOPAS_ROVID": r"ruff(?:s|ing|ed)?\b[^.]{0,40}\bin (?:the )?dummy|ruff (?:a|his|one|two|the) \w+ (?:loser|losers)",
 "KIMAGASITAS": r"establish(?:es|ed|ing)? (?:the |dummy'?s? |his |a )?(?:long |side |fifth |\w+ )?(?:suit|spades|hearts|diamonds|clubs)|set(?:s|ting)? up (?:the |dummy'?s? |his )?(?:long |side )?(?:suit|spades|hearts|diamonds|clubs)|ruff(?:ing|s|ed)? out",
 "VESZTOCSERE": r"loser[- ]on[- ]loser|discard(?:s|ed|ing)? (?:a |his |one |the )?\w* ?losers?|scissors coup",
 "VEGJATEK": r"end-?play|throw-?in|thrown in|strip(?:-| and )?(?:squeeze|endplay)?|elimination|eliminat",
 "BESZORITAS": r"squeez",
 "ADUPUCCS": r"trump coup|grand coup|smother",
 "ADUKONTROLL": r"trump control|lose control|losing control|forcing game|tapped|forced to ruff",
 "VESZELYES_VEDO": r"hold[- ]?up|avoidance|danger(?:ous)? hand|keep (?:east|west|north|south) off lead|off lead",
 "ATMENETEK": r"\bentr(?:y|ies)\b|unblock|overtak",
 "BIZTONSAGI": r"safety play|safety[- ]?play",
 "KARTYAOLVASAS": r"\bcount(?:ing)?\b|restricted choice|placed? (?:east|west) with",
 "IMPASSZ": r"finesse",
}
rows = []
for fn in sorted(glob.glob("/home/claude/kibic/tanpartik/bbo_hotd/*.pbn")):
    t = open(fn, encoding="utf-8", errors="replace").read()
    d = re.search(r'\[Deal "([^"]+)"\]', t); c = re.search(r'\[Contract "([^"]+)"\]', t)
    dc = re.search(r'\[Declarer "([^"]+)"\]', t)
    kom = re.search(r'\{(.*?)\}', t, re.S)
    if not (d and c and dc and kom): continue
    szoveg = kom.group(1).lower()
    tag = [g for g, m in MINTA.items() if re.search(m, szoveg)]
    # a felvevő a főszereplő? (a "declarer" és a védők szavainak aránya)
    fel = len(re.findall(r"\bdeclarer\b|\bsouth\b(?! leads)", szoveg))
    ved = len(re.findall(r"\bdefen[cs]e|\bdefender|opening lead|second hand|third hand", szoveg))
    try:
        f = jegyek(d.group(1), dc.group(1), c.group(1))
    except Exception:
        continue
    f.update(csoport=tag, felvevo_szoveg=fel > ved, fajl=fn.rsplit("/", 1)[1])
    rows.append(f)
json.dump(rows, open("/tmp/jatekmod_elemzes/bbo_jegyek.json", "w"), default=str)
print(len(rows), "BBO-parti;", sum(1 for r in rows if r["felvevo_szoveg"]), "felvevő-központú szöveg;",
      sum(1 for r in rows if r["szan"]), "szan")
c = collections.Counter(g for r in rows for g in r["csoport"])
print("\nmód              összes  felvevő-szöveg  szan%")
for g, n in c.most_common():
    f = sum(1 for r in rows if g in r["csoport"] and r["felvevo_szoveg"])
    s = sum(1 for r in rows if g in r["csoport"] and r["szan"])
    print(f"{g:16s} {n:5d} {f:10d}       {100*s/n:4.0f}%")
