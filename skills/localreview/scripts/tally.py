#!/usr/bin/env python3
"""Tallies votes per pooled bug into scope/tally.json and says which bugs need a tie-breaker.

2-of-3 rule, run as 2 votes + a tie-breaker: two refutes -> refuted; two positives and no refute -> verified;
a split or errored vote -> pending until a 3rd vote; still undecided after 3 -> pending (reported as unverified).
A missing or unparseable vote is errored: it never counts as a refute.
"""
import collections, glob, json, os

W = os.environ.get("LOCALREVIEW_WORK", "/tmp/localreview_work")
pool = json.load(open(f"{W}/scope/pool.json"))
out, need_third = {}, []
for b, v in sorted(pool["bugs"].items()):
    votes, errored = [], 0
    for f in sorted(glob.glob(f"{W}/reports/{b}_vote*.json")):
        try:
            x = json.load(open(f))
        except json.JSONDecodeError:
            errored += 1
            continue
        if x.get("verdict") in ("CONFIRMED", "PLAUSIBLE", "REFUTED"):
            votes.append(x)
        else:
            errored += 1
    ref = sum(x["verdict"] == "REFUTED" for x in votes)
    pos = len(votes) - ref
    cast = len(votes) + errored
    # Two agreeing votes decide. A split or an errored vote waits for the 3rd; after it, >=2 valid and <2 refutes verifies.
    if ref >= 2:
        status = "refuted"
    elif pos >= 2 and (ref == 0 or cast >= 3):
        status = "verified"
    else:
        status = "pending"
    if status == "pending" and cast == 2:
        need_third.append(b)
    sev = collections.Counter(x.get("severity") for x in votes if x["verdict"] != "REFUTED")
    c = json.load(open(f"{W}/reports/{b}_candidate.json"))
    out[b] = dict(status=status, votes=f"{pos}-{ref}", errored=errored, sev_votes=dict(sev),
                  hint=c.get("severity_hint"), cat=c.get("category"), file=c["file_path"], line=c["start_line"], dups=v["dups"])
    print(f"{b} {status:8} {pos}-{ref}{f' err={errored}' if errored else ''} hint={c.get('severity_hint')} sev={dict(sev)} {c.get('category')} {c['file_path']}:{c['start_line']}")
json.dump(out, open(f"{W}/scope/tally.json", "w"), indent=1)
counts = collections.Counter(t["status"] for t in out.values())
print(dict(counts))
if need_third:
    print("dispatch a 3rd voter for:", " ".join(need_third))
