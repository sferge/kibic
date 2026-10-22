"""
KIOSZTÁSTERVEZŐ-PRÓBA — egy FUTÓ kibic szolgáltatáson végigméri a
`mohabridzs-deal-design/1.1` szerződést, mielőtt a MohaBridzs először hív.

    python -m kibic.cli.kiosztasproba --cim http://localhost:9050 --titok XYZ

A `--titok` az AI-gateway titka (KIBIC_AI_SHARED_SECRET; ha az nincs, a
KIBIC_SHARED_SECRET). Csak a szabványos könyvtárat használja.

Pontok: képességek; generálás kézfeltétellel; seed = újrajátszhatóság;
minden licites helyzet (preset); PBN-import; hibakódok; és ha a szerveren
van DDS, a lejátszási / ellenjátéki helyzetek is.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

PBN_MINTA = """[Event "Próba"]
[Board "1"]
[Dealer "N"]
[Vulnerable "None"]
[Deal "N:AKQ2.KQ2.A32.432 J543.A54.KQ4.A65 T976.JT9.JT9.KQJ 8.8763.8765.T987"]

[Board "2"]
[Dealer "E"]
[Vulnerable "NS"]
[Deal "E:AKQ2.KQ2.A32.432 J543.A54.KQ4.A65 T976.JT9.JT9.KQJ 8.8763.8765.T987"]
"""


class Kliens:
    def __init__(self, cim: str, titok: str | None):
        self.cim, self.titok = cim.rstrip("/"), titok

    def hiv(self, ut: str, test: dict | None = None, ido: float = 150.0):
        fej = {"Content-Type": "application/json"}
        if self.titok:
            fej["Authorization"] = f"Bearer {self.titok}"
        adat = None if test is None else json.dumps(test).encode()
        req = urllib.request.Request(self.cim + ut, data=adat, headers=fej,
                                     method="GET" if test is None else "POST")
        try:
            with urllib.request.urlopen(req, timeout=ido) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}


def _ervenyes(d: dict) -> str | None:
    h = d.get("hands") or {}
    lapok = [c for u in "NESW" for c in h.get(u, [])]
    if any(len(h.get(u, [])) != 13 for u in "NESW") or len(set(lapok)) != 52:
        return "nem 4×13 / 52 különböző lap"
    if d.get("dealer") not in list("NESW") or d.get("vulnerability") not in ("none", "ns", "ew", "both"):
        return "hibás osztó / beli"
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--cim", default="http://localhost:9050")
    ap.add_argument("--titok", default=None)
    a = ap.parse_args(argv)
    k = Kliens(a.cim, a.titok)
    eredmeny: list[tuple[str, bool, str]] = []

    def pont(nev, ok, info=""):
        eredmeny.append((nev, ok, info))
        print(f"{'OK  ' if ok else 'HIBA'}  {nev}" + (f"  — {info}" if info else ""))

    st, kep = k.hiv("/v1/kibic/kiosztas/kepessegek")
    pont("képességek", st == 200 and kep.get("protocol") == "mohabridzs-deal-design/1.1",
         f"HTTP {st}, DDS: {kep.get('dds')}, helyzetek: {len(kep.get('presets') or [])}")
    if st != 200:
        return 1

    keres = {"protocol": "mohabridzs-deal-design/1.1", "request_id": "proba-1", "count": 3,
             "seed": "proba", "target": {"hands": {"N": {"hcp": "15-17", "shape": "balanced"}}}}
    st, v = k.hiv("/v1/kibic/kiosztas", keres)
    hibak = [e for d in v.get("deals", []) if (e := _ervenyes(d))]
    pont("generálás kézfeltétellel", st == 200 and v.get("status") == "ok" and not hibak
         and v.get("request_id") == "proba-1", f"HTTP {st}, {v.get('stats')}, {hibak[:1]}")
    st2, w = k.hiv("/v1/kibic/kiosztas", keres)
    pont("újrajátszható (ugyanaz a seed)", [d["deal_id"] for d in v.get("deals", [])]
         == [d["deal_id"] for d in w.get("deals", [])])

    for p in kep.get("presets") or []:
        if p.get("practice") != "bidding":
            continue
        st, v = k.hiv("/v1/kibic/kiosztas", {"count": 1, "seed": "proba",
                                              "target": {"preset": p["code"]},
                                              "time_budget_ms": 30000})
        d = (v.get("deals") or [{}])[0]
        menet = " ".join(m["call"] for m in d.get("auction") or [])
        pont(f"helyzet {p['code']}", st == 200 and v.get("status") == "ok" and not _ervenyes(d),
             f"HTTP {st}, osztó {d.get('dealer')}: {menet}")

    st, v = k.hiv("/v1/kibic/kiosztas", {"source": {"type": "pbn", "pbn": PBN_MINTA}})
    pont("PBN-import", st == 200 and (v.get("stats") or {}).get("returned") == 2,
         f"HTTP {st}, {v.get('stats')}")

    for nev, test, varhato in (
            ("ismeretlen protokoll", {"protocol": "mohabridzs-deal-design/9.9"},
             (400, "unsupported_protocol")),
            ("szabad szöveg fordító nélkül", {"text": "Stayman-gyakorlás"},
             (422, "text_unsupported")),
            ("tervezett technika", {"target": {"play": {"contract": "4S", "technique": "squeeze"}}},
             (422, "unsupported_target")),
            ("hibás kézfeltétel", {"target": {"hands": {"N": {"hcp": "17-15"}}}},
             (400, "invalid_request"))):
        st, v = k.hiv("/v1/kibic/kiosztas", test)
        kod = (v.get("error") or {}).get("code")
        if nev == "szabad szöveg fordító nélkül" and (kep.get("text") or {}).get("supported"):
            pont(nev, st == 200, "a szerveren van fordító: a szöveget vállalja")
            continue
        pont(f"hibakód: {nev}", (st, kod) == varhato, f"HTTP {st}, {kod}")

    if kep.get("dds"):
        for kod in ("FINESSE", "OPENING_LEAD"):
            st, v = k.hiv("/v1/kibic/kiosztas", {"count": 1, "seed": "proba",
                                                  "target": {"preset": kod},
                                                  "time_budget_ms": 60000}, ido=200)
            d = (v.get("deals") or [{}])[0]
            pont(f"helyzet {kod} (DDS)", st == 200 and bool(d.get("checks")),
                 f"HTTP {st}, {v.get('stats')}, {d.get('contract')}, {d.get('checks')}")
    else:
        print("—     a szerveren nincs DDS: a lejátszási helyzeteket kihagytam")

    rossz = [n for n, ok, _ in eredmeny if not ok]
    print(f"\n{len(eredmeny) - len(rossz)} / {len(eredmeny)} rendben")
    return 1 if rossz else 0


if __name__ == "__main__":
    sys.exit(main())
