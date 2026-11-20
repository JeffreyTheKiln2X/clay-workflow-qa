#!/usr/bin/env python3
"""Prove a run changed nothing: save Audiences records before, compare after.

Read only. Uses the `clay` CLI already logged in.

  record_diff.py snapshot --ids 123,456 --out before.json [--entity-type people]
  ... run the test ...
  record_diff.py snapshot --ids 123,456 --out after.json
  record_diff.py compare before.json after.json

Prints changed field ids per record, never the values (records may hold personal data).
Keep the snapshot files out of git and delete them when the test is done.
"""
import argparse, json, subprocess, sys


def snapshot(ids, entity, out):
    recs = []
    for i in range(0, len(ids), 100):
        r = subprocess.run(["clay", "audiences", "records", "get", "--entity-type", entity,
                            "--ids", ",".join(ids[i:i + 100])], capture_output=True, text=True)
        try:
            recs += json.loads(r.stdout)["data"]
        except (json.JSONDecodeError, KeyError):
            sys.exit("clay audiences records get failed: " + (r.stdout + r.stderr)[:300])
    json.dump({str(x["recordId"]): x["fields"] for x in recs}, open(out, "w"))
    missing = set(ids) - {str(x["recordId"]) for x in recs}
    print("saved %d records to %s%s" % (len(recs), out, "; not found: %s" % sorted(missing) if missing else ""))


def compare(before, after):
    b, a = json.load(open(before)), json.load(open(after))
    total = 0
    for rid in sorted(set(b) | set(a)):
        if rid not in a or rid not in b:
            print(rid, "present in only one file")
            total += 1
            continue
        ch = sorted(k for k in set(a[rid]) | set(b[rid]) if a[rid].get(k) != b[rid].get(k))
        total += len(ch)
        print(rid, "fields changed: %d%s" % (len(ch), " " + str(ch) if ch else ""))
    print("\nTOTAL fields changed: %d" % total)
    sys.exit(1 if total else 0)


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot"); s.add_argument("--ids", required=True); s.add_argument("--out", required=True)
    s.add_argument("--entity-type", default="people")
    c = sub.add_parser("compare"); c.add_argument("before"); c.add_argument("after")
    a = p.parse_args()
    if a.cmd == "snapshot":
        snapshot([i.strip() for i in a.ids.split(",") if i.strip()], a.entity_type, a.out)
    else:
        compare(a.before, a.after)


if __name__ == "__main__":
    main()
