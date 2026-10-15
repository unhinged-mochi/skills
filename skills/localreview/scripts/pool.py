#!/usr/bin/env python3
"""Candidate pool for one localreview run.

  pool.py show H<n>              list a hunter's candidates (flags bad JSON)
  pool.py add H<n>_<s> ...        add candidates as new bug_NNN (copies to reports/bug_NNN_candidate.json)
  pool.py dup bug_NNN H<n>_<s> ... fold duplicates into bug_NNN (counts as corroboration)
  pool.py drop H<n>_<s> <reason>  gate a candidate out (logged to scope/dropped.txt)
  pool.py list                    show the pool
"""
import glob, json, os, sys

W = os.environ.get("LOCALREVIEW_WORK", "/tmp/localreview_work")
P = f"{W}/scope/pool.json"


def load_candidate(cid):
    h, s = cid.rsplit("_", 1)
    path = f"{W}/hunters/{h}/bug_{s}.json"
    try:
        return json.load(open(path))
    except FileNotFoundError:
        sys.exit(f"no candidate file {path} (ids look like H3_2)")
    except json.JSONDecodeError as e:
        sys.exit(f"{path} is not valid JSON ({e}); ask the hunter to rewrite it or drop it")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    os.makedirs(f"{W}/scope", exist_ok=True)
    os.makedirs(f"{W}/reports", exist_ok=True)
    pool = json.load(open(P)) if os.path.exists(P) else {"next": 1, "bugs": {}, "merged": {}, "dropped": {}}
    save = lambda: json.dump(pool, open(P, "w"), indent=1)
    cmd, args = sys.argv[1], sys.argv[2:]
    if cmd == "show":
        files = glob.glob(f"{W}/hunters/{args[0]}/bug_*.json")
        for f in sorted(files, key=lambda x: int(x.rsplit("_", 1)[1][:-5])):
            try:
                c = json.load(open(f))
            except json.JSONDecodeError as e:
                print("BADJSON", f, e)
                continue
            missing = {"id", "file_path", "start_line", "pr_comment"} - c.keys()
            if missing:
                print("MISSING", f, sorted(missing))
                continue
            print(f"{c['id']} [{c.get('severity_hint')}/{c.get('category')}] {c['file_path']}:{c['start_line']}-{c.get('end_line')} pc={len(c['pr_comment'])}\n   {c['pr_comment'][:260]}")
        if not files:
            print(f"no candidates in {W}/hunters/{args[0]}/")
    elif cmd == "add":
        for cid in args:
            if cid in pool["merged"] or any(b["src"] == cid for b in pool["bugs"].values()):
                print("already pooled:", cid)
                continue
            c = load_candidate(cid)
            b = f"bug_{pool['next']:03d}"
            pool["next"] += 1
            pool["bugs"][b] = {"src": cid, "file": c["file_path"], "line": c["start_line"], "sum": c["pr_comment"], "dups": []}
            json.dump(c, open(f"{W}/reports/{b}_candidate.json", "w"), indent=1)
            print(b, "<-", cid)
        save()
    elif cmd == "dup":
        b = args[0]
        if b not in pool["bugs"]:
            sys.exit(f"unknown {b}; pooled: {', '.join(pool['bugs'])}")
        for cid in args[1:]:
            pool["bugs"][b]["dups"].append(cid)
            pool["merged"][cid] = b
        save()
        print("merged", args[1:], "into", b)
    elif cmd == "drop":
        reason = " ".join(args[1:]) or "unspecified"
        pool["dropped"][args[0]] = reason
        save()
        open(f"{W}/scope/dropped.txt", "a").write(f"{args[0]}: {reason}\n")
    elif cmd == "list":
        for b, v in pool["bugs"].items():
            print(b, v["src"], f"{v['file']}:{v['line']}", f"dups={v['dups']}", v["sum"][:110])
    else:
        sys.exit(__doc__)


main()
