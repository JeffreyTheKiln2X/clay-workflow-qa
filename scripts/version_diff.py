#!/usr/bin/env python3
"""Publish check: list every step that differs between two versions of a Clay workflow.

Read only, 0 credits. Uses the `clay` CLI already logged in.

  version_diff.py <wf_id>                   published version vs the live draft
  version_diff.py <wf_id> <old_snap> <new_snap>   any two snapshots (e.g. V1 vs V2 after a publish)

With no snapshots given, the draft side is the newest snapshot, and every code step of the
live draft is checked against it (a snapshot is saved before an edit, so the newest edit can
be missing from it). Prints step names, changed fields and the code diff. Exits 1 if anything
differs, 2 if the draft check fails.
"""
import difflib, json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor


def clay(*args):
    r = subprocess.run(["clay", *args], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        sys.exit("clay %s failed: %s" % (" ".join(args[:3]), (r.stdout + r.stderr)[:300]))


FIELDS = {
    "name": lambda n: n.get("name"),
    "description": lambda n: n.get("description"),
    "config": lambda n: n.get("nodeConfig"),
    "tools": lambda n: n.get("tools"),
    "code": lambda n: (n.get("currentScriptVersion") or {}).get("code"),
    "inputs": lambda n: (n.get("currentScriptVersion") or {}).get("inputSchema"),
}


def text(v):
    return v if isinstance(v, str) else json.dumps(v, indent=1, sort_keys=True)


def main():
    if len(sys.argv) not in (2, 4):
        sys.exit(__doc__)
    wf = sys.argv[1]
    if len(sys.argv) == 4:
        old_id, new_id = sys.argv[2], sys.argv[3]
    else:
        old_id = clay("workflows", "get", wf)["publishedSnapshotId"]
        new_id = clay("workflows", "snapshots", "list", wf)["data"][0]["id"]
    old, new = (clay("workflows", "snapshots", "get", wf, s) for s in (old_id, new_id))
    A, B = ({n["id"]: n for n in s["nodes"]} for s in (old, new))
    print("old %s  new %s" % (old_id, new_id))

    changed = 0
    for k in sorted(set(A) - set(B)):
        changed += 1; print("\nREMOVED step:", A[k]["name"], k)
    for k in sorted(set(B) - set(A)):
        changed += 1; print("\nADDED step:", B[k]["name"], k)
    if json.dumps(old.get("edges"), sort_keys=True) != json.dumps(new.get("edges"), sort_keys=True):
        changed += 1; print("\nCONNECTIONS between steps changed")
    for k in sorted(set(A) & set(B)):
        diff = [f for f, g in FIELDS.items() if g(A[k]) != g(B[k])]
        if not diff:
            continue
        changed += 1
        print("\n=== %s (%s): %s" % (B[k]["name"], k, ", ".join(diff)))
        for f in diff:
            for l in difflib.unified_diff(text(FIELDS[f](A[k]) or "").splitlines(),
                                          text(FIELDS[f](B[k]) or "").splitlines(), lineterm="", n=0):
                if not l.startswith(("---", "+++", "@@")):
                    print("  [%s] %s" % (f, l[:220]))
    print("\nsteps: %d old, %d new. Differences: %d" % (len(A), len(B), changed))

    if len(sys.argv) == 2:
        def live(k):
            return k, clay("workflows", "nodes", "get", wf, k)["node"]
        with ThreadPoolExecutor(8) as ex:
            D = dict(ex.map(live, B))
        off = [B[k]["name"] for k in B if D[k].get("name") != B[k]["name"]
               or D[k].get("description") != B[k]["description"]
               or (FIELDS["code"](B[k]) and D[k].get("code") != FIELDS["code"](B[k]))]
        print("live draft matches newest snapshot:", "yes" if not off else "NO, differs on %s" % off)
        if off:
            sys.exit(2)
    sys.exit(1 if changed else 0)


if __name__ == "__main__":
    main()
