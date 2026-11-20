#!/usr/bin/env python3
"""Outcome coverage: which end results have been seen, how often, and which are still missing.

No Clay calls. Reads the JSON from run_audit.py and a plain text list of every possible outcome
(one per line, `#` for comments), for example the reason codes read from the decision step.

  outcome_coverage.py runs.json outcomes.txt --field reason_code [--extra tested.txt]

--extra adds outcomes proven another way (for example single-step tests), one per line.
"""
import argparse, collections, json


def read_list(path):
    return [l.split("#")[0].strip() for l in open(path) if l.split("#")[0].strip()]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("runs"); p.add_argument("outcomes")
    p.add_argument("--field", required=True)
    p.add_argument("--extra")
    a = p.parse_args()
    rows = json.load(open(a.runs))
    seen = collections.Counter(str(r.get(a.field) or "(blank)") for r in rows)
    extra = set(read_list(a.extra)) if a.extra else set()
    expected = read_list(a.outcomes)

    print("%-36s %8s  %s" % ("outcome", "runs", "how"))
    for o in expected:
        how = "live runs" if seen.get(o) else ("other test" if o in extra else "MISSING")
        print("%-36s %8d  %s" % (o, seen.get(o, 0), how))
    covered = sum(1 for o in expected if seen.get(o) or o in extra)
    print("\ncovered %d of %d" % (covered, len(expected)))
    unknown = [k for k in seen if k not in expected and k != "(blank)"]
    if unknown:
        print("seen but not in the outcome list (add them or check them):", unknown)


if __name__ == "__main__":
    main()
