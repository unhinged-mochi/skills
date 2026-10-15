#!/usr/bin/env python3
"""Turns verified bugs into cloud-shaped output. Run tally.py first.

Reads scope/tally.json, scope/pool.json, reports/, and the run's judgment calls in scope/synth_overrides.json
(keys: canon, merge, pr_comment, severity, also_at; see reference/formats.md). Writes findings.json (headline),
findings.more.json, findings.meta.json, unverified.json, findings.sarif. Prints shape errors: fix and re-run.
"""
import collections, glob, json, os, sys

W = os.environ.get("LOCALREVIEW_WORK", "/tmp/localreview_work")
# The cloud headlined 10 of 20 candidates; local voters keep far more, so cap the nits shown up front.
HEADLINE_NITS = 8
KEYS = ("file_path", "severity", "start_line", "end_line", "pr_comment", "reasoning")
ORDER = {"normal": 0, "pre_existing": 1, "nit": 2}
IMPACT = {"data-integrity": 0, "security": 0, "billing": 0, "correctness": 1, "concurrency": 1, "error-handling": 1}

T = json.load(open(f"{W}/scope/tally.json"))
pool = json.load(open(f"{W}/scope/pool.json"))
try:
    O = json.load(open(f"{W}/scope/synth_overrides.json"))
except FileNotFoundError:
    O = {}
unknown = set(O) - {"canon", "merge", "pr_comment", "severity", "also_at"}
if unknown:
    sys.exit(f"synth_overrides.json: unknown keys {sorted(unknown)}")
bad = {b: v for b, v in O.get("severity", {}).items() if v not in ORDER}
if bad:
    sys.exit(f"synth_overrides.json: severity must be one of {list(ORDER)}, got {bad}")
missing = [b for b in [*O.get("canon", {}), *O.get("pr_comment", {}), *O.get("severity", {}), *O.get("also_at", {})] if b not in T]
if missing:
    sys.exit(f"synth_overrides.json names bugs not in the pool: {missing}")


def candidate(b):
    return json.load(open(f"{W}/reports/{b}_candidate.json"))


def hunter(cid):
    h, s = cid.rsplit("_", 1)
    return json.load(open(f"{W}/hunters/{h}/bug_{s}.json"))


def votes(b):
    out = []
    for f in sorted(glob.glob(f"{W}/reports/{b}_vote*.json")):
        try:
            out.append(json.load(open(f)))
        except json.JSONDecodeError:
            pass
    return out


def mechanical_severity(b, c):
    pos = [x.get("severity") for x in votes(b) if x.get("verdict") in ("CONFIRMED", "PLAUSIBLE")]
    top = collections.Counter(pos).most_common()
    if not top or (len(top) > 1 and top[0][1] == top[1][1]):
        return c.get("severity_hint") or "nit"
    return top[0][0]


recs = {}
for b, t in T.items():
    if t["status"] != "verified":
        continue
    c = hunter(O["canon"][b]) if b in O.get("canon", {}) else candidate(b)
    vs = [x for x in votes(b) if x.get("verdict") in ("CONFIRMED", "PLAUSIBLE")]
    refs = [x for x in votes(b) if x.get("verdict") == "REFUTED"]
    sev = O.get("severity", {}).get(b) or mechanical_severity(b, c)
    v0 = vs[0]
    qual = v0.get("qualifier") or ""
    reasoning = c["reasoning"].strip() + f"\n\n**Verification:** {sev}{f' ({qual})' if qual else ''}. Trigger: {v0.get('trigger', '').strip()} {v0.get('evidence', '').strip()}"
    how = [h for x in vs for h in (x.get("how") or [])][:6]
    if how:
        reasoning += "\n\nHow it happens:\n" + "\n".join(f"- {h}" for h in how)
    if refs:
        reasoning += "\n\n### Addressing the refutation\n" + refs[0].get("evidence", "")
    pc = (O.get("pr_comment", {}).get(b) or c["pr_comment"]).strip().replace("\n", " ")
    if c.get("pattern"):
        pc += f" sweep:`{c['pattern']}`"
    recs[b] = dict(file_path=c["file_path"], severity=sev, start_line=c["start_line"], end_line=c.get("end_line", c["start_line"]),
                   pr_comment=pc, reasoning=reasoning, _cat=c.get("category"), _votes=t["votes"],
                   _src=[pool["bugs"][b]["src"]] + t["dups"], _corr=len(t["dups"]), _merged=[])

