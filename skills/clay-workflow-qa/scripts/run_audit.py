#!/usr/bin/env python3
"""Pull one step's outputs from every run of a Clay workflow, save them, and cross-tab two fields.

Read only, 0 credits. Uses the `clay` CLI already logged in (set CLAY_CONFIG_HOME first if the
workspace has its own login folder).

  run_audit.py <wf_id> <node_id> --fields status,reason_code,label --out runs.json
               [--snapshot <wfs_id>] [--crosstab status,label] [--workers 8]

Runs with no output for that step (it did not run, or a single-step test of another step) are
skipped and counted.
"""
import argparse, collections, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor


def clay(*args):
    r = subprocess.run(["clay", *args], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.exit("clay %s failed: %s" % (" ".join(args[:3]), (r.stdout + r.stderr)[:300]))


def list_runs(wf, snapshot):
    runs, cur = [], None
    while True:
        q = {"limit": 100, "versionScope": "all", **({"workflowSnapshotId": snapshot} if snapshot else {}), **(cur or {})}
        d = clay("workflows", "analysis", "runs", "--workflow", wf, "--input", json.dumps(q))
        runs += d.get("runs", [])
        if not d.get("hasMore"):
            return runs
        cur = d["nextCursor"]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("wf"); p.add_argument("node")
    p.add_argument("--fields", required=True, help="comma list of output fields to keep")
    p.add_argument("--out", required=True)
    p.add_argument("--snapshot")
    p.add_argument("--crosstab", help="two fields, comma separated")
    p.add_argument("--workers", type=int, default=8)
    a = p.parse_args()
    fields = [f.strip() for f in a.fields.split(",") if f.strip()]

    runs = list_runs(a.wf, a.snapshot)

    def one(r):
        d = clay("workflows", "runs", "get", r["id"], "--verbose", "--node-id", a.node)
        nodes = [n for n in d.get("nodes", []) if n.get("startedAt")]
        if not nodes:
            return None
        o = nodes[0].get("outputs") or {}
        return {"run": r["id"], "snapshot": r.get("workflowSnapshotId"), "created": r.get("createdAt"),
                "data_credits": r.get("dataCreditsUsed"), "action_credits": r.get("actionCreditsUsed"),
                **{f: o.get(f) for f in fields}}

    with ThreadPoolExecutor(a.workers) as ex:
        rows = [x for x in ex.map(one, runs) if x]
    json.dump(rows, open(a.out, "w"), indent=1)
    print("runs listed %d, with output for the step %d, saved to %s" % (len(runs), len(rows), a.out))

    if a.crosstab:
        x, y = [s.strip() for s in a.crosstab.split(",")][:2]
        t = collections.defaultdict(collections.Counter)
        for r in rows:
            t[str(r.get(x) or "(blank)")][str(r.get(y) or "(blank)")] += 1
        print("\n%s  ->  %s" % (x, y))
        for k in sorted(t):
            print("  %-24s %s" % (k, dict(t[k])))


if __name__ == "__main__":
    main()
