import re, collections, json, sys
txt = open("/home/claude/kibic/tanpartik/pavlicek_teljes/pavlicek_practice_teljes.pbn", encoding="utf-8", errors="replace").read()
blokkok = re.split(r'(?=\[Event )', txt)
partik = []
for b in blokkok:
    m = re.search(r'\[Deal "([^"]+)"\]', b)
    if not m: continue
    def tag(t):
        x = re.search(r'\[%s "([^"]*)"\]' % t, b); return x.group(1) if x else None
    play = re.findall(r'Play: ([^\n}]*(?:\n[^\n}:]+(?=\n|}))*)', b)
    labels = []
    for p in play:
        p = re.sub(r'\s+', ' ', p)
        labels += [x.strip() for x in p.split(";") if x.strip()]
    d = re.findall(r'Defense: ([^\n}]*)', b)
    partik.append(dict(event=tag("Event"), deal=m.group(1), decl=tag("Declarer"), contract=tag("Contract"),
                       play=labels, defense=[x.strip() for p in d for x in p.split(";")], text=b))
json.dump([{k: v for k, v in p.items() if k != "text"} for p in partik], open("/tmp/jatekmod_elemzes/rp.json", "w"))
print(len(partik), "parti;", sum(1 for p in partik if p["play"]), "Play-címkével")
c = collections.Counter(l for p in partik for l in p["play"])
print(len(c), "különböző címke")
for l, n in c.most_common(120): print(n, l)