for sec, pri in O.get("merge", {}).items():
    if sec not in recs or pri not in recs:
        print(f"merge {sec}->{pri} skipped: both must be verified")
        continue
    s = recs.pop(sec)
    p = recs[pri]
    p["pr_comment"] += f" [also at: {s['file_path']}:{s['start_line']} - {s['pr_comment']}]"
    p["_src"] += s["_src"]
    p["_merged"].append(sec)
    if ORDER[s["severity"]] < ORDER[p["severity"]]:
        p["severity"] = s["severity"]
for b, sites in O.get("also_at", {}).items():
    for f, line, text in sites:
        recs[b]["pr_comment"] += f" [also at: {f}:{line} - {text}]"

# Report bar: every normal and pre_existing; nits ranked by corroboration, impact, then one per category first.
items = sorted(recs.items(), key=lambda kv: (ORDER[kv[1]["severity"]], kv[1]["file_path"], kv[1]["start_line"]))
nits = [kv for kv in items if kv[1]["severity"] == "nit"]
nits.sort(key=lambda kv: (-kv[1]["_corr"], IMPACT.get(kv[1]["_cat"], 2)))
seen, first, rest = set(), [], []
for kv in nits:
    (rest if kv[1]["_cat"] in seen else first).append(kv)
    seen.add(kv[1]["_cat"])
keep = {b for b, _ in (first + rest)[:HEADLINE_NITS]}
head = [kv for kv in items if kv[1]["severity"] != "nit" or kv[0] in keep]
more = [kv for kv in items if kv[1]["severity"] == "nit" and kv[0] not in keep]

shape = lambda kvs: [{k: r[k] for k in KEYS} for _, r in kvs]
meta = [{"bug_id": b, "category": r["_cat"], "votes": r["_votes"], "source_ids": r["_src"],
         "corroborated_by": r["_corr"], "merged_sites": r["_merged"], "headline": (b, r) in head} for b, r in items]
json.dump(shape(head), open(f"{W}/findings.json", "w"), indent=1)
json.dump(shape(more), open(f"{W}/findings.more.json", "w"), indent=1)
json.dump(meta, open(f"{W}/findings.meta.json", "w"), indent=1)
json.dump([b for b, t in T.items() if t["status"] == "pending"], open(f"{W}/unverified.json", "w"))
sarif = {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "localreview"}}, "results": [
    {"ruleId": b, "level": "note" if r["severity"] == "nit" else "warning", "message": {"text": r["pr_comment"]},
     "locations": [{"physicalLocation": {"artifactLocation": {"uri": r["file_path"]},
                                         "region": {"startLine": r["start_line"], "endLine": r["end_line"]}}}]}
    for b, r in items]}]}
json.dump(sarif, open(f"{W}/findings.sarif", "w"), indent=1)

# Feedback loop: shape check on what will be presented.
errors = []
for b, r in items:
    if r["severity"] not in ORDER:
        errors.append(f"{b}: severity {r['severity']!r} not in {list(ORDER)}")
    if "\n" in r["pr_comment"]:
        errors.append(f"{b}: pr_comment has a newline")
    if len(r["pr_comment"]) < 120:
        errors.append(f"{b}: pr_comment is {len(r['pr_comment'])} chars (<120); add the failure scenario")
    if not isinstance(r["start_line"], int) or r["start_line"] < 1 or r["end_line"] < r["start_line"]:
        errors.append(f"{b}: bad line range {r['start_line']}-{r['end_line']}")
print(f"{len(head)} headline + {len(more)} more findings", dict(collections.Counter(r["severity"] for _, r in items)))
for b, r in items:
    print(f"{b} {r['severity']:12} {r['file_path']}:{r['start_line']} votes={r['_votes']} corr={r['_corr']}{'' if (b, r) in head else ' (more)'}")
if errors:
    print("\nFIX BEFORE PRESENTING:\n" + "\n".join(errors))
    sys.exit(1)
